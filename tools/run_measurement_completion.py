"""Execute only the approved, frozen three-batch completion manifest.

Default mode is an offline check. --execute is bound to the explicit 16 October
00:18:20 UTC approval. No human labels are loaded. Original runs stay read-only.
"""
import argparse
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import sqlite3

from tools import bounded_gap_followup as b
from tools import build_followup_publication as publication
from tools import gap_closure_eval as g
from tools import prepare_measurement_completion as proposal

MANIFEST_SHA = '186397d8243b8dbe278949e503049ed1ef8c844f9adeb792c58a31e37655a9e3'
POLICY = b.RunPolicy(proposal.NAMESPACE, proposal.CAP, b.RESERVE, 9, 3, (('verify', 2), ('group', 1)))
APPROVAL = {'approved_utc': '2026-10-16T00:18:20Z',
            'record': 'Sentinel_6e7bc6e702608191bec358e9834b176d',
            'scope': 'Separate one-time USD0.33 allowance and specified source/machine data to OpenRouter/Crusoe; nine attempts maximum. No publication.'}


def load_bound(manifest_path, source, allowlist, prior_run):
    manifest_path, source, prior_run = Path(manifest_path), Path(source), Path(prior_run)
    if manifest_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('manifest must remain private mode 0600')
    manifest = json.loads(manifest_path.read_text())
    if g.digest(manifest) != MANIFEST_SHA:
        raise ValueError('approved manifest digest differs')
    for key, expected in {'namespace': POLICY.namespace, 'cap_nusd': POLICY.cap,
                          'max_attempts': POLICY.max_attempts, 'max_attempts_per_batch': POLICY.per_batch,
                          'reserve_per_attempt_nusd': POLICY.reserve,
                          'minimum_interval_seconds': b.MIN_REQUEST_INTERVAL_SECONDS,
                          'fallback_backoff_seconds': b.FALLBACK_BACKOFF_SECONDS,
                          'maximum_in_process_wait_seconds': b.MAX_IN_PROCESS_BACKOFF_SECONDS}.items():
        if manifest[key] != expected:
            raise ValueError('approved execution policy differs')
    publication.build(source, allowlist, prior_run)
    plan, text, old, _, identity = b.read_source(source, allowlist)
    if identity != manifest['source_identity'] or g.file_sha(prior_run / 'followup.db') != manifest['accepted_followup_database_sha256']:
        raise ValueError('frozen source artifact differs')
    with sqlite3.connect('file:' + str((prior_run / 'followup.db').resolve()) + '?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        for role, value in c.execute("SELECT role,output_json FROM calls WHERE status='succeeded'"):
            parsed = json.loads(value)
            if set(old[role]) & set(parsed):
                raise ValueError('prior result overlap')
            old[role].update(parsed)
    if proposal.pending_calls(plan, text, old) != manifest['requests']:
        raise ValueError('pending IDs or complete requests differ from approval')
    calls = [(r['logical'], r['role'], r['source_ids'], r['request']) for r in manifest['requests']]
    b.validate_scope(calls, dict(POLICY.role_counts))
    return manifest, plan, old, calls


def historic_state(c):
    return g.digest({'reservations': list(c.execute('SELECT * FROM reservations WHERE request_key NOT LIKE ? ORDER BY request_key', (POLICY.namespace + ':%',))),
                     'caps': list(c.execute('SELECT * FROM caps ORDER BY budget')),
                     'legacy': list(c.execute('SELECT * FROM legacy_sources ORDER BY name'))})


def source_fingerprints(source, prior_run):
    return {'plan': g.file_sha(Path(source) / 'plan.json'), 'database': g.file_sha(Path(source) / 'run.db'),
            'prior_run': {p.name: g.file_sha(p) for p in sorted(Path(prior_run).iterdir()) if p.is_file()}}


def preflight(out):
    route = g.verify_role_route(b.ROUTE)
    key = os.environ.get('OPENROUTER_API_KEY') or b.canary.keychain_secret(timeout_seconds=90)
    account = b.canary.verify_project_key(key, POLICY.cap)
    credits = b.router.request_json('https://openrouter.ai/api/v1/credits', key=key)['data']
    available = Decimal(str(credits['total_credits'])) - Decimal(str(credits['total_usage']))
    if not available.is_finite() or available < Decimal(POLICY.cap) / 10**9:
        raise ValueError('existing credits cannot cover approved cap')
    endpoints = b.router.request_json('https://openrouter.ai/api/v1/models/' + g.MODEL + '/endpoints')['data']['endpoints']
    endpoint = next(x for x in endpoints if x.get('tag') == b.ROUTE)
    if endpoint.get('context_length') != 131072 or not 4096 <= endpoint.get('max_completion_tokens', 0) <= 117964:
        raise ValueError('endpoint bounds exceed approved reservation')
    b.private_json(out / 'preflight.json', {'checked_utc': g.utc(), 'route': route, 'account': account,
        'existing_credit_usd': str(available), 'cap_nusd': POLICY.cap, 'reserve_per_attempt_nusd': POLICY.reserve,
        'max_attempts': POLICY.max_attempts, 'paid_calls': 0})
    return key


def summarize(out, plan, old, calls):
    expected = {logical: (role, ids, request) for logical, role, ids, request in calls}
    with sqlite3.connect('file:' + str((Path(out) / 'followup.db').resolve()) + '?mode=ro', uri=True) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute('SELECT * FROM calls ORDER BY created_utc,key')]
    merged = {role: dict(values) for role, values in old.items()}
    safe_receipts = []
    for row in rows:
        role, ids, request = expected[row['logical']]
        if row['request_sha'] != g.digest(request) or json.loads(row['request_json']) != request:
            raise ValueError('saved completion request differs')
        if row['response_body'] is not None:
            receipt = Path(out) / ('receipt-%s-%d.bin' % (row['logical'].replace(':', '-'), row['attempt']))
            if receipt.read_bytes() != row['response_body']:
                raise ValueError('saved completion receipt differs')
        if row['status'] == 'succeeded':
            values = b.strict_output(role, json.loads(row['response_body']), ids, request)
            if values != json.loads(row['output_json']) or set(values) & set(merged[role]):
                raise ValueError('accepted result overlap or mismatch')
            merged[role].update(values)
        safe_receipts.append({k: row[k] for k in ('role', 'attempt', 'status', 'http_status', 'reserved_nusd',
            'charged_nusd', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'usage_charge_nusd',
            'derived_charge_nusd', 'elapsed_seconds', 'created_utc', 'settled_utc', 'request_sha', 'retry_not_before_epoch')})
    known = sum(r['charged_nusd'] or 0 for r in rows if r['status'] in ('succeeded', 'quarantined_metered'))
    holds = sum(max(r['reserved_nusd'], r['charged_nusd'] or 0) for r in rows if r['status'] not in ('succeeded', 'quarantined_metered'))
    result = {'namespace': POLICY.namespace, 'manifest_sha256': MANIFEST_SHA, 'approval': APPROVAL,
        'attempts': len(rows), 'known_charges_nusd': known, 'unresolved_reservations_nusd': holds,
        'exposure_nusd': known + holds, 'cap_nusd': POLICY.cap, 'before': publication.comparisons(plan, old),
        'after': publication.comparisons(plan, merged), 'receipts': safe_receipts,
        'not_human_accuracy': True, 'publication': 'local only; publication not approved'}
    b.private_json(Path(out) / 'aggregate.json', result)
    b.private_json(Path(out) / 'merged-machine-outputs.json', merged)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'source', 'allowlist', 'prior-run', 'shared-budget-root', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    manifest, plan, old, calls = load_bound(a.manifest, a.source, a.allowlist, a.prior_run)
    if not a.execute:
        print(g.canon({'status': 'offline_binding_verified', 'manifest_sha256': MANIFEST_SHA, 'batches': 3,
                      'source_ids': 30, 'max_attempts': 9, 'cap_nusd': POLICY.cap})); return
    permitted = Path(__file__).resolve().parents[1] / 'local' / 'measurement_completion_20261016'
    if a.out.resolve() != permitted or a.out.is_symlink():
        raise ValueError('completion output must use its separate local directory')
    b.require_current_schema(a.out / 'followup.db')
    before_sources = source_fingerprints(a.source, a.prior_run)
    ledger_path = a.shared_budget_root / 'project_budget.db'
    proposal.ledger_snapshot(ledger_path)
    os.umask(0o077); a.out.mkdir(mode=0o700, parents=True, exist_ok=True); a.out.chmod(0o700)
    with open(a.out / 'run.lock', 'a+b') as lease:
        fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        key = preflight(a.out)
        from spotify_pipeline.project_budget import ProjectBudget
        from tools.checkpoint5000_dispatch import legacy_paths
        paths = legacy_paths()
        paths['batch_v1'] = str(a.shared_budget_root / 'deepinfra_batch10_canary.db')
        paths['batch_v2'] = str(a.shared_budget_root / 'deepinfra_batch10_canary_v2.db')
        with ProjectBudget(str(ledger_path), paths, max_global_inflight=None) as budget:
            before_ledger = historic_state(budget.db)
            b.private_json(a.out / 'approval-and-binding.json', {'manifest_sha256': MANIFEST_SHA, 'approval': APPROVAL})
            runner = b.BoundedRunner(budget, a.out, calls, {'manifest_sha256': MANIFEST_SHA},
                lambda request: b.transport(request, key), lambda: g.verify_role_route(b.ROUTE), policy=POLICY)
            try:
                status = runner.run()
            finally:
                result = summarize(a.out, plan, old, calls)
                preserved = {'original_artifacts_unchanged': source_fingerprints(a.source, a.prior_run) == before_sources,
                    'historical_ledger_rows_and_caps_unchanged': historic_state(budget.db) == before_ledger,
                    'original_fingerprints': before_sources, 'historical_ledger_state_sha256': before_ledger}
                b.private_json(a.out / 'preservation.json', preserved)
                if not all(preserved[k] for k in ('original_artifacts_unchanged', 'historical_ledger_rows_and_caps_unchanged')):
                    raise ValueError('preservation check failed; retain all evidence')
    print(g.canon({'status': status, 'attempts': result['attempts'], 'coverage': result['after']['coverage'],
                  'known_charges_nusd': result['known_charges_nusd'], 'held_nusd': result['unresolved_reservations_nusd'],
                  'exposure_nusd': result['exposure_nusd']}))


if __name__ == '__main__':
    main()

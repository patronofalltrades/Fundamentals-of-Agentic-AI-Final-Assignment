"""Prepare a private, frozen completion proposal. No inference or ledger writes.

This command cannot execute the proposal. A fresh approval and a separately
bound execution entry point are required; the exhausted five-batch runner must
not be reused by changing its constants or old manifest.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from tools import bounded_gap_followup as b
from tools import build_followup_publication as publication
from tools import gap_closure_eval as g

NAMESPACE = 'measurement-completion-20261016-v1'
CAP = 330_000_000
ATTEMPTS = 9
PER_BATCH = 3


def pending_calls(plan, text, values):
    """Require exactly the remaining original batches, without positional repair."""
    pending = {role: set(plan[role + '_ids']) - set(values[role]) for role in ('verify', 'group')}
    if {role: len(ids) for role, ids in pending.items()} != {'verify': 20, 'group': 10}:
        raise ValueError('pending coverage changed; prepare a new proposal')
    all_ids = [r for ids in pending.values() for r in ids]
    if len(set(all_ids)) != 30:
        raise ValueError('expected thirty distinct original IDs')
    selected = []
    for logical, role, ids, request in g.build_calls(plan, text):
        if role not in pending or not set(ids) & pending[role]:
            continue
        if len(ids) != 10 or not set(ids) <= pending[role] or any(not text.get(r) for r in ids):
            raise ValueError('only whole missing source batches may be proposed')
        request = b.bind_response_id_enum(g.on_route(request, b.ROUTE), ids)
        items = json.loads(request['messages'][-1]['content'].rsplit('\n', 1)[-1])
        if role == 'verify' and any(set(item) != {'review_id', 'review_text'} for item in items):
            raise ValueError('blind verifier must receive source fields only')
        if role == 'group' and any(set(item) != {'review_id', 'review_text', 'labels', 'evidence_quote'} for item in items):
            raise ValueError('grouping payload field scope changed')
        if role == 'group' and any(set(item['labels']) != {'topic', 'intent', 'severity'} for item in items):
            raise ValueError('grouping machine label scope changed')
        selected.append({'logical': logical, 'role': role, 'source_ids': ids,
                         'request_sha256': g.digest(request), 'request': request})
    if Counter(r['role'] for r in selected) != {'verify': 2, 'group': 1}:
        raise ValueError('expected exactly three frozen batches')
    if {r for row in selected for r in row['source_ids']} != set(all_ids):
        raise ValueError('pending identity coverage differs')
    return selected


def ledger_snapshot(path):
    with sqlite3.connect('file:' + str(Path(path).resolve()) + '?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        caps = dict(c.execute('SELECT budget,cap_nusd FROM caps'))
        rows = list(c.execute('SELECT request_key,budget,status,reserved_nusd,charged_nusd FROM reservations ORDER BY request_key'))
        legacy = list(c.execute('SELECT name,budget,exposure_nusd,state_sha FROM legacy_sources ORDER BY name'))
    exposure = {key: sum(r[2] for r in legacy if r[1] == key) for key in caps}
    holds = {key: {'attempts': 0, 'held_nusd': 0} for key in caps}
    for _, budget, status, reserved, charge in rows:
        settled = status in ('succeeded', 'quarantined_metered') and charge is not None
        amount = charge if settled else max(reserved, charge or 0)
        exposure[budget] += amount
        if not settled:
            holds[budget]['attempts'] += 1
            holds[budget]['held_nusd'] += amount
    if caps != {'openrouter': 5_000_000_000, 'jev': 5_000_000_000}:
        raise ValueError('provider caps changed')
    if exposure['openrouter'] + CAP > caps['openrouter']:
        raise ValueError('provider headroom cannot cover proposed cap')
    return {'caps_nusd': caps, 'exposure_nusd': exposure, 'reservation_holds': holds,
            'legacy_exposure_nusd': {key: sum(r[2] for r in legacy if r[1] == key) for key in caps},
            'state_sha256': g.digest([caps, rows, legacy])}


def prepare(source, allowlist, run, ledger, route_check):
    saved = publication.build(source, allowlist, run)
    plan, text, old, _, identity = b.read_source(source, allowlist)
    with sqlite3.connect('file:' + str((Path(run) / 'followup.db').resolve()) + '?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        for role, value in c.execute("SELECT role,output_json FROM calls WHERE status='succeeded'"):
            parsed = json.loads(value)
            if set(old[role]) & set(parsed):
                raise ValueError('accepted result overlap')
            old[role].update(parsed)
    calls = pending_calls(plan, text, old)
    route = json.loads(Path(route_check).read_text())
    if (route['route'] != {'route': b.ROUTE, 'input_usd_per_token': '5E-8', 'output_usd_per_token': '2.5E-7'}
            or not route['zdr_catalog_verified'] or route['status'] != 0
            or route['context_length'] != 131072 or route['max_completion_tokens'] != 117964):
        raise ValueError('saved public route check differs')
    ledger_before = ledger_snapshot(ledger)
    manifest = {'namespace': NAMESPACE, 'approval': 'PENDING; proposal only', 'source_identity': identity,
                'accepted_followup_database_sha256': saved['provenance']['source_artifact_sha256']['followup_database'],
                'requests': calls, 'cap_nusd': CAP, 'max_attempts': ATTEMPTS, 'max_attempts_per_batch': PER_BATCH,
                'reserve_per_attempt_nusd': b.RESERVE, 'minimum_interval_seconds': b.MIN_REQUEST_INTERVAL_SECONDS,
                'fallback_backoff_seconds': b.FALLBACK_BACKOFF_SECONDS,
                'maximum_in_process_wait_seconds': b.MAX_IN_PROCESS_BACKOFF_SECONDS}
    if ledger_snapshot(ledger) != ledger_before:
        raise ValueError('ledger changed during proposal preparation')
    safe = {'version': 1, 'namespace': NAMESPACE, 'state': 'proposal_only_not_authorized',
            'manifest_sha256': g.digest(manifest), 'source_sha256': plan['source_sha256'],
            'label_config': plan['jev_config'], 'prior_followup_database_sha256': manifest['accepted_followup_database_sha256'],
            'targets': {'verify': {'before': 980, 'target': 1000, 'pending': 20},
                        'group': {'before': 590, 'target': 600, 'pending': 10}},
            'distinct_source_ids': 30, 'batches': 3, 'reviews_per_batch': 10,
            'requests': [{'role': r['role'], 'request_sha256': r['request_sha256'],
                          'source_id_set_sha256': g.digest(sorted(r['source_ids'])),
                          'request_bytes': len(g.canon(r['request']).encode())} for r in calls],
            'route_check': route, 'max_attempts': ATTEMPTS, 'attempts_per_batch': PER_BATCH, 'retries_per_batch': 2,
            'cap_nusd': CAP, 'reserve_per_attempt_nusd': b.RESERVE,
            'maximum_incremental_charges_plus_holds_nusd': ATTEMPTS * b.RESERVE,
            'prior_followup_cost': saved['cost'], 'shared_ledger': ledger_before,
            'project_cost_limit': 'Historical full-project headroom remains unbounded. This proposal needs a new separate one-time allowance; the old USD0.38 authorization is exhausted.',
            'execution_gate': 'No execution entry point is enabled for this proposal. Bind the approved manifest and new namespace, then rerun preflight and affected tests before inference.',
            'limits': ['Coverage completion is the target. Agreement is not a completion condition or human accuracy.',
                       'Three batches can still fail. Stop at the attempt or exposure limit; further work needs another approval.',
                       'No auditor, human-label, synthetic attack, production-database or grading-release work.']}
    return manifest, safe


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('source', 'allowlist', 'run', 'ledger', 'route-check', 'private-out', 'out'):
        p.add_argument('--' + field, type=Path, required=True)
    a = p.parse_args()
    manifest, safe = prepare(a.source, a.allowlist, a.run, a.ledger, a.route_check)
    if a.private_out.exists() and json.loads(a.private_out.read_text()) != manifest:
        raise ValueError('existing private manifest differs; do not overwrite')
    a.private_out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    b.private_json(a.private_out, manifest)
    a.out.write_text(json.dumps(safe, indent=2, sort_keys=True) + '\n')
    print('Proposal saved: 30 distinct pending source IDs, three batches; no inference or ledger writes')


if __name__ == '__main__':
    main()

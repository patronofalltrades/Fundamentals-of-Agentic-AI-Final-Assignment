"""Rebuild a safe completion report from read-only saved receipts and machine data."""
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

from tools import bounded_gap_followup as b
from tools import build_followup_publication as p
from tools import gap_closure_eval as g
from tools import run_measurement_completion as c


def verifier_statistics(plan, values):
    ids = [rid for rid in plan['verify_ids'] if rid in values['verify']]
    labels, verifier = plan['jev_labels'], values['verify']
    return {'kappa': {field: g.kappa([(labels[r][field], verifier[r][field]) for r in ids], domain)
        for field, domain in (('topic', g.TOPICS), ('intent', g.INTENTS), ('severity', g.SEVERITIES))},
        'severity_mae': round(sum(abs(verifier[r]['severity'] - labels[r]['severity']) for r in ids) / len(ids), 4) if ids else None}


def build(manifest_path, source, allowlist, prior_run, run):
    run = Path(run)
    before_hashes = {x.name: g.file_sha(x) for x in sorted(run.iterdir()) if x.is_file()}
    manifest, plan, old, calls = c.load_bound(manifest_path, source, allowlist, prior_run)
    expected = {a: (role, ids, req) for a, role, ids, req in calls}
    with sqlite3.connect('file:' + str((run / 'followup.db').resolve()) + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON'); db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM calls ORDER BY created_utc,key')]
    if not rows or len(rows) > c.POLICY.max_attempts or any(n > c.POLICY.per_batch for n in Counter(r['logical'] for r in rows).values()):
        raise ValueError('completion attempt bounds differ')
    fresh = {role: {} for role in old}; receipts, invalid = [], []
    for index, row in enumerate(rows):
        role, ids, request = expected[row['logical']]
        if row['request_sha'] != g.digest(request) or json.loads(row['request_json']) != request:
            raise ValueError('completion request hash differs')
        body = row['response_body']
        if body is not None:
            receipt = run / ('receipt-%s-%d.bin' % (row['logical'].replace(':', '-'), row['attempt']))
            if receipt.read_bytes() != body: raise ValueError('completion raw receipt differs')
        if row['status'] in ('succeeded', 'quarantined_metered'):
            response = json.loads(body)
            inp, out, reasoning, derived = g.usage_of(role, response, b.ROUTE)
            reported = b.router.money_nusd(Decimal(str(response['usage']['cost']))) if response['usage'].get('cost') is not None else None
            if (inp, out, reasoning, derived, reported, max(derived, reported or 0)) != tuple(row[k] for k in
                    ('input_tokens', 'output_tokens', 'reasoning_tokens', 'derived_charge_nusd', 'usage_charge_nusd', 'charged_nusd')):
                raise ValueError('completion metered charge or usage differs')
            if row['status'] == 'succeeded':
                values = b.strict_output(role, response, ids, request)
                if values != json.loads(row['output_json']) or set(values) & (set(fresh[role]) | set(old[role])):
                    raise ValueError('completion output mismatch or overlap')
                fresh[role].update(values)
            else:
                try: b.strict_output(role, response, ids, request)
                except (ValueError, TypeError, KeyError, IndexError): pass
                else: raise ValueError('rejected output unexpectedly validates')
                invalid.append({'role': role, 'attempt': row['attempt'], 'kept_rejected': True})
        elif row['status'] not in ('uncertain', 'reserved', 'rejected_http'):
            raise ValueError('unknown completion status')
        headers = json.loads(row['response_headers_json'] or '{}')
        if headers != b.rate_headers(headers): raise ValueError('unexpected stored response header')
        respected = None
        if index + 1 < len(rows) and row['retry_not_before_epoch'] is not None:
            respected = datetime.fromisoformat(rows[index+1]['created_utc']).timestamp() >= row['retry_not_before_epoch']
            if not respected: raise ValueError('saved next admission predates durable cooldown')
        receipts.append({**{k: row[k] for k in ('role', 'attempt', 'status', 'http_status', 'reserved_nusd', 'charged_nusd',
            'input_tokens', 'output_tokens', 'reasoning_tokens', 'usage_charge_nusd', 'derived_charge_nusd',
            'elapsed_seconds', 'created_utc', 'settled_utc', 'request_sha')},
            'response_sha256': hashlib.sha256(body).hexdigest() if body is not None else None,
            'response_headers_saved': row['response_headers_json'] is not None,
            'retry_after_present': 'retry-after' in headers, 'next_admission_respected_cooldown': respected})
    merged = {role: {**old[role], **fresh[role]} for role in old}
    before, after = p.comparisons(plan, old), p.comparisons(plan, merged)
    saved = json.loads((run / 'aggregate.json').read_text())
    if saved['before'] != before or saved['after'] != after:
        raise ValueError('saved completion aggregate differs')
    preservation = json.loads((run / 'preservation.json').read_text())
    if (not preservation['original_artifacts_unchanged'] or not preservation['historical_ledger_rows_and_caps_unchanged']
            or preservation['original_fingerprints'] != c.source_fingerprints(source, prior_run)):
        raise ValueError('source preservation verification failed')
    known = sum(r['charged_nusd'] or 0 for r in rows if r['status'] in ('succeeded', 'quarantined_metered'))
    held = sum(max(r['reserved_nusd'], r['charged_nusd'] or 0) for r in rows if r['status'] not in ('succeeded', 'quarantined_metered'))
    if known + held > c.POLICY.cap: raise ValueError('completion exposure exceeds approval')
    if (known, held, known + held) != tuple(saved[k] for k in ('known_charges_nusd', 'unresolved_reservations_nusd', 'exposure_nusd')):
        raise ValueError('saved completion accounting differs')
    if before_hashes != {x.name: g.file_sha(x) for x in sorted(run.iterdir()) if x.is_file()}:
        raise ValueError('completion files changed during read-only audit')
    return {'version': 1, 'namespace': c.POLICY.namespace, 'manifest_sha256': c.MANIFEST_SHA,
        'source_sha256': plan['source_sha256'], 'label_config': plan['jev_config'],
        'execution_commit': json.loads((run / 'execution-provenance.json').read_text())['execution_commit'],
        'completion_database_sha256': before_hashes['followup.db'],
        'previous_followup_database_sha256': manifest['accepted_followup_database_sha256'],
        'approval_utc': c.APPROVAL['approved_utc'], 'recorded_through_utc': rows[-1]['settled_utc'],
        'route': {'service': 'OpenRouter', 'provider': 'Crusoe', 'model': g.MODEL, 'tag': b.ROUTE,
                  'reasoning': 'low', 'max_tokens': 4096, 'fallback': False, 'zdr': True, 'data_collection': 'deny'},
        'cost': {'attempts': len(rows), 'maximum_attempts': c.POLICY.max_attempts,
                 'status_counts': dict(Counter(r['status'] for r in rows)), 'known_charges_nusd': known,
                 'unresolved_reservations_nusd': held, 'exposure_nusd': known + held, 'cap_nusd': c.POLICY.cap},
        'new_valid_outputs': {role: len(fresh[role]) for role in ('verify', 'group')},
        'before': before, 'after': after, 'verifier_statistics': verifier_statistics(plan, merged),
        'receipts': receipts, 'invalid_batches': invalid, 'original_artifacts_and_historical_holds_preserved': True,
        'limits': ['Saved sample coverage is not population coverage or human accuracy.',
                   'Old invalid outputs and unresolved reservations remain unchanged.',
                   'Agreement denominators include only valid observed outputs; all selected IDs remain in coverage.',
                   'No new golden scoring, auditor calls, synthetic attacks or production database writes.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'source', 'allowlist', 'prior-run', 'run', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--check', action='store_true'); a = parser.parse_args()
    text = json.dumps(build(a.manifest, a.source, a.allowlist, a.prior_run, a.run), indent=2, sort_keys=True) + '\n'
    if a.check:
        if a.out.read_text() != text: raise ValueError('completion public aggregate is stale')
        print('completion aggregate is current; all saved inputs unchanged')
    else:
        a.out.write_text(text); print('safe completion aggregate written; no database writes or API calls')


if __name__ == '__main__':
    main()

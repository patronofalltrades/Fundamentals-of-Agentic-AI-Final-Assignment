"""Synthetic fixtures only; no network, human labels or private source reads."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tools import bounded_gap_followup as b
from tools import gap_closure_eval as g
from tests.test_gap_closure_eval import fake_openrouter


class AtomicBudget:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE reservations(request_key TEXT PRIMARY KEY,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
        self.db.commit()

    def reserve(self, key, budget, amount, record=None):
        with self.db:
            self.db.execute("INSERT INTO reservations VALUES(?,'reserved',?,NULL)", (key, amount))
            record(self.db)

    def settle(self, key, status, charge, record=None):
        with self.db:
            self.db.execute("UPDATE reservations SET status=?,charged_nusd=? WHERE request_key=?", (status, charge, key))
            record(self.db)

    def uncertain(self, key, record=None):
        with self.db:
            self.db.execute("UPDATE reservations SET status='uncertain' WHERE request_key=?", (key,))
            record(self.db)


def synthetic_calls():
    calls = []
    for i, role in enumerate(("verify", "verify", "group", "group", "audit_label")):
        ids = ["synthetic-%d-%d" % (i, j) for j in range(10)]
        items = [{"review_id": r, "review_text": "Synthetic playback fixture"} for r in ids]
        if role == "audit_label":
            for item in items:
                item["claimed"] = {"topic": "playback", "intent": "complaint", "severity": 3}
        schema = g.LABEL_ITEM if role == "verify" else g.group_item() if role == "group" else g.AUDIT_LABEL_ITEM
        request = g.on_route(g.role_request(role, "Synthetic test", items, schema), b.ROUTE)
        calls.append((role + ":%03d" % i, role, ids, request))
    return calls


def good(request):
    response = fake_openrouter(request)
    response["provider"] = "Crusoe"
    response["usage"]["cost"] = 0.0001
    return 200, json.dumps(response).encode(), {}


class BoundedFollowupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.budget = AtomicBudget(self.out / "shared.db"); self.addCleanup(self.budget.db.close)
        self.calls = synthetic_calls()
        self.sent = 0
        self.now, self.waited = 1000.0, 0.0

    def runner(self, send=good):
        def count(request):
            self.sent += 1
            return send(request)
        def sleep(seconds):
            self.now += seconds; self.waited += seconds
        return b.BoundedRunner(self.budget, self.out, self.calls, {"synthetic": True}, count, lambda: None,
                               clock=lambda: self.now, sleep=sleep)

    def test_success_is_not_resent_and_receipts_are_private(self):
        r = self.runner()
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 5)
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 5)
        self.assertEqual(r.exposure(), 500000)
        self.assertEqual(self.waited, 4 * b.MIN_REQUEST_INTERVAL_SECONDS)
        self.assertEqual(len(list(self.out.glob('receipt-*.bin'))), 5)
        self.assertEqual((self.out / 'followup.db').stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.out.glob('receipt-*.bin')))

    def test_uncertain_delivery_stops_all_and_cannot_resume(self):
        def lost(_): raise TimeoutError('synthetic timeout')
        r = self.runner(lost)
        self.assertEqual(r.run(), "stopped_uncertain")
        self.assertEqual(r.run(), "stopped_uncertain")
        self.assertEqual(self.sent, 1)
        self.assertEqual(r.exposure(), b.RESERVE)
        self.assertEqual(self.budget.db.execute('SELECT status FROM reservations').fetchone()[0], 'uncertain')

    def test_http_rejection_has_one_retry_and_keeps_every_hold(self):
        r = self.runner(lambda _: (429, b'{"error":"synthetic rejection"}', {}))
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 10)
        self.assertEqual(r.exposure(), 10 * b.RESERVE)
        self.assertEqual(self.waited, 9 * b.FALLBACK_BACKOFF_SECONDS)
        self.assertLessEqual(r.exposure(), b.CAP)
        self.assertTrue(all(x[0] == 2 for x in r.db.execute('SELECT COUNT(*) FROM followup.calls GROUP BY logical')))
        r.run(); self.assertEqual(self.sent, 10)

    def test_metered_invalid_output_retries_once(self):
        def invalid(request):
            status, raw, headers = good(request); response = json.loads(raw)
            rows = json.loads(response['choices'][0]['message']['content'])
            rows['results'][0]['unexpected'] = True
            response['choices'][0]['message']['content'] = json.dumps(rows)
            return status, json.dumps(response).encode(), headers
        r = self.runner(invalid); r.run()
        self.assertEqual(self.sent, 10)
        self.assertEqual(r.db.execute("SELECT COUNT(*) FROM followup.calls WHERE status='quarantined_metered'").fetchone()[0], 10)
        self.assertEqual(r.exposure(), 1000000)

    def test_wrong_provider_is_uncertain_without_retry(self):
        def wrong(request):
            _, raw, headers = good(request); response = json.loads(raw); response['provider'] = 'Other'
            return 200, json.dumps(response).encode(), headers
        r = self.runner(wrong)
        self.assertEqual(r.run(), 'stopped_uncertain'); self.assertEqual(self.sent, 1)

    def test_run_cap_rolls_back_both_admissions_before_transport(self):
        with patch.object(b, 'CAP', b.RESERVE - 1):
            r = self.runner(lambda _: (429, b'{}', {}))
            with self.assertRaisesRegex(ValueError, 'cap'):
                r.run()
        self.assertEqual(self.sent, 0)
        self.assertEqual(r.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0], 0)
        self.assertEqual(r.db.execute('SELECT COUNT(*) FROM followup.calls').fetchone()[0], 0)

    def test_unapproved_batch_or_fallback_is_rejected(self):
        with self.assertRaises(ValueError): b.validate_scope(self.calls + [self.calls[0]])
        self.calls[0][3]['provider']['allow_fallbacks'] = True
        with self.assertRaises(ValueError): b.validate_scope(self.calls)

    def test_second_active_request_is_rolled_back(self):
        self.budget.db.execute("INSERT INTO reservations VALUES('other','reserved',1,NULL)"); self.budget.db.commit()
        r = self.runner()
        with self.assertRaisesRegex(ValueError, 'another paid request'):
            r.run()
        self.assertEqual(self.sent, 0)
        self.assertEqual(r.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0], 1)

    def test_offline_report_keeps_unchanged_issue_auditor_for_paired_joins(self):
        r = self.runner(); r.run()
        audit_ids = self.calls[4][2]
        verify_ids = self.calls[0][2] + self.calls[1][2] + audit_ids
        group_ids = self.calls[2][2] + self.calls[3][2]
        label = {"topic": "playback", "intent": "complaint", "severity": 3}
        old = {"verify": {i: dict(label) for i in audit_ids}, "group": {}, "audit_label": {},
               "audit_group": {i: {"supported": True} for i in group_ids}}
        plan = {"verify_ids": verify_ids, "group_ids": group_ids,
                "jev_labels": {i: dict(label) for i in verify_ids},
                "historical_issue": {i: "PLY-FAIL" for i in group_ids},
                "label_claims": {i: {"planted": "severity" if n < 7 else None, "claim": dict(label)} for n, i in enumerate(audit_ids)},
                "group_claims": {i: {"planted": True, "claim": "PLY-FAIL"} for i in group_ids}}
        report = b.summarize(self.out, plan, old, self.calls, {"synthetic": True})
        self.assertEqual(report["new_outputs"], {"verify": 20, "group": 20, "audit_label": 10})
        self.assertEqual(report["paired_issue_coverage"]["n"], 20)
        self.assertEqual(report["paired_label_coverage"]["n"], 7)
        self.assertEqual(sum(report["paired_issue_table"].values()), 20)
        saved = json.loads((self.out / "merged-machine-outputs.json").read_text())
        self.assertEqual(saved["audit_group"], old["audit_group"])

    def test_retry_after_seconds_and_http_date_override_fallback(self):
        self.assertEqual(b.retry_delay({"retry-after": "120"}, 1000), 120)
        self.assertEqual(b.retry_delay({"retry-after": "Thu, 01 Jan 1970 00:20:00 GMT"}, 1000), 200)
        self.assertEqual(b.retry_delay({"retry-after": "nonsense"}, 1000), 45)

    def test_provider_headers_saved_and_global_cooldown_survives_resume(self):
        r = self.runner(lambda _: (429, b'{}', {"Retry-After": "600", "Set-Cookie": "secret", "X-RateLimit-Remaining": "0"}))
        self.assertEqual(r.run(), "stopped_rate_limit_wait")
        self.assertEqual(self.sent, 1)
        self.assertEqual(r.run(), "stopped_rate_limit_wait")
        self.assertEqual(self.sent, 1)
        headers = json.loads(r.db.execute('SELECT response_headers_json FROM followup.calls').fetchone()[0])
        self.assertEqual(headers, {"retry-after": "600", "x-ratelimit-remaining": "0"})
        self.now += 600
        r.send = good
        self.assertEqual(r.run(), "finished")
        self.assertEqual(r.exposure(), b.RESERVE + 500000)

    def test_candidate_id_enum_changes_hash_without_mutating_frozen_request(self):
        _, role, ids, request = self.calls[0]
        original = g.digest(request)
        candidate = b.bind_response_id_enum(request, ids)
        self.assertNotEqual(g.digest(candidate), original)
        self.assertEqual(g.digest(request), original)
        enum = candidate['response_format']['json_schema']['schema']['properties']['results']['items']['properties']['review_id']['enum']
        self.assertEqual(enum, ids)
        _, raw, _ = good(request); response = json.loads(raw)
        value = json.loads(response['choices'][0]['message']['content'])
        value['results'][1]['review_id'] = value['results'][0]['review_id']
        response['choices'][0]['message']['content'] = json.dumps(value)
        with self.assertRaises(ValueError): b.strict_output(role, response, ids, candidate)

    def test_old_run_is_rejected_without_migration_or_byte_changes(self):
        path = self.out / 'followup.db'
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE calls(status TEXT)')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.runner()
        self.assertEqual(path.read_bytes(), before)
        with patch('sys.argv', ['followup', '--source', str(self.out), '--allowlist', str(self.out / 'unused'),
                                '--out', str(self.out), '--shared-budget-root', str(self.out), '--execute']), \
                patch.object(b, 'preflight') as preflight, patch.object(b, 'read_source') as read_source:
            with self.assertRaisesRegex(ValueError, 'immutable'): b.main()
            preflight.assert_not_called()
            read_source.assert_not_called()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.out / 'approval-and-identity.json').exists())

    def test_id_enum_rejects_different_input_identity(self):
        _, _, ids, request = self.calls[0]
        with self.assertRaisesRegex(ValueError, 'exact input IDs'):
            b.bind_response_id_enum(request, list(reversed(ids)))


if __name__ == '__main__': unittest.main()

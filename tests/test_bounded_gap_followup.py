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
    return 200, json.dumps(response).encode()


class BoundedFollowupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.budget = AtomicBudget(self.out / "shared.db"); self.addCleanup(self.budget.db.close)
        self.calls = synthetic_calls()
        self.sent = 0

    def runner(self, send=good):
        def count(request):
            self.sent += 1
            return send(request)
        return b.BoundedRunner(self.budget, self.out, self.calls, {"synthetic": True}, count, lambda: None)

    def test_success_is_not_resent_and_receipts_are_private(self):
        r = self.runner()
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 5)
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 5)
        self.assertEqual(r.exposure(), 500000)
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
        r = self.runner(lambda _: (429, b'{"error":"synthetic rejection"}'))
        self.assertEqual(r.run(), "finished")
        self.assertEqual(self.sent, 10)
        self.assertEqual(r.exposure(), 10 * b.RESERVE)
        self.assertLessEqual(r.exposure(), b.CAP)
        self.assertTrue(all(x[0] == 2 for x in r.db.execute('SELECT COUNT(*) FROM followup.calls GROUP BY logical')))
        r.run(); self.assertEqual(self.sent, 10)

    def test_metered_invalid_output_retries_once(self):
        def invalid(request):
            status, raw = good(request); response = json.loads(raw)
            rows = json.loads(response['choices'][0]['message']['content'])
            rows['results'][0]['unexpected'] = True
            response['choices'][0]['message']['content'] = json.dumps(rows)
            return status, json.dumps(response).encode()
        r = self.runner(invalid); r.run()
        self.assertEqual(self.sent, 10)
        self.assertEqual(r.db.execute("SELECT COUNT(*) FROM followup.calls WHERE status='quarantined_metered'").fetchone()[0], 10)
        self.assertEqual(r.exposure(), 1000000)

    def test_wrong_provider_is_uncertain_without_retry(self):
        def wrong(request):
            _, raw = good(request); response = json.loads(raw); response['provider'] = 'Other'
            return 200, json.dumps(response).encode()
        r = self.runner(wrong)
        self.assertEqual(r.run(), 'stopped_uncertain'); self.assertEqual(self.sent, 1)

    def test_run_cap_rolls_back_both_admissions_before_transport(self):
        r = self.runner(lambda _: (429, b'{}'))
        with patch.object(b, 'CAP', b.RESERVE - 1):
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


if __name__ == '__main__': unittest.main()

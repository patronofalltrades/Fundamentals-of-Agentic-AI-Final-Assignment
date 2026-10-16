"""Synthetic execution tests. No provider credentials, source text or network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_bounded_gap_followup import AtomicBudget, good, synthetic_calls
from tools import bounded_gap_followup as b
from tools import run_measurement_completion as c


class CompletionExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.budget = AtomicBudget(self.out / 'shared.db'); self.addCleanup(self.budget.db.close)
        self.calls = [(logical, role, ids, b.bind_response_id_enum(request, ids))
                      for logical, role, ids, request in synthetic_calls()[:3]]
        self.now, self.sent = 1000.0, 0

    def runner(self, send=good, policy=c.POLICY):
        def count(request):
            self.sent += 1
            return send(request)
        def sleep(seconds): self.now += seconds
        return b.BoundedRunner(self.budget, self.out, self.calls, {'manifest_sha256': 'synthetic'},
            count, lambda: None, clock=lambda: self.now, sleep=sleep, policy=policy)

    def test_nine_attempt_bound_and_full_holds(self):
        r = self.runner(lambda _: (429, b'{}', {}))
        self.assertEqual(r.run(), 'finished')
        self.assertEqual(self.sent, 9)
        self.assertEqual(r.exposure(), 324401400)
        self.assertLessEqual(r.exposure(), c.POLICY.cap)
        self.assertEqual([x[0] for x in r.db.execute('SELECT COUNT(*) FROM followup.calls GROUP BY logical')], [3, 3, 3])
        self.assertEqual(r.run(), 'finished'); self.assertEqual(self.sent, 9)

    def test_valid_batches_are_not_repeated(self):
        r = self.runner()
        self.assertEqual(r.run(), 'finished'); self.assertEqual(self.sent, 3)
        self.assertEqual(r.run(), 'finished'); self.assertEqual(self.sent, 3)
        keys = [row[0] for row in r.db.execute('SELECT request_key FROM reservations')]
        self.assertTrue(all(key.startswith(c.POLICY.namespace + ':') for key in keys))

    def test_cooldown_persists_across_new_runner_and_policy_is_frozen(self):
        r = self.runner(lambda _: (429, b'{}', {'Retry-After': '600'}))
        self.assertEqual(r.run(), 'stopped_rate_limit_wait'); self.assertEqual(self.sent, 1)
        r.db.execute('DETACH DATABASE followup')
        r = self.runner()
        self.assertEqual(r.run(), 'stopped_rate_limit_wait'); self.assertEqual(self.sent, 1)
        self.now += 600
        self.assertEqual(r.run(), 'finished'); self.assertEqual(self.sent, 4)
        r.db.execute('DETACH DATABASE followup')
        changed = b.RunPolicy(c.POLICY.namespace, c.POLICY.cap, c.POLICY.reserve, 10, 4, c.POLICY.role_counts)
        with self.assertRaisesRegex(ValueError, 'identity changed'): self.runner(policy=changed)

    def test_uncertain_delivery_and_configuration_rejection_stop_all(self):
        r = self.runner(lambda _: (400, b'{}', {}))
        self.assertEqual(r.run(), 'stopped_configuration')
        self.assertEqual(r.run(), 'stopped_configuration')
        self.assertEqual(self.sent, 1)

    def test_mutated_request_stops_before_admission(self):
        r = self.runner()
        self.calls[0][3]['max_tokens'] = 4095
        with self.assertRaisesRegex(ValueError, 'frozen request changed'): r.run()
        self.assertEqual(self.sent, 0)
        self.assertEqual(r.exposure(), 0)

    def test_manifest_mismatch_stops_before_source_read(self):
        path = self.out / 'manifest.json'; path.write_text('{}'); path.chmod(0o600)
        with patch.object(c.publication, 'build') as read:
            with self.assertRaisesRegex(ValueError, 'manifest digest differs'):
                c.load_bound(path, self.out, self.out, self.out)
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()

import tempfile
import threading
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
from pipeline import spend
from labelling.model_client import InvalidModelOutput, TransientModelError


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class RateLimiterTests(unittest.TestCase):
    def test_requests_per_minute(self):
        c = FakeClock()
        rl = spend.RateLimiter(requests_per_minute=2, clock=c, sleep=c.sleep)
        self.assertEqual(rl.acquire(), 0.0)
        self.assertEqual(rl.acquire(), 0.0)
        waited = rl.acquire()
        self.assertAlmostEqual(waited, 30.0)
        self.assertAlmostEqual(c.t, 30.0)

    def test_tokens_per_minute_and_oversized(self):
        c = FakeClock()
        rl = spend.RateLimiter(tokens_per_minute=600, clock=c, sleep=c.sleep)
        rl.acquire(500)
        self.assertAlmostEqual(rl.acquire(200), 10.0)  # needs 100 more tokens at 10/s
        c.t += 1000
        rl.acquire(5000)  # larger than capacity: waits only for a full bucket
        self.assertEqual(len(c.sleeps), 1)

    def test_thread_safety(self):
        rl = spend.RateLimiter(requests_per_minute=1000)
        threads = [threading.Thread(target=lambda: [rl.acquire() for _ in range(50)]) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertLess(rl._req.level, 1000 - 400 + 1 + 50)  # 400 debits happened (minus small refill)


class LedgerTests(unittest.TestCase):
    def test_reserve_commit_release_and_cap(self):
        with tempfile.TemporaryDirectory() as d:
            led = spend.SpendLedger(1.0, Path(d) / "ledger.json")
            r1 = led.reserve(0.4)
            self.assertTrue(led.can_admit(0.6))
            self.assertFalse(led.can_admit(0.61))
            r2 = led.reserve(0.5)
            with self.assertRaises(spend.BudgetExceeded):
                led.reserve(0.2)
            led.commit(r1, 0.1)
            led.release(r2)
            self.assertAlmostEqual(led.spent_usd, 0.1)
            self.assertEqual(led.reserved_usd, 0)
            r3 = led.reserve(0.3)
            led.commit(r3, None)  # unknown cost: charged at the reservation, not zero
            self.assertAlmostEqual(led.committed_usd(), 0.4)
            led.save()
            again = spend.SpendLedger(1.0, Path(d) / "ledger.json")
            self.assertAlmostEqual(again.committed_usd(), 0.4)
            self.assertEqual(again.by_role["enrich"]["unpriced_calls"], 1)

    def test_uncertain_and_charge(self):
        led = spend.SpendLedger(None)
        r = led.reserve(0.2)
        led.commit(r, None, uncertain=True)
        led.charge(0.05, "memo")
        self.assertAlmostEqual(led.uncertain_usd, 0.2)
        self.assertAlmostEqual(led.spent_usd, 0.05)
        self.assertTrue(led.can_admit(1e9))

    def test_cost_from_usage(self):
        rates = {"input_per_mtok": 1.0, "cached_input_per_mtok": 0.1, "output_per_mtok": 2.0}
        self.assertAlmostEqual(spend.cost_from_usage(rates, 1_000_000, 500_000, cached_input_tokens=400_000),
                               0.6 + 0.04 + 1.0)
        self.assertIsNone(spend.cost_from_usage({}, 10, 10))
        doubled = {k: 2 * v for k, v in rates.items()}
        self.assertAlmostEqual(spend.cost_from_usage(doubled, 1000, 1000) / spend.cost_from_usage(rates, 1000, 1000), 2)


class RetryTests(unittest.TestCase):
    def test_retries_transient_then_succeeds(self):
        sleeps, seen = [], []

        def fn(attempt):
            if attempt < 3:
                raise TransientModelError("429")
            return "ok"
        out = spend.retry_call(fn, max_attempts=5, base_delay=2, sleep=sleeps.append, rng=lambda: 0.5,
                               on_error=lambda e, a, d: seen.append((a, d)))
        self.assertEqual(out, "ok")
        self.assertEqual(sleeps, [1.0, 2.0])  # full jitter: rng * base * 2^(n-1)
        self.assertEqual(seen, [(1, 1.0), (2, 2.0)])

    def test_honors_retry_after_and_bounds(self):
        sleeps = []
        err = TransientModelError("slow down")
        err.retry_after = 7

        def fn(attempt):
            raise err
        with self.assertRaises(TransientModelError):
            spend.retry_call(fn, max_attempts=3, sleep=sleeps.append, rng=lambda: 0.0)
        self.assertEqual(sleeps, [7.0, 7.0])

    def test_non_retryable_raises_immediately(self):
        calls = []

        def fn(attempt):
            calls.append(attempt)
            raise InvalidModelOutput("bad")
        with self.assertRaises(InvalidModelOutput):
            spend.retry_call(fn, sleep=lambda s: None)
        self.assertEqual(calls, [1])

    def test_backoff_cap(self):
        self.assertEqual(spend.backoff_delay(20, base=1, cap=60, rng=lambda: 1.0), 60)


if __name__ == "__main__":
    unittest.main()

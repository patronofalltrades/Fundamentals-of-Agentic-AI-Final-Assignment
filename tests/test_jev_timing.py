"""Offline regression for paid-run wall time measurement."""

import unittest
from decimal import Decimal

from tools.jev_pilot import execute_measured


class FakeLedger:
    def __init__(self, *args):
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class RunnerTimingTests(unittest.TestCase):
    def test_one_process_clock_covers_access_and_run(self):
        events = []
        ticks = iter((10.0, 12.5))
        def access(key):
            events.append(("access", key))
        def run(rows, ledger, key):
            events.append(("run", key, ledger.args))
            return {"processed_this_run": len(rows)}
        report = execute_measured([{"synthetic": True}], "synthetic.db", "hash",
                                  Decimal("0.1"), "synthetic-key", access_check=access,
                                  ledger_factory=FakeLedger, run=run, clock=lambda: next(ticks))
        self.assertEqual(report["runner_wall_seconds"], 2.5)
        self.assertEqual([event[0] for event in events], ["access", "run"])

    def test_clock_error_never_reports_negative_wall_time(self):
        ticks = iter((10.0, 9.0))
        with self.assertRaisesRegex(ValueError, "runner wall time is invalid"):
            execute_measured([], "synthetic.db", "hash", Decimal("0.1"), "synthetic-key",
                             access_check=lambda _: None, ledger_factory=FakeLedger,
                             run=lambda *_: {}, clock=lambda: next(ticks))


if __name__ == "__main__":
    unittest.main()

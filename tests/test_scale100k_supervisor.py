"""No-network state-machine checks for the foreground scale supervisor."""

import json
import fcntl
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import scale100k_supervisor as supervisor


def state(count=10000, eligible=1, labels=0, evidence=0, uncertain=0,
          states=None):
    return {"activated_source_rows": count, "jev_eligible_unique": eligible,
        "evidence_eligible_unique": 0, "labels": labels, "evidence": evidence,
        "source_states": states or {"eligible_or_awaiting_label": count},
        "requests": {"jev:uncertain": uncertain},
        "exposure_nusd": {"jev": 100, "openrouter": 200}}


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch_checkpoint = patch.object(supervisor, "CHECKPOINT",
            Path(self.tmp.name) / "checkpoint.json")
        self.patch_coverage = patch.object(supervisor, "source_coverage")
        self.patch_checkpoint.start()
        self.patch_coverage.start()
        self.addCleanup(self.patch_checkpoint.stop)
        self.addCleanup(self.patch_coverage.stop)

    def run_steps(self, steps, stopped=lambda: False, resume_reviewed=False,
                  manifest=None):
        calls = []
        def invoke(mode, manifest, sha, interrupted):
            calls.append(mode)
            expected, result = steps.pop(0)
            self.assertEqual(mode, expected)
            return result
        result = supervisor.supervise(manifest or {"rows": []}, "frozen-sha", stopped, invoke,
            resume_reviewed=resume_reviewed)
        self.assertFalse(steps)
        return result, calls

    def test_drained_segment_advances_one_gate_without_replaying_calls(self):
        done = state(10000, 0, 10000, 10000, states={"accepted": 10000})
        next_gate = state(20000, 1, 10000, 10000)
        next_gate["activated_now"] = 10000
        halted = state(20000, 1, 10000, 10000)
        code, calls = self.run_steps([
            ("status", state()),
            ("run-mixed", {"paused": False, "new_uncertain": {}, "halt_reason": None}),
            ("status", done),
            ("activate-next-gate", next_gate),
            ("status", state(20000, 1, 10000, 10000)),
            ("run-mixed", {"paused": True, "new_uncertain": {},
                "halt_reason": "budget cap reached"}),
            ("status", halted),
        ])
        self.assertEqual(code, 2)
        self.assertEqual(calls.count("run-mixed"), 2)

    def test_new_uncertain_stops_even_with_existing_holds(self):
        code, calls = self.run_steps([
            ("status", state(uncertain=4)),
            ("run-mixed", {"paused": False, "new_uncertain": {"jev": 1}}),
            ("status", state(labels=1, uncertain=5)),
        ])
        self.assertEqual(code, 2)
        self.assertEqual(calls.count("run-mixed"), 1)

    def test_saved_charged_response_recovery_precedes_any_new_paid_segment(self):
        initial = state()
        initial["requests"]["evidence:quarantined_metered"] = 1
        code, calls = self.run_steps([
            ("status", initial), ("recover-metered", {}),
            ("status", state(labels=1)),
            ("run-mixed", {"paused": True, "halt_reason": "budget cap reached",
                "new_uncertain": {}}),
            ("status", state(labels=1)),
        ])
        self.assertEqual(code, 2)
        self.assertLess(calls.index("recover-metered"), calls.index("run-mixed"))

    def test_quality_recovery_progress_is_bounded_across_restart(self):
        quality = {"paused": True, "halt_reason": "structural quality gate",
            "new_uncertain": {"jev": 0, "evidence": 0}}
        code, calls = self.run_steps([
            ("status", state()), ("run-mixed", quality),
            ("status", state(labels=1)), ("recover-metered", {}),
            ("status", state(labels=2)), ("run-mixed", quality),
            ("status", state(labels=3)), ("recover-metered", {}),
            ("status", state(labels=4)),
        ])
        self.assertEqual(code, 2)
        self.assertEqual(calls.count("recover-metered"), 2)
        saved = json.loads(supervisor.CHECKPOINT.read_text())
        self.assertEqual(saved["quality_stops"], 2)
        code, calls = self.run_steps([("status", state(labels=4))])
        self.assertEqual(code, 2)
        self.assertEqual(calls, ["status"])

    def test_reviewed_resume_clears_persistent_quality_stop(self):
        supervisor.CHECKPOINT.write_text(json.dumps({"manifest_sha": "frozen-sha",
            "quality_stops": 2, "uncertain_baseline": 0}))
        code, calls = self.run_steps([
            ("status", state()),
            ("run-mixed", {"paused": True, "halt_reason": "budget cap reached",
                "new_uncertain": {}}),
            ("status", state()),
        ], resume_reviewed=True)
        self.assertEqual(code, 2)
        self.assertIn("run-mixed", calls)
        saved = json.loads(supervisor.CHECKPOINT.read_text())
        self.assertEqual(saved["quality_stops"], 0)
        self.assertEqual(saved["uncertain_baseline"], 0)

    def test_crash_after_new_uncertain_blocks_until_reviewed_resume(self):
        supervisor.CHECKPOINT.write_text(json.dumps({"manifest_sha": "frozen-sha",
            "quality_stops": 0, "uncertain_baseline": 4}))
        code, calls = self.run_steps([("status", state(uncertain=5))])
        self.assertEqual(code, 2)
        self.assertEqual(calls, ["status"])
        self.assertEqual(json.loads(supervisor.CHECKPOINT.read_text())[
            "uncertain_baseline"], 4)
        code, calls = self.run_steps([
            ("status", state(uncertain=5)),
            ("run-mixed", {"paused": True, "halt_reason": "budget cap reached",
                "new_uncertain": {}}),
            ("status", state(uncertain=5)),
        ], resume_reviewed=True)
        self.assertEqual(code, 2)
        self.assertIn("run-mixed", calls)
        self.assertEqual(json.loads(supervisor.CHECKPOINT.read_text())[
            "uncertain_baseline"], 5)

    def test_reviewed_resume_requires_a_saved_review_stop(self):
        with self.assertRaisesRegex(ValueError, "requires a saved supervisor stop"):
            self.run_steps([("status", state())], resume_reviewed=True)

    def test_quality_without_accepted_progress_stops(self):
        code, _ = self.run_steps([
            ("status", state()),
            ("run-mixed", {"paused": True,
                "halt_reason": "structural quality gate", "new_uncertain": {}}),
            ("status", state()), ("recover-metered", {}),
            ("status", state()),
        ])
        self.assertEqual(code, 2)

    def test_budget_denial_stops_before_recovery_or_gate(self):
        code, calls = self.run_steps([
            ("status", state()),
            ("run-mixed", {"paused": True, "halt_reason": "budget cap reached",
                "new_uncertain": {}}),
            ("status", state()),
        ])
        self.assertEqual(code, 2)
        self.assertNotIn("activate-next-gate", calls)

    def test_no_progress_stops_even_if_runner_exhausted_queue(self):
        no_work = state(10000, 0, states={"evidence_context_limit": 10000})
        code, calls = self.run_steps([
            ("status", state()),
            ("run-mixed", {"paused": False, "halt_reason": None,
                "new_uncertain": {}}),
            ("status", no_work),
        ])
        self.assertEqual(code, 2)
        self.assertNotIn("activate-next-gate", calls)

    def test_accepted_target_requires_reconciled_source_statuses(self):
        complete = state(100000, 0, labels=100000, evidence=90434,
            states={"accepted": 90434, "quarantined": 9566})
        code, calls = self.run_steps([("status", complete)],
            manifest={"rows": [], "selected_rows": 100000})
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["status"])
        unfinished = state(100000, 0, labels=100000, evidence=90433,
            states={"accepted": 90433, "quarantined": 9566,
                "eligible_or_awaiting_label": 1})
        with self.assertRaisesRegex(ValueError, "unfinished eligible"):
            self.run_steps([("status", unfinished)],
                manifest={"rows": [], "selected_rows": 100000})

    def test_selected_100k_alone_does_not_complete_accepted_target(self):
        selected = state(90000, 0, labels=90000, evidence=90000,
            states={"accepted": 90000})
        code, calls = self.run_steps([("status", selected)])
        self.assertEqual(code, 2)
        self.assertEqual(calls, ["status"])
        self.assertEqual(json.loads(supervisor.CHECKPOINT.read_text())[
            "stop_reason"], "frozen source exhausted before accepted target")

    def test_interrupt_does_not_dispatch(self):
        code, calls = self.run_steps([("status", state())], lambda: True)
        self.assertEqual(code, 130)
        self.assertEqual(calls, ["status"])

    def test_scope_and_source_coverage_are_checked(self):
        self.patch_coverage.stop()
        with self.assertRaisesRegex(ValueError, "frozen 10k gate"):
            supervisor.source_coverage({"rows": []}, 90001)
        self.patch_coverage.start()
        with self.assertRaisesRegex(ValueError, "statuses do not reconcile"):
            supervisor.checked_status(state(states={"accepted": 1}), {})
        supervisor.CHECKPOINT.write_text(json.dumps({"manifest_sha": "frozen-sha",
            "quality_stops": 1}))
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            supervisor.supervise({}, "different-sha", lambda: False)

    def test_source_coverage_checks_original_id_and_hash(self):
        self.patch_coverage.stop()
        db_path = Path(self.tmp.name) / "budget.db"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE scale_rows(position INTEGER,review_id TEXT,source_sha TEXT)")
            db.executemany("INSERT INTO scale_rows VALUES (?,?,?)",
                ((10001 + n, "id" + str(n), "hash" + str(n)) for n in range(10000)))
        manifest = {"rows": [{"source_position": 10001 + n,
            "review_id": "id" + str(n), "source_sha256": "hash" + str(n)}
            for n in range(10000)]}
        with patch.object(supervisor.scale, "BUDGET", str(db_path)):
            supervisor.source_coverage(manifest, 10000)
            manifest["rows"][9999]["source_sha256"] = "wrong"
            with self.assertRaisesRegex(ValueError, "source identity differs"):
                supervisor.source_coverage(manifest, 10000)
        self.patch_coverage.start()

    def test_duplicate_supervisor_and_manual_runner_are_excluded(self):
        supervisor_lock = Path(self.tmp.name) / "supervisor.lock"
        runner_lock = Path(self.tmp.name) / "runner.lock"
        with patch.object(supervisor, "SUPERVISOR_LOCK", supervisor_lock), \
                patch.object(supervisor.scale, "LOCK", runner_lock), \
                patch.object(sys, "argv", ["supervisor"]):
            with supervisor_lock.open("a+b") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "another scale supervisor"):
                    supervisor.main()
            with runner_lock.open("a+b") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "manual paid runner"):
                    supervisor.main()


if __name__ == "__main__":
    unittest.main()

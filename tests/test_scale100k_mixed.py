"""Synthetic shared-scheduler tests. All provider transports are replaced."""

import json
from pathlib import Path
import tempfile
from threading import Lock
import time
import unittest
from unittest.mock import patch

from spotify_pipeline import project_budget
from spotify_pipeline.project_budget import ProjectBudget
from tests.test_jev import fixture_response
from tests.test_project_budget import fixtures
from tests.test_scale100k_throughput import rows, seed
from tools import scale100k_queue as scale


def evidence_response(body, malformed=False):
    sent = json.loads(body["messages"][0]["content"][
        len(scale.trial25.base.INSTRUCTION):])
    results = [{"review_id": item["review_id"], "entities": [],
        "evidence_quote": item["review_text"]} for item in sent]
    if malformed:
        results[0]["review_id"] = "foreign-id"
    return {"id": "synthetic-generation", "model": scale.evidence.MODEL,
        "provider": "DeepInfra", "usage": {"prompt_tokens": 1200,
            "completion_tokens": 1800,
            "completion_tokens_details": {"reasoning_tokens": 400}},
        "choices": [{"finish_reason": "stop",
            "message": {"content": json.dumps({"results": results})}}]}


def adopt(db):
    db.execute("INSERT INTO scale_meta VALUES ('active_evidence_config_sha',?)",
        (scale.trial25.config_sha(),))
    db.commit()


class MixedSchedulerTest(unittest.TestCase):
    def test_interrupt_drains_reserved_calls_and_resume_never_replays(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(20), labels=False)
                adopt(budget.db)
                interrupt = {"requested": False}
                calls = [0]

                def transport(stage, body, key):
                    calls[0] += 1
                    interrupt["requested"] = True
                    time.sleep(0.006)
                    return fixture_response(), 0.006, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=transport):
                    drained = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key",
                        stop_requested=lambda: interrupt["requested"])
                self.assertTrue(drained["paused"])
                self.assertIn("drained", drained["halt_reason"])
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations "
                    "WHERE status='reserved'").fetchone()[0], 0)
                attempted = budget.db.execute("SELECT COUNT(*) FROM scale_requests").fetchone()[0]
                self.assertGreater(attempted, 0)
                self.assertLessEqual(attempted, 8)
                self.assertEqual(attempted, calls[0])
                scale.assert_resume_safe(budget.db)

    def test_ready_evidence_overlaps_jev_and_all_rows_settle_once(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                items = rows(60)
                seed(budget.db, items, labels=False)
                adopt(budget.db)
                lock = Lock()
                inflight = {"jev": 0, "evidence": 0}
                seen = {"jev": 0, "evidence": 0}
                maximum, max_jev, overlap = [0], [0], [False]

                def transport(stage, body, key):
                    with lock:
                        inflight[stage] += 1
                        seen[stage] += 1
                        maximum[0] = max(maximum[0], sum(inflight.values()))
                        max_jev[0] = max(max_jev[0], inflight["jev"])
                        overlap[0] |= all(inflight.values())
                    time.sleep(0.006 if stage == "jev" else 0.025)
                    response = fixture_response() if stage == "jev" else evidence_response(body)
                    with lock:
                        inflight[stage] -= 1
                    return response, 0.006, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=transport):
                    result = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertFalse(result["paused"])
                self.assertTrue(overlap[0])
                self.assertLessEqual(maximum[0], scale.WORKERS)
                self.assertLessEqual(max_jev[0], 4)
                self.assertEqual(result["effective_worker_limits"]["jev_ceiling"], 4)
                self.assertEqual(seen, {"jev": 60, "evidence": 3})
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM scale_labels").fetchone()[0], 60)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM scale_evidence").fetchone()[0], 60)
                self.assertEqual(budget.db.execute("SELECT COUNT(DISTINCT request_key) FROM scale_requests").fetchone()[0], 63)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 0)
                self.assertEqual(result["jev_eligible_unique"], 0)
                self.assertEqual(result["evidence_eligible_unique"], 0)
                scale.assert_resume_safe(budget.db)

    def test_two_uncertain_jev_posts_pause_and_drain_without_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(12), labels=False)
                adopt(budget.db)
                calls = [0]

                def transport(stage, body, key):
                    calls[0] += 1
                    if body["state"] in ("x" * 16 + "0", "x" * 16 + "1"):
                        return None, 0.001, "JevHTTPError:529"
                    time.sleep(0.006)
                    return fixture_response(), 0.006, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=transport):
                    result = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertTrue(result["paused"])
                self.assertEqual(result["new_uncertain"]["jev"], 2)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 0)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='uncertain'").fetchone()[0], 2)
                self.assertEqual(budget.db.execute("SELECT COUNT(DISTINCT review_id) FROM scale_members").fetchone()[0], calls[0])
                self.assertGreater(result["jev_eligible_unique"], 0)
                scale.assert_resume_safe(budget.db)
                held_ids = {rid for rid, in budget.db.execute("""SELECT m.review_id
                    FROM scale_members m JOIN scale_requests q USING(request_key)
                    WHERE q.status='uncertain'""")}

                def resume_transport(stage, body, key):
                    return (fixture_response() if stage == "jev" else
                        evidence_response(body)), 0.002, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=resume_transport):
                    resumed = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertFalse(resumed["paused"])
                self.assertEqual(resumed["jev_eligible_unique"], 0)
                for rid in held_ids:
                    self.assertEqual(budget.db.execute("""SELECT COUNT(*) FROM
                        scale_members m JOIN scale_requests q USING(request_key)
                        WHERE m.review_id=? AND q.stage='jev'""", (rid,)).fetchone()[0], 1)
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 0)

    def test_three_charged_malformed_batches_stop_after_drain(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(125))
                adopt(budget.db)
                calls = [0]

                def transport(stage, body, key):
                    self.assertEqual(stage, "evidence")
                    calls[0] += 1
                    time.sleep(0.006)
                    return evidence_response(body, malformed=True), 0.006, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=transport):
                    result = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertTrue(result["paused"])
                self.assertGreaterEqual(result["malformed_batches"], 3)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 0)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='quarantined_metered'").fetchone()[0], calls[0])
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM scale_quarantines").fetchone()[0], calls[0] * 25)
                scale.assert_resume_safe(budget.db)

    def test_evidence_cooldown_does_not_pause_jev_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(250))
                budget.db.execute("DELETE FROM scale_labels WHERE review_id IN "
                    "(" + ",".join("'id%d'" % i for i in range(200, 250)) + ")")
                adopt(budget.db)
                lock = Lock()
                started = {"jev": [], "evidence": []}
                failed_at = [None]

                def transport(stage, body, key):
                    now = time.monotonic()
                    with lock:
                        started[stage].append(now)
                        first_evidence = stage == "evidence" and len(started[stage]) == 1
                    if first_evidence:
                        failed_at[0] = time.monotonic()
                        return None, 0.001, "HTTPError:429"
                    time.sleep(0.005 if stage == "jev" else 0.015)
                    return (fixture_response() if stage == "jev" else
                        evidence_response(body)), 0.005, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "backoff_seconds", return_value=0.08), \
                     patch.object(scale, "_call", side_effect=transport):
                    result = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertFalse(result["paused"])
                self.assertEqual(result["new_uncertain"]["evidence"], 1)
                self.assertTrue(any(failed_at[0] < t < failed_at[0] + 0.08
                    for t in started["jev"]))
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "reservations WHERE status='uncertain'").fetchone()[0], 1)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "reservations WHERE status='reserved'").fetchone()[0], 0)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "scale_labels").fetchone()[0], 250)
                scale.assert_resume_safe(budget.db)

    def test_shared_budget_refuses_third_call_and_drains_first_two(self):
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(12), labels=False)
                adopt(budget.db)
                exposure = budget.exposure("jev")
                cap = exposure + 2 * scale.RESERVATION_NANODOLLARS + 1
                with patch.dict(project_budget.CAPS, {"jev": cap}), \
                     patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call",
                         return_value=(fixture_response(), 0.002, None)):
                    result = scale.run_mixed(budget, "synthetic-manifest",
                        "jev-key", "evidence-key")
                self.assertTrue(result["paused"])
                self.assertIn("cap", result["halt_reason"])
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "scale_requests").fetchone()[0], 2)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "reservations WHERE status='reserved'").fetchone()[0], 0)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                    "scale_labels").fetchone()[0], 2)
                scale.assert_resume_safe(budget.db)

    def test_explicit_eight_and_twelve_jev_ramp_stays_within_global_limit(self):
        for global_workers, jev_workers, minimum in ((8, 8, 5), (12, 12, 9)):
            with self.subTest(global_workers=global_workers), tempfile.TemporaryDirectory() as folder:
                paths = fixtures(folder)
                db_path = str(Path(folder) / "project.db")
                if global_workers == 12:
                    with ProjectBudget(db_path, paths) as admin:
                        admin.configure_global_inflight(12)
                with ProjectBudget(db_path, paths,
                                   max_global_inflight=global_workers) as budget:
                    seed(budget.db, rows(40), labels=False)
                    adopt(budget.db)
                    lock = Lock()
                    in_flight = {"jev": 0, "evidence": 0}
                    max_jev, max_global = [0], [0]

                    def transport(stage, body, key):
                        with lock:
                            in_flight[stage] += 1
                            max_jev[0] = max(max_jev[0], in_flight["jev"])
                            max_global[0] = max(max_global[0], sum(in_flight.values()))
                        time.sleep(0.01 if stage == "jev" else 0.02)
                        with lock:
                            in_flight[stage] -= 1
                        return (fixture_response() if stage == "jev" else
                            evidence_response(body)), 0.01, None

                    with patch.object(scale, "verify_jev_price"), \
                         patch.object(scale.jev, "check_model_access"), \
                         patch.object(scale.benchmark, "verify_route"), \
                         patch.object(scale.canary, "verify_project_key"), \
                         patch.object(scale, "RAMP_SUCCESSES", 1), \
                         patch.object(scale, "_call", side_effect=transport):
                        result = scale.run_mixed(budget, "synthetic-manifest",
                            "jev-key", "evidence-key", global_workers, jev_workers)
                    self.assertFalse(result["paused"])
                    self.assertGreaterEqual(max_jev[0], minimum)
                    self.assertLessEqual(max_jev[0], jev_workers)
                    self.assertLessEqual(max_global[0], global_workers)
                    self.assertEqual(result["effective_worker_limits"]["jev_start"], 4)
                    self.assertEqual(result["effective_worker_limits"]["jev_ceiling"], jev_workers)
                    self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM "
                        "reservations WHERE status='reserved'").fetchone()[0], 0)

    def test_invalid_or_mismatched_worker_limits_are_rejected_before_dispatch(self):
        for pair in ((7, 4), (13, 4), (8, 3), (8, 9), (True, 4)):
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                scale.validate_mixed_limits(*pair)
        with tempfile.TemporaryDirectory() as folder:
            with ProjectBudget(str(Path(folder) / "project.db"), fixtures(folder)) as budget:
                seed(budget.db, rows(2), labels=False)
                adopt(budget.db)
                with self.assertRaisesRegex(ValueError, "ledger admission limit"):
                    scale.run_mixed(budget, "synthetic-manifest", "unused", "unused", 12, 12)


if __name__ == "__main__":
    unittest.main()

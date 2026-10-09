"""Offline throughput and safety checks for planned scale requests."""

import json
from pathlib import Path
import tempfile
from threading import Barrier, Lock
import time
import unittest
from unittest.mock import patch

from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import label_config
from spotify_pipeline.project_budget import ProjectBudget
from tests.test_jev import fixture_response
from tests.test_project_budget import fixtures
from tools import scale100k_batch25 as trial
from tools import scale100k_queue as scale
from tools import next5000_checkpoint as previous


LABEL = '{"topic":"other","intent":"praise","severity":1,"sentiment":0.5}'


def rows(count, text_size=16):
    return [{"source_position": 10001 + i, "review_id": "id" + str(i),
        "review_text": "x" * text_size + str(i), "source_sha256": "source" + str(i),
        "text_sha256": "textsha" + str(i), "labels": json.loads(LABEL)}
        for i in range(count)]


def seed(db, records, labels=True):
    scale.ensure_tables(db, "synthetic-manifest")
    db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,NULL)",
        ((r["source_position"], r["review_id"], r["review_text"],
          r["source_sha256"], r["text_sha256"]) for r in records))
    if labels:
        db.executemany("INSERT INTO scale_labels VALUES (?,?,?,?,NULL,NULL)",
            ((r["review_id"], LABEL, config_hash(label_config()), "synthetic")
             for r in records))
    db.commit()


class ThroughputSafetyTest(unittest.TestCase):
    def test_token_boundary_packs_largest_safe_prefix_and_preserves_membership(self):
        items = rows(13, 500)
        six = trial.payload(items[:6])
        bound = len(trial.base.canonical(six).encode("utf-8")) + trial.OUTPUT_LIMIT
        with patch.dict(scale.benchmark.ENDPOINT_BOUNDS, {"deepinfra": (bound, 0)}):
            self.assertEqual(trial.payload(items[:6]), six)
            with self.assertRaisesRegex(ValueError, "context bound"):
                trial.payload(items[:7])
            chunks, oversized = scale.plan_evidence_chunks(items, trial=True)
        self.assertFalse(oversized)
        plans = [plan for chunk in chunks for plan in chunk]
        self.assertEqual(len(plans[0][0]), 6)
        self.assertTrue(all(1 <= len(members) <= 6 for members, _, _ in plans))
        self.assertEqual([r["review_id"] for members, _, _ in plans for r in members],
            [r["review_id"] for r in items])
        for members, body, cfg in plans:
            self.assertEqual(cfg, trial.config_for_size(len(members)))
            self.assertEqual(body["max_tokens"], trial.OUTPUT_LIMIT)
            self.assertEqual(body["provider"]["allow_fallbacks"], False)
            sent = json.loads(body["messages"][0]["content"][len(trial.base.INSTRUCTION):])
            self.assertEqual([(r["review_id"], r["review_text"], r["source_sha"])
                for r in sent], [(r["review_id"], r["review_text"], r["source_sha256"])
                for r in members])
        self.assertNotEqual(plans[-1][2], trial.config_sha())

    def test_single_oversized_text_is_explicitly_blocked_without_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                items = rows(1, 5000)
                seed(budget.db, items)
                bound = trial.OUTPUT_LIMIT + 100
                with patch.dict(scale.benchmark.ENDPOINT_BOUNDS, {"deepinfra": (bound, 0)}), \
                     patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=AssertionError("network call")):
                    result = scale.run_stage(budget, "synthetic-manifest",
                        "evidence", "synthetic-key", trial=True)
                self.assertEqual(result["oversized_evidence_rows"], 1)
                self.assertEqual(result["eligible_unique"], 0)
                self.assertEqual(budget.db.execute(
                    "SELECT blocked_reason FROM scale_rows").fetchone()[0],
                    "evidence_context_limit")
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM reservations").fetchone()[0], 0)
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM scale_requests").fetchone()[0], 0)

    def test_ten_review_mode_keeps_versioned_tail_and_full_reservation(self):
        items = rows(11)
        chunks, oversized = scale.plan_evidence_chunks(items)
        self.assertFalse(oversized)
        plans = [plan for chunk in chunks for plan in chunk]
        self.assertEqual([len(members) for members, _, _ in plans], [10, 1])
        self.assertEqual([r["review_id"] for members, _, _ in plans for r in members],
            [r["review_id"] for r in items])
        self.assertEqual(plans[0][2], previous.evidence_config(items[:10]))
        self.assertEqual(plans[1][2], previous.evidence_config(items[10:]))
        self.assertNotEqual(plans[0][2], plans[1][2])
        self.assertTrue(all(body["max_tokens"] == scale.evidence.OUTPUT_LIMIT
            for _, body, _ in plans))

    def test_long_row_does_not_strand_other_members_or_repeat_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                items = rows(27)
                items[0]["review_text"] = "Z" * 140000
                items[-1]["review_text"] = items[0]["review_text"]
                items[-1]["text_sha256"] = items[0]["text_sha256"]
                seed(budget.db, items)
                with patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", return_value=(None, 0.01, "TimeoutError:")):
                    result = scale.run_stage(budget, "synthetic-manifest",
                        "evidence", "synthetic-key", trial=True)
                self.assertEqual(result["oversized_evidence_rows"], 1)
                self.assertEqual(dict(budget.db.execute(
                    "SELECT review_id,blocked_reason FROM scale_rows WHERE blocked_reason IS NOT NULL")),
                    {"id0": "evidence_context_limit", "id26": "evidence_context_limit"})
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM scale_members").fetchone()[0], 25)
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM reservations WHERE status='uncertain'").fetchone()[0], 1)
                self.assertEqual(budget.db.execute(
                    "SELECT reserved_nusd FROM reservations").fetchone()[0],
                    trial.reservation_nusd())
                self.assertEqual(scale.pending(budget.db, "evidence"), [])
                scale.assert_resume_safe(budget.db)

    def test_delayed_successes_settle_during_cooldown_before_next_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                items = rows(9)
                seed(budget.db, items, labels=False)
                gate, lock = Barrier(2), Lock()
                events = {}

                def delayed_call(stage, body, key):
                    rid = body["state"]
                    with lock:
                        events.setdefault(rid, {})["start"] = time.monotonic()
                    if rid in (items[0]["review_text"], items[1]["review_text"]):
                        gate.wait(timeout=5)
                    if rid == items[0]["review_text"]:
                        with lock:
                            events[rid]["finish"] = time.monotonic()
                        return None, 0.001, "JevHTTPError:529"
                    if rid != items[-1]["review_text"]:
                        time.sleep(0.015)
                    with lock:
                        events[rid]["finish"] = time.monotonic()
                    return fixture_response(), 0.015, None

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale, "_call", side_effect=delayed_call), \
                     patch.object(scale, "CHUNK_ROWS", 1), \
                     patch.object(scale, "backoff_seconds", return_value=0.08):
                    result = scale.run_stage(budget, "synthetic-manifest",
                        "jev", "synthetic-key")
                first, last = items[0]["review_text"], items[-1]["review_text"]
                self.assertEqual(result["new_uncertain"], 1)
                self.assertEqual(result["final_worker_limit"], 4)
                self.assertGreaterEqual(events[last]["start"] - events[first]["finish"], 0.07)
                self.assertTrue(any(events[r["review_text"]]["finish"] <
                    events[last]["start"] for r in items[1:8]))
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM reservations WHERE status='uncertain'").fetchone()[0], 1)
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM reservations WHERE status='succeeded'").fetchone()[0], 8)
                self.assertEqual(budget.db.execute(
                    "SELECT COUNT(*) FROM scale_labels").fetchone()[0], 8)
                scale.assert_resume_safe(budget.db)


if __name__ == "__main__":
    unittest.main()

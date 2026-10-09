import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from spotify_pipeline.checkpoint5000_queue import CheckpointQueue
from spotify_pipeline.deepinfra_batch import reservation_nusd
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256, text_sha256
from spotify_pipeline.project_budget import ProjectBudget
from tests.test_project_budget import fixtures


def rows5000():
    rows = []
    for i in range(5000):
        row = {"review_id": "synthetic-" + str(i),
            "review_text": "premium problem number " + str(i // 2),
            "review_rating": "2", "review_likes": "0", "app_version": "",
            "review_timestamp": "2023-01-01 00:00:00"}
        row["source_sha256"] = row_sha256([row[k] for k in SOURCE_FIELDS])
        row["text_sha256"] = text_sha256(row["review_text"])
        row["source_position"] = i + 1
        rows.append(row)
    return rows


class CheckpointQueueTest(unittest.TestCase):
    def test_queue_resume_cache_and_atomic_result_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            seed_label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {rows[0]["review_text"]: (seed_label, "external-direct")}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "full-hash", "prefix-hash", seed)
                self.assertEqual(queue.summary()["labels"], 2)
                next_row = queue.next_jev()
                self.assertEqual(next_row["review_id"], rows[2]["review_id"])
                key = queue.reserve("jev", [next_row], queue.label_config_sha, 2_688_000)
                self.assertEqual(queue.next_jev()["review_id"], rows[4]["review_id"])
                queue.save_label(key, next_row, seed_label, 40_000, 952, 100, 0.2)
                self.assertEqual(queue.summary()["labels"], 4)
                self.assertEqual(budget.exposure("jev"), 23_731_254)
                first = queue.next_evidence(25, first_100=True)
                self.assertEqual(len(first), 2)
                ekey = queue.reserve("evidence", first, "evidence-config", 24_903_544, 25)
                evidence = {r["review_id"]: {"entities": ["premium"],
                    "evidence_quote": "premium problem"} for r in first}
                queue.save_evidence(ekey, first, evidence, "evidence-config", 100_000,
                    300, 200, 50, "synthetic-gen", 1.2,
                    response={"id": "synthetic-gen", "usage": {"prompt_tokens": 300}})
                self.assertEqual(queue.summary()["evidence"], 4)
                self.assertEqual(queue.summary()["complete"], 4)
                self.assertIn("synthetic-gen", budget.db.execute(
                    "SELECT response_json FROM checkpoint_requests WHERE request_key=?",
                    (ekey,)).fetchone()[0])
            with ProjectBudget(path, paths) as reopened:
                queue = CheckpointQueue(reopened, rows, "full-hash", "prefix-hash", seed)
                self.assertEqual(queue.summary()["complete"], 4)
                self.assertEqual(queue.next_jev()["review_id"], rows[4]["review_id"])
                with self.assertRaisesRegex(ValueError, "already reserved"):
                    queue.reserve("evidence", first, "evidence-config", 24_903_544, 25)

    def test_uncertain_attempt_blocks_duplicate_text_on_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "full-hash", "prefix-hash")
                first = queue.next_jev()
                key = queue.reserve("jev", [first], queue.label_config_sha, 2_688_000)
                queue.fail(key, error_class="ConnectionResetError")
                self.assertEqual(queue.next_jev()["review_id"], rows[2]["review_id"])
                self.assertEqual(queue.summary()["requests"]["uncertain"], 1)
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "full-hash", "prefix-hash")
                self.assertEqual(queue.next_jev()["review_id"], rows[2]["review_id"])
                with self.assertRaisesRegex(ValueError, "unresolved delivery"):
                    queue.assert_resume_safe("jev")

    def test_explicit_evidence_deferral_retains_hold_and_excludes_attempted_texts(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:100])}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "full-hash", "prefix-hash", seed)
                first = queue.next_evidence(25, first_100=True)
                before = budget.exposure("openrouter")
                key = queue.reserve("evidence", first, "evidence-config",
                                    reservation_nusd(), 25)
                queue.fail(key, error_class="synthetic unknown delivery")
                self.assertEqual(budget.exposure("openrouter"), before + reservation_nusd())
                with self.assertRaisesRegex(ValueError, "unresolved delivery"):
                    queue.assert_resume_safe("evidence")
                queue.assert_resume_safe("evidence", defer_uncertain_evidence=True)
                next_rows = queue.next_evidence(25, first_100=True)
                self.assertTrue(next_rows)
                self.assertFalse({r["review_text"] for r in first} &
                                 {r["review_text"] for r in next_rows})
                self.assertFalse({r["review_id"] for r in first} &
                                 {r["review_id"] for r in next_rows})
                with self.assertRaisesRegex(ValueError, "cap would be reached"):
                    budget.reserve("synthetic-over-cap", "openrouter",
                                   5_000_000_000 - budget.exposure("openrouter"))
                self.assertEqual(budget.exposure("openrouter"), before + reservation_nusd())
                next_key = queue.reserve("evidence", next_rows, "evidence-config",
                    reservation_nusd(), 25)
                with self.assertRaisesRegex(ValueError, "active reservation"):
                    queue.assert_resume_safe("evidence", defer_uncertain_evidence=True)
                queue.fail(next_key, error_class="synthetic unknown delivery")
                queue.assert_resume_safe("evidence", defer_uncertain_evidence=True)


if __name__ == "__main__":
    unittest.main()

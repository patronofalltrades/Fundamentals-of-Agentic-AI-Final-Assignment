"""Synthetic identity and duplicate-prevention checks; no paid calls."""

import sqlite3
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import label_config
from spotify_pipeline.project_budget import ProjectBudget
from tools import scale100k_queue as scale
from tests.test_project_budget import fixtures


class ScaleQueueTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE scale_rows(position INTEGER,review_id TEXT,review_text TEXT,source_sha TEXT,text_sha TEXT,blocked_reason TEXT)")
        self.db.execute("CREATE TABLE scale_labels(review_id TEXT,label_json TEXT,config_sha TEXT,provenance TEXT,origin_id TEXT,request_key TEXT)")
        self.db.execute("CREATE TABLE scale_evidence(review_id TEXT,entities_json TEXT,evidence_quote TEXT,config_sha TEXT,provenance TEXT,origin_id TEXT,request_key TEXT)")
        self.db.execute("CREATE TABLE scale_requests(request_key TEXT,stage TEXT,status TEXT)")
        self.db.execute("CREATE TABLE scale_members(request_key TEXT,review_id TEXT)")
        self.db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,?)", [
            (10001, "a", "same text", "sha-a", "text-sha-a", None),
            (10002, "b", "same text", "sha-b", "text-sha-a", None),
            (10003, "c", "held text", "sha-c", "text-sha-c", "prior_uncertain_exact_text"),
            (10004, "d", "new text", "sha-d", "text-sha-d", None)])

    def tearDown(self):
        self.db.close()

    def test_exact_text_alias_keeps_distinct_source_ids_and_blocks_duplicate_post(self):
        rows = scale.pending(self.db, "jev")
        self.assertEqual([r["review_id"] for r in rows], ["a", "d"])
        self.assertEqual(rows[0]["text_sha256"], "text-sha-a")
        scale.aliases(self.db, "jev", rows[0], '{"topic":"other"}', config_hash(label_config()))
        self.assertEqual(dict(self.db.execute("SELECT review_id,origin_id FROM scale_labels")),
                         {"a": "a", "b": "a"})
        self.assertEqual([r["review_id"] for r in scale.pending(self.db, "jev")], ["d"])
        self.db.execute("INSERT INTO scale_requests VALUES ('held','jev','uncertain')")
        self.db.execute("INSERT INTO scale_members VALUES ('held','d')")
        self.assertEqual(scale.pending(self.db, "jev"), [])

    def test_evidence_requires_label_and_never_retries_attempted_exact_text(self):
        for rid in ("a", "b", "d"):
            self.db.execute("INSERT INTO scale_labels VALUES (?,?,?,?,?,?)",
                (rid, '{"topic":"other","intent":"praise","severity":1,"sentiment":0.5}',
                 "cfg", "synthetic", None, None))
        self.db.execute("INSERT INTO scale_requests VALUES ('held','evidence','uncertain')")
        self.db.execute("INSERT INTO scale_members VALUES ('held','a')")
        self.assertEqual([r["review_id"] for r in scale.pending(self.db, "evidence")], ["d"])

    def test_eight_network_slots_share_one_ledger_and_never_repeat_held_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                db = budget.db
                scale.ensure_tables(db, "synthetic-manifest")
                db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,NULL)",
                    ((10001 + i, "id" + str(i), "text" + str(i),
                      "source" + str(i), "textsha" + str(i)) for i in range(4000)))
                db.commit()
                gate = Barrier(scale.WORKERS)

                def timeout_call(stage, body, key):
                    gate.wait(timeout=5)
                    return None, 0.01, "TimeoutError:"

                with patch.object(scale, "verify_jev_price"), \
                     patch.object(scale.jev, "check_model_access"), \
                     patch.object(scale, "_call", side_effect=timeout_call), \
                     patch.object(scale.time, "sleep"):
                    result = scale.run_stage(budget, "synthetic-manifest", "jev", "synthetic-key")
                self.assertTrue(result["paused"])
                self.assertEqual(result["new_uncertain"], scale.WORKERS)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations WHERE status='uncertain'").fetchone()[0], scale.WORKERS)
                self.assertEqual(db.execute("SELECT COUNT(DISTINCT review_id) FROM scale_members").fetchone()[0], scale.WORKERS)
                self.assertEqual(len(scale.pending(db, "jev")), 4000 - scale.WORKERS)
                scale.assert_resume_safe(db)

    def test_eight_evidence_slots_keep_ten_reviews_per_post(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                db = budget.db
                scale.ensure_tables(db, "synthetic-manifest")
                db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,NULL)",
                    ((10001 + i, "id" + str(i), "text" + str(i),
                      "source" + str(i), "textsha" + str(i)) for i in range(4000)))
                label = '{"topic":"other","intent":"praise","severity":1,"sentiment":0.5}'
                db.executemany("INSERT INTO scale_labels VALUES (?,?,?,?,NULL,NULL)",
                    (("id" + str(i), label, config_hash(label_config()), "synthetic")
                     for i in range(4000)))
                db.commit()
                gate = Barrier(scale.WORKERS)

                def timeout_call(stage, body, key):
                    gate.wait(timeout=5)
                    return None, 0.01, "TimeoutError:"

                with patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=timeout_call), \
                     patch.object(scale.time, "sleep"):
                    result = scale.run_stage(budget, "synthetic-manifest", "evidence", "synthetic-key")
                self.assertEqual(result["new_uncertain"], scale.WORKERS)
                sizes = [count for count, in db.execute(
                    "SELECT COUNT(*) FROM scale_members GROUP BY request_key")]
                self.assertEqual(sizes, [10] * scale.WORKERS)
                self.assertEqual(db.execute("SELECT COUNT(DISTINCT review_id) FROM scale_members").fetchone()[0], 10 * scale.WORKERS)
                self.assertEqual(len(scale.pending(db, "evidence")), 4000 - 10 * scale.WORKERS)

    def test_gate_preserves_empty_and_historical_held_source_ids(self):
        db = sqlite3.connect(":memory:")
        try:
            scale.ensure_tables(db, "synthetic-manifest")
            db.execute("CREATE TABLE reservations(request_key TEXT,status TEXT)")
            db.execute("CREATE TABLE checkpoint_rows(review_id TEXT,review_text TEXT)")
            db.execute("CREATE TABLE checkpoint_request_members(request_key TEXT,review_id TEXT)")
            db.execute("CREATE TABLE checkpoint_requests(request_key TEXT,stage TEXT,status TEXT)")
            db.execute("CREATE TABLE next5000_rows(review_id TEXT,review_text TEXT)")
            db.execute("CREATE TABLE next5000_members(request_key TEXT,review_id TEXT)")
            db.execute("CREATE TABLE next5000_requests(request_key TEXT,stage TEXT,status TEXT)")
            rows = [{"source_position": 10001 + i, "review_id": "id" + str(i),
                "review_text": "" if i == 4 else "text" + str(i),
                "source_sha256": "source" + str(i), "text_sha256": "textsha" + str(i)}
                for i in range(scale.GATE_ROWS)]
            manifest = {"rows": rows,
                "historical_uncertain_exact_texts": ["text5"]}
            self.assertEqual(scale.activate_gate(db, manifest), scale.GATE_ROWS)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scale_rows").fetchone()[0], scale.GATE_ROWS)
            self.assertEqual(dict(db.execute("SELECT review_id,blocked_reason FROM scale_rows WHERE blocked_reason IS NOT NULL")),
                {"id4": "empty_text", "id5": "prior_uncertain_exact_text"})
            self.assertRaises(ValueError, scale.activate_gate, db, manifest)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

"""Synthetic identity and duplicate-prevention checks; no paid calls."""

import sqlite3
import json
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import label_config
from spotify_pipeline.jev import JevHTTPError
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

    def test_jev_rate_status_is_visible_to_adaptive_backoff(self):
        with patch.object(scale.jev, "post_systemone", side_effect=JevHTTPError(429)):
            response, elapsed, error = scale._call("jev", {"synthetic": True}, "synthetic-key")
        self.assertIsNone(response)
        self.assertGreaterEqual(elapsed, 0)
        self.assertEqual(error, "JevHTTPError:429")
        with patch.object(scale.jev, "post_systemone", side_effect=JevHTTPError(529)):
            self.assertEqual(scale._call("jev", {}, "synthetic-key")[2], "JevHTTPError:529")

    def test_prior_provider_overload_starts_with_four_of_eight_slots(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE scale_requests(stage TEXT,status TEXT,error_class TEXT)")
            self.assertEqual(scale.initial_worker_limit(db, "jev"), 8)
            db.execute("INSERT INTO scale_requests VALUES ('jev','uncertain','JevHTTPError:529')")
            self.assertEqual(scale.initial_worker_limit(db, "jev"), 4)
            self.assertEqual(scale.initial_worker_limit(db, "evidence"), 8)
            self.assertEqual(scale.safe_worker_ceiling(db, "jev"), 8)
            db.execute("INSERT INTO scale_requests VALUES ('jev','uncertain','JevHTTPError:529')")
            self.assertEqual(scale.safe_worker_ceiling(db, "jev"), 4)
            self.assertEqual(scale.safe_worker_ceiling(db, "evidence"), 8)
        finally:
            db.close()

    def test_25_review_trial_uses_four_new_batches_and_full_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            with ProjectBudget(str(Path(folder) / "project.db"), paths) as budget:
                db = budget.db
                scale.ensure_tables(db, "synthetic-manifest")
                db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,NULL)",
                    ((10001 + i, "id" + str(i), "text" + str(i),
                      "source" + str(i), "textsha" + str(i)) for i in range(100)))
                label = '{"topic":"other","intent":"praise","severity":1,"sentiment":0.5}'
                db.executemany("INSERT INTO scale_labels VALUES (?,?,?,?,NULL,NULL)",
                    (("id" + str(i), label, config_hash(label_config()), "synthetic")
                     for i in range(100)))
                db.commit()
                gate = Barrier(4)

                def timeout_call(stage, body, key):
                    gate.wait(timeout=5)
                    return None, 0.01, "TimeoutError:"

                with patch.object(scale.benchmark, "verify_route"), \
                     patch.object(scale.canary, "verify_project_key"), \
                     patch.object(scale, "_call", side_effect=timeout_call), \
                     patch.object(scale.time, "sleep"):
                    result = scale.run_stage(budget, "synthetic-manifest", "evidence",
                        "synthetic-key", trial=True, bounded_trial=True)
                self.assertEqual(result["batch_size"], 25)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM scale_requests").fetchone()[0], 4)
                self.assertEqual([size for size, in db.execute(
                    "SELECT COUNT(*) FROM scale_members GROUP BY request_key")], [25] * 4)
                self.assertEqual(db.execute("SELECT SUM(reserved_nusd) FROM reservations").fetchone()[0],
                    4 * scale.trial25.reservation_nusd())
                scale.assert_resume_safe(db)

    def test_offline_recovery_accepts_only_unique_expected_exact_spans(self):
        db = sqlite3.connect(":memory:")
        try:
            scale.ensure_tables(db, "synthetic-manifest")
            db.execute("CREATE TABLE reservations(request_key TEXT,status TEXT,charged_nusd INTEGER)")
            rows = [(10001 + i, "id" + str(i), "text" + str(i), "sha" + str(i),
                "textsha" + str(i), None) for i in range(25)]
            rows.append((10026, "alias0", "text0", "alias-sha", "textsha0", None))
            db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,?)", rows)
            items = [{"review_id": "id" + str(i), "entities": [],
                "evidence_quote": "text" + str(i)} for i in range(24)]
            items.append({"review_id": "unknown", "entities": [], "evidence_quote": "text24"})
            response = {"id": "synthetic-generation", "provider": "DeepInfra",
                "model": scale.evidence.MODEL, "usage": {"prompt_tokens": 100,
                "completion_tokens": 100}, "choices": [{"finish_reason": "stop",
                "message": {"content": json.dumps({"results": items})}}]}
            charge = scale.trial25.measured_usage(response)[-1]
            db.execute("""INSERT INTO scale_requests(request_key,stage,status,config_sha,
                request_sha,response_json,charged_nusd) VALUES (?,?,?,?,?,?,?)""",
                ("batch", "evidence", "quarantined_metered",
                 scale.trial25.config_sha(), "synthetic", json.dumps(response), charge))
            db.execute("INSERT INTO reservations VALUES (?,?,?)",
                ("batch", "quarantined_metered", charge))
            db.executemany("INSERT INTO scale_members VALUES (?,?)",
                (("batch", "id" + str(i)) for i in range(25)))
            db.executemany("INSERT INTO scale_quarantines VALUES (?,?,?)",
                (("id" + str(i), "structural", "batch") for i in range(25)))
            db.commit()
            result = scale.recover_metered(db)
            self.assertEqual(result, {"batches": 1, "new_accepted": 24,
                "remaining_quarantined": 1})
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scale_evidence").fetchone()[0], 25)
            self.assertEqual(db.execute("SELECT review_id FROM scale_quarantines").fetchone()[0], "id24")
            self.assertEqual(scale.recover_metered(db)["new_accepted"], 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

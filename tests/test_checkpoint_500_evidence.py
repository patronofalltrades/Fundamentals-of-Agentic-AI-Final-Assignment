"""Synthetic exact-text evidence reuse; no model or user data."""

import json
import sqlite3
import unittest
from unittest.mock import patch

from tools.checkpoint_500_evidence import (
    copy_exact_evidence, reconcile_interruption, reconcile_local_preflight,
    retry_interrupted)


class FakeLedger:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE results(review_id TEXT PRIMARY KEY,review_text TEXT,
              label_json TEXT,cache_source_id TEXT);
            CREATE TABLE evidence(review_id TEXT PRIMARY KEY,entities_json TEXT,
              evidence_quote TEXT,model TEXT,prompt_version TEXT,
              elapsed_seconds REAL,cache_source_id TEXT);
            CREATE TABLE evidence_origin(review_id TEXT PRIMARY KEY,origin TEXT,
              prior_model TEXT,prior_prompt_version TEXT,prior_elapsed_seconds REAL);
        """)

    def get_evidence(self, review_id):
        return self.conn.execute("SELECT * FROM evidence WHERE review_id=?", (review_id,)).fetchone()


class CheckpointEvidenceTests(unittest.TestCase):
    def test_retry_links_unknown_delivery_without_erasing_it(self):
        ledger = FakeLedger()
        try:
            ledger.conn.executescript("""
                CREATE TABLE evidence_attempts(id INTEGER PRIMARY KEY,review_id TEXT,
                  status TEXT,elapsed_seconds REAL,error_class TEXT);
                CREATE TABLE checkpoint_evidence_runs(id INTEGER PRIMARY KEY,
                  status TEXT,new_calls INTEGER,cache_reuses INTEGER,
                  elapsed_seconds REAL,error_class TEXT);
                INSERT INTO results VALUES
                  ('synthetic-review','Synthetic playback failure','{}',NULL);
                INSERT INTO evidence_attempts VALUES
                  (2,'synthetic-review','interrupted_uncertain',NULL,'ProcessLost');
            """)
            def save(_ledger, item):
                _ledger.conn.execute("INSERT INTO evidence_attempts VALUES (?,?,?,?,?)", (
                    3, item["review_id"], "succeeded", 0.2, None))
                _ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
                    item["review_id"], '["playback"]', "playback failure",
                    "synthetic-model", "synthetic-v1", 0.2, None))
                _ledger.conn.commit()
            with patch("tools.checkpoint_500_evidence._execute_one", side_effect=save):
                result = retry_interrupted(ledger)
            self.assertEqual(result["new_successful_calls"], 1)
            self.assertEqual(ledger.conn.execute("SELECT status FROM evidence_attempts "
                                                 "WHERE id=2").fetchone()[0], "interrupted_uncertain")
            self.assertEqual(tuple(ledger.conn.execute(
                "SELECT prior_attempt_id,retry_attempt_id FROM checkpoint_evidence_retries").fetchone()),
                (2, 3))
        finally:
            ledger.conn.close()

    def test_interrupted_attempt_keeps_unknown_delivery(self):
        ledger = FakeLedger()
        try:
            ledger.conn.executescript("""
                CREATE TABLE evidence_attempts(id INTEGER PRIMARY KEY,review_id TEXT,
                  status TEXT,elapsed_seconds REAL,error_class TEXT);
                CREATE TABLE checkpoint_evidence_runs(id INTEGER PRIMARY KEY,
                  status TEXT,new_calls INTEGER,cache_reuses INTEGER,
                  elapsed_seconds REAL,error_class TEXT);
                INSERT INTO evidence_attempts VALUES
                  (2,'synthetic-review','started',NULL,NULL);
                INSERT INTO checkpoint_evidence_runs VALUES
                  (1,'started',0,0,NULL,NULL);
            """)
            self.assertEqual(reconcile_interruption(ledger)["unknown_delivery_attempts"], 1)
            self.assertEqual(ledger.conn.execute(
                "SELECT status FROM evidence_attempts").fetchone()[0], "interrupted_uncertain")
            self.assertIsNone(ledger.conn.execute(
                "SELECT new_calls FROM checkpoint_evidence_runs").fetchone()[0])
            with self.assertRaises(ValueError):
                reconcile_interruption(ledger)
        finally:
            ledger.conn.close()

    def test_reconcile_only_documented_local_startup_failure(self):
        ledger = FakeLedger()
        try:
            ledger.conn.executescript("""
                CREATE TABLE evidence_attempts(id INTEGER PRIMARY KEY,review_id TEXT,
                  status TEXT,elapsed_seconds REAL,error_class TEXT);
                CREATE TABLE checkpoint_evidence_runs(status TEXT,new_calls INTEGER,
                  cache_reuses INTEGER,elapsed_seconds REAL);
                INSERT INTO evidence_attempts VALUES
                  (1,'synthetic-review','failed',0.08,'ValidationError');
                INSERT INTO checkpoint_evidence_runs VALUES ('failed',0,0,0.09);
            """)
            result = reconcile_local_preflight(ledger)
            self.assertEqual(result["blocked_attempts"], 1)
            self.assertEqual(ledger.conn.execute(
                "SELECT status FROM evidence_attempts").fetchone()[0], "preflight_blocked")
            with self.assertRaises(ValueError):
                reconcile_local_preflight(ledger)
        finally:
            ledger.conn.close()

    def test_compatible_cache_copies_direct_provenance_without_call(self):
        ledger = FakeLedger()
        try:
            label = json.dumps({"topic": "playback", "intent": "complaint",
                                "severity": 3, "sentiment": -0.5})
            for rid, origin in (("synthetic-original", None),
                                ("synthetic-duplicate", "synthetic-original")):
                ledger.conn.execute("INSERT INTO results VALUES (?,?,?,?)", (
                    rid, "Synthetic playback failure", label, origin))
            ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
                "synthetic-original", '["playback"]', "playback failure",
                "synthetic-model", "synthetic-prompt", 1.2, None))
            ledger.conn.commit()
            item = ledger.conn.execute("SELECT * FROM results WHERE review_id='synthetic-duplicate'").fetchone()
            copy_exact_evidence(ledger, item)
            saved = ledger.get_evidence("synthetic-duplicate")
            self.assertEqual(saved["evidence_quote"], "playback failure")
            self.assertEqual(saved["cache_source_id"], "synthetic-original")
            self.assertEqual(saved["elapsed_seconds"], 0)
            self.assertEqual(ledger.conn.execute(
                "SELECT origin FROM evidence_origin WHERE review_id='synthetic-duplicate'").fetchone()[0],
                "checkpoint_exact_text_cache")
        finally:
            ledger.conn.close()

    def test_changed_label_blocks_cache_reuse(self):
        ledger = FakeLedger()
        try:
            a = json.dumps({"topic": "playback", "intent": "complaint",
                            "severity": 3, "sentiment": -0.5})
            b = json.dumps({"topic": "catalog", "intent": "complaint",
                            "severity": 3, "sentiment": -0.5})
            ledger.conn.execute("INSERT INTO results VALUES (?,?,?,?)", (
                "synthetic-original", "Synthetic playback failure", a, None))
            ledger.conn.execute("INSERT INTO results VALUES (?,?,?,?)", (
                "synthetic-duplicate", "Synthetic playback failure", b, "synthetic-original"))
            ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
                "synthetic-original", '["playback"]', "playback failure",
                "synthetic-model", "synthetic-prompt", 1.2, None))
            item = ledger.conn.execute("SELECT * FROM results WHERE review_id='synthetic-duplicate'").fetchone()
            with self.assertRaisesRegex(ValueError, "identity differs"):
                copy_exact_evidence(ledger, item)
            self.assertIsNone(ledger.get_evidence("synthetic-duplicate"))
        finally:
            ledger.conn.close()


if __name__ == "__main__":
    unittest.main()

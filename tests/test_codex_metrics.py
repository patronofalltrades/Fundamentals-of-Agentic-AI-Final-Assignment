"""Synthetic event and resume metrics; no provider calls or real reviews."""

import json
import pathlib
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from spotify_pipeline.codex_evidence import extract_with_codex, parse_codex_usage_events
from spotify_pipeline.errors import ValidationError
from tools.finish_jev_v2_evidence import ensure_metrics_schema, execute, status


class FakeLedger:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE evidence_attempts (id INTEGER PRIMARY KEY,review_id TEXT,
              status TEXT,elapsed_seconds REAL,error_class TEXT);
            CREATE TABLE evidence (review_id TEXT,entities_json TEXT,evidence_quote TEXT,
              model TEXT,prompt_version TEXT,elapsed_seconds REAL,cache_source_id TEXT);
            CREATE TABLE evidence_origin (review_id TEXT,origin TEXT,prior_model TEXT,
              prior_prompt_version TEXT,prior_elapsed_seconds REAL);
        """)
        self.items = [{"review_id": "synthetic-1", "review_text": "Synthetic playback fails",
                       "label_json": json.dumps({"topic": "playback", "intent": "complaint",
                                                 "severity": 4, "sentiment": -0.8})}]

    def summary(self):
        return {"results": {"synthetic": 1}}

    def missing_evidence(self):
        saved = {row[0] for row in self.conn.execute("SELECT review_id FROM evidence")}
        return (item for item in self.items if item["review_id"] not in saved)


class CodexMetricsTests(unittest.TestCase):
    def test_extractor_requests_json_and_discards_event_text(self):
        def fake_run(command, **kwargs):
            self.assertIn("--json", command)
            self.assertEqual(kwargs["input"].count("Synthetic playback fails"), 1)
            pathlib.Path(command[command.index("-o") + 1]).write_text(json.dumps(
                {"entities": ["playback"], "evidence_quote": "playback fails"}))
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "type": "turn.completed", "usage": {"input_tokens": 25,
                "cached_input_tokens": 0, "output_tokens": 8},
                "review_text": "private event content"}), stderr="")
        labels = {"topic": "playback", "intent": "complaint", "severity": 4,
                  "sentiment": -0.8}
        with patch("spotify_pipeline.codex_evidence.subprocess.run", side_effect=fake_run):
            result = extract_with_codex("Synthetic playback fails", labels)
        self.assertEqual(result["usage"], {"input_tokens": 25,
                                           "cached_input_tokens": 0, "output_tokens": 8})
        self.assertNotIn("private event content", str(result))

    def test_usage_jsonl_is_numeric_only_and_missing_stays_unknown(self):
        stream = '\n'.join((json.dumps({"type": "item.completed", "review_text": "private"}),
                            json.dumps({"type": "turn.completed", "usage": {
                                "input_tokens": 25, "cached_input_tokens": 5,
                                "output_tokens": 8, "other": "private"}})))
        self.assertEqual(parse_codex_usage_events(stream),
                         {"input_tokens": 25, "cached_input_tokens": 5, "output_tokens": 8})
        self.assertIsNone(parse_codex_usage_events('{"type":"turn.completed"}'))
        for bad in ('not json', '{"type":"turn.completed","usage":{"input_tokens":true}}',
                    '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":2,"output_tokens":3}}'):
            with self.assertRaises(ValidationError):
                parse_codex_usage_events(bad)

    def test_resume_migration_preserves_unknown_and_records_stage_wall(self):
        ledger = FakeLedger()
        try:
            ledger.conn.execute("INSERT INTO evidence_attempts(review_id,status,elapsed_seconds) "
                                "VALUES ('historical','succeeded',1.5)")
            ensure_metrics_schema(ledger.conn)
            self.assertIsNone(ledger.conn.execute(
                "SELECT input_tokens FROM evidence_attempts WHERE review_id='historical'").fetchone()[0])
            result = {"evidence": {"entities": ["playback"], "evidence_quote": "playback fails"},
                      "model": "synthetic", "prompt_version": "synthetic-v1",
                      "elapsed_seconds": 0.2, "usage": {"input_tokens": 20,
                      "cached_input_tokens": 3, "output_tokens": 7}}
            with patch("tools.finish_jev_v2_evidence.extract_with_codex", return_value=result):
                report = execute(ledger, 1)
            self.assertEqual(report["new_calls_this_invocation"], 1)
            self.assertEqual(report["codex_usage_reported_attempts"], 1)
            self.assertEqual(report["codex_usage_unknown_attempts"], 1)
            self.assertEqual(report["codex_reported_token_subtotals"]["input_tokens"], 20)
            self.assertEqual(report["evidence_stage_runs"][0]["status"], "succeeded")
            self.assertGreaterEqual(report["evidence_stage_runs"][0]["elapsed_seconds"], 0)
            self.assertEqual(status(ledger)["missing_evidence"], 0)
        finally:
            ledger.conn.close()

    def test_failure_records_attempt_and_stage_without_fake_usage(self):
        ledger = FakeLedger()
        try:
            with patch("tools.finish_jev_v2_evidence.extract_with_codex",
                       side_effect=ValidationError("synthetic")):
                with self.assertRaises(ValidationError):
                    execute(ledger, 1)
            self.assertEqual(status(ledger)["evidence_attempts"], {"failed": 1})
            self.assertEqual(status(ledger)["evidence_stage_runs"][0]["status"], "failed")
            with self.assertRaisesRegex(ValueError, "manual review"):
                execute(ledger, 1)
        finally:
            ledger.conn.close()


if __name__ == "__main__":
    unittest.main()

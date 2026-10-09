import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools import build_corrected_benchmark_baseline as builder
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256


class CorrectedBenchmarkBaselineTest(unittest.TestCase):
    def test_one_reviewed_topic_is_applied_without_changing_original(self):
        row = {"review_id": "synthetic", "review_text": "Synthetic music request",
               "review_rating": "1", "review_likes": "0", "app_version": "",
               "review_timestamp": "2022-01-01"}
        source_hash = row_sha256([row[k] for k in SOURCE_FIELDS])
        labels = {"topic": "other", "intent": "complaint", "severity": 2,
                  "sentiment": -0.4, "model": "synthetic-jev"}
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "original.db"
            output = Path(folder) / "corrected.db"
            overlay_path = Path(folder) / "overlay.json"
            with sqlite3.connect(original) as db:
                db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)")
                db.execute("""CREATE TABLE results(review_id TEXT PRIMARY KEY,label_json TEXT,
                           source_sha256 TEXT,config_hash TEXT)""")
                db.execute("INSERT INTO results VALUES (?,?,?,?)",
                           ("synthetic", json.dumps(labels), source_hash, "synthetic-config"))
            document_hash = "a" * 64
            correction = {"review_id": "synthetic", "source_sha256": source_hash,
                          "original_model": {"topic": "other", "intent": "complaint", "severity": 2},
                          "human_correction": {"topic": "catalog"}, "changed_fields": ["topic"],
                          "source_document_sha256": document_hash,
                          "provenance": {"kind": "synthetic-human-review"}}
            extras = [dict(correction, review_id="outside-" + str(i)) for i in range(3)]
            overlay_path.write_text(json.dumps({
                "metadata": {"status": "development_only_unpromoted",
                             "input_sha256": document_hash},
                "corrections": [correction] + extras}), encoding="utf-8")
            overlay_sha = hashlib.sha256(overlay_path.read_bytes()).hexdigest()
            with mock.patch.object(builder.benchmark, "load_rows", return_value=[row]):
                result = builder.build("synthetic.csv", "synthetic-manifest", original,
                                       overlay_path, overlay_sha, output)
                with self.assertRaisesRegex(ValueError, "must be a new path"):
                    builder.build("synthetic.csv", "synthetic-manifest", original,
                                  overlay_path, overlay_sha, output)
            self.assertEqual(result["corrected_source_rows"], 1)
            with sqlite3.connect(original) as db:
                self.assertEqual(json.loads(db.execute("SELECT label_json FROM results").fetchone()[0]), labels)
            with sqlite3.connect(output) as db:
                changed, config = db.execute("SELECT label_json,config_hash FROM results").fetchone()
                self.assertEqual(json.loads(changed)["topic"], "catalog")
                self.assertNotEqual(config, "synthetic-config")
                self.assertEqual(db.execute("SELECT COUNT(*) FROM human_corrections").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

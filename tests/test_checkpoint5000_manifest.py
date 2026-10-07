"""Synthetic, offline checks for the private 5,000-row manifest."""

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline.jev import label_config
from tools.checkpoint5000_manifest import build, write_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "spotify_reviews_18months.csv"
        self.checkpoint = self.root / "checkpoint_500.csv"
        self.supplied = self.root / "manifest.json"
        self.db = self.root / "saved.db"
        self.overlay = self.root / "corrections.json"
        self.first = []
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS)
            writer.writeheader()
            for index in range(5000):
                row = self.row("first-%d" % index, "text-%d" % (index % 4999))
                writer.writerow(row)
                self.first.append(row)
        self.saved = [self.row("saved-%d" % i, "text-0" if i == 0 else "saved-text-%d" % i)
                      for i in range(500)]
        self.write_csv(self.checkpoint, self.saved)
        self.supplied.write_text(json.dumps({"files": {
            path.name: {"sha256": file_sha256(str(path)), "bytes": path.stat().st_size}
            for path in (self.source, self.checkpoint)}}), encoding="utf-8")
        self.make_db()
        correction = {"review_id": self.saved[0]["review_id"],
                      "source_sha256": self.source_hash(self.saved[0])}
        self.overlay.write_text(json.dumps({"metadata": {
            "source_checkpoint_sha256": file_sha256(str(self.checkpoint)),
            "status": "development_only_unpromoted"},
            "corrections": [correction] + [
                {"review_id": row["review_id"], "source_sha256": self.source_hash(row)}
                for row in self.saved[1:4]]}), encoding="utf-8")

    @staticmethod
    def row(review_id, text):
        return dict(zip(SOURCE_FIELDS, (review_id, text, "5", "0", "", "2026-01-01")))

    @staticmethod
    def source_hash(row):
        return row_sha256([row[field] for field in SOURCE_FIELDS])

    @staticmethod
    def write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def make_db(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE meta (key TEXT,value TEXT)")
            db.executemany("INSERT INTO meta VALUES (?,?)", [
                ("source_sha256", file_sha256(str(self.checkpoint))),
                ("config_hash", config_hash(label_config())),
                ("model", label_config()["model"])])
            db.execute("CREATE TABLE results (review_id TEXT,review_text TEXT,text_sha256 TEXT,"
                       "source_sha256 TEXT,config_hash TEXT)")
            db.execute("CREATE TABLE evidence (review_id TEXT,entities_json TEXT,"
                       "evidence_quote TEXT,model TEXT,prompt_version TEXT)")
            for row in self.saved:
                db.execute("INSERT INTO results VALUES (?,?,?,?,?)", (
                    row["review_id"], row["review_text"], text_sha256(row["review_text"]),
                    self.source_hash(row), config_hash(label_config())))
                db.execute("INSERT INTO evidence VALUES (?,?,?,?,?)", (
                    row["review_id"], "[]", row["review_text"], "gpt-6.1-sol",
                    "evidence-extract-v2"))

    def test_order_duplicate_cache_and_idempotence(self):
        manifest = build(str(self.source), str(self.supplied), str(self.db),
                         str(self.checkpoint), str(self.overlay))
        self.assertEqual(manifest["selected_rows"], 5000)
        self.assertEqual(manifest["counts"]["exact_text_duplicates"], 1)
        self.assertEqual(manifest["counts"]["saved500_label_matches"], 2)
        self.assertEqual(manifest["counts"]["saved500_evidence_candidates"], 2)
        self.assertEqual(manifest["counts"]["human_corrections_in_selection"], 0)
        self.assertEqual(manifest["rows"][0]["source_position"], 1)
        self.assertEqual(manifest["rows"][-1]["duplicate_of_review_id"], "first-0")
        self.assertEqual(manifest["rows"][0]["saved500_label_source_id"], "saved-0")
        out = self.root / "local" / "manifest.json"
        digest, created = write_manifest(out, manifest)
        self.assertTrue(created)
        self.assertEqual(write_manifest(out, manifest), (digest, False))
        with self.assertRaisesRegex(ValueError, "differs"):
            write_manifest(out, {**manifest, "selected_rows": 4999})

    def test_reject_changed_source_and_cache_configuration(self):
        self.source.write_text(self.source.read_text() + "changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "supplied manifest"):
            build(str(self.source), str(self.supplied))
        self.write_csv(self.source, self.first)
        # The exact bytes are the same as setUp's generated CSV.
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE meta SET value='old' WHERE key='config_hash'")
        with self.assertRaisesRegex(ValueError, "configuration differs"):
            build(str(self.source), str(self.supplied), str(self.db), str(self.checkpoint))


if __name__ == "__main__":
    unittest.main()

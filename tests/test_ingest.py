"""SYNTHETIC tests for the offline ingestion pipeline."""

import os
import tempfile
import unittest

from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import parsed_rows_sha256, row_sha256
from spotify_pipeline.db import Database
from spotify_pipeline.errors import ManifestError, PathCollisionError, StateError, ValidationError
from spotify_pipeline.ingest import extract_contract_profile, ingest

from tests.helpers import (
    SYNTHETIC_ROWS,
    completed_item,
    make_input,
    manifest_entry,
    write_csv,
    write_manifest,
)


def _expected_parsed_sha(rows):
    return parsed_rows_sha256([row_sha256(list(r)) for r in rows])


class IngestTests(unittest.TestCase):
    def _run(self, tmp, rows=None, name="sample.csv"):
        input_path = make_input(tmp, rows, name=name)
        manifest_path = os.path.join(tmp, "manifest.json")
        write_manifest(manifest_path, {name: manifest_entry(input_path)})
        db_path = os.path.join(tmp, "state.db")
        report_path = os.path.join(tmp, "report.json")
        report = ingest(input_path, manifest_path, db_path, report_path)
        return input_path, manifest_path, db_path, report_path, report

    def test_contract_profile_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report = self._run(tmp)
            core = extract_contract_profile(report)
            self.assertEqual(core["counts"]["records"], 5)
            self.assertEqual(core["counts"]["duplicate_review_ids"], 0)
            self.assertEqual(core["counts"]["empty_review_text"], 1)
            self.assertEqual(core["counts"]["missing_app_version"], 2)
            self.assertEqual(core["reviews_by_month"]["2022-05"], 1)
            self.assertEqual(core["reviews_by_rating"]["5"], 1)
            self.assertEqual(core["first_review"], "2022-05-17 00:01:07")
            self.assertEqual(core["last_review"], "2023-11-15 23:16:10")
            self.assertEqual(core["parsed_rows_sha256"], _expected_parsed_sha(SYNTHETIC_ROWS))

    def test_extended_report_has_text_identity_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report = self._run(tmp)
            extended = report["extended"]
            self.assertEqual(extended["nonempty_review_text"], 4)
            self.assertEqual(extended["distinct_nonempty_texts"], 4)
            self.assertEqual(extended["duplicate_text_excess"], 0)
            self.assertEqual(extended["status_counts"]["quarantined"], 1)
            self.assertEqual(extended["status_counts"]["pending"], 4)
            self.assertTrue(extended["manifest_validation"]["validated"])

    def test_duplicate_text_is_counted_but_not_quarantined(self):
        rows = [
            ["1", "same text", "5", "0", "", "2022-05-17 00:01:07"],
            ["2", "same text", "4", "0", "1.0.0", "2022-05-18 00:01:07"],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report = self._run(tmp, rows)
            self.assertEqual(report["extended"]["distinct_nonempty_texts"], 1)
            self.assertEqual(report["extended"]["duplicate_text_excess"], 1)

    def test_missing_version_does_not_quarantine(self):
        rows = [["1", "hello", "5", "0", "", "2022-05-17 00:01:07"]]
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report = self._run(tmp, rows)
            self.assertEqual(report["counts"]["missing_app_version"], 1)
            self.assertEqual(report["extended"]["status_counts"]["quarantined"], 0)
            self.assertEqual(report["extended"]["status_counts"]["pending"], 1)

    def test_whitespace_only_version_counted_missing(self):
        rows = [["1", "hello", "5", "0", "   ", "2022-05-17 00:01:07"]]
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report = self._run(tmp, rows)
            self.assertEqual(report["counts"]["missing_app_version"], 1)

    def test_bad_checksum_fails_without_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = make_input(tmp)
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": {"sha256": "0" * 64, "bytes": 1}})
            db_path = os.path.join(tmp, "state.db")
            report_path = os.path.join(tmp, "report.json")
            with self.assertRaises(ManifestError):
                ingest(input_path, manifest_path, db_path, report_path)
            self.assertFalse(os.path.exists(db_path))
            self.assertFalse(os.path.exists(report_path))

    def test_duplicate_id_fails_without_publishing(self):
        rows = [
            ["1", "a", "5", "0", "", "2022-05-17 00:01:07"],
            ["1", "b", "4", "0", "", "2022-05-18 00:01:07"],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            input_path = make_input(tmp, rows)
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            db_path = os.path.join(tmp, "state.db")
            with self.assertRaises(ValidationError):
                ingest(input_path, manifest_path, db_path, os.path.join(tmp, "report.json"))
            self.assertFalse(os.path.exists(db_path))

    def test_invalid_rating_fails_without_publishing(self):
        rows = [["1", "a", "9", "0", "", "2022-05-17 00:01:07"]]
        with tempfile.TemporaryDirectory() as tmp:
            input_path = make_input(tmp, rows)
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            db_path = os.path.join(tmp, "state.db")
            with self.assertRaises(ValidationError):
                ingest(input_path, manifest_path, db_path, os.path.join(tmp, "report.json"))

    def test_path_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = make_input(tmp)
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            with self.assertRaises(PathCollisionError):
                ingest(input_path, manifest_path, input_path, os.path.join(tmp, "report.json"))
            with self.assertRaises(PathCollisionError):
                ingest(input_path, manifest_path, os.path.join(tmp, "state.db"), input_path)

    def test_sidecar_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = make_input(tmp)
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            db_path = os.path.join(tmp, "state.db")
            with self.assertRaises(PathCollisionError):
                ingest(input_path, manifest_path, db_path, db_path + "-wal")

    def test_reingest_preserves_state_for_same_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, manifest_path, db_path, report_path, _ = self._run(tmp)
            cfg_hash = config_hash(
                {
                    "model": "synthetic-model",
                    "effort": "low",
                    "prompt_version": "p1",
                    "schema_version": "s1",
                }
            )
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
                self.assertEqual(db.status_counts(cfg_hash)["completed"], 1)
            report = ingest(input_path, manifest_path, db_path, report_path)
            self.assertTrue(report["extended"]["preserved_state"])
            self.assertEqual(report["extended"]["preserved_completed"], 1)
            self.assertNotIn("No classification results are present", report["extended"]["note"])
            with Database(db_path) as db:
                self.assertEqual(db.status_counts(cfg_hash)["completed"], 1)
                self.assertEqual(db.completed_ids(cfg_hash), ["1"])
                self.assertIsNotNone(db.get_classification(0, cfg_hash))

    def test_report_write_failure_preserves_prior_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, manifest_path, db_path, report_path, _ = self._run(tmp)
            with open(db_path, "rb") as handle:
                db_before = handle.read()
            with open(report_path, "rb") as handle:
                report_before = handle.read()
            blocker = os.path.join(tmp, "blocker")
            with open(blocker, "w", encoding="utf-8") as handle:
                handle.write("x")
            bad_report = os.path.join(blocker, "report.json")
            with self.assertRaises(Exception):
                ingest(input_path, manifest_path, db_path, bad_report)
            with open(db_path, "rb") as handle:
                self.assertEqual(handle.read(), db_before)
            with open(report_path, "rb") as handle:
                self.assertEqual(handle.read(), report_before)

    def test_reingest_different_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, manifest_path, db_path, report_path, _ = self._run(tmp)
            other = os.path.join(tmp, "other.csv")
            write_csv(other, [["9", "other", "5", "0", "", "2022-05-17 00:01:07"]])
            write_manifest(
                manifest_path,
                {
                    "sample.csv": manifest_entry(input_path),
                    "other.csv": manifest_entry(other),
                },
            )
            with self.assertRaises(StateError):
                ingest(other, manifest_path, db_path, report_path)

    def test_report_omits_paths_ids_and_text(self):
        rows = [["REVIEW-AAA", "secret review body", "5", "0", "", "2022-05-17 00:01:07"]]
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, report_path, _ = self._run(tmp, rows)
            with open(report_path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn(tmp, text)
            self.assertNotIn("secret review body", text)
            self.assertNotIn("REVIEW-AAA", text)


if __name__ == "__main__":
    unittest.main()

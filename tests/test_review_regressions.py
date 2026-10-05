"""SYNTHETIC regression cases from the independent code review."""

import os
import tempfile
import unittest

from spotify_pipeline.config import cache_key, config_hash
from spotify_pipeline.cost import evaluate
from spotify_pipeline.db import Database
from spotify_pipeline.errors import CostError, PipelineError, ValidationError
from spotify_pipeline.ingest import ingest
from spotify_pipeline.manifest import declared_profile
from tests.helpers import (
    SYNTHETIC_ROWS, completed_item, make_input, manifest_entry,
    measured_measurements, measured_rates, scenario, write_manifest,
)


class ReviewRegressions(unittest.TestCase):
    def test_unknown_configuration_setting_cannot_reuse_cache(self):
        cfg = {"model": "synthetic", "effort": "low", "prompt_version": "1", "schema_version": "1"}
        cfg["temperature"] = 1
        with self.assertRaises(ValidationError):
            config_hash(cfg)
        with self.assertRaises(ValidationError):
            cache_key(cfg, "synthetic text")

    def test_token_rate_cannot_use_time_unit(self):
        rates = measured_rates()
        rates["api"]["output_tokens"]["unit"] = "per_hour"
        with self.assertRaises(CostError):
            evaluate(measured_measurements(), rates, scenario())

    def test_partial_real_measurement_is_unresolved(self):
        measurements = measured_measurements()
        measurements["provenance"] = "declared_real_for_synthetic_validation_only"
        del measurements["runs"]["cold"]["api_units"]
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertEqual(report["status"], "unresolved")
        self.assertIsNone(report["pilot"]["cold"]["total"])
        self.assertFalse(report["approved_to_scale"])

    def test_huge_wall_time_is_unresolved(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["wall_seconds"] = 10 ** 1000
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertFalse(report["pilot"]["cold"]["wall_valid"])

    def test_samples_do_not_validate_full_root_profile(self):
        manifest = {"files": {"sample.csv": {}}, "profile": {"records": 660622}}
        self.assertIsNone(declared_profile(manifest, "sample.csv"))

    def test_reingest_counts_each_configuration_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_input(tmp)
            manifest = os.path.join(tmp, "manifest.json")
            write_manifest(manifest, {"sample.csv": manifest_entry(source)})
            state = os.path.join(tmp, "state.db")
            report_path = os.path.join(tmp, "report.json")
            ingest(source, manifest, state, report_path)
            with Database(state) as db:
                for prompt in ("p1", "p2"):
                    db.save_completed_batch([completed_item(0, SYNTHETIC_ROWS[0][1], prompt_version=prompt)])
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([completed_item(True, SYNTHETIC_ROWS[1][1])])
            report = ingest(source, manifest, state, report_path)["extended"]
            self.assertEqual(report["preserved_completed"], 2)
            self.assertEqual(report["status_counts"]["completed"], 0)
            self.assertEqual(len(report["configuration_status_counts"]), 2)
            for counts in report["configuration_status_counts"].values():
                self.assertEqual(counts["completed"], 1)
                self.assertEqual(counts["pending"], 3)

    def test_output_directory_and_contents_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = make_input(tmp)
            manifest = os.path.join(tmp, "manifest.json")
            write_manifest(manifest, {"sample.csv": manifest_entry(source)})
            report = os.path.join(tmp, "existing-directory")
            os.mkdir(report)
            marker = os.path.join(report, "keep.txt")
            with open(marker, "w") as handle:
                handle.write("synthetic existing work")
            with self.assertRaises(PipelineError):
                ingest(source, manifest, os.path.join(tmp, "state.db"), report)
            with open(marker) as handle:
                self.assertEqual(handle.read(), "synthetic existing work")

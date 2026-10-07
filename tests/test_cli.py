"""SYNTHETIC tests for the command line interface."""

import contextlib
import io
import json
import os
import tempfile
import unittest

from spotify_pipeline.cli import main

from tests.helpers import (
    manifest_entry,
    measured_measurements,
    measured_rates,
    scenario,
    write_csv,
    write_manifest,
)


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


class CliTests(unittest.TestCase):
    def test_no_command_prints_help(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("usage", buffer.getvalue())

    def test_ingest_status_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "sample.csv")
            write_csv(input_path, [["1", "hello", "5", "0", "", "2022-05-17 00:01:07"]])
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            db_path = os.path.join(tmp, "state.db")
            report_path = os.path.join(tmp, "report.json")
            config_path = os.path.join(tmp, "config.json")
            _write_json(
                config_path,
                {
                    "model": "synthetic-model",
                    "effort": "low",
                    "prompt_version": "p1",
                    "schema_version": "s1",
                },
            )
            checkpoint_path = os.path.join(tmp, "checkpoint.json")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(
                    main(["ingest", "--input", input_path, "--manifest", manifest_path, "--db", db_path, "--report", report_path]),
                    0,
                )
                self.assertEqual(main(["status", "--db", db_path, "--config", config_path]), 0)
                self.assertEqual(
                    main(["checkpoint", "--db", db_path, "--out", checkpoint_path, "--config", config_path]),
                    0,
                )
            self.assertTrue(os.path.exists(report_path))
            self.assertTrue(os.path.exists(checkpoint_path))
            with open(checkpoint_path, "r", encoding="utf-8") as handle:
                checkpoint = json.load(handle)
            self.assertEqual(checkpoint["completed_ids"], [])
            self.assertEqual(checkpoint["pending_count"], 1)

    def test_status_missing_db_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "missing.db")
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = main(["status", "--db", missing])
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(missing))

    def test_status_non_database_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            junk = os.path.join(tmp, "junk.db")
            with open(junk, "w", encoding="utf-8") as handle:
                handle.write("not a database")
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = main(["status", "--db", junk])
            self.assertEqual(code, 2)

    def test_checkpoint_out_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "sample.csv")
            write_csv(input_path, [["1", "hello", "5", "0", "", "2022-05-17 00:01:07"]])
            manifest_path = os.path.join(tmp, "manifest.json")
            write_manifest(manifest_path, {"sample.csv": manifest_entry(input_path)})
            db_path = os.path.join(tmp, "state.db")
            report_path = os.path.join(tmp, "report.json")
            config_path = os.path.join(tmp, "config.json")
            _write_json(
                config_path,
                {
                    "model": "synthetic-model",
                    "effort": "low",
                    "prompt_version": "p1",
                    "schema_version": "s1",
                },
            )
            with contextlib.redirect_stdout(io.StringIO()):
                main(["ingest", "--input", input_path, "--manifest", manifest_path, "--db", db_path, "--report", report_path])
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = main(["checkpoint", "--db", db_path, "--out", db_path, "--config", config_path])
            self.assertEqual(code, 2)

    def test_cost_out_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            measurements = os.path.join(tmp, "measurements.json")
            rates = os.path.join(tmp, "rates.json")
            scenario_path = os.path.join(tmp, "scenario.json")
            _write_json(measurements, measured_measurements())
            _write_json(rates, measured_rates())
            _write_json(scenario_path, scenario())
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = main(
                    [
                        "cost",
                        "--measurements",
                        measurements,
                        "--rates",
                        rates,
                        "--scenario",
                        scenario_path,
                        "--out",
                        rates,
                    ]
                )
            self.assertEqual(code, 2)

    def test_malformed_json_manifest_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "sample.csv")
            write_csv(input_path, [["1", "hello", "5", "0", "", "2022-05-17 00:01:07"]])
            manifest_path = os.path.join(tmp, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as handle:
                handle.write("{not valid json")
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = main(
                    [
                        "ingest",
                        "--input",
                        input_path,
                        "--manifest",
                        manifest_path,
                        "--db",
                        os.path.join(tmp, "state.db"),
                        "--report",
                        os.path.join(tmp, "report.json"),
                    ]
                )
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

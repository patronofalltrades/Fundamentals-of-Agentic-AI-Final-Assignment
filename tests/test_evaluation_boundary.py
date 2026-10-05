"""Synthetic tests for isolated, aggregate-only human evaluation."""

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

from spotify_pipeline.contract import row_sha256
from spotify_pipeline.csvio import iter_source_rows
from spotify_pipeline.errors import ValidationError
from tools.evaluate_human_labels import evaluate
from tools.export_human_labels import LabelExportError


class EvaluationBoundaryTests(unittest.TestCase):
    def test_direct_cli_invocation_from_repo_root(self):
        repository = os.path.dirname(os.path.dirname(__file__))
        result = subprocess.run(
            [sys.executable, "tools/evaluate_human_labels.py", "--help"],
            cwd=repository,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--predictions", result.stdout)

    def _files(self, directory):
        source = os.path.join(directory, "blank.csv")
        answers = os.path.join(directory, "answers.csv")
        predictions = os.path.join(directory, "predictions.jsonl")
        header = ["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp", "topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review"]
        original = ["synthetic-1", "Playback stops", "2", "0", "", "2023-01-01 00:00:00"]
        with open(source, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerow(original + [""] * 7)
        with open(answers, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerow(original + ["playback", "complaint", "-0.5", "3", "[]", "stops", "false"])
        with open(source, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        record = {"review_id": original[0], "source_sha256": row_sha256(original), "status": "completed", "topic": "playback", "intent": "complaint", "sentiment": -0.5, "severity": 3, "entities": [], "evidence_quote": "stops", "needs_review": False, "label_config": "test-version"}
        with open(predictions, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return source, answers, predictions, digest

    def test_aggregate_only_and_source_rejects_label_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            source, answers, predictions, digest = self._files(directory)
            with self.assertRaises(ValidationError):
                list(iter_source_rows(answers))
            report = evaluate(source, answers, predictions, 1, digest)
            self.assertEqual(report["human_answer_rows"], 1)
            self.assertEqual(report["topic_accuracy_all_human_rows"], "1.000000")
            self.assertEqual(report["severity_mae_completed_only"], "0.000000")
            serialized = json.dumps(report)
            self.assertNotIn("synthetic-1", serialized)
            self.assertNotIn("Playback stops", serialized)

    def test_missing_prediction_counts_against_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            source, answers, predictions, digest = self._files(directory)
            with open(predictions, "w", encoding="utf-8"):
                pass
            report = evaluate(source, answers, predictions, 1, digest)
            self.assertEqual(report["topic_accuracy_all_human_rows"], "0.000000")
            self.assertEqual(report["prediction_rows_missing_or_uncompleted"], 1)
            self.assertIsNone(report["severity_mae_completed_only"])

    def test_incomplete_human_answers_block_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            source, answers, predictions, digest = self._files(directory)
            with open(answers, "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            rows[1][11] = "not present"
            with open(answers, "w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(rows)
            with self.assertRaisesRegex(LabelExportError, "evidence_quote"):
                evaluate(source, answers, predictions, 1, digest)


if __name__ == "__main__":
    unittest.main()

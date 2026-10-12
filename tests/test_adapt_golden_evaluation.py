"""Synthetic aggregate-only checks for the dashboard golden-score adapter."""

import unittest

from tools import adapt_golden_evaluation as adapter


def inputs():
    aggregate = {
        "human_answer_rows": 50,
        "prediction_rows_completed": 50,
        "prediction_rows_missing_or_uncompleted": 0,
        "topic_accuracy_all_human_rows": "0.520000",
        "intent_accuracy_all_human_rows": "0.760000",
        "exact_topic_intent_severity_agreement_all_human_rows": "0.280000",
        "severity_mae_completed_only": "0.560000",
    }
    detailed = {
        "frozen_predictions_sha256": adapter.FROZEN_PREDICTIONS,
        "human_answer_rows": 50,
        "human_needs_review": {"false": 38, "true": 12},
        "case_level_data_in_report": False,
        "topic_exact": 26,
        "intent_exact": 38,
        "severity_exact": 30,
    }
    return aggregate, detailed


class AdapterTests(unittest.TestCase):
    def test_valid_aggregate_produces_only_importable_summary(self):
        aggregate, detailed = inputs()
        report = adapter.build(aggregate, detailed, adapter.FROZEN_PREDICTIONS,
                               adapter.HUMAN_BENCHMARK, adapter.LABEL_CONFIG)
        self.assertEqual(report["agreement"], {"topic": .52, "intent": .76,
                                               "severity": .6, "joint": .28})
        self.assertFalse(report["official"])
        self.assertEqual(report["label_configs"], [adapter.LABEL_CONFIG])
        self.assertNotIn("cases", report)

    def test_refuses_changed_source_or_incomplete_predictions(self):
        aggregate, detailed = inputs()
        with self.assertRaisesRegex(ValueError, "digest changed"):
            adapter.build(aggregate, detailed, "0" * 64, adapter.HUMAN_BENCHMARK,
                          adapter.LABEL_CONFIG)
        aggregate["prediction_rows_missing_or_uncompleted"] = 1
        with self.assertRaisesRegex(ValueError, "completed"):
            adapter.build(aggregate, detailed, adapter.FROZEN_PREDICTIONS,
                          adapter.HUMAN_BENCHMARK, adapter.LABEL_CONFIG)


if __name__ == "__main__":
    unittest.main()

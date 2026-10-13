"""Synthetic tests for aggregate-only blind grouping scoring."""

import unittest

from tools.score_grouping_independent40 import score


class BlindGroupingScoreTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"rows": [
            {"case_ref": "H01", "source_text": "synthetic one", "source_sha256": "a" * 64},
            {"case_ref": "H02", "source_text": "synthetic two", "source_sha256": "b" * 64},
        ]}
        self.answers = [
            {"case_ref": "H01", "source_text": "synthetic one", "independent_issue_id": "ACC-LOGIN",
             "evidence_rationale": "synthetic rationale", "uncertainty_notes": ""},
            {"case_ref": "H02", "source_text": "synthetic two", "independent_issue_id": "PLY-FAIL",
             "evidence_rationale": "synthetic rationale", "uncertainty_notes": "unsure"},
        ]
        self.predictions = [
            {"case_ref": "H01", "source_sha256": "a" * 64, "predicted_issue_id": "ACC-LOGIN"},
            {"case_ref": "H02", "source_sha256": "b" * 64, "predicted_issue_id": "PLY-QUALITY"},
        ]
        self.catalog = {"issues": [{"issue_id": value} for value in
            ("ACC-LOGIN", "PLY-FAIL", "PLY-QUALITY")]}

    def test_counts_exact_and_family_agreement_without_case_details(self):
        result = score(self.manifest, self.catalog, self.answers, self.predictions)
        self.assertEqual(result, {"cases": 2, "exact_agreement": 1,
            "family_agreement": 2, "uncertain_answers": 1,
            "answer_issue_ids_used": 2, "prediction_issue_ids_used": 2})

    def test_rejects_changed_answer_source(self):
        self.answers[0]["source_text"] = "tampered"
        with self.assertRaisesRegex(ValueError, "source identity"):
            score(self.manifest, self.catalog, self.answers, self.predictions)

    def test_rejects_missing_prediction(self):
        with self.assertRaisesRegex(ValueError, "case coverage"):
            score(self.manifest, self.catalog, self.answers, self.predictions[:1])

    def test_rejects_unknown_answer_issue_without_echoing_it(self):
        self.answers[0]["independent_issue_id"] = "PRIVATE-INVALID"
        with self.assertRaisesRegex(ValueError, "invalid issue decision") as caught:
            score(self.manifest, self.catalog, self.answers, self.predictions)
        self.assertNotIn("PRIVATE-INVALID", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

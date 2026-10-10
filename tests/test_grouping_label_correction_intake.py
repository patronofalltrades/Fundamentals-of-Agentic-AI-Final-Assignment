"""Synthetic checks for human correction intake, without source or golden data."""

import unittest

from tools.grouping_label_correction_intake import blank_rows, validate
from tools.reconcile_grouping_pilot_v3 import CORRECTION_CASES


class CorrectionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.pilot = {"schema_version": "spotify-issue-grouping-pilot100-v1",
            "rows": [{"pilot_index": i, "review_id": "synthetic-%03d" % i,
                "source_sha256": "a" * 64, "source_text": "Synthetic review text %d" % i,
                "topic": "other", "intent": "complaint", "severity": 2,
                "evidence": {"evidence_quote": "Synthetic review"}}
                for i in range(1, 101)]}
        self.overlay = {"mapping_rule_version": "pilot-primary-problem-v3-20261010",
            "status": "pilot_partial_decisions_not_production_membership",
            "counts": {"production_memberships": 0},
            "entries": [{"pilot_index": i,
                "review_id": "synthetic-%03d" % i,
                "source_sha256": "a" * 64,
                "status": "label_correction_pending",
                "production_membership_issue_id": None}
                for i in sorted(CORRECTION_CASES)]}

    def test_blank_sheet_remains_pending_and_unmapped(self):
        rows = blank_rows(self.pilot, self.overlay)
        result = validate(self.pilot, self.overlay, rows)
        self.assertEqual(result["pending"], 6)
        self.assertEqual(result["validated_not_applied"], 0)
        self.assertEqual(result["production_memberships"], 0)
        self.assertTrue(all(row["production_membership_issue_id"] is None
                            for row in result["rows"]))

    def test_explicit_changed_label_and_exact_quote_stay_overlay_only(self):
        rows = blank_rows(self.pilot, self.overlay)
        rows[0]["corrected_topic"] = "playback"
        rows[0]["corrected_evidence_quote"] = "review text 18"
        rows[0]["reviewer_confirmed"] = "yes"
        rows[0]["correction_rationale"] = "Synthetic human decision"
        result = validate(self.pilot, self.overlay, rows)
        self.assertEqual(result["validated_not_applied"], 1)
        self.assertEqual(result["pending"], 5)
        self.assertEqual(result["rows"][0]["changes"],
                         {"topic": "playback", "evidence_quote": "review text 18"})
        self.assertEqual(self.pilot["rows"][17]["topic"], "other")

    def test_rejects_non_source_quote_and_unconfirmed_edit(self):
        rows = blank_rows(self.pilot, self.overlay)
        rows[0]["corrected_evidence_quote"] = "not in synthetic source"
        rows[0]["reviewer_confirmed"] = "yes"
        rows[0]["correction_rationale"] = "Synthetic rationale"
        with self.assertRaisesRegex(ValueError, "exact source span"):
            validate(self.pilot, self.overlay, rows)
        rows[0]["reviewer_confirmed"] = ""
        with self.assertRaisesRegex(ValueError, "unconfirmed correction"):
            validate(self.pilot, self.overlay, rows)

    def test_rejects_changed_saved_source_and_noop(self):
        rows = blank_rows(self.pilot, self.overlay)
        rows[0]["saved_topic"] = "playback"
        with self.assertRaisesRegex(ValueError, "saved source"):
            validate(self.pilot, self.overlay, rows)
        rows = blank_rows(self.pilot, self.overlay)
        rows[0]["reviewer_confirmed"] = "yes"
        rows[0]["correction_rationale"] = "Synthetic rationale"
        with self.assertRaisesRegex(ValueError, "no changed field"):
            validate(self.pilot, self.overlay, rows)


if __name__ == "__main__":
    unittest.main()

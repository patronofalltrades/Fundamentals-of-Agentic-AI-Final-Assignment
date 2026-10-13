"""Synthetic checks for disjoint pilot selection and provisional review gates."""

import unittest

from tools.grouping_pilot100 import freeze
from tools.validate_grouping_pilot import validate


class GroupingPilotTests(unittest.TestCase):
    def test_pilot_is_disjoint_by_id_and_exact_text(self):
        topics = ("access", "billing", "catalog", "downloads", "other",
                  "playback", "support", "usability")
        rows = [{"review_id": "synthetic-%05d" % i,
            "source_text": "Synthetic text %d" % i, "topic": topics[i % 8],
            "intent": "cancellation" if i % 3 == 0 else "complaint",
            "severity": 5 if i % 5 == 0 else 3,
            "known_semantic_flag": i % 7 == 0} for i in range(30403)]
        design = {"schema_version": "spotify-issue-catalog-sample-v1",
            "rows": rows[:64]}
        frame = {"schema_version": "spotify-issue-grouping-frame-v1", "rows": rows}
        pilot = freeze(frame, design)
        self.assertEqual(pilot, freeze(frame, design))
        self.assertEqual(len(pilot["rows"]), 100)
        self.assertFalse({r["review_id"] for r in pilot["rows"]} &
                         {r["review_id"] for r in design["rows"]})
        self.assertFalse({r["source_text"] for r in pilot["rows"]} &
                         {r["source_text"] for r in design["rows"]})

    def test_review_preserves_abstention_and_flags(self):
        pilot = {"schema_version": "spotify-issue-grouping-pilot100-v1",
            "rows": [{"pilot_index": i, "stratum": "synthetic",
                "review_id": "synthetic-%d" % i, "source_sha256": "a" * 64,
                "source_text": "Synthetic text %d" % i,
                "evidence": {"evidence_quote": "Synthetic", "entities": []},
                "topic": "other", "intent": "complaint", "severity": 2,
                "known_semantic_flag": i == 2} for i in range(1, 101)]}
        catalog = {"schema_version": "spotify-issue-catalog-v1",
            "status": "pilot_authorized",
            "issues": [{"issue_id": "SYN", "title": "Synthetic", "definition": "Fixture"}]}
        assignments = {"schema_version": "spotify-issue-pilot-assignments-v1",
            "reviewer_type": "model_assisted_offline",
            "rows": [{"pilot_index": i,
                "provisional_issue_id": None if i == 1 else "SYN",
                "evidence_rationale": "Fixture evidence",
                "alternative_issue_ids": [],
                "ambiguity_reason": "Abstain" if i == 1 else None}
                for i in range(1, 101)]}
        result = validate(pilot, catalog, assignments)
        self.assertEqual(result["summary"]["abstain"], 1)
        self.assertEqual(result["summary"]["review_cases"], 2)
        self.assertEqual([r["pilot_index"] for r in result["review_cases"]], [1, 2])
        with self.assertRaisesRegex(ValueError, "provisional assignments differ"):
            validate(pilot, catalog, dict(assignments, rows=assignments["rows"][:-1]))


if __name__ == "__main__":
    unittest.main()

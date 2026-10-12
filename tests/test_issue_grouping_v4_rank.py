"""Synthetic checks for complete corrected-frame ranking."""

import unittest

from tools.issue_grouping_v4_rank import rank


class RankV4Tests(unittest.TestCase):
    def setUp(self):
        self.frame = {"schema_version": "spotify-issue-grouping-frame-v4",
            "membership_rule": "one_issue_per_record",
            "mapping_rule_version": "pilot-primary-problem-v3-20261010",
            "baseline_candidates": 3, "public_candidates": 2,
            "known_flagged_candidates": 1,
            "rows": [
                {"review_id": "synthetic-1", "intent": "complaint",
                 "severity": 2, "known_semantic_flag": False},
                {"review_id": "synthetic-2", "intent": "cancellation",
                 "severity": 4, "known_semantic_flag": False},
                {"review_id": "synthetic-3", "intent": "complaint",
                 "severity": 5, "known_semantic_flag": True}]}
        self.catalog = {"status": "approved",
            "mapping_rule_version": "pilot-primary-problem-v3-20261010",
            "issues": [{"issue_id": "A", "title": "Synthetic A"},
                       {"issue_id": "B", "title": "Synthetic B"}]}
        self.memberships = [
            {"issue_id": "B", "review_id": "synthetic-1"},
            {"issue_id": "A", "review_id": "synthetic-2"},
            {"issue_id": "B", "review_id": "synthetic-3"}]

    def test_baseline_and_public_rank_separately(self):
        result = rank(self.frame, self.catalog, self.memberships)
        self.assertEqual((result["baseline_denominator"],
                          result["public_denominator"]), (3, 2))
        self.assertEqual([row["issue_id"] for row in result["baseline"]],
                         ["B", "A"])
        self.assertEqual([row["issue_id"] for row in result["public_advisory"]],
                         ["A", "B"])
        self.assertEqual([row["priority_score"] for row in
                          result["public_advisory"]], [4, 2])

    def test_missing_duplicate_foreign_and_unknown_membership_fail(self):
        for rows in (self.memberships[:2],
                     self.memberships + [self.memberships[0]],
                     self.memberships[:2] + [
                         {"issue_id": "A", "review_id": "foreign"}],
                     self.memberships[:2] + [
                         {"issue_id": "unknown", "review_id": "synthetic-3"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                rank(self.frame, self.catalog, rows)

    def test_score_tie_uses_issue_id(self):
        self.frame["rows"][0]["severity"] = 4
        self.frame["rows"][2]["severity"] = 1
        result = rank(self.frame, self.catalog, self.memberships)
        self.assertEqual([row["issue_id"] for row in result["public_advisory"]],
                         ["A", "B"])


if __name__ == "__main__":
    unittest.main()

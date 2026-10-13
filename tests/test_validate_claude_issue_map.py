"""Arithmetic checks for the independent, offline issue-map audit."""

import unittest

from tools.validate_claude_issue_map import independent_ranking


class IndependentRankingTests(unittest.TestCase):
    def test_tie_order_half_up_mean_and_public_exclusion(self):
        frame = {
            "a": {"severity": 1, "known_semantic_flag": False},
            "b": {"severity": 2, "known_semantic_flag": False},
            "c": {"severity": 2, "known_semantic_flag": False},
            "d": {"severity": 5, "known_semantic_flag": True},
        }
        membership = {"a": "B", "b": "B", "c": "B", "d": "A"}
        baseline = independent_ranking(membership, frame, True)
        self.assertEqual([row["issue_id"] for row in baseline], ["A", "B"])
        self.assertEqual([row["severity_sum"] for row in baseline], ["5", "5"])
        self.assertEqual(baseline[1]["mean_severity"], "1.666667")
        public = independent_ranking(membership, frame, False)
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["complaint_count"], "3")


if __name__ == "__main__":
    unittest.main()

"""Aggregate-only scoring of the frozen blind-human grouping check."""

import unittest

from tools.diagnose_issue_map_blockers import score_blind_rows


class BlindIssueDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.manifest = [
            {"case_ref": f"c{i}", "review_id": f"r{i}", "source_sha256": f"s{i}",
             "source_text": f"text {i}", "saved_topic": topic}
            for i, topic in enumerate(("playback", "playback", "access", "usability"), 1)
        ]
        human = ("PLY-FAIL", "PLY-SELECTION", "ACC-LOGIN", "USE-ADS")
        self.answers = [
            {"case_ref": f"c{i}", "source_text": f"text {i}",
             "independent_issue_id": issue, "evidence_rationale": "reason",
             "uncertainty_notes": ""}
            for i, issue in enumerate(human, 1)
        ]
        agent = ("PLY-FAIL", "PLY-SHUFFLE", "APP-LAUNCH", "BIL-PRICE")
        self.agents = [
            {"review_id": f"r{i}", "agent_issue_id": issue,
             "confidence": "high" if i < 3 else "low"}
            for i, issue in enumerate(agent, 1)
        ]
        self.valid = set(human + agent)

    def test_exact_and_family_agreement_remain_separate_by_confidence(self):
        result = score_blind_rows(self.manifest, self.answers, self.agents, self.valid)
        self.assertEqual(result["overall"], {"cases": 4, "exact": 1, "family": 2})
        self.assertEqual(result["by_confidence"]["high"],
                         {"cases": 2, "exact": 1, "family": 2})
        self.assertEqual(result["by_confidence"]["low"],
                         {"cases": 2, "exact": 0, "family": 0})
        self.assertEqual(result["by_saved_topic"]["playback"],
                         {"cases": 2, "exact": 1, "family": 2})
        self.assertEqual(result["uncertain_answers"], 0)
        self.assertNotIn("review_id", str(result))
        self.assertNotIn("case_ref", str(result))

    def test_rejects_answer_with_changed_source_text(self):
        self.answers[0]["source_text"] = "changed"
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            score_blind_rows(self.manifest, self.answers, self.agents, self.valid)


if __name__ == "__main__":
    unittest.main()

"""Offline checks for complete issue membership and deterministic ranking."""

import unittest

from tools.issue_grouping_handoff import EXPORT_SHA256, SCHEMA, rank


class IssueGroupingHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = {"schema_version": SCHEMA,
            "accepted_export_sha256": EXPORT_SHA256,
            "membership_rule": "one_issue_per_record",
            "rows": [{"review_id": "synthetic-%05d" % i, "severity": 2 + i % 4,
                "known_semantic_flag": i < 24} for i in range(30403)]}
        cls.catalog = {"schema_version": "spotify-issue-catalog-v1",
            "mapping_rule_version": "synthetic-v1",
            "issues": [{"issue_id": "a", "title": "Synthetic A", "definition": "Fixture only"},
                {"issue_id": "b", "title": "Synthetic B", "definition": "Fixture only"}]}
        cls.membership = [{"issue_id": "a" if i % 2 == 0 else "b",
            "review_id": "synthetic-%05d" % i} for i in range(30403)]

    def test_complete_mapping_has_separate_flagged_public_projection(self):
        result = rank(self.frame, self.catalog, self.membership)
        self.assertEqual(sum(x["complaint_count"] for x in result["baseline"]), 30403)
        self.assertEqual(sum(x["complaint_count"] for x in result["public_advisory"]), 30379)
        self.assertEqual(result["baseline"][0]["priority_score"],
                         result["baseline"][0]["severity_sum"])
        self.assertEqual(sorted(x["rank"] for x in result["public_advisory"]), [1, 2])
        self.assertTrue(all(len(x["mean_severity"].split(".")[1]) == 6
                            for x in result["baseline"]))

    def test_missing_or_repeated_membership_fails(self):
        with self.assertRaisesRegex(ValueError, "all 30,403"):
            rank(self.frame, self.catalog, self.membership[:-1])
        with self.assertRaisesRegex(ValueError, "foreign, repeated"):
            rank(self.frame, self.catalog, self.membership + [self.membership[0]])

    def test_catalog_is_required_and_no_topic_mapping_is_inferred(self):
        with self.assertRaisesRegex(ValueError, "explicit versioned"):
            rank(self.frame, {}, self.membership)
        with self.assertRaisesRegex(ValueError, "foreign, repeated"):
            rank(self.frame, self.catalog,
                 [{"issue_id": "topic-playback", "review_id": m["review_id"]}
                  for m in self.membership])


if __name__ == "__main__":
    unittest.main()

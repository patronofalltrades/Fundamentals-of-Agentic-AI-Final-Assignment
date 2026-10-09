"""Synthetic checks for a bounded, reproducible issue-design sample."""

import unittest

from tools.issue_catalog_sample import TOPICS, freeze


class IssueCatalogSampleTests(unittest.TestCase):
    def test_strata_are_disjoint_and_reproducible(self):
        rows = []
        for topic in TOPICS:
            for i in range(40):
                rows.append({"review_id": "synthetic-%s-%02d" % (topic, i),
                    "topic": topic, "intent": "cancellation" if i % 4 == 0 else "complaint",
                    "severity": 5 if i % 5 == 0 else 3,
                    "known_semantic_flag": i % 7 == 0})
        rows.extend({"review_id": "synthetic-extra-%05d" % i, "topic": "other",
            "intent": "complaint", "severity": 2, "known_semantic_flag": False}
            for i in range(30403 - len(rows)))
        frame = {"schema_version": "spotify-issue-grouping-frame-v1", "rows": rows}
        first = freeze(frame)
        self.assertEqual(first, freeze(frame))
        self.assertEqual(len(first["rows"]), 64)
        self.assertEqual(len({r["review_id"] for r in first["rows"]}), 64)
        self.assertEqual(first["strata"]["cancellation"], 8)
        self.assertEqual(first["strata"]["severity5"], 8)
        self.assertEqual(first["strata"]["known_semantic_flag"], 8)


if __name__ == "__main__":
    unittest.main()

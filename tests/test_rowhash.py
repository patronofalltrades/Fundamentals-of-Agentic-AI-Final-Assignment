import unittest

from tests import _paths  # noqa: F401
import check_submission as checker
from pipeline import rowhash


class RowHashMatchesChecker(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(rowhash.FIELDS, checker.FIELDS)
        self.assertEqual(rowhash.TOPICS, checker.TOPICS)
        self.assertEqual(rowhash.INTENTS, checker.INTENTS)

    def test_row_sha_unicode_and_whitespace(self):
        rows = [
            {"review_id": "a", "review_text": "  Café\n“quoted” 🎵 ", "review_rating": "5",
             "review_likes": "0", "app_version": "", "review_timestamp": "2023-01-01 00:00:00"},
            {"review_id": "b", "review_text": "", "review_rating": "1",
             "review_likes": "12", "app_version": "8.8.1", "review_timestamp": "2022-05-17 00:01:07"},
        ]
        for row in rows:
            self.assertEqual(rowhash.row_sha(row), checker.row_sha(row))
            self.assertEqual(rowhash.canonical(row), checker.canonical(row))

    def test_real_cost_100_rows(self):
        path = _paths.DATASET_DIR / "cost_100.csv"
        if not path.exists():
            self.skipTest("dataset not available")
        for row in checker.csv_rows(path):
            self.assertEqual(rowhash.row_sha(row), checker.row_sha(row))


if __name__ == "__main__":
    unittest.main()

import csv
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import check_submission as checker
from pipeline import prepare as prep

HEADER = ["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"]


def write_csv(path, rows, bom=True):
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for r in rows:
            w.writerow(r)


def row(rid, text, ts="2023-01-01 00:00:00"):
    return [rid, text, "3", "0", "8.8.1", ts]


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_indexes_match_checker(self):
        path = self.dir / "in.csv"
        rows = [row("a", "Great app"), row("b", "  "), row("c", "Great app"), row("d", "Crash, \"again\"\nline2"),
                row("e", ""), row("f", " Great app")]
        write_csv(path, rows)
        p = prep.prepare(path)
        self.assertEqual(list(p.texts), ["a", "b", "c", "d", "e", "f"])
        self.assertEqual(p.texts["d"], "Crash, \"again\"\nline2")
        for r in checker.csv_rows(path):
            self.assertEqual(p.source_sha[r["review_id"]], checker.row_sha(r))
        self.assertEqual(p.empty_ids, ["b", "e"])
        self.assertEqual(p.text_first, {"Great app": "a", "Crash, \"again\"\nline2": "d", " Great app": "f"})
        self.assertEqual(p.stats["distinct_nonempty_texts"], 3)
        self.assertEqual(p.stats["repeated_nonempty_texts"], 1)
        self.assertEqual(p.file_sha256, checker.sha(path))
        prof = checker.profile(path)
        self.assertEqual(prof["counts"]["empty_review_text"], len(p.empty_ids))

    def test_duplicate_id_raises(self):
        path = self.dir / "dup.csv"
        write_csv(path, [row("a", "x"), row("a", "y")])
        with self.assertRaises(prep.DuplicateReviewId):
            prep.prepare(path)

    def test_malformed_row_raises(self):
        path = self.dir / "bad.csv"
        path.write_text(",".join(HEADER) + "\na,text,3,0\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            prep.prepare(path)

    def test_limit(self):
        path = self.dir / "in.csv"
        write_csv(path, [row(str(i), "t%d" % i) for i in range(10)])
        p = prep.prepare(path, limit=4)
        self.assertEqual(list(p.texts), ["0", "1", "2", "3"])
        self.assertTrue(p.limited)

    def test_real_cost_100(self):
        path = _paths.DATASET_DIR / "cost_100.csv"
        if not path.exists():
            self.skipTest("dataset not available")
        p = prep.prepare(path)
        self.assertEqual(len(p.texts), 100)
        for r in checker.csv_rows(path):
            self.assertEqual(p.source_sha[r["review_id"]], checker.row_sha(r))


if __name__ == "__main__":
    unittest.main()

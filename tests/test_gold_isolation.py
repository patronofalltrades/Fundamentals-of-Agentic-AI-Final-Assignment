"""Golden labels never reach the pipeline: no module under src/ or the run CLIs mentions evals/ files."""
import re
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"golden_50_human|gold_benchmark|golden_50\.jsonl|evals/golden")


class GoldIsolation(unittest.TestCase):
    def test_pipeline_code_never_references_golden_files(self):
        files = list((ROOT / "src").rglob("*.py")) + [ROOT / n for n in ("run_pipeline.py", "run_labelling.py", "export_grading.py")]
        offenders = [str(f.relative_to(ROOT)) for f in files if PATTERN.search(f.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_benchmark_builds_and_matches_checker_format(self):
        import sys
        sys.path.insert(0, str(ROOT / "evals"))
        import build_gold
        cases, bench = build_gold.build(build_gold.load_rows())
        self.assertEqual(len(cases), 50)
        self.assertTrue(all(c["status"] == "approved" and c["reviewer"] for c in bench["cases"]))


if __name__ == "__main__":
    unittest.main()

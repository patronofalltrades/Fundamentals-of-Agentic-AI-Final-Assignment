from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
from pipeline import claims as C


def sample_claims():
    ranking = [{"rank": 1, "issue_id": "playback.crash", "complaint_count": 3, "severity_sum": 12,
                "mean_severity": "4.000000", "priority_score": 12},
               {"rank": 2, "issue_id": "usability.ads", "complaint_count": 4, "severity_sum": 8,
                "mean_severity": "2.000000", "priority_score": 8}]
    return {c["claim_id"]: c for c in C.build_claims(ranking)}


class Citations(unittest.TestCase):
    def test_valid_citations(self):
        rep = C.validate_memo_citations("Crashes: 12 [C001-severity_sum], 3 users [C001-complaint_count].",
                                        sample_claims(), top_n=2)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["cited"], ["C001-complaint_count", "C001-severity_sum"])
        self.assertEqual(rep["uncited_top_issues"], ["usability.ads"])
        self.assertIn("C001-mean_severity", rep["uncited_top_claims"])

    def test_unknown_and_grouped_citations(self):
        rep = C.validate_memo_citations("x [C001-severity_sum, C003-severity_sum] y [C002-made_up]",
                                        sample_claims())
        self.assertFalse(rep["ok"])
        self.assertEqual(rep["unknown"], ["C002-made_up", "C003-severity_sum"])
        self.assertEqual(rep["n_citations"], 3)

    def test_no_citations_not_ok(self):
        self.assertFalse(C.validate_memo_citations("no numbers here", sample_claims())["ok"])

    def test_roundtrip_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        rows = list(sample_claims().values())
        C.write_claims(tmp / "claims.csv", rows)
        self.assertEqual((tmp / "claims.csv").read_text().splitlines()[0], "claim_id,issue_id,metric,value")
        self.assertEqual(C.load_claims(tmp / "claims.csv"), sample_claims())


if __name__ == "__main__":
    unittest.main()

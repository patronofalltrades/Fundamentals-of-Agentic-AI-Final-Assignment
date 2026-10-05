from __future__ import annotations

import random
import unittest
from fractions import Fraction

from tests import _paths  # noqa: F401
import check_submission as checker
from pipeline import rank
from pipeline.claims import build_claims


def rec(intent="complaint", severity=3, status="completed"):
    return {"status": status, "intent": intent, "severity": severity}


def half_up(fr: Fraction) -> str:
    """Independent half-up reference using exact fractions (positive values only)."""
    scaled = fr * 1000000
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r >= scaled.denominator:
        q += 1
    return "%d.%06d" % divmod(q, 1000000)


class MeanString(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(rank.mean_string(2, 3), "0.666667")
        self.assertEqual(rank.mean_string(1, 8), "0.125000")
        self.assertEqual(rank.mean_string(1, 2000000), "0.000001")      # 0.0000005 -> up
        self.assertEqual(rank.mean_string(2469133, 2000000), "1.234567")  # 1.2345665: half-up, not half-even
        self.assertEqual(rank.mean_string(10, 2), "5.000000")
        self.assertEqual(rank.mean_string(3, 3), "1.000000")

    def test_matches_checker_and_fraction_reference(self):
        rnd = random.Random(7)
        for _ in range(3000):
            n = rnd.randint(1, 5000)
            total = rnd.randint(n, 5 * n)
            got = rank.mean_string(total, n)
            self.assertEqual(got, checker.mean_string(total, n))
            self.assertEqual(got, half_up(Fraction(total, n)))


class ComputeRanking(unittest.TestCase):
    def test_ties_sorted_by_issue_id(self):
        records = {"a": rec(severity=4), "b": rec(severity=2), "c": rec(severity=2), "d": rec(severity=4)}
        membership = [("z.issue", "a"), ("m.issue", "b"), ("m.issue", "c"), ("b.issue", "d")]
        out = rank.compute_ranking(membership, records)
        self.assertEqual([(r["rank"], r["issue_id"], r["priority_score"]) for r in out],
                         [(1, "b.issue", 4), (2, "m.issue", 4), (3, "z.issue", 4)])
        self.assertEqual(out[1]["mean_severity"], "2.000000")

    def test_exclusions_mirror_checker(self):
        records = {"a": rec(severity=5), "p": rec(intent="praise", severity=1), "q": rec(status="quarantined"),
                   "c": rec(intent="cancellation", severity=2)}
        membership = [("x", "a"), ("x", "a"), ("x", "p"), ("x", "q"), ("x", "missing"), ("", "c"), ("y", "c")]
        out = rank.compute_ranking(membership, records)
        self.assertEqual([(r["issue_id"], r["complaint_count"], r["severity_sum"]) for r in out],
                         [("x", 1, 5), ("y", 1, 2)])

    def test_random_property_matches_checker_ranking(self):
        """Random memberships: identical to the checker's own calculation (copied loop)."""
        rnd = random.Random(11)
        for _ in range(50):
            records = {"r%d" % i: rec(severity=rnd.randint(1, 5)) for i in range(rnd.randint(1, 200))}
            issues = ["t.%s" % chr(97 + rnd.randint(0, 6)) for _ in records]
            membership = list(zip(issues, records))
            ours = rank.compute_ranking(membership, records)
            members = {}
            for iid, rid in membership:
                members.setdefault(iid, []).append(records[rid]["severity"])
            calc = [{"issue_id": i, "complaint_count": len(v), "severity_sum": sum(v),
                     "mean_severity": checker.mean_string(sum(v), len(v)), "priority_score": sum(v)}
                    for i, v in members.items()]
            calc.sort(key=lambda x: (-x["priority_score"], x["issue_id"]))
            for i, row in enumerate(calc, 1):
                row["rank"] = i
            self.assertEqual(ours, calc)

    def test_csv_and_claims_strings(self):
        records = {"a": rec(severity=2), "b": rec(severity=1), "c": rec(severity=1)}
        out = rank.compute_ranking([("x", "a"), ("y", "b"), ("y", "c")], records)
        text = rank.ranking_csv_text(out)
        self.assertEqual(text, "rank,issue_id,complaint_count,severity_sum,mean_severity,priority_score\n"
                               "1,x,1,2,2.000000,2\n2,y,2,2,1.000000,2\n")
        claims = build_claims(out)
        self.assertEqual(len(claims), 8)
        self.assertEqual(claims[0], {"claim_id": "C001-complaint_count", "issue_id": "x",
                                     "metric": "complaint_count", "value": "1"})
        self.assertEqual(claims[6]["claim_id"], "C002-mean_severity")
        self.assertEqual(claims[6]["value"], "1.000000")


if __name__ == "__main__":
    unittest.main()

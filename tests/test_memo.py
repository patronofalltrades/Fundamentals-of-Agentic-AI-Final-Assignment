from __future__ import annotations

import json
import unittest

from tests import _paths  # noqa: F401
from tests.test_export import FakeChat, TempDirCase, build_fixture, calls_of, make_ctx
from pipeline import group, memo, rank, verify
from pipeline.claims import load_claims, validate_memo_citations


class MemoRun(TempDirCase):
    def setUp(self):
        super().setUp()
        self.csv, self.run = build_fixture(self.tmp)
        ctx = make_ctx(self.run, self.csv, FakeChat())
        verify.run(ctx)
        group.run(ctx)
        rank.run(ctx)

    def test_inputs_and_dry_run_template(self):
        n = len(calls_of(self.run))
        s = memo.run(make_ctx(self.run, self.csv, FakeChat(), dry_run=True))
        self.assertEqual(s["source"], "template")
        self.assertEqual(len(calls_of(self.run)), n)  # dry run logs no call
        inputs = json.loads((self.run / "memo" / "inputs.json").read_text())
        self.assertTrue(inputs["product_question"].startswith("Where should Spotify invest"))
        self.assertLessEqual(len(inputs["top_issues"]), 10)
        self.assertTrue(all(len(t["quotes"]) <= 3 for t in inputs["top_issues"]))
        self.assertIn("DERIVED", inputs["area_rollup"]["label"])
        cov = inputs["coverage"]
        self.assertEqual((cov["source_ids"], cov["completed"], cov["quarantined"], cov["pending"]), (14, 13, 1, 0))
        self.assertEqual(cov["completed_via_exact_text_cache"], 2)
        self.assertIsNotNone(inputs["verify_agreement"])
        # area rollup equals the sum of ranking rows per area
        ranking = (self.run / "rank" / "ranking.csv").read_text().splitlines()[1:]
        total = sum(int(r.split(",")[3]) for r in ranking)
        self.assertEqual(sum(a["severity_sum"] for a in inputs["area_rollup"]["areas"].values()), total)
        text = (self.run / "memo" / "memo.md").read_text()
        rep = validate_memo_citations(text, load_claims(self.run / "rank" / "claims.csv"), 10)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["uncited_top_issues"], [])
        # deterministic
        memo.run(make_ctx(self.run, self.csv, None, dry_run=True))
        self.assertEqual(text, (self.run / "memo" / "memo.md").read_text())

    def test_model_memo_logged_and_cached(self):
        s = memo.run(make_ctx(self.run, self.csv, FakeChat()))
        self.assertEqual(s["source"], "model")
        mcalls = calls_of(self.run, "memo")
        self.assertEqual(len(mcalls), 1)
        self.assertEqual(mcalls[0]["review_ids"], [])
        self.assertEqual(mcalls[0]["outcome"], "succeeded")
        self.assertIn("[C00", (self.run / "memo" / "memo.md").read_text())
        chat = FakeChat()
        s = memo.run(make_ctx(self.run, self.csv, chat))
        self.assertEqual(chat.n, 0)
        self.assertTrue(s["cache_hit"])
        self.assertEqual(len(calls_of(self.run, "memo")), 1)
        self.assertTrue(json.loads((self.run / "memo" / "cache.json").read_text())["hit"])

    def test_bad_citations_retry_then_template(self):
        s = memo.run(make_ctx(self.run, self.csv, FakeChat({"memo": "bad_cite"})))
        self.assertEqual(s["source"], "template_fallback")
        self.assertEqual([c["outcome"] for c in calls_of(self.run, "memo")], ["failed", "failed"])
        rep = json.loads((self.run / "memo" / "citations.json").read_text())
        self.assertTrue(rep["ok"])
        self.assertIn("citation check failed", rep["model_errors"][0])


if __name__ == "__main__":
    unittest.main()

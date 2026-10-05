from __future__ import annotations

import copy
import json
import unittest

from tests import _paths  # noqa: F401
from tests.test_export import FakeChat, TempDirCase, build_fixture, calls_of, make_ctx
from pipeline import verify
from pipeline.io import read_jsonl


class Sample(unittest.TestCase):
    def test_deterministic_bounded_and_excludes_cached(self):
        records = {"id%d" % i: {"status": "completed"} for i in range(400)}
        records["id5"]["cache_source_id"] = "id1"
        records["q"] = {"status": "quarantined"}
        texts = {k: "t" for k in records}
        a = verify.select_sample(records, texts, sample_fraction=0.05, min_items=20, max_items=500)
        b = verify.select_sample(dict(reversed(list(records.items()))), texts, sample_fraction=0.05,
                                 min_items=20, max_items=500)
        self.assertEqual(a["review_ids"], b["review_ids"])
        self.assertEqual(a["candidates"], 399)
        self.assertGreaterEqual(a["selected"], 20)
        self.assertNotIn("id5", a["review_ids"])
        self.assertNotIn("q", a["review_ids"])
        c = verify.select_sample(records, texts, sample_fraction=0.9, min_items=20, max_items=30)
        self.assertEqual(c["selected"], 30)
        self.assertEqual(c["review_ids"], a["review_ids"][:30] if a["selected"] >= 30 else c["review_ids"])
        for rid in a["review_ids"][:a["under_threshold"]]:
            self.assertLess(verify.hash_fraction(rid), 0.05)

    def test_parse_payload_variants(self):
        self.assertEqual(verify.parse_json_payload('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(verify.parse_json_payload('Here: {"a": 1} done'), {"a": 1})
        m, d = verify._as_mapping({"labels": [{"review_id": "x", "topic": "other"}, {"review_id": "x"}]})
        self.assertEqual(d, ["x"])
        with self.assertRaises(ValueError):
            verify.parse_json_payload("nothing")


class VerifyRun(TempDirCase):
    def setUp(self):
        super().setUp()
        self.csv, self.run = build_fixture(self.tmp)

    def test_report_labels_and_no_prediction_leak(self):
        good = {"topic": "playback", "intent": "complaint", "severity": 3, "needs_review": False}
        chat = FakeChat(verify_labels={"r01": good, "r04": {"topic": "bogus"}})
        ctx = make_ctx(self.run, self.csv, chat, config={"verify": {"sample_fraction": 1.0, "min_items": 1,
                                                                    "max_items": 50, "batch_size": 5}})
        before = copy.deepcopy(ctx.records)
        summary = verify.run(ctx)
        self.assertEqual(ctx.records, before)  # never modifies records
        sample = json.loads((self.run / "verify" / "sample.json").read_text())["review_ids"]
        self.assertNotIn("r05", sample)   # cached
        self.assertNotIn("r02", sample)   # quarantined
        self.assertEqual(len(sample), 11)
        # batches of <= 5, one call each, review_ids exactly the sent ids
        vcalls = calls_of(self.run, "verify")
        self.assertEqual(len(vcalls), 3)
        self.assertEqual(sorted(i for c in vcalls for i in c["review_ids"]), sorted(sample))
        self.assertTrue(all(c["phase"] == "resume" and c["outcome"] == "succeeded" for c in vcalls))
        for call in chat.calls:
            sent = call["messages"][-1]["content"]
            self.assertNotIn("severity\": 4", sent)
            batch = json.loads(sent.split("REVIEWS:\n", 1)[1])
            self.assertEqual(set(batch[0]), {"review_id", "review_text"})
        report = json.loads((self.run / "verify" / "report.json").read_text())
        self.assertEqual(report["n"], 11)
        self.assertEqual(report["verifier_invalid"], 1)  # r04 bogus topic
        self.assertEqual(report["status_counts"], {"invalid": 1, "ok": 10})
        labels = {l["review_id"]: l for l in read_jsonl(self.run / "verify" / "labels.jsonl")}
        self.assertEqual(labels["r01"]["severity"], 3)
        self.assertEqual(report["agreement_counts"]["severity_within_1"] >= 1, True)
        dis = {d["review_id"]: d for d in report["disagreements"]}
        self.assertEqual(dis["r01"]["fields"], ["severity"])
        self.assertEqual(dis["r01"]["enrich"]["severity"], 4)
        self.assertIn("crashing", dis["r01"]["review_text"])
        self.assertTrue(any(p["enrich"] == "4" and p["verifier"] == "3" for p in report["confusion_pairs"]["severity"]))
        self.assertEqual(summary["sampled"], 11)

    def test_retry_once_then_call_failed(self):
        ctx = make_ctx(self.run, self.csv, FakeChat({"verify": "fail_first"}),
                       config={"verify": {"sample_fraction": 1.0, "min_items": 1, "max_items": 50}})
        verify.run(ctx)
        vcalls = calls_of(self.run, "verify")
        self.assertEqual([c["outcome"] for c in vcalls], ["failed", "succeeded"])
        self.assertEqual([c["attempt"] for c in vcalls], [1, 2])
        self.assertEqual(vcalls[0]["input_tokens"], 0)
        # garbage twice -> every item call_failed; both attempts logged as failed
        run2 = self.tmp / "b"
        csv2, run2 = build_fixture(run2)
        ctx2 = make_ctx(run2, csv2, FakeChat({"verify": "garbage"}),
                        config={"verify": {"sample_fraction": 1.0, "min_items": 1, "max_items": 50}})
        verify.run(ctx2)
        self.assertEqual([c["outcome"] for c in calls_of(run2, "verify")], ["failed", "failed"])
        report = json.loads((run2 / "verify" / "report.json").read_text())
        self.assertEqual(report["status_counts"], {"call_failed": report["n"]})

    def test_stage_cache_hit_and_miss(self):
        cfg = {"verify": {"sample_fraction": 1.0, "min_items": 1, "max_items": 50}}
        verify.run(make_ctx(self.run, self.csv, FakeChat(), config=cfg))
        self.assertFalse(json.loads((self.run / "verify" / "cache.json").read_text())["hit"])
        n = len(calls_of(self.run))
        # same run dir again: hit, no new calls
        chat = FakeChat()
        verify.run(make_ctx(self.run, self.csv, chat, config=cfg))
        self.assertEqual(chat.n, 0)
        self.assertEqual(len(calls_of(self.run)), n)
        self.assertTrue(json.loads((self.run / "verify" / "cache.json").read_text())["hit"])
        # warm run dir: hit from warm_from
        csv2, warm = build_fixture(self.tmp / "warm")
        chat = FakeChat()
        s = verify.run(make_ctx(warm, csv2, chat, config=cfg, extras={"warm_from": self.run}))
        self.assertEqual(chat.n, 0)
        self.assertEqual(calls_of(warm, "verify"), [])
        cache = json.loads((warm / "verify" / "cache.json").read_text())
        self.assertTrue(cache["hit"])
        self.assertEqual(cache["source"], str(self.run / "verify" / "responses.jsonl"))
        self.assertEqual(s["calls"], 0)
        # changed model -> miss
        chat = FakeChat()
        chat.model = "other-model"
        verify.run(make_ctx(warm, csv2, chat, config=cfg, extras={"warm_from": self.run}))
        self.assertGreater(chat.n, 0)


if __name__ == "__main__":
    unittest.main()

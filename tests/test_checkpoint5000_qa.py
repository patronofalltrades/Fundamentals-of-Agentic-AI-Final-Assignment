"""Synthetic checkpoint QA fixtures. No real reviews or human answers."""
import copy
import unittest

from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256
from tools.checkpoint5000_qa import audit


def fixture(n=50):
    rows = [{"review_id": "synthetic-%03d" % i,
             "review_text": "Spotify playback stops on phone %d." % i,
             "review_rating": "1", "review_likes": "0", "app_version": "",
             "review_timestamp": "2023-01-01 00:00:00"} for i in range(n)]
    hashes = [row_sha256([r[k] for k in SOURCE_FIELDS]) for r in rows]
    results = [{"review_id": r["review_id"], "review_text": r["review_text"],
        "source_sha256": hashes[i], "batch_id": i // 10, "status": "completed",
        "topic": "playback", "intent": "complaint", "sentiment": -0.5,
        "severity": 3, "entities": ["Spotify"], "evidence_quote": "playback stops",
        "needs_review": False, "label_config": "v2", "config_hash": "synthetic-config",
        "is_cached": False, "cache_source_id": None,
        "request_id": "synthetic-request-%d" % (i // 10),
        "provenance": "synthetic_fixture", "label_prompt_version": "jev-rubric-v2",
        "label_schema_version": "jev-labels-v1", "evidence_prompt_version": "test-v1"}
        for i, r in enumerate(rows)]
    return {"manifest": [{"review_id": r["review_id"], "source_sha256": hashes[i]}
                         for i, r in enumerate(rows)], "source_rows": rows,
            "batches": [{"batch_id": b, "status": "succeeded",
                         "review_ids": [r["review_id"] for r in rows[b*10:(b+1)*10]]}
                        for b in range((n+9)//10)], "results": results}


class CheckpointQaTest(unittest.TestCase):
    def check(self, bundle):
        return audit(bundle, evidence_prompt="test-v1", sample_size=7)

    def test_complete_and_deterministic_sample(self):
        bundle = fixture()
        report, sample = self.check(bundle)
        self.assertTrue(report["structurally_clean"])
        self.assertEqual(report["accepted_rows"], 50)
        self.assertEqual(report["unique_source_texts"], 50)
        self.assertEqual(len(sample["random_review_ids"]), 7)
        self.assertEqual(sample, self.check(bundle)[1])
        self.assertNotIn("synthetic-000", str(report))

    def test_partial_25_of_50_and_unreviewed_human_rows(self):
        bundle = fixture()
        bundle["results"] = bundle["results"][:25]
        for batch in bundle["batches"][2:]:
            batch["status"] = "pending" if batch["batch_id"] >= 3 else "uncertain"
        bundle["batches"][2]["status"] = "uncertain"
        bundle["batches"][3]["status"] = "quarantined"
        report, sample = self.check(bundle)
        self.assertEqual(report["completed_rows"], 25)
        self.assertEqual(report["accepted_rows"], 20)
        self.assertEqual(report["unresolved_rows"], 30)
        self.assertEqual(report["failure_reasons"]["completed_in_unsettled_batch"], 5)
        self.assertEqual(report["counts_by_state"]["uncertain"], 5)
        self.assertEqual(report["counts_by_state"]["quarantined"], 10)
        self.assertEqual(report["counts_by_state"]["pending"], 10)
        self.assertTrue(sample["semantic_review_pending"])

    def test_cross_review_evidence_and_malformed_array(self):
        bundle = fixture(10)
        bundle["results"][0]["evidence_quote"] = "phone 1"
        bundle["results"][1]["entities"] = "Spotify"
        report, _ = self.check(bundle)
        self.assertFalse(report["structurally_clean"])
        self.assertGreaterEqual(report["failure_reasons"]["invalid_evidence_span"], 2)

    def test_resume_duplicates_foreign_and_missing_ids(self):
        bundle = fixture(20)
        bundle["batches"][1]["review_ids"][0] = bundle["batches"][0]["review_ids"][0]
        bundle["batches"][1]["review_ids"][1] = "foreign-synthetic"
        bundle["results"].append(copy.deepcopy(bundle["results"][0]))
        report, _ = self.check(bundle)
        failures = report["failure_reasons"]
        self.assertGreater(failures["duplicate_across_batches"], 0)
        self.assertGreater(failures["foreign_batch_id"], 0)
        self.assertGreater(failures["duplicate_result_id"], 0)
        self.assertGreater(failures["missing_batch_id"], 0)

    def test_hash_version_and_cache_provenance(self):
        bundle = fixture(10)
        cached = bundle["results"][1]
        cached["review_text"] = bundle["source_rows"][0]["review_text"]
        cached["is_cached"] = True
        cached["cache_source_id"] = bundle["results"][0]["review_id"]
        cached["label_config"] = "wrong-config"
        cached["label_prompt_version"] = "stale"
        bundle["manifest"][2]["source_sha256"] = "0" * 64
        report, _ = self.check(bundle)
        self.assertIn("invalid_cache_provenance", report["failure_reasons"])
        self.assertIn("label_prompt_mismatch", report["failure_reasons"])
        self.assertIn("source_hash_mismatch", report["failure_reasons"])

    def test_fifty_direct_members_and_cached_alias_without_model_batch(self):
        bundle = fixture(51)
        alias = bundle["source_rows"][-1]
        alias["review_text"] = bundle["source_rows"][0]["review_text"]
        source_hash = row_sha256([alias[k] for k in SOURCE_FIELDS])
        bundle["manifest"][-1]["source_sha256"] = source_hash
        cached = bundle["results"][-1]
        cached.update({"review_text": alias["review_text"], "source_sha256": source_hash,
            "is_cached": True, "cache_source_id": bundle["results"][0]["review_id"],
            "batch_id": None, "request_id": None})
        bundle["batches"] = [{"batch_id": 0, "status": "succeeded",
            "review_ids": [r["review_id"] for r in bundle["source_rows"][:50]]}]
        for result in bundle["results"][:50]:
            result["batch_id"] = 0
        report, _ = self.check(bundle)
        self.assertTrue(report["structurally_clean"], report["failure_reasons"])
        self.assertEqual(report["accepted_rows"], 51)

    def test_blocked_exact_text_aliases_follow_uncertain_and_quarantined_origin(self):
        bundle = fixture(4)
        for alias_index, origin_index in ((1, 0), (3, 2)):
            alias = bundle["source_rows"][alias_index]
            alias["review_text"] = bundle["source_rows"][origin_index]["review_text"]
            bundle["manifest"][alias_index]["source_sha256"] = row_sha256(
                [alias[k] for k in SOURCE_FIELDS])
        bundle["batches"] = [
            {"batch_id": 0, "status": "uncertain", "review_ids": ["synthetic-000"]},
            {"batch_id": 1, "status": "quarantined", "review_ids": ["synthetic-002"]},
        ]
        bundle["results"] = []
        bundle["blocked_aliases"] = [
            {"review_id": "synthetic-001", "source_sha256": bundle["manifest"][1]["source_sha256"],
             "cache_source_id": "synthetic-000", "batch_id": 0, "status": "uncertain"},
            {"review_id": "synthetic-003", "source_sha256": bundle["manifest"][3]["source_sha256"],
             "cache_source_id": "synthetic-002", "batch_id": 1, "status": "quarantined"},
        ]
        report, _ = self.check(bundle)
        self.assertTrue(report["structurally_clean"], report["failure_reasons"])
        self.assertEqual(report["counts_by_state"], {"quarantined": 2, "uncertain": 2})
        bundle["blocked_aliases"][0]["cache_source_id"] = "synthetic-002"
        invalid, _ = self.check(bundle)
        self.assertIn("invalid_blocked_alias_provenance", invalid["failure_reasons"])


if __name__ == "__main__":
    unittest.main()

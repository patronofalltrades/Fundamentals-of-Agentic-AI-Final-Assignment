import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from spotify_pipeline.checkpoint5000_queue import CheckpointQueue
from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256
from spotify_pipeline.jev import label_config
from spotify_pipeline.project_budget import ProjectBudget
from tests.test_checkpoint5000_queue import rows5000
from tests.test_project_budget import fixtures
from tools.checkpoint5000_qa import audit
from tools.checkpoint5000_qa_bundle import make_bundle


class QaBundleTest(unittest.TestCase):
    def test_completed_and_quarantined_direct_and_cache_rows_audit_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = rows5000()
            source = root / "spotify_reviews_18months.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS)
                writer.writeheader()
                writer.writerows([{k: row[k] for k in SOURCE_FIELDS} for row in rows])
            (root / "manifest.json").write_text(json.dumps({"files": {
                source.name: {"sha256": file_sha256(str(source))}}}), encoding="utf-8")
            private = root / "local" / "checkpoint5000_manifest.json"
            private.parent.mkdir()
            manifest = {"schema_version": "checkpoint5000-manifest-v1",
                "selected_rows": 5000, "source_file": source.name,
                "source_file_sha256": file_sha256(str(source)),
                "label_config_hash": config_hash(label_config()),
                "rows": [dict(review_id=r["review_id"], source_position=r["source_position"],
                    text=r["review_text"], source_sha256=r["source_sha256"],
                    text_sha256=r["text_sha256"]) for r in rows]}
            private.write_text(json.dumps(manifest), encoding="utf-8")
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:200])}
            paths = fixtures(folder)
            budget_path = str(root / "project.db")
            with ProjectBudget(budget_path, paths) as budget:
                queue = CheckpointQueue(budget, rows, manifest["source_file_sha256"],
                                        file_sha256(str(private)), seed)
                chosen = queue.next_evidence(25, first_100=True)
                key = queue.reserve("evidence", chosen, "config", 24_903_544, 25)
                accepted = {r["review_id"]: {"entities": ["premium"],
                    "evidence_quote": "premium problem"} for r in chosen}
                queue.save_evidence(key, chosen, accepted, "config", 100_000,
                    300, 200, 50, "synthetic-gen", 1.2)
                second = queue.next_evidence(25, first_100=True)
                second_key = queue.reserve("evidence", second, "config", 24_903_544, 25)
                accepted = {r["review_id"]: {"entities": ["premium"],
                    "evidence_quote": "premium problem"} for r in second[1:]}
                queue.save_evidence(second_key, second, accepted, "config", 100_000,
                    300, 200, 50, "synthetic-gen-2", 1.2,
                    invalid={second[0]["review_id"]: "invalid exact quote"})
                third = queue.next_evidence(25)
                third_key = queue.reserve("evidence", third, "config", 24_903_544, 25)
                queue.fail(third_key, error_class="synthetic unknown delivery")
                fourth = queue.next_evidence(25)
                fourth_key = queue.reserve("evidence", fourth, "config", 24_903_544, 25)
                queue.fail(fourth_key, metered_charge=100_000,
                    error_class="synthetic malformed response",
                    response={"id": "synthetic-malformed", "usage": {"prompt_tokens": 300}})
            with mock.patch("tools.checkpoint5000_dispatch.DATASET", str(root)), \
                 mock.patch("tools.checkpoint5000_qa_bundle.DATASET", str(root)):
                bundle = make_bundle(str(private), budget_path)
            result, _ = audit(bundle, evidence_prompt="deepinfra-batch-evidence-v3")
            self.assertTrue(result["structurally_clean"], result["failure_reasons"])
            self.assertEqual(result["accepted_rows"], 98)
            self.assertEqual(result["cached_rows"], 49)
            self.assertEqual(result["counts_by_state"]["quarantined"], 52)
            self.assertEqual(result["counts_by_state"]["uncertain"], 50)
            self.assertEqual(len(bundle["blocked_aliases"]), 50)
            self.assertEqual(result["unresolved_rows"], 4902)
            quarantined = [r for r in bundle["results"] if r["status"] == "quarantined"]
            self.assertEqual(sorted(r["is_cached"] for r in quarantined), [False, True])


if __name__ == "__main__":
    unittest.main()

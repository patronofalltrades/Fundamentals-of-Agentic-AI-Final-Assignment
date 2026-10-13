import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools import checkpoint5000_audit_sample as sample


class AuditSampleTest(unittest.TestCase):
    def test_reproducible_random_frame_and_separate_risk_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / "project.db")
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE checkpoint_labels(review_id TEXT,label_json TEXT)")
                db.executemany("INSERT INTO checkpoint_labels VALUES (?,?)", [
                    (f"synthetic-{i}", json.dumps({"confidence": {"topic": 0.5 if i % 3
                        else 0.95}})) for i in range(140)])
            source = [{"review_id": f"synthetic-{i}"} for i in range(150)]
            results = [{"review_id": f"synthetic-{i}", "source_sha256": f"{i:064x}",
                "status": "completed", "needs_review": i % 2 == 0,
                "severity": 3 if i % 4 == 0 else 1, "is_cached": i % 5 == 0,
                "batch_id": "partial" if i % 6 == 0 else "complete"}
                for i in range(140)]
            results += [{"review_id": f"synthetic-{i}", "source_sha256": f"{i:064x}",
                "status": "quarantined", "reason": "synthetic invalid"}
                for i in range(140, 150)]
            bundle = {"source_rows": source, "results": results,
                "batches": [{"batch_id": "partial", "status": "partial_succeeded"},
                            {"batch_id": "complete", "status": "succeeded"}]}
            with mock.patch.object(sample, "make_bundle", return_value=bundle), \
                 mock.patch.object(sample, "audit", return_value=({
                     "structurally_clean": True}, [])):
                first = sample.build_pack("synthetic", db_path)
                second = sample.build_pack("synthetic", db_path)
            self.assertEqual(first, second)
            random_ids = {r["review_id"] for r in first["random_accepted"]}
            risk_ids = [r["review_id"] for rows in first["risk_cases"].values() for r in rows]
            self.assertEqual(len(random_ids), 100)
            self.assertEqual(len(risk_ids), len(set(risk_ids)))
            self.assertFalse(random_ids & set(risk_ids))
            self.assertEqual(len(first["risk_cases"]["quarantined"]), 10)


if __name__ == "__main__":
    unittest.main()

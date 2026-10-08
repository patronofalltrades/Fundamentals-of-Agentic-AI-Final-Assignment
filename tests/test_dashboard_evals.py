"""SYNTHETIC tests: the evaluation and benchmark registry and the /api/evals route."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import bundle
from dashboard.backend import SQLiteBackend
from dashboard.server import route
from tests.test_dashboard_vercel import build_dashboard_copy
from tools import build_eval_registry as registry

ROOT = Path(__file__).resolve().parents[1]


def get(db, path):
    status, _, body = route(lambda: SQLiteBackend(db), "GET", path, "")
    return status, json.loads(body)


class RegistryTests(unittest.TestCase):
    def test_saved_registry_is_current(self):
        self.assertEqual(registry.main(["--check"]), 0)

    def test_every_source_report_is_fingerprinted(self):
        saved = json.loads((ROOT / "dashboard" / "evals.json").read_text(encoding="utf-8"))
        paths = {s["path"] for s in saved["built_from"]}
        for source in saved["built_from"]:
            data = (ROOT / source["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), source["sha256"], source["path"])
        for item in saved["items"]:
            self.assertTrue(set(item["sources"]) <= paths, item["id"])
            self.assertIn(item["status"], ("measured", "partial", "estimate", "pending"))

    def test_values_come_from_reports(self):
        rubric = json.loads((ROOT / registry.RUBRIC).read_text(encoding="utf-8"))
        item = next(i for i in registry.build()["items"] if i["id"] == "prompt-v1-v2")
        topic = next(m for m in item["metrics"] if m["label"] == "Topic changed")
        self.assertEqual((topic["value"], topic["of"]),
                         (rubric["changes"]["field_changed_counts"]["topic"], rubric["source_rows_validated"]))


class EvalsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.copy = build_dashboard_copy(self.temp.name)

    def test_pending_state_before_grading(self):
        status, body = get(self.copy, "/api/evals")
        self.assertEqual(status, 200)
        self.assertEqual(body["golden"], {"status": "pending"})
        self.assertEqual([i["id"] for i in body["items"]],
                         ["prompt-v1-v2", "labelling-runs", "projection-100k", "extractor-benchmark"])
        checks = {c["name"]: c["status"] for c in body["checks"]}
        self.assertEqual(checks["Ranking reproduced from saved labels"], "pending")
        self.assertEqual(checks["Memo numbers match saved claims"], "pending")
        self.assertEqual(checks["Source file fingerprint recorded"], "passed")

    def test_portable_database_passes_the_text_check(self):
        bundle.export_bundle(self.copy, str(self.tmp / "bundle"))
        portable = str(self.tmp / "portable.db")
        with SQLiteBackend(portable, readonly=False) as b:
            bundle.load_bundle(b, str(self.tmp / "bundle"))
        checks = {c["name"]: c["status"] for c in get(portable, "/api/evals")[1]["checks"]}
        self.assertEqual(checks["Full review texts kept out of the public database"], "passed")


if __name__ == "__main__":
    unittest.main()

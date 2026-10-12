"""SYNTHETIC tests: monthly trend aggregates, saved golden-set evaluations and the top-issue summary."""

import json
import tempfile
import unittest
from pathlib import Path

from dashboard import bundle
from dashboard.backend import NeonHTTPBackend, SQLiteBackend
from dashboard.evaluation import load_evaluation
from dashboard.server import summary
from dashboard.store import connect, import_analysis, import_checkpoint, month_aggregates
from spotify_pipeline.db import Database
from tests.helpers import completed_item, make_db
from tests.test_dashboard_vercel import build_dashboard_copy

ROWS = [
    ["synthetic-1", "Playback stutters", "1", "0", "", "2022-05-17 00:01:07"],
    ["synthetic-2", "Billing doubled", "1", "0", "", "2022-05-30 10:00:00"],
    ["synthetic-3", "Good playlist", "5", "0", "", "2022-06-01 12:00:00"],
    ["synthetic-4", "Crashes on start", "1", "0", "", "2022-07-04 08:00:00"],
    ["synthetic-5", "Wants a feature", "4", "0", "", "2022-07-09 08:00:00"],
]
ITEMS = [
    dict(severity=4, topic="playback"),
    dict(severity=3, topic="billing", intent="cancellation"),
    dict(severity=1, topic="other", intent="praise"),
    dict(severity=5, topic="access"),
    dict(severity=2, topic="usability", intent="request"),
]
EXPECTED_MONTHS = {
    "2022-05": {"reviews": 2, "complaints": 2, "severity_sum": 7},
    "2022-06": {"reviews": 1, "complaints": 0, "severity_sum": 0},
    "2022-07": {"reviews": 2, "complaints": 1, "severity_sum": 5},
}


def save(source, indices):
    with Database(source) as db:
        db.save_completed_batch([completed_item(i, ROWS[i][1], request_id="req-%d" % i, **ITEMS[i]) for i in indices])


def build_monthly_copy(tmp):
    source = make_db(tmp, ROWS)
    save(source, range(len(ROWS)))
    target = str(Path(tmp) / "dashboard.db")
    import_checkpoint(source, target)
    return target


def month_rows(backend):
    return sorted(tuple(r) for r in backend.execute(
        "SELECT dimension, value, count FROM dashboard_aggregate WHERE dimension LIKE 'month_%'"))


def report(label_config, **overrides):
    value = {"status": "ready", "official": True, "benchmark_version": "golden-synthetic-v1",
             "benchmark_sha256": "a" * 64, "total_cases": 4, "approved_cases": 4, "missing_or_invalid_predictions": 0,
             "agreement": {"topic": 0.5, "intent": 0.75, "severity": 0.25, "joint": None},
             "severity_mae_on_valid_predictions": 0.5, "label_configs": [label_config], "run": "runs/synthetic",
             "cases": [{"review_id": "synthetic-1", "intent_correct": True}]}
    value.update(overrides)
    return value


def sqlite_transport(local):
    """Fake Neon transport that runs the translated SQL on a local SQLite file."""
    def untranslate(query):
        for n in range(query.count("$"), 0, -1):
            query = query.replace("$%d" % n, "?")
        return query

    def transport(url, headers, body, timeout):
        payload = json.loads(body)
        if "queries" in payload:
            with local._conn:
                for q in payload["queries"]:
                    local._conn.execute(untranslate(q["query"]), q["params"])
            return {"results": []}
        query = untranslate(payload["query"])
        if query.startswith("CREATE"):  # Postgres DDL; the local file already has the tables
            return {"fields": [], "rows": []}
        query = query.replace("information_schema.tables WHERE table_name=", "sqlite_master WHERE type='table' AND name=")
        cursor = local._conn.execute(query, payload["params"])
        rows = cursor.fetchall()
        names = [d[0] for d in cursor.description] if cursor.description else []
        types = [20 if rows and isinstance(rows[0][i], int) else 25 for i in range(len(names))]
        return {"fields": [{"name": n, "dataTypeID": t} for n, t in zip(names, types)],
                "rows": [[None if v is None else str(v) for v in r] for r in rows]}
    return transport


class TrendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.copy = build_monthly_copy(self.temp.name)
        self.bundle_dir = self.tmp / "bundle"
        self.manifest = bundle.export_bundle(self.copy, str(self.bundle_dir))
        self.target = str(self.tmp / "portable.db")

    def load(self, bundle_dir=None, target=None):
        with SQLiteBackend(target or self.target, readonly=False) as backend:
            return bundle.load_bundle(backend, str(bundle_dir or self.bundle_dir))

    def write_old_bundle(self):
        old = self.tmp / "old-bundle"
        old.mkdir()
        (old / "rows.jsonl").write_bytes((self.bundle_dir / "rows.jsonl").read_bytes())
        manifest = {k: v for k, v in self.manifest.items() if k != "months"}
        (old / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return old

    def test_export_months_counts_and_determinism(self):
        self.assertEqual(self.manifest["months"], EXPECTED_MONTHS)
        self.assertEqual(list(self.manifest["months"]), sorted(EXPECTED_MONTHS))
        again = bundle.export_bundle(self.copy, str(self.tmp / "bundle-2"))
        self.assertEqual((self.bundle_dir / "manifest.json").read_bytes(), (self.tmp / "bundle-2" / "manifest.json").read_bytes())
        self.assertEqual(again["rows_sha256"], self.manifest["rows_sha256"])
        raw = (self.bundle_dir / "rows.jsonl").read_text()
        self.assertNotIn("review_timestamp", raw)
        self.assertNotIn("2022-0", raw)

    def test_rows_hash_unchanged_by_months(self):
        original = bundle.month_aggregates
        bundle.month_aggregates = lambda conn: {}
        try:
            without = bundle.export_bundle(self.copy, str(self.tmp / "no-months"))
        finally:
            bundle.month_aggregates = original
        self.assertEqual(without["rows_sha256"], self.manifest["rows_sha256"])
        self.assertEqual((self.tmp / "no-months" / "rows.jsonl").read_bytes(), (self.bundle_dir / "rows.jsonl").read_bytes())

    def test_month_aggregates_count_all_rows_but_only_completed_complaints(self):
        partial_dir = self.tmp / "partial"
        partial_dir.mkdir()
        source = make_db(str(partial_dir), ROWS)
        save(source, [1, 2])  # rows 0, 3 and 4 are not processed
        with connect(source, readonly=True) as conn:
            self.assertEqual(month_aggregates(conn), {
                "2022-05": {"reviews": 2, "complaints": 1, "severity_sum": 3},
                "2022-06": {"reviews": 1, "complaints": 0, "severity_sum": 0},
                "2022-07": {"reviews": 2, "complaints": 0, "severity_sum": 0}})

    def test_load_writes_month_dimensions(self):
        self.assertEqual(self.load()["result"], "imported")
        self.assertEqual(self.load()["result"], "unchanged")
        with SQLiteBackend(self.target) as backend:
            self.assertEqual(month_rows(backend), [
                ("month_complaints", "2022-05", 2), ("month_complaints", "2022-07", 1),
                ("month_reviews", "2022-05", 2), ("month_reviews", "2022-06", 1), ("month_reviews", "2022-07", 2),
                ("month_severity_sum", "2022-05", 7), ("month_severity_sum", "2022-07", 5)])

    def test_local_refresh_aggregates_match_the_bundle(self):
        self.load()
        with SQLiteBackend(self.copy) as local, SQLiteBackend(self.target) as portable:
            self.assertEqual(month_rows(local), month_rows(portable))
            self.assertEqual(summary(local)["trends"], summary(portable)["trends"])

    def test_old_manifest_loads_then_months_are_added_without_rows(self):
        old = self.write_old_bundle()
        self.assertEqual(self.load(old)["result"], "imported")
        with SQLiteBackend(self.target) as backend:
            self.assertEqual(month_rows(backend), [])
            self.assertIsNone(summary(backend)["trends"])
        self.assertEqual(self.load(old)["result"], "unchanged")
        inserted = []
        original = SQLiteBackend.run_batch

        def recording(self_, statements):
            inserted.extend(sql for sql, _ in statements)
            return original(self_, statements)

        SQLiteBackend.run_batch = recording
        try:
            result = self.load()
        finally:
            SQLiteBackend.run_batch = original
        self.assertEqual((result["result"], result["months"]), ("aggregates_refreshed", 3))
        self.assertFalse(any("records" in sql or "classifications" in sql or "record_state" in sql for sql in inserted))
        self.assertEqual(self.load()["result"], "unchanged")
        with SQLiteBackend(self.target) as backend:
            self.assertEqual(len(month_rows(backend)), 7)
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM records").fetchone()[0], 5)
            self.assertEqual(summary(backend)["raw_labels"]["intent"]["complaint"], 2)

    def test_refresh_over_postgres_transport(self):
        self.load(self.write_old_bundle())
        with SQLiteBackend(self.target, readonly=False) as local:
            neon = NeonHTTPBackend("postgres://u:p@ep-x.neon.tech/d", transport=sqlite_transport(local))
            self.assertEqual(bundle.load_bundle(neon, str(self.bundle_dir))["result"], "aggregates_refreshed")
            self.assertEqual(bundle.load_bundle(neon, str(self.bundle_dir))["result"], "unchanged")
            self.assertEqual(len(month_rows(local)), 7)

    def test_inconsistent_months_are_rejected(self):
        path = self.bundle_dir / "manifest.json"
        good = json.loads(path.read_text())
        for months in ({"2022-05": {"reviews": 9, "complaints": 2, "severity_sum": 7}},
                       {"2022-13": EXPECTED_MONTHS["2022-05"]},
                       dict(EXPECTED_MONTHS, **{"2022-05": {"reviews": 2, "complaints": 2}})):
            path.write_text(json.dumps(dict(good, months=months)))
            with self.assertRaises(ValueError, msg=str(months)):
                self.load()

    def test_summary_trends_shape(self):
        self.load()
        with SQLiteBackend(self.target) as backend:
            trends = summary(backend)["trends"]
        self.assertEqual(trends, {"granularity": "month", "months": ["2022-05", "2022-06", "2022-07"], "reviews": [2, 1, 2],
                                  "complaints": [2, 0, 1], "mean_severity": ["3.500000", None, "5.000000"]})

    def test_summary_trends_null_without_month_aggregates(self):
        with SQLiteBackend(self.copy, readonly=False) as backend:
            backend.run_batch([("DELETE FROM dashboard_aggregate WHERE dimension LIKE 'month_%'", ())])
            self.assertIsNone(summary(backend)["trends"])


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.copy = build_dashboard_copy(self.temp.name)
        with SQLiteBackend(self.copy) as backend:
            self.label_config = backend.execute("SELECT DISTINCT label_config FROM classifications").fetchone()[0]

    def load(self, value, label_set="original"):
        with SQLiteBackend(self.copy, readonly=False) as backend:
            return load_evaluation(backend, value, label_set)

    def saved(self):
        with SQLiteBackend(self.copy) as backend:
            return summary(backend)

    def test_pending_then_saved_unchanged_replaced(self):
        self.assertEqual(self.saved()["evaluation"], {"status": "pending"})
        self.assertEqual(self.saved()["quality"]["human_evaluation"], "pending")
        self.assertEqual(self.load(report(self.label_config))["result"], "saved")
        self.assertEqual(self.load(report(self.label_config))["result"], "unchanged")
        self.assertEqual(self.load(report(self.label_config, note="extra keys are ignored"))["result"], "unchanged")
        changed = report(self.label_config, agreement={"topic": 0.6, "intent": 0.75, "severity": 0.25, "joint": 0.2})
        self.assertEqual(self.load(changed)["result"], "replaced")
        self.assertEqual(self.load(report(self.label_config), "adjudicated")["result"], "saved")
        result = self.saved()
        self.assertEqual(result["quality"]["human_evaluation"], "saved")
        self.assertEqual(result["evaluation"]["status"], "saved")
        self.assertEqual(sorted(result["evaluation"]["sets"]), ["adjudicated", "original"])
        self.assertEqual(result["evaluation"]["sets"]["original"], {
            "label_set": "original", "benchmark_version": "golden-synthetic-v1", "benchmark_sha256": "a" * 64,
            "approved_cases": 4, "total_cases": 4, "missing_or_invalid_predictions": 0,
            "agreement": {"topic": 0.6, "intent": 0.75, "severity": 0.25, "joint": 0.2},
            "severity_mae_on_valid_predictions": 0.5, "official": True, "label_config": self.label_config})
        body = json.dumps(result)
        self.assertNotIn("synthetic-1", body)
        self.assertNotIn('"cases"', body)

    def test_refusals_write_nothing(self):
        no_configs = report(self.label_config)
        del no_configs["label_configs"]
        cases = [
            no_configs,
            report(self.label_config, label_configs=[]),
            report(self.label_config, label_configs=["other-classifier"]),
            report(self.label_config, label_configs=[self.label_config, "other-classifier"]),
            report(self.label_config, agreement={"topic": 1.5, "intent": 0.5, "severity": 0.5, "joint": 0.5}),
            report(self.label_config, agreement={"topic": "0.5", "intent": 0.5, "severity": 0.5, "joint": 0.5}),
            report(self.label_config, agreement={"topic": True, "intent": 0.5, "severity": 0.5, "joint": 0.5}),
            report(self.label_config, agreement={"topic": 0.5}),
            report(self.label_config, approved_cases=0),
            report(self.label_config, approved_cases=2.0),
            report(self.label_config, benchmark_sha256="not-a-hash"),
        ]
        for case in cases:
            with self.assertRaises(ValueError, msg=str(case)):
                self.load(case)
        for label_set in ("", "Has Space", "x" * 40):
            with self.assertRaises(ValueError):
                self.load(report(self.label_config), label_set)
        self.assertEqual(self.saved()["evaluation"], {"status": "pending"})

    def test_mismatch_message_names_the_classifier(self):
        with self.assertRaisesRegex(ValueError, "different classifier"):
            self.load(report(self.label_config, label_configs=["other-classifier"]))

    def test_postgres_transport(self):
        with SQLiteBackend(self.copy, readonly=False) as local:
            neon = NeonHTTPBackend("postgres://u:p@ep-x.neon.tech/d", transport=sqlite_transport(local))
            self.assertEqual(load_evaluation(neon, report(self.label_config), "original")["result"], "saved")
            self.assertEqual(load_evaluation(neon, report(self.label_config), "original")["result"], "unchanged")
            self.assertEqual(summary(neon)["evaluation"]["status"], "saved")


class TopIssueTests(unittest.TestCase):
    def test_null_then_rank_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = build_monthly_copy(tmp)
            with connect(copy, readonly=True) as conn:
                self.assertIsNone(summary(conn)["top_issue"])
                source = summary(conn)["source"]
            import_analysis(copy, {"run_id": "synthetic-run", "source_sha256": source["sha256"],
                                   "config_hash": source["config_hash"], "recommendations": [],
                                   "issues": [{"issue_id": "issue-billing", "title": "Billing", "row_indices": [1]},
                                              {"issue_id": "issue-crash", "title": "Crashes", "row_indices": [0, 3]}]})
            with connect(copy, readonly=True) as conn:
                self.assertEqual(summary(conn)["top_issue"], {
                    "issue_id": "issue-crash", "title": "Crashes", "mean_severity": "4.500000",
                    "priority_score": 9, "complaint_count": 2})


if __name__ == "__main__":
    unittest.main()

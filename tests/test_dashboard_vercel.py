"""SYNTHETIC tests: storage backends, the bundle import contract, and the WSGI (Vercel) entry."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from dashboard import bundle
from dashboard.analysis import load_analysis
from dashboard.backend import NeonHTTPBackend, Row, SQLiteBackend, from_env, translate_sqlite_to_postgres
from dashboard.server import route, summary
from dashboard.store import connect, import_analysis, import_checkpoint
from dashboard.wsgi import make_app
from spotify_pipeline.db import Database
from tests.helpers import completed_item, make_db

ROWS = [
    ["synthetic-1", "Playback stutters", "1", "0", "", "2022-05-17 00:01:07"],
    ["synthetic-2", "Billing doubled", "1", "0", "", "2022-05-18 00:01:07"],
    ["synthetic-3", "Good playlist", "5", "0", "", "2022-05-19 00:01:07"],
]
PATHS = ["/api/summary", "/api/reviews?limit=50", "/api/reviews?topic=billing", "/api/reviews?q=stutters",
         "/api/reviews/0", "/api/issues", "/api/recommendations"]


def build_dashboard_copy(tmp):
    source = make_db(tmp, ROWS)
    with Database(source) as db:
        db.save_completed_batch([
            completed_item(0, ROWS[0][1], severity=4, topic="playback"),
            completed_item(1, ROWS[1][1], severity=4, topic="billing", intent="cancellation", request_id="req-2"),
            completed_item(2, ROWS[2][1], severity=1, topic="other", intent="praise", request_id="req-3"),
        ])
    target = str(Path(tmp) / "dashboard.db")
    import_checkpoint(source, target)
    return target


def call(opener, path_and_query, method="GET"):
    path, _, query = path_and_query.partition("?")
    status, _, body = route(opener, method, path, query)
    return status, json.loads(body)


class BackendTests(unittest.TestCase):
    def test_row_access_like_sqlite_row(self):
        row = Row(["key", "value"], ["a", 1])
        self.assertEqual((row[0], row["value"], dict(row), list(row)), ("a", 1, {"key": "a", "value": 1}, ["a", 1]))
        self.assertEqual(dict([Row(["k", "v"], ["x", "y"])]), {"x": "y"})

    def test_translate_placeholders_and_instr(self):
        sql = "SELECT '?' AS q FROM t WHERE a=? AND instr(lower(b),lower(?))>0 LIMIT ? OFFSET ?"
        self.assertEqual(translate_sqlite_to_postgres(sql),
                         "SELECT '?' AS q FROM t WHERE a=$1 AND strpos(lower(b),lower($2))>0 LIMIT $3 OFFSET $4")

    def test_neon_request_shape_and_type_parsing(self):
        seen = []

        def transport(url, headers, body, timeout):
            seen.append((url, headers, json.loads(body)))
            return {"fields": [{"name": "n", "dataTypeID": 20}, {"name": "s", "dataTypeID": 701},
                               {"name": "t", "dataTypeID": 25}, {"name": "b", "dataTypeID": 16}],
                    "rows": [["3", "0.5", "x", "t"]]}

        backend = NeonHTTPBackend("postgresql://user:secret@ep-test-123.eu-central-1.aws.neon.tech/db?sslmode=require",
                                  transport=transport)
        row = backend.execute("SELECT COUNT(*) AS n FROM t WHERE x=?", ("a",)).fetchone()
        self.assertEqual((row["n"], row["s"], row["t"], row["b"]), (3, 0.5, "x", True))
        url, headers, body = seen[0]
        self.assertEqual(url, "https://ep-test-123.eu-central-1.aws.neon.tech/sql")
        self.assertEqual(body, {"query": "SELECT COUNT(*) AS n FROM t WHERE x=$1", "params": ["a"]})
        self.assertIn("secret", headers["Neon-Connection-String"])
        self.assertNotIn("secret", url)
        backend.run_batch([("INSERT INTO t VALUES (?)", (1,)), ("INSERT INTO t VALUES (?)", (2,))])
        self.assertEqual([q["query"] for q in seen[-1][2]["queries"]], ["INSERT INTO t VALUES ($1)"] * 2)

    def test_from_env_prefers_database_url_and_rejects_bad_url(self):
        self.assertIsInstance(from_env({"DATABASE_URL": "postgres://u:p@h.neon.tech/d"}), NeonHTTPBackend)
        with self.assertRaises(ValueError):
            from_env({})
        with self.assertRaises(ValueError):
            NeonHTTPBackend("mysql://u:p@h/d")


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.copy = build_dashboard_copy(self.temp.name)
        self.bundle_dir = self.tmp / "bundle"
        self.manifest = bundle.export_bundle(self.copy, str(self.bundle_dir))
        self.target = str(self.tmp / "portable.db")

    def load(self, target=None, **kw):
        with SQLiteBackend(target or self.target, readonly=False) as backend:
            return bundle.load_bundle(backend, str(self.bundle_dir), **kw)

    def test_bundle_excludes_full_text_and_keeps_ids_and_counts(self):
        rows = [json.loads(l) for l in (self.bundle_dir / "rows.jsonl").read_text().splitlines()]
        self.assertEqual([r["review_id"] for r in rows], ["synthetic-1", "synthetic-2", "synthetic-3"])
        raw = (self.bundle_dir / "rows.jsonl").read_text()
        for field in ("review_text", "review_rating", "review_timestamp"):
            self.assertNotIn('"%s"' % field, raw)
        self.assertEqual(self.manifest["counts"], {"completed_rows": 3, "nonempty_rows": 3, "source_rows": 3,
                                                   "distinct_nonempty_texts": 3})
        with self.assertRaises(ValueError):  # export never overwrites
            bundle.export_bundle(self.copy, str(self.bundle_dir))

    def test_load_is_idempotent_and_api_matches_the_original(self):
        self.assertEqual(self.load()["result"], "imported")
        self.assertEqual(self.load()["result"], "unchanged")
        for path in PATHS:
            original = call(lambda: connect(self.copy, readonly=True), path)
            portable = call(lambda: SQLiteBackend(self.target), path)
            if path == "/api/reviews/0":
                self.assertTrue(original[1].pop("review_text_available_in_database"))
                self.assertFalse(portable[1].pop("review_text_available_in_database"))
            self.assertEqual(original, portable, path)
        with SQLiteBackend(self.target) as backend:
            self.assertFalse(backend.table_exists("texts"))
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM records WHERE review_id LIKE 'synthetic-%'").fetchone()[0], 3)

    def test_interrupted_load_resumes_without_duplicates(self):
        calls = {"n": 0}
        original = SQLiteBackend.run_batch

        def flaky(self_, statements):
            calls["n"] += 1
            if calls["n"] == 3:  # meta batch, first row chunk, then fail on the second chunk
                raise RuntimeError("simulated connection loss")
            return original(self_, statements)

        SQLiteBackend.run_batch = flaky
        try:
            with self.assertRaises(RuntimeError):
                self.load(chunk_size=1)
        finally:
            SQLiteBackend.run_batch = original
        with SQLiteBackend(self.target) as backend:
            self.assertEqual(backend.execute("SELECT value FROM dashboard_meta WHERE key='import_status'").fetchone()[0], "importing")
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
        self.assertEqual(self.load(chunk_size=1)["result"], "imported")
        with SQLiteBackend(self.target) as backend:
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM classifications").fetchone()[0], 3)

    def test_tampered_bundle_and_other_source_are_rejected(self):
        rows_path = self.bundle_dir / "rows.jsonl"
        good = rows_path.read_text()
        rows_path.write_text(good.replace("Playback stutters", "Edited quote"))
        with self.assertRaises(ValueError):
            self.load()
        rows_path.write_text(good)
        self.load()
        other_dir = self.tmp / "other"
        other_dir.mkdir()
        other_copy = build_dashboard_copy(str(other_dir))
        other_bundle = self.tmp / "other-bundle"
        manifest = bundle.export_bundle(other_copy, str(other_bundle))
        self.assertEqual(manifest["rows_sha256"], self.manifest["rows_sha256"])  # same synthetic rows
        manifest_path = other_bundle / "manifest.json"
        changed = json.loads(manifest_path.read_text())
        changed["source"]["file_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(changed))
        with SQLiteBackend(self.target, readonly=False) as backend:
            with self.assertRaises(ValueError):
                bundle.load_bundle(backend, str(other_bundle))

    def test_summary_flags_demo_coverage(self):
        self.load()
        with SQLiteBackend(self.target) as backend:
            target = summary(backend)["target"]
        self.assertEqual(target, {"minimum_source_rows": 100000, "is_demo": True})


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        tmp = Path(self.temp.name)
        self.copy = build_dashboard_copy(self.temp.name)
        bundle.export_bundle(self.copy, str(tmp / "bundle"))
        self.portable = str(tmp / "portable.db")
        with SQLiteBackend(self.portable, readonly=False) as backend:
            bundle.load_bundle(backend, str(tmp / "bundle"))
            ident = backend.execute("SELECT value FROM meta WHERE key='file_sha256'").fetchone()[0]
            config = backend.execute("SELECT DISTINCT config_hash FROM record_state").fetchone()[0]
        self.payload = {"run_id": "synthetic-run", "source_sha256": ident, "config_hash": config,
                        "issues": [{"issue_id": "z", "title": "Playback", "row_indices": [0]},
                                   {"issue_id": "a", "title": "Billing", "row_indices": [1]}],
                        "recommendations": [{"recommendation_id": "draft-1", "text": "Investigate both.",
                                             "issue_ids": ["z", "a"]}]}

    def test_portable_backend_matches_original_sqlite_importer(self):
        import_analysis(self.copy, self.payload)
        with SQLiteBackend(self.portable, readonly=False) as backend:
            self.assertEqual(load_analysis(backend, self.payload)["memberships"], 2)
        original = lambda path: call(lambda: connect(self.copy, readonly=True), path)[1]
        portable = lambda path: call(lambda: SQLiteBackend(self.portable), path)[1]
        self.assertEqual(original("/api/issues")["items"], portable("/api/issues")["items"])
        self.assertEqual(original("/api/recommendations"), portable("/api/recommendations"))
        self.assertEqual(original("/api/issues/a")["reviews"], portable("/api/issues/a")["reviews"])
        self.assertEqual(original("/api/summary")["analysis"]["grouping"], "accepted")
        self.assertEqual(portable("/api/summary")["analysis"]["grouping"], "accepted")
        ranked = call(lambda: SQLiteBackend(self.portable), "/api/issues")[1]["items"]
        self.assertEqual([(i["issue_id"], i["priority_score"], i["mean_severity"]) for i in ranked],
                         [("a", 4, "4.000000"), ("z", 4, "4.000000")])

    def test_rejections_and_immutability(self):
        with SQLiteBackend(self.portable, readonly=False) as backend:
            for bad in ({**self.payload, "config_hash": "wrong"},
                        {**self.payload, "issues": [{"issue_id": "p", "title": "Praise", "row_indices": [2]}]},
                        {**self.payload, "recommendations": [{"recommendation_id": "r", "text": "x", "issue_ids": ["nope"]}]}):
                with self.assertRaises(ValueError):
                    load_analysis(backend, bad)
            load_analysis(backend, self.payload)
            with self.assertRaises(ValueError):
                load_analysis(backend, self.payload)
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM analysis_run").fetchone()[0], 1)

    def test_failed_batch_writes_nothing(self):
        with SQLiteBackend(self.portable, readonly=False) as backend:
            bad = dict(self.payload, issues=self.payload["issues"] + [{"issue_id": "a2", "title": "Dup", "row_indices": [1]}])
            original = backend.run_batch

            def failing(statements):
                original(statements[:-1] + [("INSERT INTO issue (run_id, issue_id, title) VALUES (?, ?, ?)",
                                             ("synthetic-run", "a", "duplicate key"))])
            backend.run_batch = failing
            with self.assertRaises(Exception):
                load_analysis(backend, bad)
            backend.run_batch = original
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM analysis_run").fetchone()[0], 0)
            self.assertEqual(backend.execute("SELECT COUNT(*) FROM issue").fetchone()[0], 0)

    def test_postgres_path_is_one_transaction(self):
        sent = []
        with SQLiteBackend(self.portable) as local:
            def transport(url, headers, body, timeout):
                payload = json.loads(body)
                if "queries" in payload:
                    sent.append(payload["queries"])
                    return {"results": []}
                sql = payload["query"]
                for n in range(len(payload["params"]), 0, -1):
                    sql = sql.replace("$%d" % n, "?")
                rows = local.execute(sql, payload["params"]).fetchall()
                names = [d[0] for d in local._conn.execute(sql, payload["params"]).description] if rows else []
                return {"fields": [{"name": n, "dataTypeID": 25} for n in names], "rows": [list(r) for r in rows]}

            result = load_analysis(NeonHTTPBackend("postgres://u:p@ep-x.neon.tech/d", transport=transport), self.payload)
        self.assertEqual(result["memberships"], 2)
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0][0]["query"].startswith("INSERT INTO analysis_run"))
        self.assertTrue(all("$" in q["query"] and "?" not in q["query"] for q in sent[0]))


class WSGITests(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        from pathlib import Path as _P
        patcher = mock.patch("dashboard.server.DIST", _P("/nonexistent-web-dist"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.copy = build_dashboard_copy(self.temp.name)
        self.app = make_app(lambda: SQLiteBackend(self.copy))

    def request(self, path, method="GET", query=""):
        environ = {}
        setup_testing_defaults(environ)
        environ.update({"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query, "wsgi.input": io.BytesIO()})
        captured = {}

        def start_response(status, headers):
            captured["status"], captured["headers"] = status, dict(headers)

        body = b"".join(self.app(environ, start_response))
        return captured["status"], captured["headers"], body

    def test_get_routes_static_and_headers(self):
        status, headers, body = self.request("/api/summary")
        self.assertEqual(status, "200 OK")
        self.assertEqual(json.loads(body)["coverage"]["source_rows"], 3)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, headers, body = self.request("/")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Supporting review evidence", body)
        self.assertEqual(self.request("/app.js")[0], "200 OK")
        self.assertEqual(self.request("/api/reviews", query="topic=billing")[0], "200 OK")
        self.assertEqual(self.request("/api/reviews", query="topic=nope")[0], "400 Bad Request")
        self.assertEqual(self.request("/etc/passwd")[0], "404 Not Found")

    def test_writes_rejected_and_head_has_no_body(self):
        self.assertEqual(self.request("/api/summary", method="POST")[0], "405 Method Not Allowed")
        self.assertEqual(self.request("/api/summary", method="DELETE")[0], "405 Method Not Allowed")
        status, headers, body = self.request("/api/summary", method="HEAD")
        self.assertEqual((status, body), ("200 OK", b""))
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_database_errors_are_not_echoed(self):
        def broken():
            raise RuntimeError("postgres://user:secret@host/db refused")

        app = make_app(broken)
        environ = {}
        setup_testing_defaults(environ)
        environ.update({"REQUEST_METHOD": "GET", "PATH_INFO": "/api/summary"})
        captured = {}
        body = b"".join(app(environ, lambda s, h: captured.update(status=s)))
        self.assertEqual(captured["status"], "503 Service Unavailable")
        self.assertNotIn(b"secret", body)


if __name__ == "__main__":
    unittest.main()

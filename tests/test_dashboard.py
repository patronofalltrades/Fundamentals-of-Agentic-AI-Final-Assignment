"""SYNTHETIC dashboard import, ranking, and HTTP tests."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dashboard.server import issues, make_handler, recommendations, reviews, summary
from dashboard.store import connect, import_analysis, import_checkpoint
from spotify_pipeline.db import Database
from tests.helpers import completed_item, make_db


ROWS = [
    ["synthetic-1", "Playback stutters", "1", "0", "", "2022-05-17 00:01:07"],
    ["synthetic-2", "Billing doubled", "1", "0", "", "2022-05-18 00:01:07"],
    ["synthetic-3", "Good playlist", "5", "0", "", "2022-05-19 00:01:07"],
]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = make_db(self.temp.name, ROWS)
        with Database(self.source) as db:
            db.save_completed_batch([
                completed_item(0, ROWS[0][1], severity=4, topic="playback"),
                completed_item(1, ROWS[1][1], severity=4, topic="billing", intent="cancellation", request_id="req-2"),
                completed_item(2, ROWS[2][1], severity=5, topic="other", intent="praise", request_id="req-3"),
            ])
        self.target = str(Path(self.temp.name) / "dashboard.db")
        import_checkpoint(self.source, self.target)
        with connect(self.target, readonly=True) as conn:
            self.base = summary(conn)
            self.config = conn.execute("SELECT DISTINCT config_hash FROM record_state").fetchone()[0]

    def test_import_is_idempotent_and_rejects_other_source(self):
        self.assertEqual(import_checkpoint(self.source, self.target)["result"], "unchanged")
        with connect(self.target, readonly=True) as conn:
            self.assertEqual(summary(conn)["coverage"]["source_rows"], 3)
        other_dir = Path(self.temp.name) / "other"
        other_dir.mkdir()
        other = make_db(str(other_dir), ROWS[:2], name="other.csv")
        with self.assertRaises(ValueError):
            import_checkpoint(other, self.target)

    def test_pending_state_and_private_ids(self):
        with connect(self.target, readonly=True) as conn:
            self.assertEqual(issues(conn)["status"], "pending")
            self.assertEqual(recommendations(conn)["items"], [])
            self.assertEqual(reviews(conn, topic="billing")["total"], 1)
            self.assertEqual(self.base["coverage"]["distinct_nonempty_texts"], 3)
            self.assertNotIn("review_id", reviews(conn)["items"][0])
            self.assertNotIn("review_text", reviews(conn)["items"][0])

    def test_membership_ranking_and_recommendation_links(self):
        payload = {"run_id": "synthetic-run", "source_sha256": self.base["source"]["sha256"], "config_hash": self.config,
                   "issues": [{"issue_id": "z", "title": "Playback", "row_indices": [0]}, {"issue_id": "a", "title": "Billing", "row_indices": [1]}],
                   "recommendations": [{"recommendation_id": "draft-1", "text": "Investigate both issues.", "issue_ids": ["z", "a"]}]}
        with self.assertRaises(ValueError):
            import_analysis(self.target, {**payload, "source_sha256": "wrong"})
        with self.assertRaises(ValueError):
            import_analysis(self.target, {**payload, "issues": [{"issue_id": "bad", "title": "Praise", "row_indices": [2]}]})
        result = import_analysis(self.target, payload)
        self.assertEqual(result["memberships"], 2)
        with connect(self.target, readonly=True) as conn:
            self.assertEqual([x["issue_id"] for x in issues(conn)["items"]], ["a", "z"])
            self.assertEqual([x["priority_score"] for x in issues(conn)["items"]], [4, 4])
            self.assertEqual(issues(conn)["items"][0]["mean_severity"], "4.000000")
            self.assertEqual(recommendations(conn)["items"][0]["issue_ids"], ["a", "z"])
            self.assertEqual(reviews(conn, issue_id="a")["total"], 1)
        with self.assertRaises(ValueError):
            import_analysis(self.target, payload)

    def test_http_get_only_and_static_ui(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.target))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:%d" % server.server_port
        with urlopen(base + "/api/summary") as response:
            self.assertEqual(json.load(response)["coverage"]["source_rows"], 3)
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        with urlopen(base + "/") as response:
            self.assertIn(b"Supporting review evidence", response.read())
        with self.assertRaises(HTTPError) as denied:
            urlopen(Request(base + "/api/summary", data=b"{}", method="POST"))
        self.assertEqual(denied.exception.code, 405)
        with self.assertRaises(HTTPError) as denied:
            urlopen(base + "/api/reviews?topic=not-a-topic")
        self.assertEqual(denied.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

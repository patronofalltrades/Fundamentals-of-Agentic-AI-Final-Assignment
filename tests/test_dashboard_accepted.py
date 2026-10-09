"""SYNTHETIC tests: importing the private accepted-evidence handoff into a local dashboard database."""

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from dashboard.accepted_import import import_accepted
from dashboard.backend import SQLiteBackend
from dashboard.server import route
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256

SOURCE = [
    ("synthetic-1", "The app crashes every time I open my playlist on the train", "1", "0", "8.7", "2022-05-17 08:00:00"),
    ("synthetic-2", "Love the new radio mixes", "5", "3", "8.7", "2022-05-17 09:00:00"),
    ("synthetic-3", "Charged twice for family plan this month", "1", "0", "8.7", "2022-06-01 10:00:00"),
    ("synthetic-4", "Lyrics are out of sync on every song", "2", "0", "8.7", "2022-06-02 10:00:00"),
    ("synthetic-5", "   ", "3", "0", "8.7", "2022-06-03 10:00:00"),
    ("synthetic-6", "Podcasts stop after a minute", "1", "0", "8.7", "2022-06-04 10:00:00"),
    ("synthetic-7", "Not opened yet", "4", "0", "8.7", "2022-06-05 10:00:00"),
]


def accepted(i, topic, intent, severity, quote, entities, blocked=False):
    rid, text = SOURCE[i][0], SOURCE[i][1]
    findings = [{"category": "label_semantics", "summary": "synthetic"}] if blocked else []
    return {"review_id": rid, "source_position": i + 1,
            "source_sha256": row_sha256(list(SOURCE[i])),
            "source": dict(zip(SOURCE_FIELDS, SOURCE[i])),
            "labels": {"topic": topic, "intent": intent, "severity": severity, "sentiment": -0.4, "needs_review": False,
                       "model": "jev-synthetic", "confidence": {"topic": 0.9}, "input_tokens": 10, "output_tokens": 5},
            "evidence": {"evidence_quote": quote, "entities": entities},
            "provenance": {"label": {"config_sha256": "c" * 64, "kind": "jev_direct", "request_key": "k"},
                           "evidence": {"config_sha256": "e" * 64, "kind": "deepinfra_direct", "request_key": "k"}},
            "semantic_review": {"findings": findings, "human_review_required": blocked,
                                "representative_evidence_blocked_by_known_flags": blocked,
                                "sampled_in_first500_audit": False}}


def excluded(i, status, reason, position=True):
    item = {"review_id": SOURCE[i][0], "source_sha256": row_sha256(list(SOURCE[i])), "status": status, "reason": reason,
            "request_key": "k"}
    if position:
        item["source_position"] = i + 1
    return item


class AcceptedImportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.csv = self.tmp / "source.csv"
        with self.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(SOURCE_FIELDS)
            w.writerows(SOURCE)
        self.handoff = {
            "schema_version": "spotify-accepted100k-dashboard-handoff-v1",
            "scope": "development_source_reviews_only",
            "source_file_sha256": file_sha256(str(self.csv)),
            "coverage": {"selected_source_rows": 7, "accepted_rows": 4, "excluded_rows": 3, "pending_rows": 1,
                         "in_flight_rows": 0, "known_semantic_flags_excluded_from_representative_evidence": 1},
            "records": [
                accepted(0, "playback", "complaint", 4, "crashes every time I open my playlist", ["playlist"]),
                accepted(1, "other", "praise", 1, "Love the new radio mixes", []),
                accepted(2, "billing", "complaint", 5, "Charged twice", ["family plan"], blocked=True),
                accepted(3, "playback", "complaint", 3, "out of sync", ["Lyrics"]),
            ],
            "excluded": [
                excluded(4, "empty_text", "empty source text"),
                excluded(5, "quarantined", "ValidationError: evidence quote must be a nonblank exact source substring",
                         position=False),
                excluded(6, "eligible_or_awaiting_label", "untouched source row"),
            ],
            "request_metadata": [{"stage": "jev", "status": "succeeded"}],
            "cost_nusd": {}, "semantic_overlay": {"not_human_accuracy": True},
        }

    def run_import(self, handoff=None, name="dash.db", digest=None):
        path = self.tmp / ("handoff-%s.json" % name)
        path.write_text(json.dumps(handoff or self.handoff))
        db = str(self.tmp / name)
        manifest = import_accepted(str(path), str(self.csv), db, digest or file_sha256(str(path)), now="2026-10-10T00:00:00+00:00")
        return manifest, db

    def get(self, db, path, query=""):
        status, _, body = route(lambda: SQLiteBackend(db), "GET", path, query)
        return status, json.loads(body), body.decode()

    def test_states_counts_links_and_exclusions(self):
        manifest, db = self.run_import()
        self.assertEqual(manifest["state_counts"], {"accepted": 4, "quarantined": 1, "unresolved": 0, "empty": 1, "pending": 1})
        self.assertEqual(manifest["representative_evidence_exclusions"], 1)
        self.assertEqual(manifest["imported_at"], "2026-10-10T00:00:00+00:00")
        self.assertNotIn(str(self.tmp), json.dumps(manifest))

        _, s, _ = self.get(db, "/api/summary")
        self.assertEqual(s["states"], manifest["state_counts"])
        self.assertEqual(s["coverage"]["completed_rows"], 4)
        self.assertEqual(sum(s["raw_labels"]["intent"].values()), 4)  # accepted rows only
        self.assertEqual(sum(s["trends"]["reviews"]), 4)
        self.assertEqual(s["representative_exclusions"], 1)
        self.assertNotIn("frozen_manifest_sha256", s["import"])

        _, reviews, _ = self.get(db, "/api/reviews", "limit=50")
        self.assertEqual((reviews["total"], reviews["excluded_blocked"]), (3, 1))
        self.assertNotIn(2, [i["row_index"] for i in reviews["items"]])

        expected = {0: "accepted", 2: "accepted", 4: "empty", 5: "quarantined", 6: "pending"}
        for row, state in expected.items():
            status, detail, _ = self.get(db, "/api/reviews/%d" % row)
            self.assertEqual((status, detail["state"]), (200, state), row)
            self.assertEqual("topic" in detail, state == "accepted", row)
        self.assertTrue(self.get(db, "/api/reviews/2")[1]["representative_blocked"])
        self.assertIn("not a model failure", self.get(db, "/api/reviews/6")[1]["reason"])
        self.assertEqual(self.get(db, "/api/reviews/99")[0], 404)

    def test_api_never_returns_source_text(self):
        _, db = self.run_import()
        bodies = "".join(self.get(db, p, q)[2] for p, q in [("/api/summary", ""), ("/api/reviews", "limit=50"),
                                                             ("/api/evals", "")] +
                         [("/api/reviews/%d" % i, "") for i in range(7)])
        self.assertNotIn(SOURCE[0][1], bodies)  # its quote is a strict substring
        self.assertNotIn(SOURCE[2][5], bodies)  # timestamps stay private too

    def test_gates_stop_before_writing(self):
        def mutate(fn):
            h = copy.deepcopy(self.handoff)
            fn(h)
            return h
        cases = {
            "schema": mutate(lambda h: h.update(schema_version="other")),
            "duplicate": mutate(lambda h: h["excluded"].append(dict(h["excluded"][0]))),
            "partition": mutate(lambda h: h["excluded"].pop()),
            "unknown state": mutate(lambda h: h["excluded"][1].update(status="lost")),
            "source hash": mutate(lambda h: h["records"][1].update(source_sha256="0" * 64)),
            "position": mutate(lambda h: h["records"][1].update(source_position=3)),
            "quote": mutate(lambda h: h["records"][0]["evidence"].update(evidence_quote="not in the review")),
            "entity": mutate(lambda h: h["records"][0]["evidence"].update(entities=["play"])),
            "blocked count": mutate(lambda h: h["coverage"].update(known_semantic_flags_excluded_from_representative_evidence=2)),
            "blocked lacks finding": mutate(lambda h: h["records"][2]["semantic_review"].update(findings=[])),
            "pending count": mutate(lambda h: h["coverage"].update(pending_rows=0)),
            "csv hash": mutate(lambda h: h.update(source_file_sha256="0" * 64)),
        }
        for name, handoff in cases.items():
            with self.assertRaises(ValueError, msg=name):
                self.run_import(handoff, name=name.replace(" ", "-") + ".db")
            self.assertFalse((self.tmp / (name.replace(" ", "-") + ".db")).exists(), name)
        with self.assertRaises(ValueError):
            self.run_import(name="digest.db", digest="0" * 64)
        self.run_import(name="once.db")
        with self.assertRaises(ValueError):  # never overwrites an existing database
            self.run_import(name="once.db")


if __name__ == "__main__":
    unittest.main()

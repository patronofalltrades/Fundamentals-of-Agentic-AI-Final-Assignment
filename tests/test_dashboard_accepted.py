"""SYNTHETIC tests: importing the private accepted-evidence handoff into a local dashboard database."""

import copy
import csv
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dashboard.accepted_import import import_accepted
from dashboard.backend import SQLiteBackend
from dashboard.public_boundary import MAX_EXCERPT_WORDS, SHORTENED_MARK, has_personal_info, reason_category
from dashboard.server import route
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256

SOURCE = [
    ("synthetic-1", "The app crashes every time I open my playlist on the train", "1", "0", "8.7", "2022-05-17 08:00:00"),
    ("synthetic-2", "I love the new radio mixes", "5", "3", "8.7", "2022-05-17 09:00:00"),
    ("synthetic-3", "Charged twice for family plan this month", "1", "0", "8.7", "2022-06-01 10:00:00"),
    ("synthetic-4", "Lyrics are out of sync on every song", "2", "0", "8.7", "2022-06-02 10:00:00"),
    ("synthetic-5", "   ", "3", "0", "8.7", "2022-06-03 10:00:00"),
    ("synthetic-6", "Podcasts stop after a minute", "1", "0", "8.7", "2022-06-04 10:00:00"),
    ("synthetic-7", "Not opened yet", "4", "0", "8.7", "2022-06-05 10:00:00"),
    ("synthetic-8", " ".join(["shuffle keeps repeating the same five songs"] * 5), "2", "0", "8.7", "2022-06-06 10:00:00"),
    ("synthetic-9", "Write to someone@example.com because the app logs me out", "1", "0", "8.7", "2022-06-07 10:00:00"),
    ("synthetic-10", "my account was fixed by Quenby today", "5", "0", "8.7", "2022-06-08 10:00:00"),
]
LONG = SOURCE[7][1]  # 35 words


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
            "coverage": {"selected_source_rows": 10, "accepted_rows": 7, "excluded_rows": 3, "pending_rows": 1,
                         "in_flight_rows": 0, "known_semantic_flags_excluded_from_representative_evidence": 1},
            "records": [
                accepted(0, "playback", "complaint", 4, "crashes every time I open my playlist", ["playlist"]),
                accepted(1, "other", "praise", 1, "love the new radio mixes", []),
                accepted(2, "billing", "complaint", 5, "Charged twice", ["family plan"], blocked=True),
                accepted(3, "playback", "complaint", 3, "out of sync", ["Lyrics"]),
                accepted(7, "playback", "complaint", 2, LONG, []),
                accepted(8, "access", "complaint", 4, SOURCE[8][1], []),
                accepted(9, "support", "praise", 1, "fixed by Quenby", []),  # a possible name
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

    def bodies(self, db):
        """Every public response a visitor can reach: summary, lists, search, details, issues and evals."""
        _, page, body = self.get(db, "/api/reviews", "limit=50")
        out = [body] + [self.get(db, p, q)[2] for p, q in [
            ("/api/summary", ""), ("/api/reviews", "q=crash"), ("/api/reviews", "topic=playback"),
            ("/api/issues", ""), ("/api/evals", ""), ("/api/claims", ""), ("/api/memo", "")]]
        out += [self.get(db, "/api/reviews/" + item["ref"])[2] for item in page["items"]]
        return out

    def test_states_counts_and_trends(self):
        manifest, db = self.run_import()
        self.assertEqual(manifest["state_counts"], {"accepted": 7, "quarantined": 1, "unresolved": 0, "empty": 1, "pending": 1})
        self.assertEqual(manifest["imported_at"], "2026-10-10T00:00:00+00:00")
        self.assertNotIn(str(self.tmp), json.dumps(manifest))
        _, s, _ = self.get(db, "/api/summary")
        self.assertEqual(s["states"], manifest["state_counts"])
        self.assertEqual(s["coverage"]["completed_rows"], 7)
        self.assertEqual(sum(s["raw_labels"]["intent"].values()), 7)  # accepted rows only
        self.assertEqual(sum(s["trends"]["reviews"]), 7)
        self.assertNotIn("frozen_manifest_sha256", s["import"])

    def test_public_records_use_opaque_references_only(self):  # acceptance test 1
        _, db = self.run_import()
        _, page, _ = self.get(db, "/api/reviews", "limit=50")
        refs = [item["ref"] for item in page["items"]]
        self.assertEqual(len(refs), 4)  # 7 accepted - 1 flagged - 2 with possible personal information
        self.assertTrue(all(re.fullmatch(r"r[0-9a-f]{16}", r) for r in refs))
        for row in range(len(SOURCE) + 2):
            self.assertEqual(self.get(db, "/api/reviews/%d" % row)[0], 404, row)  # no numeric route
        self.assertEqual(self.get(db, "/api/reviews/r" + "0" * 16)[0], 404)
        _, again = self.run_import(name="again.db")
        _, other, _ = self.get(again, "/api/reviews", "limit=50")
        self.assertFalse(set(refs) & {i["ref"] for i in other["items"]})  # random, not derived from the row
        private = [r[0] for r in sqlite3.connect(db).execute("SELECT ref FROM public_example")]
        self.assertEqual(sorted(private), sorted(refs))
        for body in self.bodies(db):
            for rid, *rest in SOURCE:
                self.assertNotIn(rid, body)
                self.assertNotIn(row_sha256([rid] + rest), body)
            for key in ('"row_index"', '"source_sha256"', '"review_id"', '"source_position"'):
                self.assertNotIn(key, body)

    def test_excerpts_are_bounded_marked_and_screened(self):  # acceptance test 2
        _, db = self.run_import()
        _, page, _ = self.get(db, "/api/reviews", "limit=50")
        for item in page["items"]:
            words = item["excerpt"].split()
            self.assertLessEqual(len(words) - item["shortened"], MAX_EXCERPT_WORDS)
            self.assertEqual(words[-1] == SHORTENED_MARK, item["shortened"])
            self.assertFalse(has_personal_info(item["excerpt"]))
        long = [i for i in page["items"] if i["shortened"]]
        self.assertEqual(len(long), 1)
        self.assertTrue(LONG.startswith(long[0]["excerpt"][:-2]))
        self.assertEqual(page["excluded_personal_info"], 2)
        self.assertTrue(has_personal_info("Mark.Waudby"))
        self.assertFalse(has_personal_info("Great app, love it", {"great": 9, "love": 9}))
        self.assertTrue(has_personal_info("Thanks Waudby", {"thanks": 9}))
        bodies = "".join(self.bodies(db))
        self.assertNotIn(LONG, bodies)  # the full quote stays private
        self.assertNotIn("someone@example.com", bodies)
        self.assertNotIn("Quenby", bodies)
        self.assertNotIn(SOURCE[0][1], bodies)  # review text and timestamps stay private
        self.assertNotIn(SOURCE[2][5], bodies)
        saved = sqlite3.connect(db).execute("SELECT evidence_quote FROM classifications WHERE row_index=7").fetchone()[0]
        self.assertEqual(saved, LONG)  # the private exact quote is unchanged and still validates
        validate_evidence(LONG, {"evidence_quote": saved, "entities": []})
        self.assertEqual(self.get(db, "/api/reviews", "q=five songs")[1]["total"], 1)
        self.assertEqual(self.get(db, "/api/reviews", "q=logs me out")[1]["total"], 0)

    def test_nonaccepted_rows_only_as_category_counts(self):  # acceptance test 3
        _, db = self.run_import()
        _, s, _ = self.get(db, "/api/summary")
        self.assertEqual(s["reason_categories"], {"empty": {"empty_text": 1}, "pending": {"awaiting_label": 1},
                                                  "quarantined": {"evidence_quote_check_failed": 1}})
        bodies = "".join(self.bodies(db))
        for raw in ("ValidationError", "nonblank exact source substring", "untouched source row", "empty source text",
                    "eligible_or_awaiting_label", "source_state"):
            self.assertNotIn(raw, bodies)
        self.assertEqual(reason_category("uncertain_direct", "request delivery unresolved"), "delivery_unconfirmed")
        self.assertEqual(reason_category("quarantined", "missing source ID"), "batch_id_check_failed")
        self.assertEqual(reason_category("prior_uncertain_exact_text", "x"), "repeat_of_unresolved_text")

    def test_flagged_records_counted_but_never_public(self):  # acceptance test 4
        manifest, db = self.run_import()
        self.assertEqual(manifest["representative_evidence_exclusions"], 1)
        _, s, _ = self.get(db, "/api/summary")
        self.assertEqual(s["states"]["accepted"], 7)  # the flagged record stays in the processing total
        self.assertEqual(s["representative_exclusions"], 1)
        self.assertEqual(s["import"]["issue_candidates"],
                         {"contract_baseline": 5, "public_projection": 4, "flagged_excluded": 1})
        self.assertNotIn("Charged twice", "".join(self.bodies(db)))
        self.assertEqual(self.get(db, "/api/reviews", "topic=billing")[1]["total"], 0)

    def test_issue_ranking_pending_then_recomputed_without_flags(self):  # acceptance test 5
        _, db = self.run_import()
        _, issues, _ = self.get(db, "/api/issues")
        self.assertEqual((issues["status"], issues["items"]), ("pending", []))
        self.assertEqual(self.get(db, "/api/recommendations")[1]["status"], "pending")
        conn = sqlite3.connect(db)
        config = conn.execute("SELECT DISTINCT config_hash FROM record_state").fetchone()[0]
        with conn:  # a synthetic saved run: row 2 is flagged and must not count
            conn.execute("INSERT INTO analysis_run (run_id, source_sha256, config_hash, grouping_status, verifier_status, "
                         "recommendation_status) VALUES ('run-1', 's', ?, 'saved', 'pending', 'pending')", (config,))
            conn.executemany("INSERT INTO issue VALUES ('run-1', ?, ?)", [("I2", "Sync"), ("I1", "Crashes"), ("I4", "Playlists"), ("I3", "Billing")])
            conn.executemany("INSERT INTO issue_membership VALUES ('run-1', ?, ?)",
                             [("I1", 0), ("I1", 7), ("I2", 3), ("I2", 7), ("I3", 2), ("I3", 8), ("I4", 0)])
        conn.close()
        _, issues, _ = self.get(db, "/api/issues")
        got = [(i["issue_id"], i["priority_score"], i["review_count"]) for i in issues["items"]]
        # I1 = 4+2 and I2 = 3+2. I3 = 4 only: flagged row 2 (severity 5) is left out. I3 and I4 tie on 4: issue ID order.
        self.assertEqual(got, [("I1", 6, 2), ("I2", 5, 2), ("I3", 4, 1), ("I4", 4, 1)])
        scores = [i["priority_score"] for i in issues["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual({i["issue_id"] for i in issues["items"]}, {"I1", "I2", "I3", "I4"})  # no fabricated issues
        examples = self.get(db, "/api/issues/I3")[1]["reviews"]["items"]
        self.assertEqual(examples, [])  # row 8 has personal information; row 2 is flagged

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

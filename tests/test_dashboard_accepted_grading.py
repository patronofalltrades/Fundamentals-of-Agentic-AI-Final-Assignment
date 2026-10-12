"""SYNTHETIC tests: loading the pipeline's grading folder into an accepted-evidence database."""

import csv
import json
import sqlite3
import unittest

from dashboard.accepted_grading import catalog_from
from dashboard.backend import SQLiteBackend
from dashboard.grading_import import claims_from, load_grading, rank
from dashboard.server import _provisional_claims_match
from spotify_pipeline.contract import file_sha256

from tests import test_dashboard_accepted as base

SOURCE = base.SOURCE

CATALOG = {"catalog_id": "synthetic-catalog", "issues": [
    {"issue_id": "PLY-FAIL", "title": "Playback fails or stops"},
    {"issue_id": "BIL-CHARGE", "title": "Incorrect or continuing charge"},
    {"issue_id": "ACC-LOGIN", "title": "Sign-in failure"},
    {"issue_id": "CAT-LYRICS", "title": "Lyrics unavailable"}]}
# Candidates in the fixture: rows 0, 3, 7 (playback), 2 (billing, flagged) and 8 (access).
MEMBERSHIP = [("PLY-FAIL", "synthetic-1"), ("PLY-FAIL", "synthetic-4"), ("PLY-FAIL", "synthetic-8"),
              ("BIL-CHARGE", "synthetic-3"), ("ACC-LOGIN", "synthetic-9")]


class AcceptedGradingTests(unittest.TestCase):
    setUp = base.AcceptedImportTests.setUp
    run_import = base.AcceptedImportTests.run_import
    get = base.AcceptedImportTests.get
    bodies = base.AcceptedImportTests.bodies

    def test_provisional_ledger_requires_exact_claim_fields(self):
        saved = [{"claim_id": "claim-0001-complaint_count", "issue_id": "USE-ADS",
                  "metric": "complaint_count", "value": "5197"}]
        line = "- claim-0001-complaint_count: USE-ADS complaint_count = 5197\n"
        self.assertTrue(_provisional_claims_match(line, saved))
        self.assertFalse(_provisional_claims_match(line, [{**saved[0], "value": "0"}]))
        self.assertFalse(_provisional_claims_match(line, [{**saved[0], "issue_id": "PLY-FAIL"}]))

    def records(self, corrections=None):
        out = {}
        for rec in self.handoff["records"]:
            lab, ev = rec["labels"], rec["evidence"]
            out[rec["review_id"]] = {
                "review_id": rec["review_id"], "source_sha256": rec["source_sha256"], "status": "completed",
                "topic": lab["topic"], "intent": lab["intent"], "sentiment": lab["sentiment"],
                "severity": lab["severity"], "entities": ev["entities"], "evidence_quote": ev["evidence_quote"],
                "needs_review": lab["needs_review"], "label_config": "synthetic"}
        for rec in self.handoff["excluded"]:
            out[rec["review_id"]] = {"review_id": rec["review_id"], "source_sha256": rec["source_sha256"],
                                     "status": "quarantined", "reason": "not accepted"}
        for rid, changes in (corrections or {}).items():
            out[rid].update(changes)
        return out

    def folder(self, name="grading", membership=MEMBERSHIP, corrections=None, declared=None, memo=None,
               ranking=None, run=None):
        root = self.tmp / name
        root.mkdir()
        records = self.records(corrections)
        (root / "run.json").write_text(json.dumps(dict({
            "version": "synthetic", "analysis_count": len(SOURCE), "analysis_sha256": file_sha256(str(self.csv)),
            "classification_input_fields": ["review_text"], "allow_multi_issue": False,
            "human_label_corrections": sorted(corrections or {}) if declared is None else declared}, **(run or {}))))
        (root / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records.values()))
        with (root / "membership.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["issue_id", "review_id"])
            w.writerows(membership)
        ranking = ranking or rank(membership, records)
        claims = claims_from(ranking)
        for file, fields, rows in (("ranking.csv", ["rank", "issue_id", "complaint_count", "severity_sum",
                                                     "mean_severity", "priority_score"], ranking),
                                   ("claims.csv", ["claim_id", "issue_id", "metric", "value"], claims)):
            with (root / file).open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
        lines = ["# Synthetic memo", ""] + ["- %s: %s" % (c["claim_id"], c["value"]) for c in claims]
        (root / "memo.md").write_text(memo if memo is not None else "\n".join(lines) + "\n")
        return str(root)

    def catalog(self):
        path = self.tmp / "catalog.json"
        if not path.exists():
            path.write_text(json.dumps(CATALOG))
        return catalog_from(str(path))

    def load(self, db, folder, **kw):
        with SQLiteBackend(db, readonly=False) as backend:
            return load_grading(backend, folder, catalog=kw.pop("catalog", self.catalog()), **kw)

    def test_loads_and_serves_public_and_baseline_rankings(self):
        _, db = self.run_import()
        result = self.load(db, self.folder())
        self.assertTrue(result["ranking_matches"])
        self.assertEqual(result["memo_claim_check"], "passed")
        self.assertEqual(result["issue_candidates"], {"contract_baseline": 5, "public_projection": 4, "flagged_excluded": 1})
        _, issues, _ = self.get(db, "/api/issues")
        self.assertEqual([(i["issue_id"], i["title"], i["review_count"], i["priority_score"]) for i in issues["items"]],
                         [("PLY-FAIL", "Playback fails or stops", 3, 9), ("ACC-LOGIN", "Sign-in failure", 1, 4)])
        self.assertEqual([(i["issue_id"], i["review_count"], i["priority_score"]) for i in issues["baseline"]],
                         [("PLY-FAIL", 3, 9), ("BIL-CHARGE", 1, 5), ("ACC-LOGIN", 1, 4)])
        self.assertEqual(issues["flagged_members_excluded"], 1)
        _, s, _ = self.get(db, "/api/summary")
        self.assertEqual(s["analysis"]["grouping"], "accepted")
        self.assertEqual(s["top_issue"]["issue_id"], "PLY-FAIL")
        self.assertEqual(s["import"]["issue_candidates"]["contract_baseline"], 5)
        self.assertEqual(s["import"]["issue_import"]["catalog_sha256"], self.catalog()["sha256"])
        self.assertEqual(self.get(db, "/api/memo")[1]["status"], "claims_checked")
        _, detail, _ = self.get(db, "/api/issues/PLY-FAIL")
        self.assertTrue(all(set(r) >= {"ref", "excerpt"} and "row_index" not in r for r in detail["reviews"]["items"]))
        self.assertEqual(self.get(db, "/api/issues/BIL-CHARGE")[0], 404)  # only flagged members: not public
        for body in self.bodies(db) + [self.get(db, "/api/issues/PLY-FAIL")[2]]:
            for rid, *_ in SOURCE:
                self.assertNotIn('"%s"' % rid, body)

    def test_checked_memo_action_is_an_advisory_recommendation(self):
        _, db = self.run_import()
        checked_claims = claims_from(rank(MEMBERSHIP, self.records()))
        memo = ("# Synthetic provisional memo\n\n"
                "Leading issue: PLY-FAIL.\n\n"
                "## recommended next action\n"
                "Review a targeted sample before deciding on a change.\n\n"
                "## checked claim ledger\n" +
                "\n".join("- %s: %s" % (c["claim_id"], c["value"]) for c in checked_claims) + "\n")
        self.load(db, self.folder(name="action", memo=memo))
        _, result, body = self.get(db, "/api/recommendations")
        self.assertEqual(result["status"], "provisional_from_checked_memo")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["issue_ids"], ["PLY-FAIL"])
        self.assertEqual(result["items"][0]["claim_ids"],
                         ["claim-0001-complaint_count", "claim-0001-severity_sum"])
        self.assertNotIn("synthetic-1", body)
        self.assertEqual(self.get(db, "/api/summary")[1]["analysis"]["recommendations"],
                         "provisional_from_checked_memo")

    def test_declared_correction_is_applied_everywhere(self):
        _, db = self.run_import()
        before = self.get(db, "/api/summary")[1]
        refs = {r[0] for r in sqlite3.connect(db).execute("SELECT ref FROM public_example")}
        change = {"synthetic-4": {"intent": "praise", "evidence_quote": "out of sync on every song"}}
        members = [m for m in MEMBERSHIP if m[1] != "synthetic-4"]
        result = self.load(db, self.folder(membership=members, corrections=change))
        self.assertEqual(result["human_label_corrections"], 1)
        self.assertEqual(result["issue_candidates"]["contract_baseline"], 4)
        s = self.get(db, "/api/summary")[1]
        self.assertEqual(s["raw_labels"]["intent"]["praise"], before["raw_labels"]["intent"]["praise"] + 1)
        self.assertEqual(sum(s["trends"]["complaints"]), sum(before["trends"]["complaints"]) - 1)
        self.assertEqual(s["import"]["public_examples"]["public"], before["import"]["public_examples"]["public"])
        _, found, _ = self.get(db, "/api/reviews", "q=every song")
        self.assertEqual([i["excerpt"] for i in found["items"]], ["out of sync on every song"])
        self.assertIn(found["items"][0]["ref"], refs)  # the public reference is kept
        _, issues, _ = self.get(db, "/api/issues")
        self.assertEqual(issues["items"][0]["priority_score"], 6)

    def test_undeclared_or_invalid_corrections_are_refused(self):
        _, db = self.run_import()
        change = {"synthetic-4": {"severity": 5}}
        for kw, message in (({"corrections": change, "declared": []}, "do not match"),
                            ({"declared": ["synthetic-4"]}, "do not match"),
                            ({"corrections": {"synthetic-4": {"evidence_quote": "not in the text"}}}, "quote"),
                            ({"corrections": {"synthetic-4": {"topic": "lyrics"}}}, "invalid")):
            with self.subTest(message=message, kw=sorted(kw)):
                with self.assertRaisesRegex(ValueError, message):
                    self.load(db, self.folder(name="g%d" % id(kw), **kw))
        self.assertIsNone(sqlite3.connect(db).execute("SELECT * FROM analysis_run").fetchone())

    def test_membership_must_equal_the_candidates(self):
        _, db = self.run_import()
        for name, members in (("missing", MEMBERSHIP[:-1]),
                              ("praise", MEMBERSHIP + [("PLY-FAIL", "synthetic-2")]),
                              ("twice", MEMBERSHIP + [("ACC-LOGIN", "synthetic-1")])):
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, "membership"):
                    self.load(db, self.folder(name=name, membership=members))

    def test_ranking_catalog_and_repeat_gates(self):
        _, db = self.run_import()
        records = self.records()
        wrong = rank(MEMBERSHIP, records)
        wrong[0] = dict(wrong[0], severity_sum="10", priority_score="10")
        with self.assertRaisesRegex(ValueError, "ranking.csv differs"):
            self.load(db, self.folder(name="wrong", ranking=wrong))
        other = [("PLY-OTHER", rid) if issue == "PLY-FAIL" else (issue, rid) for issue, rid in MEMBERSHIP]
        with self.assertRaisesRegex(ValueError, "not in the catalog"):
            self.load(db, self.folder(name="other", membership=other))
        with self.assertRaisesRegex(ValueError, "allow_multi_issue"):
            self.load(db, self.folder(name="multi", run={"allow_multi_issue": True}))
        self.load(db, self.folder(name="ok"))
        with self.assertRaisesRegex(ValueError, "already holds an analysis run"):
            self.load(db, self.folder(name="again"))

    def test_memo_is_checked_as_public_text(self):
        _, db = self.run_import()
        long_quote = '"%s"' % " ".join(["word"] * 31)
        for name, memo, message in (("id", "See synthetic-6 for detail.\n", "review ID"),
                                    ("email", "Contact someone@example.com.\n", "email"),
                                    ("link", "See https://example.com/x.\n", "link"),
                                    ("quote", "A user wrote %s.\n" % long_quote, "quotes more than")):
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, message):
                    self.load(db, self.folder(name=name, memo=memo))
        self.assertIsNone(sqlite3.connect(db).execute("SELECT * FROM analysis_run").fetchone())

    def test_folder_without_catalog_uses_issue_ids(self):
        _, db = self.run_import()
        with SQLiteBackend(db, readonly=False) as backend:
            result = load_grading(backend, self.folder())
        self.assertIsNone(result["catalog_sha256"])
        _, issues, _ = self.get(db, "/api/issues")
        self.assertEqual(issues["items"][0]["title"], "PLY-FAIL")  # no catalog: IDs as titles


if __name__ == "__main__":
    unittest.main()

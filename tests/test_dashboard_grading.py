"""SYNTHETIC tests: loading the pipeline's grading folder into the dashboard."""

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import bundle
from dashboard.backend import SQLiteBackend
from dashboard.grading_import import claims_from, load_grading, memo_claim_check, rank
from dashboard.server import route
from tests.test_dashboard_vercel import build_dashboard_copy


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def get(db, path):
    path, _, query = path.partition("?")
    status, _, body = route(lambda: SQLiteBackend(db), "GET", path, query)
    return status, json.loads(body)


class GradingImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.copy = build_dashboard_copy(self.temp.name)
        with SQLiteBackend(self.copy) as b:
            self.source = b.execute("SELECT value FROM meta WHERE key='file_sha256'").fetchone()[0]
            self.rows = {r[0]: {"row_sha256": r[1], "intent": r[2], "severity": r[3], "topic": r[4]} for r in b.execute(
                "SELECT r.review_id, r.row_sha256, c.intent, c.severity, c.topic FROM records r "
                "JOIN classifications c USING(row_index)")}
        self.folder = self.tmp / "grading"
        self.write_folder()

    def write_folder(self, membership=None, ranking_edit=None, severity_edit=None, memo=None, gz=False):
        folder = self.folder
        folder.mkdir(exist_ok=True)
        for name in ("records.jsonl", "records.jsonl.gz"):
            (folder / name).unlink(missing_ok=True)
        (folder / "run.json").write_text(json.dumps({"version": "a5-audit-v1", "analysis_count": 3,
                                                     "analysis_sha256": self.source, "allow_multi_issue": False}))
        lines = []
        for rid, r in self.rows.items():
            severity = severity_edit.get(rid, r["severity"]) if severity_edit else r["severity"]
            lines.append(json.dumps({"review_id": rid, "source_sha256": r["row_sha256"], "status": "completed",
                                     "topic": r["topic"], "intent": r["intent"], "severity": severity}))
        data = "\n".join(lines) + "\n"
        if gz:
            with gzip.open(folder / "records.jsonl.gz", "wt", encoding="utf-8") as f:
                f.write(data)
        else:
            (folder / "records.jsonl").write_text(data)
        membership = membership or [("issue-playback", "synthetic-1"), ("issue-billing", "synthetic-2")]
        write_csv(folder / "membership.csv", ["issue_id", "review_id"],
                  [{"issue_id": i, "review_id": r} for i, r in sorted(membership)])
        labels = {rid: {"severity": r["severity"]} for rid, r in self.rows.items()}
        labels.update({rid: {"severity": 1} for _, rid in membership if rid not in labels})  # fixture only
        ranking = rank(membership, labels)
        if ranking_edit:
            ranking[0].update(ranking_edit)
        write_csv(folder / "ranking.csv", ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity",
                                           "priority_score"], ranking)
        claims = claims_from(rank(membership, labels))
        write_csv(folder / "claims.csv", ["claim_id", "issue_id", "metric", "value"], claims)
        if memo is None:
            memo = "# Memo\n" + "\n".join("- %s: %s [%s]" % (c["issue_id"], c["value"], c["claim_id"]) for c in claims)
        (folder / "memo.md").write_text(memo)
        return claims

    def count(self, table):
        with SQLiteBackend(self.copy) as b:
            return b.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]

    def test_loads_checks_ranking_and_serves_claims_and_memo(self):
        result = load_grading(SQLiteBackend(self.copy, readonly=False), str(self.folder),
                              issue_names={"issue-billing": "Billing charges"})
        self.assertEqual((result["issues"], result["memberships"], result["claims"]), (2, 2, 8))
        self.assertEqual((result["memo_claim_check"], result["ranking_matches"]), ("passed", True))
        issues = get(self.copy, "/api/issues")[1]["items"]
        self.assertEqual([(i["issue_id"], i["title"], i["priority_score"]) for i in issues],
                         [("issue-billing", "Billing charges", 4), ("issue-playback", "issue-playback", 4)])
        detail = get(self.copy, "/api/issues/issue-billing")[1]
        self.assertEqual([c["claim_id"] for c in detail["claims"]][:1], ["claim-0001-complaint_count"])
        self.assertEqual(detail["reviews"]["total"], 1)
        memo = get(self.copy, "/api/memo")[1]
        self.assertEqual(memo["status"], "claims_checked")
        self.assertIn("[claim-0002-severity_sum]", memo["text"])
        self.assertEqual(get(self.copy, "/api/claims?issue_id=issue-playback")[1]["items"][0]["claim_id"],
                         "claim-0002-complaint_count")
        self.assertEqual(get(self.copy, "/api/summary")[1]["analysis"]["memo"], "claims_checked")
        with self.assertRaises(ValueError):  # saved runs are immutable
            load_grading(SQLiteBackend(self.copy, readonly=False), str(self.folder))

    def test_portable_database_and_gzip_records(self):
        bundle.export_bundle(self.copy, str(self.tmp / "bundle"))
        portable = str(self.tmp / "portable.db")
        with SQLiteBackend(portable, readonly=False) as b:
            bundle.load_bundle(b, str(self.tmp / "bundle"))
        self.write_folder(gz=True)
        load_grading(SQLiteBackend(portable, readonly=False), str(self.folder))
        self.assertEqual(get(portable, "/api/memo")[1]["status"], "claims_checked")
        self.assertEqual(len(get(portable, "/api/claims")[1]["items"]), 8)

    def test_mismatches_are_rejected_before_any_write(self):
        cases = [
            dict(ranking_edit={"severity_sum": "9"}),                 # ranking.csv not reproducible
            dict(severity_edit={"synthetic-1": 2}),                    # export holds a different run
            dict(membership=[("issue-praise", "synthetic-3")]),        # non-complaint member
            dict(membership=[("issue-x", "missing-id")]),              # unknown review
        ]
        for case in cases:
            self.write_folder(**case)
            with self.assertRaises((ValueError, KeyError), msg=str(case)):
                load_grading(SQLiteBackend(self.copy, readonly=False), str(self.folder))
            self.assertEqual(self.count("analysis_run"), 0, case)
        self.write_folder()
        run = json.loads((self.folder / "run.json").read_text())
        (self.folder / "run.json").write_text(json.dumps(dict(run, analysis_sha256="0" * 64)))
        with self.assertRaises(ValueError):
            load_grading(SQLiteBackend(self.copy, readonly=False), str(self.folder))
        self.assertEqual(self.count("analysis_run"), 0)

    def test_memo_without_every_claim_is_saved_but_flagged(self):
        self.write_folder(memo="Invest in billing. claim-0001-severity_sum is 4.")
        result = load_grading(SQLiteBackend(self.copy, readonly=False), str(self.folder))
        self.assertEqual(result["memo_claim_check"], "failed")
        self.assertEqual(get(self.copy, "/api/memo")[1]["status"], "claim_check_failed")

    def test_memo_check_rules(self):
        claims = [{"claim_id": "claim-0001-severity_sum", "value": "35"}]
        self.assertEqual(memo_claim_check("Usability 35 [claim-0001-severity_sum]", claims), "passed")
        self.assertEqual(memo_claim_check("Usability 34 [claim-0001-severity_sum]", claims), "failed")
        self.assertEqual(memo_claim_check("35 [claim-0001-severity_sum] and [claim-0009-x]", claims), "failed")
        self.assertEqual(memo_claim_check("  ", claims), "missing")


if __name__ == "__main__":
    unittest.main()

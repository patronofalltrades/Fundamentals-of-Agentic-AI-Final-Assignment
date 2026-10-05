"""Export tests plus the shared synthetic fixture (tiny CSV + run dir + fake chat) used by the
verify/group/memo tests. The end-to-end test asserts check_submission.audit() == "pass"."""
from __future__ import annotations

import csv
import gzip
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import check_submission as checker
from pipeline.context import ChatResult, StageContext
from pipeline.io import append_jsonl, read_jsonl
from pipeline.rowhash import FIELDS, row_sha

LABEL_CONFIG = "test/model:prompt-v1:schema-a5-v1"

# id, text, label (topic, intent, severity, entities) or None, special
ROWS = [
    ("r01", "The app keeps crashing every time I open it. Useless.", ("playback", "complaint", 4, ["crash"])),
    ("r02", "", None),
    ("r03", "Love it", ("other", "praise", 1, [])),
    ("r04", "Too many ads between every song, so annoying", ("usability", "complaint", 3, ["ads"])),
    ("r05", "Love it", "cache:r03"),
    ("r06", "I was charged twice for premium and no refund", ("billing", "complaint", 5, ["charge", "refund"])),
    ("r07", "Can't log in after the update", ("access", "complaint", 4, ["login", "update"])),
    ("r08", "Please add a sleep timer", ("usability", "request", 1, [])),
    ("r09", "Too many ads between every song, so annoying", "cache:r04"),
    ("r10", "zzqx", ("other", "unclear", 1, [])),  # quarantined in inv1, completed on resume
    ("r11", "Songs stop playing when the screen is off", ("playback", "complaint", 3, [])),
    ("r12", "I am cancelling, way too expensive now", ("billing", "cancellation", 3, ["price"])),
    ("r13", "My downloads disappeared after the update", ("downloads", "complaint", 4, ["download", "update"])),
    ("r14", "Search never finds the song I type", ("catalog", "complaint", 3, ["search"])),
]
INITIAL = ["r01", "r03", "r04", "r06"]
RESUME = ["r07", "r08", "r10", "r11", "r12", "r13", "r14"]


def csv_row(rid, text, i):
    return {"review_id": rid, "review_text": text, "review_rating": str(1 + i % 5), "review_likes": str(i),
            "app_version": "8.8.%d" % i if i % 3 else "", "review_timestamp": "2023-01-%02d 10:00:00" % (1 + i)}


class FakeChat:
    """Offline chat with the ChatResult shape. ``mode`` per role: 'good', 'garbage', 'fail_first', 'bad_cite'."""
    model = "fake-chat-1"
    provider = "fake"

    def __init__(self, modes=None, verify_labels=None):
        self.modes = dict(modes or {})
        self.verify_labels = verify_labels or {}
        self.calls = []
        self.n = 0

    def complete(self, messages, *, max_tokens, temperature=0.0, response_format=None):
        system, user = messages[0]["content"], messages[-1]["content"]
        role = "verify" if "independent reviewer" in system else "group" if "issue clusters" in system else "memo"
        self.calls.append({"role": role, "messages": messages, "max_tokens": max_tokens})
        self.n += 1
        mode = self.modes.get(role, "good")
        if mode == "fail_first" and sum(c["role"] == role for c in self.calls) == 1:
            raise RuntimeError("simulated 500")
        if mode == "garbage":
            text = "not json at all"
        elif role == "verify":
            batch = json.loads(user.split("REVIEWS:\n", 1)[1])
            text = json.dumps({b["review_id"]: self.verify_labels.get(
                b["review_id"], {"topic": "other", "intent": "complaint", "severity": 2, "needs_review": False})
                for b in batch})
        elif role == "group":
            payload = json.loads(user)
            items = [{"issue_id": i["issue_id"], "name": "Named " + i["issue_id"], "description": "desc"}
                     for i in payload["issues"]]
            if mode == "dupes":
                items += [{"issue_id": "made.up", "name": "x", "description": ""}, dict(items[0])]
            text = json.dumps({"issues": items})
        else:
            inputs = json.loads(user.split("\n", 1)[1])
            if mode == "bad_cite":
                text = "Invest in playback [C999-severity_sum]."
            else:
                t = inputs["top_issues"][0]
                text = "# Memo\n\nInvest in %s: severity_sum %s [%s]." % (
                    t["area"], t["metrics"]["severity_sum"]["value"], t["metrics"]["severity_sum"]["claim_id"])
        return ChatResult(text=text, request_id="fake-%d" % self.n, model=self.model, input_tokens=100 + self.n,
                          output_tokens=20)


def build_fixture(base: Path):
    """Write data.csv and a run dir with initial/resume enrich calls, cache reuse and quarantines."""
    base.mkdir(parents=True, exist_ok=True)
    csv_path = base / "data.csv"
    rows = [csv_row(rid, text, i) for i, (rid, text, _) in enumerate(ROWS)]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    by_id = {r["review_id"]: r for r in rows}
    labels = {rid: lab for rid, _, lab in ROWS}
    run = base / "run"
    (run / "checkpoints").mkdir(parents=True)

    def completed(rid, cache_from=None):
        topic, intent, sev, ents = labels[cache_from or rid]
        rec = {"review_id": rid, "source_sha256": row_sha(by_id[rid]), "status": "completed", "topic": topic,
               "intent": intent, "sentiment": -0.5 if intent != "praise" else 0.8, "severity": sev,
               "entities": ents, "evidence_quote": by_id[cache_from or rid]["review_text"],
               "needs_review": False, "label_config": LABEL_CONFIG}
        if cache_from:
            rec["cache_source_id"] = cache_from
        return rec

    def call(ids, phase, inv, outcome="succeeded", n=0):
        return {"request_id": "enrich-%s-%d" % (inv, n), "role": "enrich", "review_ids": ids, "model": "test-model",
                "phase": phase, "outcome": outcome, "label_config": LABEL_CONFIG,
                "input_tokens": 0 if outcome == "failed" else 50 * len(ids), "output_tokens": 10 * len(ids),
                "invocation_id": inv, "attempt": 1, "error": None if outcome == "succeeded" else "bad output"}

    recs = run / "records.jsonl"
    append_jsonl(recs, {"review_id": "r02", "source_sha256": row_sha(by_id["r02"]), "status": "quarantined",
                        "reason": "empty_review_text"})
    append_jsonl(run / "calls.jsonl", [call(INITIAL, "initial", "inv1"),
                                       call(["r10"], "initial", "inv1", "failed", 1),
                                       call(["r10"], "initial", "inv1", "failed", 2)])
    append_jsonl(recs, [completed(r) for r in INITIAL] + [completed("r05", "r03")])
    append_jsonl(recs, {"review_id": "r10", "source_sha256": row_sha(by_id["r10"]), "status": "quarantined",
                        "reason": "invalid_model_output:bad json"})
    ck1 = sorted(INITIAL + ["r05"])
    (run / "checkpoints" / "inv1-start.json").write_text(json.dumps({"completed_ids": []}))
    (run / "checkpoints" / "inv1-end.json").write_text(json.dumps({"completed_ids": ck1}))
    append_jsonl(run / "invocations.jsonl", {"invocation_id": "inv1", "phase": "initial", "stop_reason": "max_batches"})

    append_jsonl(run / "calls.jsonl", [call(["r07"], "resume", "inv2", "failed", 1),
                                       call(RESUME, "resume", "inv2", n=3)])
    append_jsonl(recs, [completed(r) for r in RESUME] + [completed("r09", "r04")])
    ck2 = sorted(ck1 + RESUME + ["r09"])
    (run / "checkpoints" / "inv2-end.json").write_text(json.dumps({"completed_ids": ck2}))
    append_jsonl(run / "invocations.jsonl", {"invocation_id": "inv2", "phase": "resume", "stop_reason": "done"})
    return csv_path, run


def make_ctx(run: Path, csv_path: Path, chat=None, *, dry_run=False, config=None, phase="resume", extras=None):
    texts = {r["review_id"]: r["review_text"] for r in checker.csv_rows(csv_path)}
    records = {}
    for rec in read_jsonl(run / "records.jsonl"):
        records[rec["review_id"]] = rec
    cfg = {"verify": {"sample_fraction": 0.5, "min_items": 4, "max_items": 50}}
    cfg.update(config or {})
    return StageContext(run_dir=run, config=cfg, label_config=LABEL_CONFIG, phase=phase, invocation_id="inv2",
                        dry_run=dry_run, texts=texts, records=records, chat=chat,
                        log_call=lambda e: append_jsonl(run / "calls.jsonl", e), extras=dict(extras or {}))


def calls_of(run: Path, role=None):
    return [c for c in read_jsonl(run / "calls.jsonl") if role is None or c["role"] == role]


def run_downstream(ctx):
    from pipeline import group, memo, rank, verify
    return [verify.run(ctx), group.run(ctx), rank.run(ctx), memo.run(ctx)]


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="a5-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


class EndToEndAudit(TempDirCase):
    def _export_and_audit(self, use_gzip):
        from pipeline import export
        csv_path, run = build_fixture(self.tmp)
        ctx = make_ctx(run, csv_path, FakeChat())
        run_downstream(ctx)
        out = self.tmp / "grading"
        summary = export.export(run, csv_path, out, use_gzip=use_gzip)
        result = checker.audit(out, checker.reference(csv_path, csv_path))
        return csv_path, run, out, summary, result

    def test_audit_passes(self):
        csv_path, run, out, summary, result = self._export_and_audit(False)
        self.assertEqual(result["issue_counts"], {})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["coverage"]["valid_cache_reuses"], 2)
        self.assertEqual(result["coverage"]["quarantined"], 1)  # the empty text
        self.assertEqual(summary["missing"], [])
        # one line per CSV ID, in CSV order, grading fields only
        lines = [json.loads(l) for l in (out / "records.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["review_id"] for l in lines], [r[0] for r in ROWS])
        self.assertEqual(set(lines[0]), {"review_id", "source_sha256", "status", "topic", "intent", "sentiment",
                                         "severity", "entities", "evidence_quote", "needs_review", "label_config"})
        self.assertEqual(lines[4]["cache_source_id"], "r03")
        run_json = json.loads((out / "run.json").read_text())
        self.assertEqual(list(run_json), ["version", "analysis_count", "analysis_sha256",
                                          "classification_input_fields", "allow_multi_issue"])
        self.assertEqual(run_json["analysis_count"], len(ROWS))
        # calls keep extras
        self.assertIn("invocation_id", json.loads((out / "calls.jsonl").read_text().splitlines()[0]))

    def test_audit_passes_gzip_and_replaces_plain(self):
        from pipeline import export
        csv_path, run, out, summary, result = self._export_and_audit(False)
        export.export(run, csv_path, out, use_gzip=True)
        self.assertFalse((out / "records.jsonl").exists())
        self.assertFalse((out / "calls.jsonl").exists())
        with gzip.open(out / "records.jsonl.gz", "rt", encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), len(ROWS))
        result = checker.audit(out, checker.reference(csv_path, csv_path))
        self.assertEqual(result["status"], "pass", result["issue_counts"])
        # deterministic gzip bytes
        first = (out / "records.jsonl.gz").read_bytes()
        export.export(run, csv_path, out, use_gzip=True)
        self.assertEqual(first, (out / "records.jsonl.gz").read_bytes())

    def test_self_check_writes_report_and_caches_reference(self):
        from pipeline import export
        csv_path, run = build_fixture(self.tmp)
        run_downstream(make_ctx(run, csv_path, FakeChat()))
        out = self.tmp / "grading"
        export.export(run, csv_path, out)
        ref_path, report = self.tmp / ".local" / "ref.json", self.tmp / "self-check.json"
        res = export.self_check(out, csv_path, ref_path, report)
        self.assertEqual(res["status"], "pass", res["issue_counts"])
        self.assertTrue(ref_path.exists() and report.exists())
        mtime = ref_path.stat().st_mtime_ns
        export.self_check(out, csv_path, ref_path, report)
        self.assertEqual(mtime, ref_path.stat().st_mtime_ns)  # reused, not rebuilt


class ExportDetails(TempDirCase):
    def test_unresolved_quarantine_is_reported_by_checker(self):
        from pipeline import export
        csv_path, run = build_fixture(self.tmp)
        run_downstream(make_ctx(run, csv_path, FakeChat()))
        kept = [l for l in (run / "records.jsonl").read_text().splitlines()
                if not ('"r10"' in l and '"completed"' in l)]
        (run / "records.jsonl").write_text("\n".join(kept) + "\n")
        out = self.tmp / "g"
        export.export(run, csv_path, out)
        lines = {l["review_id"]: l for l in map(json.loads, (out / "records.jsonl").read_text().splitlines())}
        self.assertEqual(lines["r10"]["reason"], "invalid_model_output:bad json")
        result = checker.audit(out, checker.reference(csv_path, csv_path))
        # a non-empty quarantined review is accounted for but still counts as unfinished
        self.assertIn("unfinished_classification", result["issue_counts"])
        self.assertEqual(result["coverage"]["quarantined"], 2)

    def test_not_processed_latest_status_and_extras_dropped(self):
        from pipeline import export
        csv_path, run = build_fixture(self.tmp)
        rows = list(checker.csv_rows(csv_path))
        # r14: later quarantine must not override an earlier completed line; r13 gets an extra field
        append_jsonl(run / "records.jsonl", {"review_id": "r14", "source_sha256": "x", "status": "quarantined",
                                             "reason": "retries_exhausted:timeout"})
        recs = [json.loads(l) for l in (run / "records.jsonl").read_text().splitlines()]
        r13 = dict([r for r in recs if r["review_id"] == "r13"][-1], internal_score=0.9, cache_source_id=None)
        append_jsonl(run / "records.jsonl", r13)
        # drop r11 entirely from the run -> not_processed
        kept = [l for l in (run / "records.jsonl").read_text().splitlines() if '"r11"' not in l]
        (run / "records.jsonl").write_text("\n".join(kept) + "\n" + '{"review_id": "r1')  # torn tail
        out = self.tmp / "g"
        summary = export.export(run, csv_path, out)
        lines = {l["review_id"]: l for l in map(json.loads, (out / "records.jsonl").read_text().splitlines())}
        self.assertEqual(lines["r14"]["status"], "completed")
        self.assertNotIn("internal_score", lines["r13"])
        self.assertNotIn("cache_source_id", lines["r13"])
        self.assertEqual(lines["r11"], {"review_id": "r11", "source_sha256": row_sha(rows[10]),
                                        "status": "quarantined", "reason": "not_processed"})
        self.assertEqual(summary["records"]["not_processed"], 1)
        self.assertEqual(summary["checkpoint_before"]["source"], str(run / "checkpoints" / "inv1-end.json"))
        self.assertEqual(summary["checkpoint_after"]["source"], str(run / "checkpoints" / "inv2-end.json"))
        self.assertIn("membership.csv", summary["missing"])

    def test_explicit_checkpoints(self):
        from pipeline import export
        csv_path, run = build_fixture(self.tmp)
        p = self.tmp / "before.json"
        p.write_text(json.dumps({"completed_ids": ["r01"]}))
        export.export(run, csv_path, self.tmp / "g", checkpoint_before=p)
        self.assertEqual(json.loads((self.tmp / "g" / "checkpoint_before.json").read_text()), {"completed_ids": ["r01"]})

    def test_cli_runs(self):
        import export_grading
        csv_path, run = build_fixture(self.tmp)
        run_downstream(make_ctx(run, csv_path, FakeChat()))
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            rc = export_grading.main(["--run", str(run), "--csv", str(csv_path), "--out", str(self.tmp / "g"), "--gzip",
                                      "--self-check", "--reference", str(self.tmp / "ref.json"),
                                      "--self-check-out", str(self.tmp / "sc.json")])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads((self.tmp / "sc.json").read_text())["status"], "pass")


if __name__ == "__main__":
    unittest.main()

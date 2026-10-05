import contextlib
import gc
import io
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from tests import _paths  # noqa: F401
from tests.test_enrich import FakeClient
from tests.test_prepare import row, write_csv
import check_submission as checker
import run_pipeline
from pipeline import clients
from pipeline.clients import MockChat

CONFIG = {
    "label_config": "fake/v1:prompt-v1:schema-a5-v1",
    "client": {"provider": "typesafe", "api_key_env": "A5_TEST_NO_SUCH_KEY"},
    "chat": {"provider": "anthropic", "api_key_env": "A5_TEST_NO_SUCH_KEY"},
    "batching": {"max_reviews_per_request": 4, "size_by_tokens": False},
    "limits": {"workers": 1, "spend_cap_usd": 1.0, "progress_every_batches": 0},
}
NOISY = ("resume_snapshot_mismatch", "resume_call_evidence", "reprocessed_checkpoint", "invalid_cache_reuse",
         "unlogged_completed_records", "invalid_request_id", "unbounded_batch", "call_config_mismatch",
         "invalid_schema", "unsupported_quote", "duplicate_review_id", "source_mismatch", "invalid_run_phase",
         "invalid_call_ids", "invalid_usage", "unfinished_classification", "missing_records",
         "incorrect_empty_reason", "duplicate_checkpoint_id", "malformed_jsonl")


def make_rows():
    rows = [row("id%02d" % i, "Review %d: the app keeps crashing" % (i % 9)) for i in range(20)]
    rows.insert(5, row("empty1", "  "))
    return rows


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv = self.dir / "in.csv"
        write_csv(self.csv, make_rows())
        self.cfg = self.dir / "cfg.json"
        self.cfg.write_text(json.dumps(CONFIG))
        self.out = self.dir / "run"

    def tearDown(self):
        gc.collect()
        self.tmp.cleanup()

    def run_cli(self, *extra, client=None, hooks=None, out=None, cfg=None):
        argv = [str(self.csv), "--config", str(cfg or self.cfg), "--out", str(out or self.out), "--quiet"] + list(extra)
        h = {"skip_dotenv": True, "sleep": lambda s: None}
        if client is not None:
            h["enrich_client"] = client
        h.update(hooks or {})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = run_pipeline.main(argv, hooks=h)
        self.last_stderr = err.getvalue()
        return code

    def invocations(self, out=None):
        p = Path(out or self.out) / "invocations.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()]

    def calls(self, out=None):
        p = Path(out or self.out) / "calls.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def checkpoint(self, inv, which):
        return json.loads((self.out / inv["checkpoint_" + which]).read_text())["completed_ids"]

    def export_and_audit(self, before, after):
        """Minimal grading export (one record per CSV id) and the real checker audit."""
        g = self.dir / "grading"
        g.mkdir(exist_ok=True)
        latest = {}
        for line in (self.out / "records.jsonl").read_text().splitlines():
            r = json.loads(line)
            latest[r["review_id"]] = r
        with (g / "records.jsonl").open("w") as f:
            for r in checker.csv_rows(self.csv):
                f.write(json.dumps(latest[r["review_id"]]) + "\n")
        (g / "calls.jsonl").write_text((self.out / "calls.jsonl").read_text())
        (g / "checkpoint_before.json").write_text(json.dumps({"completed_ids": before}))
        (g / "checkpoint_after.json").write_text(json.dumps({"completed_ids": after}))
        ref = checker.reference(self.csv, self.csv)
        (g / "run.json").write_text(json.dumps({"version": checker.VERSION, "analysis_count": len(ref["rows"]),
                                                "analysis_sha256": ref["analysis_sha256"],
                                                "classification_input_fields": ["review_text"],
                                                "allow_multi_issue": False}))
        return checker.audit(g, ref)

    def test_interrupt_resume_and_checker_evidence(self):
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--max-batches", "1",
                                      client=FakeClient()), 0)
        second = FakeClient()
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", client=second), 0)
        inv1, inv2 = self.invocations()
        self.assertEqual((inv1["phase"], inv1["stop_reason"]), ("initial", "max_batches"))
        self.assertEqual((inv2["phase"], inv2["stop_reason"]), ("resume", "completed"))
        before, after = self.checkpoint(inv1, "end"), self.checkpoint(inv2, "end")
        self.assertEqual(before, self.checkpoint(inv2, "start"))
        self.assertTrue(before and set(before) < set(after))
        self.assertEqual(len(after), 20)
        resent = {i for c in second.calls for i in c}
        self.assertFalse(resent & set(before))
        for e in self.calls():
            if e["invocation_id"] == inv2["invocation_id"]:
                self.assertEqual(e["phase"], "resume")
                self.assertTrue(e["label_config"].startswith("mock:"))
        self.assertEqual(set(inv2["stage_seconds"]), set(run_pipeline.STAGES))
        self.assertIsNone(inv2["stage_seconds"]["verify"])
        self.assertIsInstance(inv2["stage_seconds"]["enrich"], float)
        self.assertIsInstance(inv2["wall_seconds"], float)
        result = self.export_and_audit(before, after)
        bad = {k: v for k, v in result["issue_counts"].items() if k in NOISY}
        self.assertEqual(bad, {}, result["examples"])
        self.assertEqual(result["coverage"]["valid_cache_reuses"], 11)
        self.assertEqual(result["coverage"]["quarantined"], 1)
        # A third invocation has nothing to do: zero enrich calls.
        third = FakeClient()
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", client=third), 0)
        self.assertEqual(third.calls, [])
        self.assertEqual(self.invocations()[-1]["counts"]["enrich_calls"], 0)

    def test_default_mock_client_dry_run(self):
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich"), 0)
        cfg = json.loads((self.out / "run_config.json").read_text())
        self.assertEqual(cfg["label_config"], "mock:" + CONFIG["label_config"])
        self.assertTrue(cfg["dry_run"])
        self.assertTrue(all(e["model"] == "mock" for e in self.calls()))

    def test_mock_guard_refuses_non_dry_run(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("A5_TEST_NO_SUCH_KEY", None)
            os.environ.pop("TYPESAFE_API_KEY", None)
            code = self.run_cli("--stages", "ingest,enrich")
        self.assertEqual(code, 4)
        self.assertIn("MockClient", self.last_stderr)
        self.assertFalse((self.out / "records.jsonl").exists())
        cfg = dict(CONFIG, client={"provider": "mock"})
        p = self.dir / "mockcfg.json"
        p.write_text(json.dumps(cfg))
        self.assertEqual(self.run_cli("--stages", "ingest,enrich", cfg=p), 4)
        self.assertEqual(self.run_cli("--stages", "ingest,enrich", "--dry-run", cfg=p), 0)

    def test_chat_guard_refuses_without_key(self):
        os.environ.pop("A5_TEST_NO_SUCH_KEY", None)
        with self.assertRaises(clients.MockGuardError):
            clients.build_chat(CONFIG, dry_run=False)
        self.assertIsInstance(clients.build_chat(CONFIG, dry_run=True), MockChat)
        with self.assertRaises(clients.ClientConfigError):
            clients.build_chat({"chat": {"provider": "nope"}}, dry_run=False)

    def test_mock_label_config_refused_for_real_runs(self):
        with self.assertRaises(clients.MockGuardError):
            clients.resolve_label_config({"label_config": "mock:x"}, dry_run=False)
        self.assertEqual(clients.resolve_label_config({"label_config": "mock:x"}, dry_run=True), "mock:x")

    def test_limit_refused_for_full_run_config(self):
        p = self.dir / "full.json"
        p.write_text(json.dumps(dict(CONFIG, full_run=True)))
        self.assertEqual(self.run_cli("--dry-run", "--limit", "5", cfg=p), 4)
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--limit", "5"), 0)
        self.assertEqual(json.loads((self.out / "run_config.json").read_text())["rows"], 5)

    def test_run_dir_config_mismatch_refused(self):
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--max-batches", "1"), 0)
        p = self.dir / "other.json"
        p.write_text(json.dumps(dict(CONFIG, label_config="fake/v2")))
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", cfg=p), 4)

    def test_warm_from(self):
        cold = self.dir / "cold"
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", out=cold, client=FakeClient()), 0)
        warm = self.dir / "warm"
        client = FakeClient()
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--warm-from", str(cold),
                                      out=warm, client=client), 0)
        self.assertEqual(client.calls, [])
        inv = self.invocations(warm)[-1]
        self.assertEqual(inv["phase"], "resume")
        self.assertEqual(inv["counts"]["enrich_calls"], 0)
        self.assertEqual(self.calls(warm), [])
        wf = json.loads((warm / "run_config.json").read_text())["warm_from"]
        self.assertEqual(wf["records_copied"], 20)
        self.assertEqual(wf["source_label_config"], "mock:" + CONFIG["label_config"])
        # Same command again in the same warm dir is fine (already seeded) and still makes no calls.
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--warm-from", str(cold),
                                      out=warm, client=client), 0)
        self.assertEqual(client.calls, [])
        # Different label_config is refused.
        p = self.dir / "other.json"
        p.write_text(json.dumps(dict(CONFIG, label_config="fake/v2")))
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--warm-from", str(cold),
                                      out=self.dir / "warm2", cfg=p), 4)
        self.assertIn("differs", self.last_stderr)

    def test_torn_records_line_then_resume(self):
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", "--max-batches", "2",
                                      client=FakeClient()), 0)
        with (self.out / "records.jsonl").open("a") as f:
            f.write('{"review_id":"id19","status":"comp')
        self.assertEqual(self.run_cli("--dry-run", "--stages", "ingest,enrich", client=FakeClient()), 0)
        lines = (self.out / "records.jsonl").read_text().splitlines()
        ids = {json.loads(l)["review_id"] for l in lines}  # every line parses
        self.assertEqual(len(ids), 21)

    def test_budget_stop_exit_code(self):
        p = self.dir / "cap.json"
        p.write_text(json.dumps(dict(CONFIG, limits=dict(CONFIG["limits"], spend_cap_usd=0.25,
                                                          reserve_usd_per_enrich_request=0.1))))
        code = self.run_cli("--dry-run", "--stages", "ingest,enrich", cfg=p, client=FakeClient())
        self.assertEqual(code, 2)
        inv = self.invocations()[-1]
        self.assertEqual(inv["stop_reason"], "budget")
        ledger = json.loads((self.out / "ledger.json").read_text())
        self.assertLessEqual(ledger["committed_usd"], 0.25)

    def test_client_error_exit_code(self):
        from labelling.model_client import ModelClientError

        def hook(n, r):
            raise ModelClientError("HTTP 402: credits")
        code = self.run_cli("--dry-run", "--stages", "ingest,enrich", client=FakeClient(hook))
        self.assertEqual(code, 3)
        self.assertIn("402", self.last_stderr)
        self.assertEqual(self.calls()[0]["outcome"], "failed")

    def test_sigint_style_stop(self):
        stop = threading.Event()
        code = self.run_cli("--dry-run", "--stages", "ingest,enrich", client=FakeClient(lambda n, r: stop.set()),
                            hooks={"stop_event": stop})
        self.assertEqual(code, 130)
        inv = self.invocations()[-1]
        self.assertEqual(inv["stop_reason"], "interrupted")
        self.assertEqual(len(self.checkpoint(inv, "end")), 10)  # in-flight batch of 4 + their 6 exact-text copies

    def test_downstream_stage_dispatch(self):
        seen = {}
        fake = types.ModuleType("pipeline.rank")
        fake.run = lambda ctx: seen.update(ctx=ctx) or {"issues": 3}
        with mock.patch.dict(sys.modules, {"pipeline.rank": fake}):
            code = self.run_cli("--dry-run", "--stages", "ingest,enrich,rank", client=FakeClient())
        self.assertEqual(code, 0)
        ctx = seen["ctx"]
        self.assertEqual(ctx.label_config, "mock:" + CONFIG["label_config"])
        self.assertEqual(ctx.phase, "initial")
        self.assertEqual(len(ctx.records), 21)
        self.assertEqual(list(ctx.texts)[:2], ["id00", "id01"])
        inv = self.invocations()[-1]
        self.assertEqual(inv["stage_summaries"]["rank"], {"issues": 3})
        self.assertIsInstance(inv["stage_seconds"]["rank"], float)

    def test_missing_stage_module(self):
        with mock.patch.dict(sys.modules, {"pipeline.memo": None}):
            code = self.run_cli("--dry-run", "--stages", "memo")
        self.assertEqual(code, 5)
        self.assertIn("not available", self.last_stderr)


class DotenvTests(unittest.TestCase):
    def test_parse_without_override_or_leaking_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("# comment\n\nA5_K1=plain\nexport A5_K2=\"quoted value\"\nA5_K3='single'\n"
                         "A5_K4=\nA5_K5=keep # trailing\nnot a line\nA5_SET=fromfile\n")
            env = {"A5_SET": "already"}
            found = clients.load_dotenv(p, env)
            self.assertEqual(env["A5_K1"], "plain")
            self.assertEqual(env["A5_K2"], "quoted value")
            self.assertEqual(env["A5_K3"], "single")
            self.assertEqual(env["A5_K4"], "")
            self.assertEqual(env["A5_K5"], "keep")
            self.assertEqual(env["A5_SET"], "already")  # never overrides
            self.assertEqual(sorted(found), ["A5_K1", "A5_K2", "A5_K3", "A5_K5", "A5_SET"])
            self.assertEqual(clients.load_dotenv(Path(d) / "missing", env), [])

    def test_cli_logs_names_only(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            write_csv(d / "in.csv", make_rows())
            (d / "cfg.json").write_text(json.dumps(CONFIG))
            (d / ".env").write_text("A5_SECRET_TEST=s3cr3t-value\n")
            err = io.StringIO()
            with mock.patch.object(run_pipeline, "ROOT", d), mock.patch.dict(os.environ, {}), \
                    contextlib.redirect_stderr(err):
                os.environ.pop("A5_SECRET_TEST", None)
                code = run_pipeline.main([str(d / "in.csv"), "--config", str(d / "cfg.json"), "--out",
                                          str(d / "run"), "--dry-run", "--stages", "ingest"])
                self.assertEqual(os.environ.get("A5_SECRET_TEST"), "s3cr3t-value")
            self.assertEqual(code, 0)
            self.assertIn("A5_SECRET_TEST", err.getvalue())
            self.assertNotIn("s3cr3t-value", err.getvalue())
            for f in (d / "run").rglob("*"):
                if f.is_file():
                    self.assertNotIn("s3cr3t-value", f.read_text())


if __name__ == "__main__":
    unittest.main()

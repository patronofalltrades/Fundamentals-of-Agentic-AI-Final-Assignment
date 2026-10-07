import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError


spec = importlib.util.spec_from_file_location(
    "benchmark", Path(__file__).resolve().parents[1] / "tools/openrouter_extractor_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkTest(unittest.TestCase):
    def test_pinned_privacy_schema_and_usage(self):
        row = {"review_id": "synthetic", "review_text": "Spotify playback fails."}
        payload = benchmark.make_payload("deepinfra", row, {
            "topic": "playback", "intent": "complaint", "severity": 4, "sentiment": -0.5})
        self.assertEqual(payload["provider"], {
            "only": ["deepinfra/bf16"], "allow_fallbacks": False,
            "require_parameters": True, "data_collection": "deny", "zdr": True})
        self.assertEqual(payload["response_format"]["json_schema"]["strict"], True)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        response = {"provider": "DeepInfra", "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"entities": ["Spotify"], "evidence_quote": "playback fails"})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "completion_tokens_details": {"reasoning_tokens": 30}}}
        evidence, inp, out, reasoning, _, _, charge = benchmark.parse_response(response, row, "deepinfra")
        self.assertEqual(evidence["entities"], ["Spotify"])
        self.assertEqual((inp, out, reasoning, charge), (100, 50, 30, 12200))
        response["choices"][0]["message"]["content"] = json.dumps({
            "entities": ["pot"], "evidence_quote": "playback fails"})
        with self.assertRaises(Exception):
            benchmark.parse_response(response, row, "deepinfra")

    def test_reservation_survives_uncertain_and_blocks_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            db = benchmark.connect(str(Path(folder) / "ledger.db"), "synthetic-source")
            row = {"review_id": "synthetic", "review_text": "Spotify playback fails."}
            payload = benchmark.make_payload("groq", row, {
                "topic": "playback", "intent": "complaint", "severity": 4, "sentiment": -0.5})
            benchmark.reserve(db, "groq", row, payload, "synthetic-row", "synthetic-request")
            self.assertEqual(benchmark.budget_used(db), 29_491_200)
            with self.assertRaises(Exception):
                benchmark.reserve(db, "groq", row, payload, "synthetic-row", "synthetic-request")
            with self.assertRaises(ValueError):
                benchmark.connect(str(Path(folder) / "ledger.db"), "different-source")

    def test_published_limit_is_required_before_paid_work(self):
        original = benchmark.request_json
        model, tag, input_rate, output_rate = benchmark.ROUTES["deepinfra"]
        listing = {"data": {"endpoints": [{
            "tag": tag, "model_id": model, "status": 0,
            "context_length": 131072, "max_completion_tokens": 117964,
            "pricing": {"prompt": str(input_rate), "completion": str(output_rate)},
            "supported_parameters": ["response_format", "structured_outputs", "reasoning_effort", "max_tokens"]}]}}
        try:
            benchmark.request_json = lambda url: listing
            benchmark.verify_route("deepinfra")
            listing["data"]["endpoints"][0]["status"] = -5
            with self.assertRaisesRegex(ValueError, "deepinfra/bf16 has catalog status -5"):
                benchmark.verify_route("deepinfra")
            listing["data"]["endpoints"][0]["status"] = 0
            listing["data"]["endpoints"][0]["max_completion_tokens"] += 1
            with self.assertRaises(ValueError):
                benchmark.verify_route("deepinfra")
        finally:
            benchmark.request_json = original

    def test_public_get_retries_transient_errors_only(self):
        calls = []
        def transient(url):
            calls.append(url)
            if len(calls) == 1:
                raise URLError("synthetic reset")
            return {"data": "synthetic"}
        with mock.patch.object(benchmark, "request_json", side_effect=transient), \
             mock.patch.object(benchmark.time, "sleep"):
            self.assertEqual(benchmark.public_catalog_json("deepinfra", "https://example.invalid/catalog"),
                             {"data": "synthetic"})
        self.assertEqual(len(calls), 2)
        with mock.patch.object(benchmark, "request_json", side_effect=URLError("synthetic reset")) as get, \
             mock.patch.object(benchmark.time, "sleep"):
            with self.assertRaisesRegex(ConnectionError, "after 3 attempts"):
                benchmark.public_catalog_json("groq", "https://example.invalid/catalog")
            self.assertEqual(get.call_count, 3)
        with mock.patch.object(benchmark, "request_json", side_effect=HTTPError(
                "https://example.invalid/catalog", 403, "synthetic", {}, None)) as get:
            with self.assertRaisesRegex(ConnectionError, "HTTP 403"):
                benchmark.public_catalog_json("groq", "https://example.invalid/catalog")
            self.assertEqual(get.call_count, 1)

    def test_post_error_is_not_retried_and_blocks_resume(self):
        row = {"review_id": "synthetic", "review_text": "Playback fails", "review_rating": "1",
               "review_likes": "0", "app_version": "", "review_timestamp": "2022-01-01"}
        labels = {"topic": "playback", "intent": "complaint", "severity": 4, "sentiment": -0.5}
        with tempfile.TemporaryDirectory() as folder:
            baseline = str(Path(folder) / "baseline.db")
            ledger = str(Path(folder) / "ledger.db")
            db = sqlite3.connect(baseline)
            db.execute("CREATE TABLE results(review_id TEXT,label_json TEXT,source_sha256 TEXT,config_hash TEXT)")
            db.execute("INSERT INTO results VALUES (?,?,?,?)", (row["review_id"], json.dumps(labels),
                benchmark.row_sha256([row[k] for k in benchmark.SOURCE_FIELDS]), "synthetic-config"))
            db.commit()
            db.close()
            with mock.patch.object(benchmark, "load_rows", return_value=[row]), \
                 mock.patch.object(benchmark, "file_sha256", return_value="synthetic-source"), \
                 mock.patch.object(benchmark, "verify_route"), \
                 mock.patch.object(benchmark, "request_json", side_effect=URLError("synthetic reset")) as post, \
                 mock.patch.dict(benchmark.os.environ, {"OPENROUTER_API_KEY": "synthetic-only"}):
                with self.assertRaisesRegex(RuntimeError, "inference POST delivery/charge uncertain"):
                    benchmark.run("unused.csv", "unused.json", ledger, baseline, 1)
                self.assertEqual(post.call_count, 1)
                with self.assertRaisesRegex(ValueError, "unresolved inference call"):
                    benchmark.run("unused.csv", "unused.json", ledger, baseline, 1)
                self.assertEqual(post.call_count, 1)
            saved = sqlite3.connect(ledger)
            self.assertEqual(saved.execute("SELECT status FROM calls").fetchone()[0], "uncertain")
            self.assertEqual(benchmark.budget_used(saved), 24_903_544)

    def test_reconciliation_keeps_exposure_and_requires_explicit_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = str(Path(folder) / "ledger.db")
            # Model the schema already saved by the first live benchmark run.
            db = sqlite3.connect(ledger)
            db.execute("""CREATE TABLE calls (
              id INTEGER PRIMARY KEY, route TEXT NOT NULL, review_id TEXT NOT NULL,
              source_sha TEXT NOT NULL, status TEXT NOT NULL, reserved_nusd INTEGER NOT NULL,
              charged_nusd INTEGER, input_tokens INTEGER, output_tokens INTEGER,
              reasoning_tokens INTEGER, provider TEXT, finish_reason TEXT,
              elapsed_seconds REAL, error_class TEXT, response_id TEXT,
              evidence_json TEXT, UNIQUE(route,review_id))""")
            db.execute("INSERT INTO calls(route,review_id,source_sha,status,reserved_nusd) VALUES (?,?,?,?,?)",
                       ("deepinfra", "synthetic", "synthetic-row", "uncertain", 24_903_544))
            db.commit()
            db.close()
            db = benchmark.connect(ledger, "synthetic-source")
            with self.assertRaises(ValueError):
                benchmark.reconcile_no_visible_bill(ledger, 1, "", "")
            benchmark.reconcile_no_visible_bill(
                ledger, 1, "2026-10-07T10:18:00Z", "Synthetic account observation")
            self.assertEqual(benchmark.budget_used(db), 24_903_544)
            self.assertEqual(db.execute("SELECT status FROM calls WHERE id=1").fetchone()[0],
                             "reconciled_no_visible_bill")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reconciliations").fetchone()[0], 1)
            row = {"review_id": "synthetic", "review_text": "Synthetic playback fails"}
            source_row = dict(row, review_rating="1", review_likes="0", app_version="",
                              review_timestamp="2022-01-01")
            baseline = str(Path(folder) / "baseline.db")
            labels = sqlite3.connect(baseline)
            labels.execute("CREATE TABLE results(review_id TEXT,label_json TEXT,source_sha256 TEXT,config_hash TEXT)")
            labels.execute("INSERT INTO results VALUES (?,?,?,?)", ("synthetic",
                json.dumps({"topic": "other", "intent": "praise", "severity": 1, "sentiment": 0.5}),
                benchmark.row_sha256([source_row[k] for k in benchmark.SOURCE_FIELDS]), "synthetic-config"))
            labels.commit()
            labels.close()
            with mock.patch.object(benchmark, "load_rows", return_value=[source_row]), \
                 mock.patch.object(benchmark, "file_sha256", return_value="synthetic-source"), \
                 mock.patch.object(benchmark, "request_json") as post:
                with self.assertRaisesRegex(ValueError, "needs explicit reconciliation or retry"):
                    benchmark.run("unused.csv", "unused.json", ledger, baseline, 1)
                post.assert_not_called()
            with self.assertRaises(ValueError):
                benchmark.reconcile_no_visible_bill(ledger, 1, "2026-10-07T10:18:00Z", "again")
            benchmark.reserve(db, "deepinfra", row, {}, "synthetic-row", "synthetic-request",
                              retry_reconciled_id=1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM calls").fetchone()[0], 2)
            self.assertEqual(benchmark.budget_used(db), 49_807_088)
            with self.assertRaises(ValueError):
                benchmark.reserve(db, "deepinfra", row, {}, "synthetic-row", "synthetic-request",
                                  retry_reconciled_id=1)

    def test_label_and_request_identity_block_stale_reuse(self):
        row = {"review_id": "synthetic", "review_text": "Synthetic playback fails",
               "review_rating": "1", "review_likes": "0", "app_version": "",
               "review_timestamp": "2022-01-01"}
        labels = {"topic": "playback", "intent": "complaint", "severity": 4,
                  "sentiment": -0.5, "model": "synthetic-v2"}
        with tempfile.TemporaryDirectory() as folder:
            ledger = str(Path(folder) / "ledger.db")
            baseline = str(Path(folder) / "baseline.db")
            source_hash = benchmark.row_sha256([row[k] for k in benchmark.SOURCE_FIELDS])
            data = sqlite3.connect(baseline)
            data.execute("CREATE TABLE results(review_id TEXT,label_json TEXT,source_sha256 TEXT,config_hash TEXT)")
            data.execute("INSERT INTO results VALUES (?,?,?,?)",
                         (row["review_id"], json.dumps(labels), source_hash, "synthetic-config"))
            data.commit()
            data.close()
            db = benchmark.connect(ledger, "synthetic-source")
            old_sha = benchmark.request_fingerprint("deepinfra", row, labels, "synthetic-config")
            benchmark.reserve(db, "deepinfra", row, {}, source_hash, old_sha)
            db.execute("UPDATE calls SET status='succeeded',charged_nusd=100 WHERE id=1")
            db.commit()
            saved = benchmark.load_baseline(baseline, [row])
            self.assertEqual(benchmark.plan_calls(db, [row], saved, 1)[0][4], "reuse")
            changed = dict(labels, severity=3)
            data = sqlite3.connect(baseline)
            data.execute("UPDATE results SET label_json=?", (json.dumps(changed),))
            data.commit()
            data.close()
            changed_sha = benchmark.request_fingerprint("deepinfra", row, changed, "synthetic-config")
            self.assertNotEqual(old_sha, changed_sha)
            self.assertNotEqual(old_sha,
                benchmark.request_fingerprint("deepinfra", row, labels, "changed-label-config"))
            self.assertNotEqual(old_sha,
                benchmark.request_fingerprint("groq", row, labels, "synthetic-config"))
            saved = benchmark.load_baseline(baseline, [row])
            self.assertEqual(benchmark.plan_calls(db, [row], saved, 1)[0][4], "changed_input")
            with mock.patch.object(benchmark, "load_rows", return_value=[row]), \
                 mock.patch.object(benchmark, "file_sha256", return_value="synthetic-source"), \
                 mock.patch.object(benchmark, "request_json") as post:
                with self.assertRaisesRegex(ValueError, "separate repeat-call approval"):
                    benchmark.run("unused.csv", "unused.json", ledger, baseline, 1)
                post.assert_not_called()
            with self.assertRaisesRegex(ValueError, "no duplicate call admitted"):
                benchmark.reserve(db, "deepinfra", row, {}, source_hash, old_sha,
                                  allow_changed_inputs=True)
            benchmark.reserve(db, "deepinfra", row, {}, source_hash, changed_sha,
                              allow_changed_inputs=True)
            self.assertEqual(benchmark.budget_used(db), 100 + 24_903_544)

    def test_legacy_binding_is_explicit_and_preserves_charge(self):
        row = {"review_id": "synthetic", "review_text": "Synthetic playback fails",
               "review_rating": "1", "review_likes": "0", "app_version": "",
               "review_timestamp": "2022-01-01"}
        labels = {"topic": "playback", "intent": "complaint", "severity": 4,
                  "sentiment": -0.5, "model": "synthetic-v2"}
        with tempfile.TemporaryDirectory() as folder:
            ledger = str(Path(folder) / "ledger.db")
            baseline = str(Path(folder) / "baseline.db")
            source_hash = benchmark.row_sha256([row[k] for k in benchmark.SOURCE_FIELDS])
            data = sqlite3.connect(baseline)
            data.execute("CREATE TABLE results(review_id TEXT,label_json TEXT,source_sha256 TEXT,config_hash TEXT)")
            data.execute("INSERT INTO results VALUES (?,?,?,?)",
                         (row["review_id"], json.dumps(labels), source_hash, "synthetic-config"))
            data.commit()
            data.close()
            db = benchmark.connect(ledger, "synthetic-source")
            db.execute("""INSERT INTO calls(route,review_id,source_sha,status,reserved_nusd,
                       charged_nusd,provider,evidence_json) VALUES (?,?,?,?,?,?,?,?)""",
                       ("deepinfra", "synthetic", source_hash, "succeeded", 24_903_544,
                        100, "DeepInfra", json.dumps({"entities": [],
                        "evidence_quote": "playback fails"})))
            db.commit()
            self.assertEqual(benchmark.plan_calls(db, [row],
                benchmark.load_baseline(baseline, [row]), 1)[0][4], "legacy_unknown")
            with mock.patch.object(benchmark, "load_rows", return_value=[row]), \
                 mock.patch.object(benchmark, "file_sha256", return_value="synthetic-source"):
                benchmark.bind_legacy_successes("unused.csv", "unused.json", ledger, baseline)
            self.assertEqual(db.execute("SELECT charged_nusd FROM calls").fetchone()[0], 100)
            self.assertEqual(db.execute("SELECT input_binding FROM calls").fetchone()[0],
                             "inferred_from_frozen_baseline")
            self.assertEqual(benchmark.plan_calls(db, [row],
                benchmark.load_baseline(baseline, [row]), 1)[0][4], "reuse")


if __name__ == "__main__":
    unittest.main()

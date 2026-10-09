import importlib.util
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock
from urllib.error import URLError


spec = importlib.util.spec_from_file_location(
    "batch10", Path(__file__).resolve().parents[1] / "tools/deepinfra_batch10_canary.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def fixture():
    topics = ["access", "catalog", "playback", "usability", "billing",
              "other", "other", "other", "other", "other"]
    texts = ["Password fails", "Library item missing", "Playback stalls",
             "Menus are hard", "Premium charged twice", "The ads are loud",
             "Long complaint " + "bad interface " * 18,
             "Search fails", "Download fails", "Support is slow"]
    rows = [{"review_id": "synthetic-%02d" % i, "review_text": text,
             "review_rating": "1", "review_likes": "0", "app_version": "",
             "review_timestamp": "2022-01-01 00:00:00"}
            for i, text in enumerate(texts)]
    labels = {r["review_id"]: ({"topic": topics[i], "intent": "complaint",
             "severity": 3, "sentiment": -0.5}, "source-sha", "config-sha")
              for i, r in enumerate(rows)}
    return rows, labels


def response(rows, quotes=None):
    quotes = quotes or {r["review_id"]: r["review_text"].split()[0] for r in rows}
    return {"id": "synthetic-generation", "provider": "DeepInfra",
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
            "results": [{"review_id": r["review_id"], "entities": [],
                         "evidence_quote": quotes[r["review_id"]]} for r in rows]})}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 900,
                  "completion_tokens_details": {"reasoning_tokens": 600}}}


class BatchTenTest(unittest.TestCase):
    def test_keychain_lookup_and_provider_limit_do_not_leak_secret(self):
        dummy = "synthetic-secret-only"
        stream = io.StringIO()
        with mock.patch.object(batch.subprocess, "run", return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=(dummy + "\n").encode(), stderr=b"")) as lookup, \
             contextlib.redirect_stdout(stream):
            self.assertEqual(batch.keychain_secret(), dummy)
        self.assertNotIn(dummy, stream.getvalue())
        args = lookup.call_args.args[0]
        self.assertEqual(args[:2], ["/usr/bin/security", "find-generic-password"])
        self.assertNotIn(dummy, args)
        with mock.patch.object(batch.subprocess, "run", return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=(dummy + "\n").encode(), stderr=b"")) as custom:
            self.assertEqual(batch.keychain_secret(service="spotify-review-jev",
                account="hanif-spotify-project"), dummy)
            self.assertEqual(custom.call_args.args[0][2:6],
                ["-s", "spotify-review-jev", "-a", "hanif-spotify-project"])
        with mock.patch.object(batch.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                cmd="security", timeout=90)):
            with self.assertRaisesRegex(ValueError, "foreground Terminal"):
                batch.keychain_secret(timeout_seconds=90)
        data = {"data": {"limit": 5, "limit_remaining": 5,
                         "limit_reset": None, "is_management_key": False,
                         "is_provisioning_key": False}}
        with mock.patch.object(batch.single, "request_json", return_value=data) as get:
            result = batch.verify_project_key(dummy, batch.reservation_nusd())
            self.assertEqual(result["limit_usd"], "5")
            self.assertNotIn(dummy, json.dumps(result))
            self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/key")
            data["data"]["limit_reset"] = "monthly"
            with self.assertRaisesRegex(ValueError, "non-resetting"):
                batch.verify_project_key(dummy, batch.reservation_nusd())
            data["data"]["limit_reset"] = None
            data["data"]["limit_remaining"] = 0.001
            with self.assertRaisesRegex(ValueError, "full reservation"):
                batch.verify_project_key(dummy, batch.reservation_nusd())

    def test_selection_payload_and_exact_id_validation(self):
        rows, labels = fixture()
        chosen = batch.select_canary(rows, labels)
        self.assertEqual(len(chosen), 10)
        payload = batch.payload(chosen, labels)
        instruction = payload["messages"][0]["content"]
        self.assertIn("products, features, plans, or explicitly described problems", instruction)
        self.assertIn("Do not list ordinary verbs, adjectives, or generic words", instruction)
        self.assertEqual(payload["provider"], {"only": ["deepinfra/bf16"],
            "allow_fallbacks": False, "require_parameters": True,
            "data_collection": "deny", "zdr": True})
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["response_format"]["json_schema"]["strict"], True)
        parsed, inp, out, reason, charge = batch.validate_batch_response(response(chosen), chosen)
        self.assertEqual((len(parsed), inp, out, reason), (10, 1200, 900, 600))
        self.assertEqual(charge, 1200 * 37 + 900 * 170)
        current_hash = batch.config_sha()
        with mock.patch.object(batch, "PROMPT_VERSION", "deepinfra-batch10-evidence-v1"):
            self.assertNotEqual(batch.config_sha(), current_hash)
        duplicate = response(chosen)
        body = json.loads(duplicate["choices"][0]["message"]["content"])
        body["results"][9]["review_id"] = body["results"][0]["review_id"]
        duplicate["choices"][0]["message"]["content"] = json.dumps(body)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            batch.validate_batch_response(duplicate, chosen)
        missing = response(chosen)
        body = json.loads(missing["choices"][0]["message"]["content"])
        body["results"].pop()
        missing["choices"][0]["message"]["content"] = json.dumps(body)
        with self.assertRaisesRegex(ValueError, "count"):
            batch.validate_batch_response(missing, chosen)
        crossed = response(chosen)
        body = json.loads(crossed["choices"][0]["message"]["content"])
        body["results"][0]["evidence_quote"] = chosen[1]["review_text"]
        crossed["choices"][0]["message"]["content"] = json.dumps(body)
        with self.assertRaises(Exception):
            batch.validate_batch_response(crossed, chosen)

    def test_atomic_result_commit_quarantine_and_no_retry(self):
        rows, labels = fixture()
        with tempfile.TemporaryDirectory() as folder:
            prior_path = str(Path(folder) / "prior.db")
            prior = sqlite3.connect(prior_path)
            prior.execute("CREATE TABLE calls(id INTEGER PRIMARY KEY,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
            prior.execute("INSERT INTO calls VALUES (1,'succeeded',24903544,1000)")
            prior.commit()
            prior.close()
            _, prior_sha = batch.prior_exposure(prior_path)
            ledger = str(Path(folder) / "batch.db")
            db = batch.connect(ledger, "source-sha", "baseline-sha", prior_sha)
            batch.initialize(db, rows, labels)
            with mock.patch.object(batch.single, "verify_route"), \
                 mock.patch.object(batch, "verify_project_key"), \
                 mock.patch.object(batch.single, "request_json", return_value=response(rows)) as post:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    outcome = pool.submit(batch.execute, db, rows, labels,
                                          prior_path, prior_sha, "synthetic-key").result()
                self.assertEqual(outcome["accepted_rows"], 10)
                post.assert_called_once()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM results").fetchone()[0], 10)
            self.assertEqual(db.execute("SELECT status FROM batches").fetchone()[0], "succeeded")
            original_charge = db.execute("SELECT charged_nusd FROM batches").fetchone()[0]
            with db:
                db.execute("UPDATE meta SET value=? WHERE key='cap_nusd'", (str(batch.single.CAP_NUSD),))
            upgraded = batch.connect(ledger, "source-sha", "baseline-sha", prior_sha)
            self.assertEqual(upgraded.execute("SELECT charged_nusd FROM batches").fetchone()[0], original_charge)
            self.assertEqual(upgraded.execute("SELECT COUNT(*) FROM results").fetchone()[0], 10)
            self.assertEqual(upgraded.execute("SELECT prior_cap_nusd,new_cap_nusd FROM cap_history").fetchone(),
                             (batch.single.CAP_NUSD, batch.CAP_NUSD))
            upgraded.close()
            duplicate = dict(rows[0], review_id="synthetic-copy")
            cached_labels = dict(labels, **{duplicate["review_id"]: labels[rows[0]["review_id"]]})
            self.assertEqual(batch.materialize_exact_text_cache(db, [duplicate], cached_labels), 1)
            self.assertEqual(batch.materialize_exact_text_cache(db, [duplicate], cached_labels), 0)
            self.assertEqual(db.execute("SELECT cache_source_id FROM results WHERE review_id='synthetic-copy'").fetchone()[0],
                             rows[0]["review_id"])
            with mock.patch.object(batch, "config_sha", return_value="different-config"):
                self.assertEqual(batch.materialize_exact_text_cache(
                    db, [dict(rows[0], review_id="synthetic-other-config")],
                    dict(labels, **{"synthetic-other-config": labels[rows[0]["review_id"]]})), 0)
            changed_labels = dict(cached_labels)
            changed_labels["synthetic-other-label"] = (
                dict(labels[rows[0]["review_id"]][0], severity=4), "source-sha", "config-sha")
            self.assertEqual(batch.materialize_exact_text_cache(
                db, [dict(rows[0], review_id="synthetic-other-label")], changed_labels), 0)
            with mock.patch.object(batch.single, "request_json") as post:
                with self.assertRaisesRegex(ValueError, "pending"):
                    batch.execute(db, rows, labels, prior_path, prior_sha, "synthetic-key")
                post.assert_not_called()
            with self.assertRaisesRegex(ValueError, "settings or prior ledger changed"):
                batch.connect(ledger, "source-sha", "different-baseline", prior_sha)
            db.close()

            bad_ledger = str(Path(folder) / "bad.db")
            bad = batch.connect(bad_ledger, "source-sha", "baseline-sha", prior_sha)
            batch.initialize(bad, rows, labels)
            malformed = response(rows)
            content = json.loads(malformed["choices"][0]["message"]["content"])
            content["results"][7]["evidence_quote"] = "invented quote"
            malformed["choices"][0]["message"]["content"] = json.dumps(content)
            with mock.patch.object(batch.single, "verify_route"), \
                 mock.patch.object(batch, "verify_project_key"), \
                 mock.patch.object(batch.single, "request_json", return_value=malformed) as post:
                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    batch.execute(bad, rows, labels, prior_path, prior_sha, "synthetic-key")
                post.assert_called_once()
            self.assertEqual(bad.execute("SELECT COUNT(*) FROM results").fetchone()[0], 0)
            self.assertEqual(bad.execute("SELECT status FROM batches").fetchone()[0], "quarantined")
            self.assertEqual(batch.canary_exposure(bad), 24_903_544)
            bad.close()

            unknown_ledger = str(Path(folder) / "unknown-cost.db")
            unknown = batch.connect(unknown_ledger, "source-sha", "baseline-sha", prior_sha)
            batch.initialize(unknown, rows, labels)
            no_usage = response(rows)
            no_usage.pop("usage")
            with mock.patch.object(batch.single, "verify_route"), \
                 mock.patch.object(batch, "verify_project_key"), \
                 mock.patch.object(batch.single, "request_json", return_value=no_usage):
                with self.assertRaisesRegex(RuntimeError, "quarantined"):
                    batch.execute(unknown, rows, labels, prior_path, prior_sha, "synthetic-key")
            self.assertEqual(unknown.execute("SELECT charged_nusd FROM batches").fetchone()[0], None)
            self.assertEqual(unknown.execute("SELECT COUNT(*) FROM results").fetchone()[0], 0)
            self.assertEqual(batch.canary_exposure(unknown), 24_903_544)
            unknown.close()

    def test_unknown_delivery_and_combined_cap_hold(self):
        rows, labels = fixture()
        with tempfile.TemporaryDirectory() as folder:
            prior_path = str(Path(folder) / "prior.db")
            prior = sqlite3.connect(prior_path)
            prior.execute("CREATE TABLE calls(id INTEGER PRIMARY KEY,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
            prior.execute("INSERT INTO calls VALUES (1,'uncertain',4975100000,NULL)")
            prior.commit()
            prior.close()
            _, prior_sha = batch.prior_exposure(prior_path)
            ledger = str(Path(folder) / "batch.db")
            db = batch.connect(ledger, "source-sha", "baseline-sha", prior_sha)
            batch.initialize(db, rows, labels)
            with self.assertRaisesRegex(ValueError, "combined prior and canary exposure"):
                batch.reserve(db, prior_path, prior_sha)
            self.assertEqual(db.execute("SELECT status FROM batches").fetchone()[0], "pending")
            db.close()
            prior = sqlite3.connect(prior_path)
            prior.execute("UPDATE calls SET reserved_nusd=1000 WHERE id=1")
            prior.commit()
            prior.close()
            with self.assertRaisesRegex(ValueError, "historical ledger changed"):
                db = batch.connect(ledger, "source-sha", "baseline-sha", prior_sha)
                batch.reserve(db, prior_path, prior_sha)
            db.close()

            _, fresh_sha = batch.prior_exposure(prior_path)
            uncertain = batch.connect(str(Path(folder) / "uncertain.db"),
                                      "source-sha", "baseline-sha", fresh_sha)
            batch.initialize(uncertain, rows, labels)
            with mock.patch.object(batch.single, "verify_route"), \
                 mock.patch.object(batch, "verify_project_key"), \
                 mock.patch.object(batch.single, "request_json", side_effect=URLError("synthetic reset")) as post:
                with self.assertRaisesRegex(RuntimeError, "delivery uncertain"):
                    batch.execute(uncertain, rows, labels, prior_path, fresh_sha, "synthetic-key")
                self.assertEqual(post.call_count, 1)
                with self.assertRaisesRegex(ValueError, "pending"):
                    batch.execute(uncertain, rows, labels, prior_path, fresh_sha, "synthetic-key")
                self.assertEqual(post.call_count, 1)
            self.assertEqual(uncertain.execute("SELECT status FROM batches").fetchone()[0], "uncertain")
            self.assertEqual(batch.canary_exposure(uncertain), 24_903_544)
            uncertain.close()

import csv
import gzip
import json
from pathlib import Path
import signal
import tempfile
import unittest

from spotify_pipeline.contract import TOPICS
from tools import gap_closure_eval as g


class FakeBudget:
    def __init__(self):
        self.rows = {}

    def reserve(self, key, budget, amount):
        if key in self.rows:
            raise ValueError("request already reserved or settled; no duplicate call")
        self.rows[key] = "reserved"

    def settle(self, key, status, charge):
        assert self.rows[key] == "reserved"
        self.rows[key] = status

    def uncertain(self, key):
        self.rows[key] = "uncertain"

    def cancel_unsent(self, key):
        del self.rows[key]


def fake_openrouter(request):
    items = json.loads(request["messages"][0]["content"].split("\n", 1)[1])
    name = request["response_format"]["json_schema"]["name"]
    out = []
    for item in items:
        rid = item["review_id"]
        if name == "gap_verify":
            out.append({"review_id": rid, "topic": "playback", "intent": "complaint", "severity": 3})
        elif name == "gap_group":
            out.append({"review_id": rid, "issue_id": "PLY-FAIL"})
        elif name == "gap_audit_label":
            out.append({"review_id": rid, "topic_supported": True, "intent_supported": True,
                        "severity_supported": item["claimed"]["severity"] == 3})
        elif name == "gap_audit_group":
            out.append({"review_id": rid, "supported": item["claimed_issue"]["issue_id"] == "PLY-FAIL"})
        else:
            out.append({"review_id": rid, "entities": [], "evidence_quote": item["review_text"].split(".")[0]})
    return {"id": "gen-1", "model": g.MODEL, "provider": "DeepInfra",
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": out})}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}


ONE = {"topic": {"type": "choice", "choice": "playback", "confidence": 0.9},
       "intent": {"type": "choice", "choice": "complaint", "confidence": 0.9},
       "severity": {"type": "choice", "choice": "3", "confidence": 0.9},
       "sentiment": {"type": "score", "score": 1.0, "confidence": 0.9}}


def fake_jev(request):
    answers = {k: ONE[k.split("_")[-1]] for k in request["questions"]}
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 900, "output_tokens": 10}, "answers": answers}


class GapClosureEvalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.records, self.membership = root / "source.csv", root / "records.jsonl.gz", root / "m.csv"
        self.golden = root / "golden.csv"
        n = 1800
        with self.source.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"))
            for i in range(n):
                w.writerow(("id-%04d" % i, "synthetic review number %04d stops playing" % i, "1", "0", "1", "2026-01-01"))
        with gzip.open(self.records, "wt") as f:
            for i in range(n):
                f.write(json.dumps({"review_id": "id-%04d" % i, "status": "completed", "topic": "playback",
                    "intent": "complaint", "severity": 3, "evidence_quote": "stops playing"}) + "\n")
        with self.membership.open("w", newline="") as f:
            w = csv.writer(f); w.writerow(("issue_id", "review_id"))
            for i in range(n):
                w.writerow(("PLY-FAIL", "id-%04d" % i))
        with self.golden.open("w", newline="") as f:
            w = csv.writer(f); w.writerow(("review_id", "topic")); w.writerow(("id-0001", "SECRET-ANSWER"))
        self.plan, self.texts = g.build_plan(self.records, self.membership, self.source, [self.golden])
        self.out = root / "private"
        g.save_plan(self.out, self.plan, self.texts)

    def test_plan_is_deterministic_disjoint_and_excludes_golden_ids(self):
        again, _ = g.build_plan(self.records, self.membership, self.source, [self.golden])
        self.assertEqual(g.digest(again), g.digest(self.plan))
        self.assertEqual(len(self.plan["verify_ids"]), 1000)
        self.assertEqual(len(self.plan["group_ids"]), 600)
        self.assertFalse(set(self.plan["verify_ids"]) & set(self.plan["group_ids"]))
        self.assertNotIn("id-0001", set(self.plan["verify_ids"]) | set(self.plan["group_ids"]))
        self.assertNotIn("SECRET-ANSWER", g.canon(self.plan))
        self.assertEqual(sum(1 for x in self.plan["label_claims"].values() if x["planted"]), 50)
        self.assertEqual(sum(1 for x in self.plan["group_claims"].values() if x["planted"]), 50)
        for rid, x in self.plan["group_claims"].items():
            if x["planted"]:
                self.assertNotEqual(g.family(x["claim"]), "PLY")
        for rid, x in self.plan["label_claims"].items():
            if x["planted"] == "topic":
                self.assertIn(x["claim"]["topic"], TOPICS)
                self.assertNotEqual(x["claim"]["topic"], "playback")

    def test_blind_requests_carry_text_only(self):
        calls = g.build_calls(self.plan, self.texts)
        self.assertEqual(len(calls), 100 + 10 + 60 + 10 + 10 + 16 + 6)
        batch = [c for c in calls if c[1] == "jev_batch10"][0]
        self.assertEqual(len(batch[3]["state"]["reviews"]), 10)
        self.assertEqual(len(batch[3]["questions"]), 40)
        self.assertIn("`reviews[9]`", batch[3]["questions"]["r09_topic"]["instructions"])
        verify = [c for c in calls if c[1] == "verify"][0][3]
        items = json.loads(verify["messages"][0]["content"].split("\n", 1)[1])
        self.assertEqual({tuple(sorted(i)) for i in items}, {("review_id", "review_text")})
        group = [c for c in calls if c[1] == "group"][0][3]
        self.assertNotIn("historical", group["messages"][0]["content"])
        self.assertNotIn(g.CANARY, verify["messages"][0]["content"])
        inject = [c for c in calls if c[0] == "inject_verify:base"][0][3]
        self.assertIn(g.CANARY, inject["messages"][0]["content"])
        self.assertTrue(g.bound(self.plan) < 1_500_000_000)

    def run_all(self, interrupt_after=None, resume=False, transports=None):
        c = g.open_db(self.out)
        budget = FakeBudget() if not hasattr(self, "budget") else self.budget
        self.budget = budget
        runner = g.Runner(c, budget, 1_500_000_000, {}, "resumed" if resume else "initial",
                          transports or {"jev": fake_jev, "openrouter": fake_openrouter})
        previous = signal.signal(signal.SIGINT, lambda *_: runner.stop.set())
        try:
            text = dict(c.execute("select id,review_text from texts"))
            done = runner.run(g.build_calls(self.plan, text), text, 3, interrupt_after)
            if done and not runner.stop.is_set():
                done = runner.run(g.build_calls(self.plan, text, g.synthetic_labels(c)), text, 3)
            name = "checkpoint_before" if runner.stop.is_set() else "checkpoint_after"
            g.checkpoint(c, self.out, name, "test")
            return done, runner
        finally:
            signal.signal(signal.SIGINT, previous)
            c.close()

    def test_interrupt_resume_never_resends_and_report_has_no_text(self):
        done, runner = self.run_all(interrupt_after=30)
        self.assertFalse(done)
        before = json.loads((self.out / "checkpoint_before.json").read_text())
        self.assertGreaterEqual(len(before["settled_keys"]), 30)
        self.assertLess(len(before["settled_keys"]), 213)
        sent = []
        def counting(request):
            sent.append(g.digest(request)); return fake_openrouter(request)
        done, _ = self.run_all(resume=True, transports={"jev": fake_jev, "openrouter": counting})
        self.assertTrue(done)
        result, cases, calls = g.report(self.out)
        self.assertEqual(result["calls"], 213)
        self.assertEqual(result["jev_ten_per_request"]["agreement_with_single_review_jev"]["joint"]["n"], 100)
        self.assertEqual(result["jev_ten_per_request"]["input_tokens_per_review"], 90.0)
        self.assertEqual(result["interrupt_resume"]["settled_requests_resent"], 0)
        self.assertTrue(result["interrupt_resume"]["settled_before_kept_after"])
        self.assertEqual(result["blind_verifier"]["agreement_with_jev"]["joint"]["n"], 1000)
        self.assertEqual(result["grouping_stage"]["exact_issue_agreement"]["n"], 600)
        self.assertEqual(result["planted_errors"]["issues"]["auditor_detected"]["n"], 50)
        self.assertEqual(result["planted_errors"]["labels"]["blind_verifier_disagreed_with_planted_value"]["n"], 50)
        self.assertEqual(result["prompt_injection"]["canary_leaks"], [])
        self.assertEqual({x["route"] for x in calls if x["role"] == "verify"}, {"deepinfra/bf16"})
        self.assertEqual({x["route"] for x in calls if x["role"] == "jev_batch10"}, {"typesafe/jev-1.13.0"})
        self.assertTrue(all(len(x["request_sha256"]) == 64 for x in calls))
        self.assertTrue(all(len(x["response_sha256"]) == 64 for x in calls if x["status"] == "succeeded"))
        self.assertEqual({x["generation_id"] for x in calls if x["role"] == "verify"}, {"gen-1"})
        blob = g.canon([result, cases, calls])
        for text in list(self.texts.values())[:50]:
            self.assertNotIn(text, blob)
        self.assertNotIn("stops playing", blob)

    def test_unknown_delivery_holds_and_is_not_retried(self):
        def broken(request):
            raise TimeoutError("socket")
        self.run_all(interrupt_after=None, transports={"jev": fake_jev, "openrouter": broken})
        c = g.open_db(self.out)
        statuses = dict(c.execute("select status,count(*) from calls group by status"))
        c.close()
        self.assertEqual(statuses["uncertain"], 187)  # 186 role calls and the evidence batch
        self.assertEqual(statuses["succeeded"], 26)  # 16 synthetic Jev rows and 10 ten-review Jev requests
        sent = []
        self.run_all(resume=True, transports={"jev": fake_jev, "openrouter": lambda r: sent.append(r)})
        self.assertEqual(sent, [])

    def test_definite_http_error_is_held_and_retried_under_a_new_key(self):
        import io, urllib.error
        g.COOLDOWN_SECONDS, saved = 0, g.COOLDOWN_SECONDS
        self.addCleanup(setattr, g, "COOLDOWN_SECONDS", saved)
        failed = set()
        def flaky(request):
            sha = g.digest(request)
            if sha not in failed:
                failed.add(sha)
                raise urllib.error.HTTPError(g.URL, 429, "Too Many Requests", {}, io.BytesIO(b'{"error":"rate"}'))
            return fake_openrouter(request)
        done, _ = self.run_all(transports={"jev": fake_jev, "openrouter": flaky})
        self.assertTrue(done)
        c = g.open_db(self.out)
        statuses = dict(c.execute("select status,count(*) from calls group by status"))
        retried = c.execute("select count(*) from calls where key like 'verify:%#2' and status='succeeded'").fetchone()[0]
        body = json.loads(c.execute("select response_json from responses where key='verify:000'").fetchone()[0])
        c.close()
        self.assertEqual(statuses["rejected_http"], 187)
        self.assertEqual(retried, 100)
        self.assertEqual(body["http_status"], 429)
        self.assertEqual([k for k, s in self.budget.rows.items() if s == "uncertain"].__len__(), 187)
        result, _, _ = g.report(self.out)
        self.assertEqual(result["blind_verifier"]["labelled"], 1000)
        self.assertEqual(result["prompt_injection"]["contamination"]["verifier"]["benign_rows"], 8)

    def test_route_amendment_pins_one_route_and_checks_its_name_and_price(self):
        calls = g.build_calls(self.plan, self.texts)
        body = calls[0][3]
        moved = g.on_route(body, "crusoe/bf16")
        self.assertEqual(moved["provider"]["only"], ["crusoe/bf16"])
        self.assertFalse(moved["provider"]["allow_fallbacks"])
        self.assertTrue(moved["provider"]["zdr"])
        self.assertEqual({k: v for k, v in moved.items() if k != "provider"}, {k: v for k, v in body.items() if k != "provider"})
        self.assertEqual(body["provider"]["only"], ["deepinfra/bf16"])
        with self.assertRaises(ValueError):
            g.on_route(body, "groq")
        response = fake_openrouter(body)
        with self.assertRaisesRegex(ValueError, "provider"):
            g.usage_of("verify", response, "crusoe/bf16")
        response["provider"] = "Crusoe"
        self.assertEqual(g.usage_of("verify", response, "crusoe/bf16")[3], g.money(1000, 200, "crusoe/bf16"))
        self.assertGreater(g.money(1000, 200, "crusoe/bf16"), g.money(1000, 200, "deepinfra/bf16"))
        self.assertEqual(g.role_reserve(), g.money(g.CONTEXT, g.OUTPUT_LIMIT))

    def test_rejected_output_is_metered_and_quarantined(self):
        def tampered(request):
            r = fake_openrouter(request)
            body = json.loads(r["choices"][0]["message"]["content"])
            body["results"][0]["review_id"] = "ADMIN-0000"
            r["choices"][0]["message"]["content"] = json.dumps(body)
            return r
        self.run_all(transports={"jev": fake_jev, "openrouter": tampered})
        c = g.open_db(self.out)
        row = c.execute("select status,charged_nusd from calls where key='verify:000'").fetchone()
        value = json.loads(c.execute("select value_json from outputs where key='verify:000'").fetchone()[0])
        c.close()
        self.assertEqual(row[0], "quarantined_metered")
        self.assertGreater(row[1], 0)
        self.assertIn("unknown or repeated review_id", value["rejected"])


if __name__ == "__main__":
    unittest.main()

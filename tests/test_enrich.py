import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
from tests.test_prepare import write_csv, row
from labelling.model_client import (BatchResult, CallUsage, InvalidModelOutput, ModelClientError, Record,
                                    TransientModelError)
from pipeline import enrich as en
from pipeline.prepare import prepare
from pipeline.rowhash import INTENTS, TOPICS
from pipeline.spend import SpendLedger
from pipeline.state import CallLog, RecordStore

LC = "fake/v1:prompt-v1:schema-a5-v1"


def label_for(rid, text, lc):
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)  # by text: duplicates agree
    return Record(review_id=rid, topic=TOPICS[h % 8], intent=INTENTS[h % 5], sentiment=round((h % 21 - 10) / 10, 1),
                  severity=h % 5 + 1, entities=["x"] if h % 2 else [], evidence_quote=text.strip()[:25],
                  needs_review=bool(h % 3 == 0), label_config=lc)


class FakeClient:
    """Deterministic client. ``hook(call_no, reviews)`` may return an action or raise.

    Actions: None (normal), "drop:<id>", "badquote:<id>", "wronglc:<id>", "boolsev:<id>", "dup:<id>",
    "foreign", or a ready BatchResult.
    """

    model = "fake-model-1"

    def __init__(self, hook=None, request_id=None):
        self.hook = hook
        self.request_id = request_id
        self.calls = []
        self.lock = threading.Lock()

    def classify_batch(self, reviews, label_config):
        with self.lock:
            self.calls.append([r.review_id for r in reviews])
            n = len(self.calls)
        action = self.hook(n, reviews) if self.hook else None
        recs = [label_for(r.review_id, r.review_text, label_config) for r in reviews]
        if isinstance(action, str):
            kind, _, target = action.partition(":")
            out = []
            for rec in recs:
                if rec.review_id == target or kind == "foreign":
                    if kind == "drop":
                        continue
                    if kind == "badquote":
                        rec = Record(**dict(rec.__dict__, evidence_quote="NOT IN TEXT"))
                    if kind == "wronglc":
                        rec = Record(**dict(rec.__dict__, label_config="other"))
                    if kind == "boolsev":
                        rec = Record(**dict(rec.__dict__, severity=True))
                    if kind == "dup":
                        out.append(rec)
                out.append(rec)
            if kind == "foreign":
                out = recs + [Record(**dict(recs[0].__dict__, review_id="zzz-foreign"))]
            recs = out
        rid = self.request_id or "fake-%d" % n
        return BatchResult(request_id=rid, records=recs, usage=CallUsage(model="fake-model-1@served",
                                                                          input_tokens=10 * len(reviews),
                                                                          output_tokens=5 * len(reviews)))

    @staticmethod
    def max_batch_by_tokens(texts, budget=32000, hard_cap=50):
        return min(hard_cap, 4)


class Harness:
    def __init__(self, rows, tmp):
        self.dir = Path(tmp)
        self.csv = self.dir / "in.csv"
        write_csv(self.csv, rows)
        self.prepared = prepare(self.csv)
        self.store = RecordStore(self.dir / "records.jsonl")
        self.calls = CallLog(self.dir / "calls.jsonl")
        self.sleeps = []

    def enricher(self, client, phase="initial", ledger=None, stop_event=None, **settings):
        s = en.EnrichSettings(**dict({"max_batch": 4, "size_by_tokens": False}, **settings))
        return en.Enricher(prepared=self.prepared, store=self.store, call_log=self.calls, client=client,
                           label_config=LC, phase=phase, invocation_id="inv", settings=s, ledger=ledger,
                           stop_event=stop_event, sleep=self.sleeps.append, rng=lambda: 0.5)

    def events(self):
        return [json.loads(l) for l in (self.dir / "calls.jsonl").read_text().splitlines()] \
            if (self.dir / "calls.jsonl").exists() else []

    def latest(self):
        store = RecordStore(self.dir / "records.jsonl")
        try:
            return store.all_latest()
        finally:
            store.close()


def rows_n(n, prefix="r"):
    return [row("%s%02d" % (prefix, i), "Review number %d about playback" % i) for i in range(n)]


class EnrichBasics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        import gc
        gc.collect()
        self.tmp.cleanup()

    def test_all_completed_and_valid(self):
        h = Harness(rows_n(10) + [row("e1", "   "), row("e2", "")], self.tmp.name)
        self.assertEqual(en.write_empty_quarantines(h.prepared, h.store), 2)
        self.assertEqual(en.write_empty_quarantines(h.prepared, h.store), 0)  # idempotent
        client = FakeClient()
        s = h.enricher(client).run()
        self.assertEqual(s["stop_reason"], "completed")
        self.assertEqual(s["completed_new"], 10)
        self.assertEqual([len(c) for c in client.calls], [4, 4, 2])
        sent = {i for c in client.calls for i in c}
        self.assertNotIn("e1", sent)
        self.assertNotIn("e2", sent)
        recs = h.latest()
        self.assertEqual(recs["e1"], {"review_id": "e1", "source_sha256": h.prepared.source_sha["e1"],
                                      "status": "quarantined", "reason": "empty_review_text"})
        for rid in [r for r in recs if r.startswith("r")]:
            self.assertEqual(recs[rid]["status"], "completed")
            self.assertIn(recs[rid]["evidence_quote"], h.prepared.texts[rid])
            self.assertEqual(recs[rid]["label_config"], LC)
        ev = h.events()
        self.assertTrue(all(e["outcome"] == "succeeded" and e["phase"] == "initial" and e["role"] == "enrich"
                            and e["label_config"] == LC and e["model"] == "fake-model-1@served" for e in ev))
        self.assertEqual(sum(e["input_tokens"] for e in ev), 100)

    def test_token_sizing_uses_client_sizer(self):
        h = Harness(rows_n(9), self.tmp.name)
        client = FakeClient()
        h.enricher(client, max_batch=50, size_by_tokens=True).run()
        self.assertEqual([len(c) for c in client.calls], [4, 4, 1])

    def test_request_ids_unique_even_if_provider_repeats(self):
        h = Harness(rows_n(10), self.tmp.name)
        h.enricher(FakeClient(request_id="same-id")).run()
        ids = [e["request_id"] for e in h.events()]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(ids[0], "same-id")


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        import gc
        gc.collect()
        self.tmp.cleanup()

    def test_exact_text_reuse(self):
        rows = [row("a", "Same text"), row("b", "Other"), row("c", "Same text"), row("d", "same text"),
                row("e", "Same text "), row("f", "Other"), row("g", "Third"), row("h", "Same text")]
        h = Harness(rows, self.tmp.name)
        client = FakeClient()
        s = h.enricher(client).run()
        sent = [i for c in client.calls for i in c]
        self.assertEqual(sent, ["a", "b", "d", "e", "g"])  # first id per exact text only
        self.assertEqual(s["cache_copies"], 3)
        recs = h.latest()
        for dup, orig in (("c", "a"), ("h", "a"), ("f", "b")):
            self.assertEqual(recs[dup]["cache_source_id"], orig)
            self.assertNotIn("cache_source_id", recs[orig])
            for k in en.LABEL_FIELDS:
                self.assertEqual(recs[dup][k], recs[orig][k])
            self.assertEqual(recs[dup]["source_sha256"], h.prepared.source_sha[dup])
        for rid in ("d", "e"):  # case / whitespace differences are not exact matches
            self.assertNotIn("cache_source_id", recs[rid])
        logged = {i for e in h.events() if e["outcome"] == "succeeded" for i in e["review_ids"]}
        self.assertTrue({"a", "b"} <= logged and not {"c", "f", "h"} & logged)

    def test_reuse_from_store_on_restart_makes_no_calls(self):
        rows = [row("a", "Same text"), row("b", "Same text"), row("c", "Same text")]
        h = Harness(rows, self.tmp.name)
        h.enricher(FakeClient()).run()
        # Simulate losing the copies (e.g. a crash right after the original was saved).
        lines = [l for l in (h.dir / "records.jsonl").read_text().splitlines() if '"review_id":"a"' in l]
        (h.dir / "records.jsonl").write_text("\n".join(lines) + "\n")
        h.store = RecordStore(h.dir / "records.jsonl")
        client = FakeClient()
        s = h.enricher(client, phase="resume").run()
        self.assertEqual(client.calls, [])
        self.assertEqual(s["cache_copies"], 2)
        recs = h.latest()
        self.assertEqual(recs["b"]["cache_source_id"], "a")
        self.assertEqual(recs["c"]["cache_source_id"], "a")  # direct original, never a chain

    def test_cache_disabled_sends_everything(self):
        h = Harness([row("a", "Same"), row("b", "Same")], self.tmp.name)
        client = FakeClient()
        h.enricher(client, cache_enabled=False).run()
        self.assertEqual(client.calls, [["a", "b"]])


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        import gc
        gc.collect()
        self.tmp.cleanup()

    def test_transient_retry_with_backoff_and_retry_after(self):
        h = Harness(rows_n(3), self.tmp.name)

        def hook(n, reviews):
            if n == 1:
                raise TransientModelError("HTTP 503")
            if n == 2:
                e = TransientModelError("HTTP 429")
                e.retry_after = 9
                raise e
        s = h.enricher(FakeClient(hook)).run()
        self.assertEqual(s["completed_new"], 3)
        self.assertEqual(h.sleeps, [0.5, 9])
        ev = h.events()
        self.assertEqual([e["outcome"] for e in ev], ["failed", "failed", "succeeded"])
        self.assertEqual([e["attempt"] for e in ev], [1, 2, 3])
        self.assertEqual(ev[0]["input_tokens"], 0)
        self.assertTrue(ev[0]["error"].startswith("transient"))

    def test_timeout_flagged_uncertain(self):
        h = Harness(rows_n(2), self.tmp.name)

        def hook(n, reviews):
            if n == 1:
                raise TransientModelError("The read operation timed out")
            if n == 2:
                e = TransientModelError("APITimeoutError")
                e.uncertain_charge = True
                raise e
        ledger = SpendLedger(1.0)
        h.enricher(FakeClient(hook), ledger=ledger, reserve_usd_per_request=0.01).run()
        ev = h.events()
        self.assertEqual([e.get("uncertain_charge") for e in ev[:2]], [True, True])
        self.assertAlmostEqual(ledger.uncertain_usd, 0.02)

    def test_transient_exhausted_quarantines_and_stops(self):
        h = Harness(rows_n(12), self.tmp.name)

        def hook(n, reviews):
            raise TransientModelError("HTTP 500")
        s = h.enricher(FakeClient(hook), max_transient_attempts=2, max_consecutive_failed_batches=2).run()
        self.assertEqual(s["stop_reason"], "transient_failures")
        self.assertEqual(s["calls"], 4)
        recs = h.latest()
        self.assertEqual(len(recs), 8)
        self.assertTrue(all(r["reason"].startswith("retries_exhausted:") for r in recs.values()))

    def test_invalid_output_retry_then_split_then_quarantine(self):
        h = Harness(rows_n(4), self.tmp.name)

        def hook(n, reviews):
            if any(r.review_id == "r02" for r in reviews):
                raise InvalidModelOutput("malformed answers")
        client = FakeClient(hook)
        s = h.enricher(client).run()
        recs = h.latest()
        self.assertEqual(recs["r02"]["status"], "quarantined")
        self.assertTrue(recs["r02"]["reason"].startswith("invalid_model_output:"))
        self.assertEqual({r for r in recs if recs[r]["status"] == "completed"}, {"r00", "r01", "r03"})
        sizes = [len(c) for c in client.calls]
        self.assertEqual(sizes, [4, 4, 2, 2, 2, 1, 1, 1])  # 2 tries per failing level; good halves pass
        self.assertEqual(s["calls_failed"], 6)

    def test_foreign_id_is_invalid_response(self):
        h = Harness(rows_n(2), self.tmp.name)
        client = FakeClient(lambda n, r: "foreign" if n == 1 else None)
        s = h.enricher(client).run()
        self.assertEqual(s["completed_new"], 2)
        ev = h.events()
        self.assertEqual(ev[0]["outcome"], "failed")
        self.assertIn("unrequested", ev[0]["error"])
        self.assertEqual(ev[0]["input_tokens"], 20)  # billed usage kept on the failed attempt

    def test_missing_id_retried_in_new_batch(self):
        h = Harness(rows_n(3), self.tmp.name)
        client = FakeClient(lambda n, r: "drop:r01" if n == 1 else None)
        s = h.enricher(client).run()
        self.assertEqual(client.calls, [["r00", "r01", "r02"], ["r01"]])
        self.assertEqual(s["completed_new"], 3)

    def test_missing_id_quarantined_after_retry(self):
        h = Harness(rows_n(2), self.tmp.name)
        client = FakeClient(lambda n, r: "drop:r01")
        h.enricher(client).run()
        self.assertEqual(h.latest()["r01"]["reason"], "missing_from_response")

    def test_per_record_validation(self):
        for action, reason in (("badquote", "evidence_quote_not_in_source"), ("wronglc", "label_config_mismatch"),
                               ("boolsev", "severity"), ("dup", "duplicate_review_id")):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as d:
                h = Harness(rows_n(3), d)
                client = FakeClient(lambda n, r, a=action: a + ":r01")
                h.enricher(client).run()
                recs = h.latest()
                self.assertEqual(recs["r01"]["status"], "quarantined")
                self.assertEqual(recs["r01"]["reason"], "invalid_model_output:" + reason)
                self.assertEqual(recs["r00"]["status"], "completed")
                self.assertEqual(client.calls, [["r00", "r01", "r02"], ["r01"]])

    def test_validate_record_rules(self):
        good = label_for("a", "hello world", LC)
        self.assertIsNotNone(en.validate_record(good, "hello world", LC)[0])
        bad = [dict(good.__dict__, topic="music"), dict(good.__dict__, sentiment=float("nan")),
               dict(good.__dict__, sentiment=1.5), dict(good.__dict__, entities=["ok", " "]),
               dict(good.__dict__, needs_review=0), dict(good.__dict__, evidence_quote="  "),
               dict(good.__dict__, severity=6), dict(good.__dict__, severity=3.0)]
        for b in bad:
            self.assertIsNone(en.validate_record(b, "hello world", LC)[0], b)

    def test_model_client_error_stops(self):
        h = Harness(rows_n(8), self.tmp.name)

        def hook(n, reviews):
            if n == 2:
                raise ModelClientError("HTTP 402: out of credits")
        s = h.enricher(FakeClient(hook)).run()
        self.assertEqual(s["stop_reason"], "model_client_error")
        self.assertIn("402", s["stop_message"])
        self.assertEqual(len(h.store.completed_ids(LC)), 4)
        self.assertEqual(h.events()[-1]["outcome"], "failed")

    def test_budget_stop(self):
        h = Harness(rows_n(12), self.tmp.name)
        ledger = SpendLedger(0.25)
        client = FakeClient()
        s = h.enricher(client, ledger=ledger, reserve_usd_per_request=0.1).run()
        self.assertEqual(s["stop_reason"], "budget")
        self.assertEqual(len(client.calls), 2)  # 0.2 committed + 0.1 next > 0.25
        self.assertAlmostEqual(ledger.committed_usd(), 0.2)

    def test_budget_uses_provider_cost(self):
        h = Harness(rows_n(12), self.tmp.name)
        ledger = SpendLedger(10.0, rates={"enrich": {"input_per_mtok": 1000.0, "output_per_mtok": 0.0}})
        client = FakeClient()
        s = h.enricher(client, ledger=ledger, est_output_tokens_per_review=0).run()
        self.assertEqual(s["stop_reason"], "completed")
        self.assertAlmostEqual(ledger.spent_usd, 120 * 1000.0 / 1e6)


class ConcurrencyAndResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        import gc
        gc.collect()
        self.tmp.cleanup()

    def test_workers_share_store(self):
        h = Harness(rows_n(40) + [row("d%d" % i, "Review number 3 about playback") for i in range(3)], self.tmp.name)
        client = FakeClient()
        s = h.enricher(client, workers=4).run()
        self.assertEqual(s["completed_new"], 40)
        self.assertEqual(s["cache_copies"], 3)
        sent = [i for c in client.calls for i in c]
        self.assertEqual(len(sent), len(set(sent)))
        lines = (h.dir / "records.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 43)

    def test_max_batches_then_resume_never_resends(self):
        h = Harness(rows_n(10), self.tmp.name)
        first = FakeClient()
        s1 = h.enricher(first, max_batches=2).run()
        self.assertEqual(s1["stop_reason"], "max_batches")
        before = h.store.completed_ids(LC)
        self.assertEqual(len(before), 8)
        second = FakeClient()
        s2 = h.enricher(second, phase="resume").run()
        self.assertEqual(s2["stop_reason"], "completed")
        resent = {i for c in second.calls for i in c}
        self.assertEqual(resent & before, set())
        self.assertEqual(resent, {"r08", "r09"})
        phases = [e["phase"] for e in h.events()]
        self.assertEqual(phases, ["initial", "initial", "resume"])

    def test_stop_event_interrupts(self):
        h = Harness(rows_n(12), self.tmp.name)
        stop = threading.Event()

        def hook(n, reviews):
            stop.set()
        s = h.enricher(FakeClient(hook), stop_event=stop).run()
        self.assertEqual(s["stop_reason"], "interrupted")
        self.assertEqual(len(h.store.completed_ids(LC)), 4)  # in-flight batch finished and saved


if __name__ == "__main__":
    unittest.main()

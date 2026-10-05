"""Enrichment harness (docs/INTERFACES.md §5).

Pending queue -> exact-text cache -> batches (<=50, optional token sizing) -> client call with
bounded retries -> per-record validation -> save (calls, then records) after every batch.
The client is untrusted: every returned record is re-validated here.

Save order note: within a batch we append the call events *before* the records. If the process
dies between the two writes, the IDs are simply re-sent on resume (a duplicate call is visible in
calls.jsonl). The reverse order would leave completed records with no call evidence, which the
checker flags as ``unlogged_completed_records`` and cannot be repaired afterwards.
"""
from __future__ import annotations

import math
import random
import re
import socket
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .context import make_call_event, utc_now
from .rowhash import INTENTS, TOPICS
from .spend import BudgetExceeded, backoff_delay, cost_from_usage

LABEL_FIELDS = ("topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review", "label_config")
HARD_MAX_BATCH = 50

STOP_COMPLETED = "completed"
STOP_MAX_BATCHES = "max_batches"
STOP_INTERRUPTED = "interrupted"
STOP_BUDGET = "budget"
STOP_CLIENT_ERROR = "model_client_error"
STOP_TRANSIENT = "transient_failures"


def _errors():
    from labelling import model_client as mc
    return mc.ModelClientError, mc.TransientModelError, mc.InvalidModelOutput, mc.ReviewInput


# --------------------------------------------------------------------------- settings

@dataclass
class EnrichSettings:
    max_batch: int = HARD_MAX_BATCH
    size_by_tokens: bool = True
    token_budget: int = 32000
    workers: int = 1
    cache_enabled: bool = True
    retry_quarantined: bool = True
    max_transient_attempts: int = 5
    invalid_attempts: int = 2              # "one retry" on InvalidModelOutput, then split
    missing_retry_rounds: int = 1          # missing/invalid records re-sent once, then quarantined
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    max_consecutive_failed_batches: int = 3
    max_batches: Optional[int] = None
    est_output_tokens_per_review: int = 60
    reserve_usd_per_request: Optional[float] = None
    provider: Optional[str] = None

    @classmethod
    def from_config(cls, config: Dict[str, Any], **overrides) -> "EnrichSettings":
        b = config.get("batching") or {}
        lim = config.get("limits") or {}
        rc = config.get("result_cache") or {}
        cl = config.get("client") or {}
        s = cls(
            max_batch=int(b.get("max_reviews_per_request", HARD_MAX_BATCH)),
            size_by_tokens=bool(b.get("size_by_tokens", True)),
            token_budget=int(b.get("token_budget", 32000)),
            workers=int(lim.get("workers", 1)),
            cache_enabled=bool(rc.get("enabled", True)),
            retry_quarantined=bool(lim.get("retry_quarantined", True)),
            max_transient_attempts=int(lim.get("max_transient_attempts", 5)),
            invalid_attempts=int(lim.get("invalid_attempts", 2)),
            missing_retry_rounds=int(lim.get("missing_retry_rounds", 1)),
            backoff_base_seconds=float(lim.get("backoff_base_seconds", 1.0)),
            backoff_max_seconds=float(lim.get("backoff_max_seconds", 60.0)),
            max_consecutive_failed_batches=int(lim.get("max_consecutive_failed_batches", 3)),
            est_output_tokens_per_review=int(lim.get("est_output_tokens_per_review", 60)),
            reserve_usd_per_request=lim.get("reserve_usd_per_enrich_request"),
            provider=cl.get("provider"),
        )
        for k, v in overrides.items():
            if v is not None:
                setattr(s, k, v)
        s.max_batch = max(1, min(HARD_MAX_BATCH, s.max_batch))
        s.workers = max(1, s.workers)
        return s


# --------------------------------------------------------------------------- validation

def _get(rec, name, default=None):
    if isinstance(rec, dict):
        return rec.get(name, default)
    return getattr(rec, name, default)


def validate_record(rec, source_text: str, label_config: str) -> Tuple[Optional[dict], str]:
    """Return ``(normalized_label_fields, "")`` or ``(None, reason)``. Mirrors the checker's schema."""
    topic, intent = _get(rec, "topic"), _get(rec, "intent")
    if topic not in TOPICS:
        return None, "topic"
    if intent not in INTENTS:
        return None, "intent"
    sev = _get(rec, "severity")
    if type(sev) is not int or not 1 <= sev <= 5:
        return None, "severity"
    sent = _get(rec, "sentiment")
    if type(sent) not in (int, float) or not math.isfinite(sent) or not -1 <= sent <= 1:
        return None, "sentiment"
    ents = _get(rec, "entities")
    if not isinstance(ents, (list, tuple)) or not all(isinstance(x, str) and x.strip() for x in ents):
        return None, "entities"
    quote = _get(rec, "evidence_quote")
    if not isinstance(quote, str) or not quote.strip():
        return None, "evidence_quote_blank"
    if quote not in source_text:
        return None, "evidence_quote_not_in_source"
    nr = _get(rec, "needs_review")
    if type(nr) is not bool:
        return None, "needs_review"
    lc = _get(rec, "label_config")
    if lc != label_config:
        return None, "label_config_mismatch"
    return {"topic": topic, "intent": intent, "sentiment": sent, "severity": sev, "entities": list(ents),
            "evidence_quote": quote, "needs_review": nr, "label_config": lc}, ""


def quarantine_record(review_id: str, source_sha256: str, reason: str) -> dict:
    return {"review_id": review_id, "source_sha256": source_sha256, "status": "quarantined", "reason": reason}


def write_empty_quarantines(prepared, store) -> int:
    """Ingest step: every blank text is quarantined ``empty_review_text`` and never sent."""
    out = []
    for rid in prepared.empty_ids:
        latest = store.latest(rid) if rid in store else None
        if latest and latest.get("status") == "quarantined" and latest.get("reason") == "empty_review_text" \
                and latest.get("source_sha256") == prepared.source_sha[rid]:
            continue
        out.append(quarantine_record(rid, prepared.source_sha[rid], "empty_review_text"))
    return store.upsert(out)


def _is_timeout(exc: BaseException) -> bool:
    for e in (exc, exc.__cause__, exc.__context__):
        if isinstance(e, (TimeoutError, socket.timeout)):
            return True
    return bool(re.search(r"time[d]?[\s_-]?out", str(exc), re.I))


class _Stop(Exception):
    def __init__(self, reason: str, message: str = ""):
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


class _BadResponse(Exception):
    pass


@dataclass
class UnitOutcome:
    ids: List[str]
    events: List[dict] = field(default_factory=list)
    completed: List[dict] = field(default_factory=list)
    quarantined: List[dict] = field(default_factory=list)
    stop: Optional[Tuple[str, str]] = None
    transient_exhausted: bool = False


# --------------------------------------------------------------------------- harness

class Enricher:
    def __init__(self, *, prepared, store, call_log, client, label_config: str, phase: str, invocation_id: str,
                 settings: Optional[EnrichSettings] = None, limiter=None, ledger=None,
                 stop_event: Optional[threading.Event] = None, sleep: Callable[[float], None] = time.sleep,
                 rng: Callable[[], float] = random.random, clock: Callable[[], float] = time.monotonic,
                 progress: Optional[Callable[[dict], None]] = None):
        self.p = prepared
        self.store = store
        self.call_log = call_log
        self.client = client
        self.lc = label_config
        self.phase = phase
        self.invocation_id = invocation_id
        self.s = settings or EnrichSettings()
        self.limiter = limiter
        self.ledger = ledger
        self.stop_event = stop_event or threading.Event()
        self.sleep = sleep
        self.rng = rng
        self.clock = clock
        self.progress = progress
        self.stop_reason: Optional[str] = None
        self.stop_message = ""
        self.counts = {"units": 0, "calls": 0, "calls_succeeded": 0, "calls_failed": 0, "completed_new": 0,
                       "quarantined_new": 0, "cache_copies": 0, "input_tokens": 0, "output_tokens": 0,
                       "uncertain_charge_calls": 0}
        (self.ModelClientError, self.TransientModelError, self.InvalidModelOutput, self.ReviewInput) = _errors()
        self._sizer = getattr(client, "max_batch_by_tokens", None) or \
            getattr(sys.modules.get(type(client).__module__), "max_batch_by_tokens", None)
        self._waiters: Dict[str, List[str]] = {}

    # -- planning
    def plan(self) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Return (originals to send in file order, [(id, cache source id)] copies available now)."""
        texts, lc, store = self.p.texts, self.lc, self.store
        sources: Dict[str, str] = {}
        done = set()
        for rid, text in texts.items():
            m = store.meta(rid)
            if m is not None and m[0] == "completed" and m[1] == lc:
                done.add(rid)
                if self.s.cache_enabled and not m[2] and text not in sources:
                    sources[text] = rid
        originals: List[str] = []
        copies: List[Tuple[str, str]] = []
        first_pending: Dict[str, str] = {}
        for rid, text in texts.items():
            if rid in done or not text.strip():
                continue
            if not self.s.retry_quarantined:
                m = store.meta(rid)
                if m is not None and m[0] == "quarantined":
                    continue
            if self.s.cache_enabled:
                src = sources.get(text)
                if src is not None:
                    copies.append((rid, src))
                    continue
                orig = first_pending.get(text)
                if orig is not None:
                    self._waiters.setdefault(orig, []).append(rid)
                    continue
                first_pending[text] = rid
            originals.append(rid)
        return originals, copies

    def _copy(self, rid: str, src: dict) -> dict:
        rec = {"review_id": rid, "source_sha256": self.p.source_sha[rid], "status": "completed"}
        for k in LABEL_FIELDS:
            rec[k] = src[k]
        rec["cache_source_id"] = src["review_id"]
        return rec

    def batches(self, originals: List[str]) -> Iterator[List[str]]:
        i, n_all = 0, len(originals)
        while i < n_all:
            window = originals[i:i + self.s.max_batch]
            n = len(window)
            if self.s.size_by_tokens and self._sizer is not None:
                wtexts = [self.p.texts[r] for r in window]
                try:
                    n = int(self._sizer(wtexts, budget=self.s.token_budget, hard_cap=self.s.max_batch))
                except TypeError:
                    n = int(self._sizer(wtexts))
                n = max(1, min(len(window), n))
            yield window[:n]
            i += n

    # -- one call attempt loop for one request
    def _estimate(self, ids: List[str]) -> Tuple[int, float]:
        est_in = sum(len(self.p.texts[r]) for r in ids) // 3 + 150 * len(ids) + 1000
        if self.s.reserve_usd_per_request is not None:
            return est_in, float(self.s.reserve_usd_per_request)
        rates = self.ledger.rates_for("enrich") if self.ledger else None
        cost = cost_from_usage(rates, est_in, self.s.est_output_tokens_per_review * len(ids))
        return est_in, float(cost or 0.0)

    def _event(self, ids, outcome, attempt, started, t0, *, model=None, request_id=None, usage=None,
               error=None, cost=None, **extra) -> dict:
        def num(name):
            v = getattr(usage, name, None) if usage is not None else None
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
            return int(v) if ok else None
        model = model or (getattr(usage, "model", None) if usage is not None else None) \
            or getattr(self.client, "model", None) or "unknown"
        return make_call_event(
            role="enrich", review_ids=list(ids), model=str(model), phase=self.phase, outcome=outcome,
            label_config=self.lc, input_tokens=num("input_tokens") or 0, output_tokens=num("output_tokens") or 0,
            request_id=request_id, invocation_id=self.invocation_id, attempt=attempt, started_at=started,
            ended_at=utc_now(), duration_ms=int((self.clock() - t0) * 1000),
            provider=(getattr(usage, "provider", None) if usage is not None else None) or self.s.provider,
            error=error, cached_input_tokens=num("cached_input_tokens"), reasoning_tokens=num("reasoning_tokens"),
            cost_usd=cost, batch_size=len(ids), fallback=False, **extra)

    def _call(self, ids: List[str], out: UnitOutcome):
        """Return ((good, redo), None) on a usable response, or (None, (kind, detail)) after retries."""
        reviews = [self.ReviewInput(review_id=r, review_text=self.p.texts[r]) for r in ids]
        est_tokens, est_cost = self._estimate(ids)
        transient = invalid = attempt = 0
        while True:
            if attempt and self.stop_event.is_set():
                raise _Stop(STOP_INTERRUPTED, "interrupted during retries")
            attempt += 1
            res = None
            if self.ledger is not None:
                try:
                    res = self.ledger.reserve(est_cost, "enrich")
                except BudgetExceeded as e:
                    raise _Stop(STOP_BUDGET, str(e))
            if self.limiter is not None:
                self.limiter.acquire(est_tokens)
            started, t0 = utc_now(), self.clock()
            try:
                result = self.client.classify_batch(reviews, self.lc)
            except self.TransientModelError as e:
                uncertain = bool(getattr(e, "uncertain_charge", False)) or _is_timeout(e)
                if self.ledger is not None:
                    if uncertain:
                        self.ledger.commit(res, None, "enrich", uncertain=True)
                    else:
                        self.ledger.release(res)
                out.events.append(self._event(ids, "failed", attempt, started, t0, usage=getattr(e, "usage", None),
                                              error="transient: " + str(e)[:300], uncertain_charge=uncertain))
                transient += 1
                if transient >= self.s.max_transient_attempts:
                    return None, ("transient", str(e)[:120])
                self.sleep(backoff_delay(transient, base=self.s.backoff_base_seconds, cap=self.s.backoff_max_seconds,
                                         rng=self.rng, retry_after=getattr(e, "retry_after", None)))
                continue
            except self.InvalidModelOutput as e:
                kind_detail = str(e)[:120]
                err = "invalid_output: " + str(e)[:300]
            except self.ModelClientError as e:
                if self.ledger is not None:
                    self.ledger.release(res)
                out.events.append(self._event(ids, "failed", attempt, started, t0, error="client_error: " + str(e)[:300]))
                raise _Stop(STOP_CLIENT_ERROR, str(e))
            except Exception as e:  # noqa: BLE001 - an untrusted client bug is treated as invalid output
                kind_detail = type(e).__name__
                err = "client_exception: %s: %s" % (type(e).__name__, str(e)[:250])
            else:
                usage = getattr(result, "usage", None)
                cost = getattr(usage, "cost_usd", None) if usage is not None else None
                if cost is None and self.ledger is not None:
                    cost = cost_from_usage(self.ledger.rates_for("enrich"),
                                           int(getattr(usage, "input_tokens", 0) or 0),
                                           int(getattr(usage, "output_tokens", 0) or 0),
                                           getattr(usage, "cached_input_tokens", None))
                if self.ledger is not None:
                    self.ledger.commit(res, cost, "enrich")
                res = None
                rid = getattr(result, "request_id", None)
                try:
                    good, redo = self._validate(ids, result)
                except _BadResponse as e:
                    out.events.append(self._event(ids, "failed", attempt, started, t0, usage=usage,
                                                  request_id=rid, error="invalid_response: " + str(e)[:300], cost=cost))
                    kind_detail = str(e)[:120]
                    err = None
                else:
                    out.events.append(self._event(ids, "succeeded", attempt, started, t0, usage=usage,
                                                  request_id=rid, cost=cost,
                                                  invalid_records=len([1 for _, r in redo if r != "missing_from_response"]),
                                                  missing_records=len([1 for _, r in redo if r == "missing_from_response"])))
                    return (good, redo), None
            # invalid output path (exception or unusable response)
            if res is not None and self.ledger is not None:
                self.ledger.release(res)
            if err is not None:
                out.events.append(self._event(ids, "failed", attempt, started, t0, error=err))
            invalid += 1
            if invalid >= self.s.invalid_attempts:
                return None, ("invalid", kind_detail)

    def _validate(self, ids: List[str], result) -> Tuple[List[dict], List[Tuple[str, str]]]:
        records = getattr(result, "records", None)
        if records is None or isinstance(records, (str, bytes, dict)):
            raise _BadResponse("records is not a list")
        try:
            records = list(records)
        except TypeError:
            raise _BadResponse("records is not iterable")
        requested = set(ids)
        seen: Dict[str, Any] = {}
        dups, foreign = set(), []
        for rec in records:
            rid = _get(rec, "review_id")
            if not isinstance(rid, str) or rid not in requested:
                foreign.append(rid)
                continue
            if rid in seen:
                dups.add(rid)
                continue
            seen[rid] = rec
        if foreign:
            raise _BadResponse("unrequested review_id(s) in response: %r" % (foreign[:3],))
        good, redo = [], []
        for rid in ids:
            if rid in dups:
                redo.append((rid, "invalid_model_output:duplicate_review_id"))
                continue
            rec = seen.get(rid)
            if rec is None:
                redo.append((rid, "missing_from_response"))
                continue
            fields, why = validate_record(rec, self.p.texts[rid], self.lc)
            if fields is None:
                redo.append((rid, "invalid_model_output:" + why))
                continue
            row = {"review_id": rid, "source_sha256": self.p.source_sha[rid], "status": "completed"}
            row.update(fields)
            good.append(row)
        return good, redo

    def _run_batch(self, ids: List[str], out: UnitOutcome) -> List[Tuple[str, str]]:
        ok, failure = self._call(ids, out)
        if ok is None:
            kind, detail = failure
            if kind == "invalid" and len(ids) > 1:
                mid = len(ids) // 2
                return self._run_batch(ids[:mid], out) + self._run_batch(ids[mid:], out)
            if kind == "transient":
                out.transient_exhausted = True
                reason = "retries_exhausted:" + detail
            else:
                reason = "invalid_model_output:" + detail
            out.quarantined.extend(quarantine_record(r, self.p.source_sha[r], reason) for r in ids)
            return []
        good, redo = ok
        out.completed.extend(good)
        return redo

    def process_unit(self, ids: List[str]) -> UnitOutcome:
        out = UnitOutcome(ids=list(ids))
        try:
            redo = self._run_batch(list(ids), out)
            rounds = 0
            while redo and rounds < self.s.missing_retry_rounds:
                rounds += 1
                redo = self._run_batch([r for r, _ in redo], out)
            for rid, reason in redo:
                out.quarantined.append(quarantine_record(rid, self.p.source_sha[rid], reason))
        except _Stop as s:
            out.stop = (s.reason, s.message)
        return out

    # -- writing (main thread only)
    def _write(self, out: UnitOutcome) -> None:
        self.call_log.log_many(out.events)
        rows = list(out.completed) + list(out.quarantined)
        for rec in out.completed:
            for w in self._waiters.pop(rec["review_id"], []):
                rows.append(self._copy(w, rec))
                self.counts["cache_copies"] += 1
        for rec in out.quarantined:
            for w in self._waiters.pop(rec["review_id"], []):
                rows.append(quarantine_record(w, self.p.source_sha[w], "same_text_as_quarantined:" + rec["review_id"]))
                self.counts["quarantined_new"] += 1
        self.store.upsert(rows)
        c = self.counts
        c["units"] += 1
        c["completed_new"] += len(out.completed)
        c["quarantined_new"] += len(out.quarantined)
        for e in out.events:
            c["calls"] += 1
            c["calls_succeeded" if e["outcome"] == "succeeded" else "calls_failed"] += 1
            c["input_tokens"] += e["input_tokens"]
            c["output_tokens"] += e["output_tokens"]
            c["uncertain_charge_calls"] += bool(e.get("uncertain_charge"))
        if self.ledger is not None:
            self.ledger.save()
        if self.progress:
            self.progress(dict(c))

    def _admit(self, batch: List[str], admitted: int) -> bool:
        if self.stop_reason:
            return False
        if self.stop_event.is_set():
            self.stop_reason, self.stop_message = STOP_INTERRUPTED, "stop requested (SIGINT)"
            return False
        if self.s.max_batches is not None and admitted >= self.s.max_batches:
            self.stop_reason, self.stop_message = STOP_MAX_BATCHES, "--max-batches %d reached" % self.s.max_batches
            return False
        if self.ledger is not None and not self.ledger.can_admit(self._estimate(batch)[1]):
            self.stop_reason, self.stop_message = STOP_BUDGET, "spend cap would be exceeded by the next batch"
            return False
        return True

    def _after(self, out: UnitOutcome, state: Dict[str, int]) -> None:
        if out.stop and not self.stop_reason:
            self.stop_reason, self.stop_message = out.stop
        if out.transient_exhausted and not out.completed:
            state["consecutive_failed"] += 1
            if state["consecutive_failed"] >= self.s.max_consecutive_failed_batches and not self.stop_reason:
                self.stop_reason = STOP_TRANSIENT
                self.stop_message = "%d consecutive batches exhausted transient retries" % state["consecutive_failed"]
        elif out.completed:
            state["consecutive_failed"] = 0

    def run(self) -> dict:
        t0 = self.clock()
        originals, copies = self.plan()
        pending_at_start = len(originals) + len(copies) + sum(len(v) for v in self._waiters.values())
        # Copies from records completed in earlier invocations (no call; never logged as one).
        cache_ready = 0
        chunk: List[dict] = []
        src_cache: Dict[str, dict] = {}
        for rid, src in copies:
            if src not in src_cache:
                if len(src_cache) > 10000:
                    src_cache.clear()
                src_cache[src] = self.store.latest(src)
            chunk.append(self._copy(rid, src_cache[src]))
            if len(chunk) >= 2000:
                cache_ready += self.store.upsert(chunk)
                chunk = []
        cache_ready += self.store.upsert(chunk)
        self.counts["cache_copies"] += cache_ready

        state = {"consecutive_failed": 0}
        admitted = 0
        gen = self.batches(originals)
        if self.s.workers <= 1:
            for batch in gen:
                if not self._admit(batch, admitted):
                    break
                admitted += 1
                out = self.process_unit(batch)
                self._write(out)
                self._after(out, state)
        else:
            with ThreadPoolExecutor(max_workers=self.s.workers) as ex:
                inflight = set()
                exhausted = False
                while True:
                    while not exhausted and len(inflight) < self.s.workers:
                        batch = next(gen, None)
                        if batch is None:
                            exhausted = True
                            break
                        if not self._admit(batch, admitted):
                            exhausted = True
                            break
                        admitted += 1
                        inflight.add(ex.submit(self.process_unit, batch))
                    if not inflight:
                        break
                    done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                    for fut in done:
                        out = fut.result()
                        self._write(out)
                        self._after(out, state)
                    if self.stop_reason:
                        exhausted = True
        remaining = sum(1 for rid, text in self.p.texts.items() if text.strip()
                        and (self.store.meta(rid) or ("", None, False))[:2] != ("completed", self.lc))
        if not self.stop_reason:
            self.stop_reason = STOP_COMPLETED
        summary = dict(self.counts)
        summary.update({"phase": self.phase, "label_config": self.lc, "pending_at_start": pending_at_start,
                        "originals_to_send": len(originals), "batches_admitted": admitted,
                        "remaining_unfinished": remaining, "stop_reason": self.stop_reason,
                        "stop_message": self.stop_message, "seconds": round(self.clock() - t0, 3)})
        return summary

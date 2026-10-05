"""Verify stage: an independent re-label of a deterministic sample (docs/INTERFACES.md §6).

The verifier sees only ``(review_id, review_text)`` — never the enrichment prediction and never
golden labels. Its output is evidence only: this stage never modifies ``records``.

This module also holds the small helpers shared by the chat-role stages (verify, group, memo):
``chat_attempt`` (one logged attempt), ``StageCache`` (downstream result cache keyed by the
stage's inputs and configuration, so a warm run makes zero new calls) and ``parse_json_payload``.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pipeline.context import StageContext, make_call_event, utc_now
from pipeline.io import append_jsonl, atomic_write_json, atomic_write_text, dumps_line, read_jsonl
from pipeline.rowhash import INTENTS, TOPICS, canonical

STAGE = "verify"
PROMPT_VERSION = "verify-default-v1"
MAX_BATCH = 25
ROOT = Path(__file__).resolve().parents[2]
OVERRIDE_PROMPT = ROOT / "evals" / "verifier_prompt.md"

DEFAULT_PROMPT = """You are an independent reviewer labelling Spotify app-store reviews.
Classify the review text itself. Ignore star ratings and anything not in the text.

topic (exactly one):
- access: login, signup, password or account access
- usability: navigation, controls, layout, queue/playlist management, ad interruptions
- playback: playback failure, crashes, lag, connection failures, audio quality, resource use
- downloads: downloading, saved music, offline listening, disappearing downloads
- catalog: missing songs/artists, search/discovery, recommendations, lyrics availability
- billing: price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls
- support: contacting support and the support response
- other: general praise/criticism, unrelated content, or no supported specific topic
Choose the problem with the highest supported severity; on a tie, the first specific problem
mentioned. For a positive review choose the first specific praised feature; general praise is
"other". Mentioning a paid plan alone does not make the topic billing.

intent (first that applies): cancellation (explicitly leaving, uninstalling, cancelling, or
threatening to) -> complaint (negative experience, including mixed praise/criticism) -> request
(desired change without a reported failure) -> praise -> unclear. Bare boycott slogans and
meaningless text are unclear. General "bad app" is a complaint.

severity (integer 1-5):
1 no reported problem (praise, neutral/unclear, pure feature request)
2 dislike, generic criticism, minor annoyance, cosmetic issue; no functional loss
3 a degraded or restricted function; some use or workaround remains
4 a clearly blocked core task, such as inability to log in or play music
5 explicit serious financial, privacy, or data harm (an expensive plan, a crash, or angry
  language alone is insufficient)

needs_review (boolean): true when context is missing or the label is genuinely ambiguous.
Do not invent impact."""

OUTPUT_INSTRUCTIONS = (
    "Label every review below. Return ONLY a JSON object keyed by review_id, where each value is "
    '{"topic": <topic>, "intent": <intent>, "severity": <1-5 integer>, "needs_review": <true|false>}. '
    "Use exactly the review_id strings given. No prose, no markdown."
)

LABEL_FIELDS = ("topic", "intent", "severity", "needs_review")


# --------------------------------------------------------------------------- shared helpers

def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chat_model_name(ctx: StageContext, stage: str) -> str:
    """Best-effort model id before a call is made (used for cache keys and failed-attempt logs)."""
    model = getattr(ctx.chat, "model", None) or (ctx.config.get(stage) or {}).get("model")
    if not model:
        model = (ctx.config.get("chat") or {}).get("model")
    return str(model) if model else "unknown"


def _known_request_ids(ctx: StageContext) -> set:
    cache = ctx.extras.setdefault("_request_ids", None)
    if cache is None:
        cache = set()
        for event in read_jsonl(Path(ctx.run_dir) / "calls.jsonl"):
            rid = event.get("request_id")
            if isinstance(rid, str):
                cache.add(rid)
        ctx.extras["_request_ids"] = cache
    return cache


def _unique_request_id(ctx: StageContext, provider_id: Optional[str], attempt: int) -> str:
    known = _known_request_ids(ctx)
    rid = provider_id or "local-" + uuid.uuid4().hex
    if rid in known:
        rid = "%s#%d" % (rid, attempt)
    while rid in known:
        rid = "%s#%s" % (rid, uuid.uuid4().hex[:8])
    known.add(rid)
    return rid


def chat_attempt(ctx: StageContext, *, role: str, messages: List[dict], max_tokens: int,
                 review_ids: Sequence[str], attempt: int, response_format: Optional[str] = None,
                 validate=None, **extra) -> Tuple[Optional[Any], Optional[str], dict]:
    """Make one chat call and log exactly one call event.

    ``validate(text)`` returns the parsed value or raises ValueError. A provider error or a
    validation failure is logged with ``outcome="failed"`` (usage kept when the provider sent it).
    Returns ``(parsed_or_None, raw_text_or_None, event)``.
    """
    started, t0 = utc_now(), time.monotonic()
    result, error, parsed = None, None, None
    try:
        result = ctx.chat.complete(messages, max_tokens=max_tokens, temperature=0.0,
                                   response_format=response_format)
        parsed = validate(result.text) if validate else result.text
    except Exception as exc:  # noqa: BLE001 - every failure is logged as a failed attempt
        error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
    ended, duration = utc_now(), int((time.monotonic() - t0) * 1000)
    event = make_call_event(
        role=role, review_ids=list(review_ids),
        model=(getattr(result, "model", None) or chat_model_name(ctx, role)),
        phase=ctx.phase, outcome="failed" if error else "succeeded", label_config=ctx.label_config,
        input_tokens=getattr(result, "input_tokens", 0) or 0,
        output_tokens=getattr(result, "output_tokens", 0) or 0,
        request_id=_unique_request_id(ctx, getattr(result, "request_id", None), attempt),
        invocation_id=ctx.invocation_id, attempt=attempt, started_at=started, ended_at=ended,
        duration_ms=duration, provider=getattr(ctx.chat, "provider", None), error=error,
        cached_input_tokens=getattr(result, "cached_input_tokens", None),
        cost_usd=getattr(result, "cost_usd", None), **extra)
    ctx.log_call(event)
    return (None if error else parsed), (getattr(result, "text", None) if result else None), event


def parse_json_payload(text: str):
    """Parse a JSON object/array from model text, tolerating code fences and stray prose."""
    if not isinstance(text, str):
        raise ValueError("response text is not a string")
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    try:
        return json.loads(s)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = s.find(open_c), s.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except ValueError:
                continue
    raise ValueError("no JSON object in response")


class StageCache:
    """Downstream result cache: ``cache_key = sha256(canonical({stage, prompt, model, config, payload}))``.

    Saved results live in ``<run_dir>/<stage>/responses.jsonl``; lookups check the current run dir
    first, then ``ctx.extras["warm_from"]`` (a prior run dir). A hit means no model call and no
    call log line. ``finish()`` writes ``<stage>/cache.json``.
    """

    def __init__(self, ctx: StageContext, stage: str):
        self.ctx, self.stage = ctx, stage
        self.path = Path(ctx.run_dir) / stage / "responses.jsonl"
        self.sources: List[Tuple[Path, Dict[str, dict]]] = []
        dirs = [Path(ctx.run_dir)]
        warm = ctx.extras.get("warm_from") if isinstance(ctx.extras, dict) else None
        if warm:
            dirs.append(Path(warm))
        for d in dirs:
            p = d / stage / "responses.jsonl"
            entries: Dict[str, dict] = {}
            for line in read_jsonl(p):
                if isinstance(line.get("cache_key"), str):
                    entries[line["cache_key"]] = line
            self.sources.append((p, entries))
        self.calls: List[dict] = []

    @staticmethod
    def key(stage: str, prompt: str, model: str, config: dict, payload) -> str:
        return sha256_hex(canonical({"stage": stage, "prompt_sha256": sha256_hex(prompt), "model": model,
                                     "config": config, "payload": payload}))

    def get(self, key: str) -> Optional[dict]:
        for path, entries in self.sources:
            if key in entries:
                entry = dict(entries[key])
                entry["_source"] = str(path)
                self.calls.append({"cache_key": key, "hit": True, "source": str(path)})
                return entry
        return None

    def put(self, key: str, text: str, event: dict) -> None:
        entry = {"cache_key": key, "stage": self.stage, "text": text, "request_id": event.get("request_id"),
                 "model": event.get("model"), "input_tokens": event.get("input_tokens"),
                 "output_tokens": event.get("output_tokens"), "invocation_id": self.ctx.invocation_id,
                 "saved_at": utc_now()}
        append_jsonl(self.path, entry)
        self.sources[0][1][key] = entry
        self.calls.append({"cache_key": key, "hit": False, "source": None})

    def miss(self, key: str) -> None:
        self.calls.append({"cache_key": key, "hit": False, "source": None})

    def finish(self) -> dict:
        keys = [c["cache_key"] for c in self.calls]
        sources = sorted({c["source"] for c in self.calls if c["source"]})
        hit = bool(self.calls) and all(c["hit"] for c in self.calls)
        summary = {"cache_key": sha256_hex(canonical(keys)) if keys else None, "hit": hit,
                   "source": (sources[0] if len(sources) == 1 else sources) if hit else None,
                   "calls": self.calls}
        atomic_write_json(Path(self.ctx.run_dir) / self.stage / "cache.json", summary)
        return summary


def cached_chat(ctx: StageContext, cache: StageCache, *, role: str, key: str, messages: List[dict],
                max_tokens: int, review_ids: Sequence[str], validate, retries: int = 1,
                response_format: Optional[str] = None, revise=None, **extra) -> Tuple[Optional[Any], dict]:
    """Return ``(parsed, info)``; use the stage cache, else call with one retry on failure.

    ``revise(messages, text, error) -> messages`` (optional) builds the retry request from a response
    that failed validation, so the model sees what to fix. The cache key stays that of the original
    request: the cached text is the validated answer for these inputs.
    """
    entry = cache.get(key)
    if entry is not None:
        try:
            return validate(entry["text"]), {"cache_hit": True, "request_id": entry.get("request_id"),
                                             "source": entry["_source"]}
        except ValueError:
            cache.calls.pop()  # stale/invalid cached entry: fall through to a real call
    errors = []
    for attempt in range(1, retries + 2):
        parsed, text, event = chat_attempt(ctx, role=role, messages=messages, max_tokens=max_tokens,
                                           review_ids=review_ids, attempt=attempt, validate=validate,
                                           response_format=response_format, stage_cache_key=key, **extra)
        if event["outcome"] == "succeeded":
            cache.put(key, text, event)
            return parsed, {"cache_hit": False, "request_id": event["request_id"], "attempts": attempt}
        errors.append(event["error"])
        if revise is not None and text:
            messages = revise(messages, text, event["error"])
    cache.miss(key)
    return None, {"cache_hit": False, "request_id": None, "attempts": retries + 1, "errors": errors}


# --------------------------------------------------------------------------- verify stage

def load_prompt() -> Tuple[str, str]:
    """(prompt_text, source). evals/verifier_prompt.md overrides the default when present."""
    if OVERRIDE_PROMPT.exists():
        text = OVERRIDE_PROMPT.read_text(encoding="utf-8").strip()
        if text:
            return text, "evals/verifier_prompt.md"
    return DEFAULT_PROMPT, "default:" + PROMPT_VERSION


def hash_fraction(review_id: str) -> float:
    return int(sha256_hex(review_id)[:16], 16) / float(1 << 64)


def select_sample(records: Dict[str, dict], texts: Dict[str, str], *, sample_fraction: float,
                  min_items: int, max_items: int) -> dict:
    """Completed, non-cached records ranked by sha256(review_id); take those under the threshold,
    clamped to [min_items, max_items]. Deterministic and independent of record order."""
    candidates = []
    for rid, rec in records.items():
        if rec.get("status") != "completed" or rec.get("cache_source_id") or rid not in texts:
            continue
        candidates.append((hash_fraction(rid), rid))
    candidates.sort()
    under = sum(1 for h, _ in candidates if h < sample_fraction)
    n = min(max(under, min_items), max_items, len(candidates))
    return {"method": "sha256(review_id)[:16] / 2^64 < sample_fraction, clamped to [min_items, max_items]",
            "sample_fraction": sample_fraction, "min_items": min_items, "max_items": max_items,
            "candidates": len(candidates), "under_threshold": under, "selected": n,
            "review_ids": [rid for _, rid in candidates[:n]]}


def _as_mapping(payload) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize a verifier response to {review_id: item}; returns (mapping, duplicate_ids)."""
    items, dups = {}, []
    if isinstance(payload, dict):
        for k in ("labels", "results", "items", "reviews"):
            if isinstance(payload.get(k), list) and len(payload) == 1:
                payload = payload[k]
                break
    if isinstance(payload, list):
        for item in payload:
            rid = item.get("review_id") if isinstance(item, dict) else None
            if not isinstance(rid, str):
                continue
            if rid in items:
                dups.append(rid)
            items[rid] = item
        return items, dups
    if isinstance(payload, dict):
        return dict(payload), dups
    raise ValueError("response is neither a JSON object nor a list")


def validate_label(item) -> Optional[str]:
    """Return an error string, or None when the verifier label is valid."""
    if not isinstance(item, dict):
        return "not an object"
    if item.get("topic") not in TOPICS:
        return "bad topic %r" % (item.get("topic"),)
    if item.get("intent") not in INTENTS:
        return "bad intent %r" % (item.get("intent"),)
    sev = item.get("severity")
    if type(sev) is not int or not 1 <= sev <= 5:
        return "bad severity %r" % (sev,)
    if type(item.get("needs_review")) is not bool:
        return "bad needs_review %r" % (item.get("needs_review"),)
    return None


def build_messages(prompt: str, batch: List[dict]) -> List[dict]:
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": OUTPUT_INSTRUCTIONS + "\n\nREVIEWS:\n" + dumps_line(batch)}]


def build_report(sample_ids: List[str], labels: Dict[str, dict], records: Dict[str, dict],
                 texts: Dict[str, str], extra: dict) -> dict:
    statuses = Counter(labels[r]["status"] for r in sample_ids)
    ok = [r for r in sample_ids if labels[r]["status"] == "ok"]
    agree = Counter()
    confusion = {f: Counter() for f in ("topic", "intent", "severity", "needs_review")}
    disagreements = []
    for rid in ok:
        pred, ver = records[rid], labels[rid]
        diff = []
        for f in ("topic", "intent", "severity", "needs_review"):
            if pred.get(f) == ver[f]:
                agree[f] += 1
            else:
                diff.append(f)
                confusion[f][(str(pred.get(f)), str(ver[f]))] += 1
        if isinstance(pred.get("severity"), int) and abs(pred["severity"] - ver["severity"]) <= 1:
            agree["severity_within_1"] += 1
        if all(f not in diff for f in ("topic", "intent", "severity")):
            agree["joint"] += 1
        if diff:
            disagreements.append({"review_id": rid, "fields": diff, "review_text": texts.get(rid, ""),
                                  "enrich": {f: pred.get(f) for f in LABEL_FIELDS},
                                  "verifier": {f: ver[f] for f in LABEL_FIELDS}})
    n_ok = len(ok)

    def rate(k):
        return round(agree[k] / n_ok, 6) if n_ok else None

    return dict(extra, **{
        "n": len(sample_ids), "n_valid": n_ok, "verifier_invalid": len(sample_ids) - n_ok,
        "status_counts": dict(sorted(statuses.items())),
        "agreement": {"topic": rate("topic"), "intent": rate("intent"), "severity_exact": rate("severity"),
                      "severity_within_1": rate("severity_within_1"), "needs_review": rate("needs_review"),
                      "joint_topic_intent_severity": rate("joint")},
        "agreement_counts": {k: agree[k] for k in ("topic", "intent", "severity", "severity_within_1",
                                                     "needs_review", "joint")},
        "confusion_pairs": {f: [{"enrich": a, "verifier": b, "count": c}
                                for (a, b), c in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))]
                            for f, cnt in confusion.items()},
        "disagreements": disagreements,
        "note": "Agreement is computed over items with a valid verifier label; invalid/missing/failed "
                "verifier items are counted in verifier_invalid. Verify never modifies records.",
    })


def run(ctx: StageContext) -> dict:
    cfg = ctx.config.get("verify") or {}
    out = ctx.stage_dir(STAGE)
    sample = select_sample(ctx.records, ctx.texts,
                           sample_fraction=float(cfg.get("sample_fraction", 0.05)),
                           min_items=int(cfg.get("min_items", 20)), max_items=int(cfg.get("max_items", 500)))
    atomic_write_json(out / "sample.json", sample)
    sample_ids = sample["review_ids"]
    prompt, prompt_source = load_prompt()
    batch_size = max(1, min(MAX_BATCH, int(cfg.get("batch_size", MAX_BATCH))))
    max_text = int(cfg.get("max_text_chars", 4000))
    max_tokens = int(cfg.get("max_tokens", 60 * batch_size + 200))
    model = chat_model_name(ctx, STAGE)
    cache = StageCache(ctx, STAGE)
    labels: Dict[str, dict] = {}
    unknown_ids: List[str] = []
    calls_made = cache_hits = 0
    key_config = {"max_tokens": max_tokens, "max_text_chars": max_text, "temperature": 0.0}

    for start in range(0, len(sample_ids), batch_size):
        ids = sample_ids[start:start + batch_size]
        batch = [{"review_id": rid, "review_text": ctx.texts[rid][:max_text]} for rid in ids]
        if ctx.chat is None:
            for rid in ids:
                labels[rid] = {"review_id": rid, "status": "not_run", "error": "no chat client"}
            continue
        messages = build_messages(prompt, batch)
        key = StageCache.key(STAGE, prompt, model, key_config, batch)
        parsed, info = cached_chat(ctx, cache, role=STAGE, key=key, messages=messages, max_tokens=max_tokens,
                                   review_ids=ids, response_format="json",
                                   validate=lambda t: _as_mapping(parse_json_payload(t)),
                                   prompt_source=prompt_source)
        cache_hits += bool(info["cache_hit"])
        calls_made += info.get("attempts", 0)
        if parsed is None:
            for rid in ids:
                labels[rid] = {"review_id": rid, "status": "call_failed", "error": (info.get("errors") or [""])[-1]}
            continue
        mapping, dups = parsed
        unknown_ids.extend(sorted(k for k in mapping if k not in set(ids)))
        for rid in ids:
            base = {"review_id": rid, "request_id": info["request_id"], "cache_hit": info["cache_hit"]}
            if rid in dups:
                labels[rid] = dict(base, status="invalid", error="duplicate id in response")
            elif rid not in mapping:
                labels[rid] = dict(base, status="missing", error="id missing from response")
            else:
                err = validate_label(mapping[rid])
                if err:
                    labels[rid] = dict(base, status="invalid", error=err)
                else:
                    labels[rid] = dict(base, status="ok", **{f: mapping[rid][f] for f in LABEL_FIELDS})

    atomic_write_text(out / "labels.jsonl", "".join(dumps_line(labels[r]) + "\n" for r in sample_ids))
    report = build_report(sample_ids, labels, ctx.records, ctx.texts, {
        "prompt_source": prompt_source, "prompt_sha256": sha256_hex(prompt), "model": model,
        "batch_size": batch_size, "unknown_ids_in_responses": unknown_ids,
        "sample": {k: v for k, v in sample.items() if k != "review_ids"},
    })
    atomic_write_json(out / "report.json", report)
    cache_summary = cache.finish()
    return {"sampled": len(sample_ids), "valid": report["n_valid"], "verifier_invalid": report["verifier_invalid"],
            "calls": calls_made, "cache_hits": cache_hits, "cache_hit": cache_summary["hit"],
            "topic_agreement": report["agreement"]["topic"]}

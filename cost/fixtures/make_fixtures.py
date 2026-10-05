#!/usr/bin/env python3
"""Regenerate the SYNTHETIC cost-calculator fixture (tests only; NOT a measured pilot).

Writes a 10-row synthetic CSV, a synthetic manifest, and two fake run directories
(`runs/pilot-cold`, `runs/pilot-warm`) in the shape of docs/INTERFACES.md section 4.
Every token count, duration and cost below is invented to exercise the calculator:
a failed+retried call (HTTP 429), a timeout flagged `uncertain_charge`, an exact-text
cache hit, an empty-text quarantine, and a warm run with zero enrichment calls.

Usage (from the repo root):
    python3 cost/fixtures/make_fixtures.py
    python3 cost/cost_calc.py collect --cold cost/fixtures/runs/pilot-cold \
        --warm cost/fixtures/runs/pilot-warm --csv cost/fixtures/cost_10_synthetic.csv \
        --manifest cost/fixtures/manifest_synthetic.json --expect-rows 10 --out cost/fixtures
    python3 cost/cost_calc.py replay --source cost/fixtures
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")
LABEL_CONFIG = "typesafe/jev-latest:prompt-v1:schema-a5-v1"
JEV = "jev-1.13.0"
CHAT = "claude-haiku-4-5"

ROWS = [
    ("syn-001", "SYNTHETIC: app crashes every time I open a playlist", "1", "0", "8.8.0.1", "2023-01-01 10:00:00"),
    ("syn-002", "SYNTHETIC: love it", "5", "2", "8.8.0.1", "2023-01-02 10:00:00"),
    ("syn-003", "SYNTHETIC: please add a sleep timer to podcasts", "4", "0", "8.8.0.2", "2023-01-03 10:00:00"),
    ("syn-004", "SYNTHETIC: love it", "5", "0", "", "2023-01-04 10:00:00"),
    ("syn-005", "SYNTHETIC: charged twice for premium this month", "1", "7", "8.8.0.2", "2023-01-05 10:00:00"),
    ("syn-006", "SYNTHETIC: downloads disappear after update", "2", "1", "8.8.0.3", "2023-01-06 10:00:00"),
    ("syn-007", "SYNTHETIC: cancelling, too many ads", "1", "0", "8.8.0.3", "2023-01-07 10:00:00"),
    ("syn-008", "SYNTHETIC: cannot log in with my email", "1", "3", "8.8.0.3", "2023-01-08 10:00:00"),
    ("syn-009", "SYNTHETIC: okay I guess", "3", "0", "8.8.0.4", "2023-01-09 10:00:00"),
    ("syn-010", "", "3", "0", "8.8.0.4", "2023-01-10 10:00:00"),
]

LABELS = {
    "syn-001": ("playback", "complaint", -0.8, 4, ["crash"], "app crashes every time I open a playlist"),
    "syn-002": ("other", "praise", 0.9, 1, [], "love it"),
    "syn-003": ("usability", "request", 0.1, 2, ["sleep timer"], "please add a sleep timer to podcasts"),
    "syn-005": ("billing", "complaint", -0.9, 5, ["premium"], "charged twice for premium this month"),
    "syn-006": ("downloads", "complaint", -0.6, 4, ["downloads"], "downloads disappear after update"),
    "syn-007": ("billing", "cancellation", -0.7, 4, ["ads"], "cancelling, too many ads"),
    "syn-008": ("access", "complaint", -0.7, 4, ["log in"], "cannot log in with my email"),
    "syn-009": ("other", "unclear", 0.0, 1, [], "okay I guess"),
}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row: dict) -> str:
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def call(rid, role, ids, model, phase, outcome, inp, out, inv, attempt, start, end, ms, provider,
         error=None, cached=None, reasoning=None, cost=None, **extra):
    ev = {"request_id": rid, "role": role, "review_ids": ids, "model": model, "phase": phase,
          "outcome": outcome, "label_config": LABEL_CONFIG, "input_tokens": inp, "output_tokens": out,
          "invocation_id": inv, "attempt": attempt, "started_at": start, "ended_at": end,
          "duration_ms": ms, "provider": provider, "error": error, "cached_input_tokens": cached,
          "reasoning_tokens": reasoning, "cost_usd": cost}
    ev.update(extra)
    return ev


def main() -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FIELDS)
    for r in ROWS:
        w.writerow(r)
    csv_bytes = buf.getvalue().encode("utf-8")
    csv_path = HERE / "cost_10_synthetic.csv"
    csv_path.write_bytes(csv_bytes)
    sha = hashlib.sha256(csv_bytes).hexdigest()
    (HERE / "manifest_synthetic.json").write_text(json.dumps({
        "SYNTHETIC": "Test fixture only. Not the course manifest.",
        "files": {"cost_10_synthetic.csv": {"bytes": len(csv_bytes), "sha256": sha}},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = {r[0]: dict(zip(FIELDS, r)) for r in ROWS}
    recs = []
    for rid, row in rows.items():
        if rid == "syn-010":
            recs.append({"review_id": rid, "source_sha256": row_sha(row), "status": "quarantined",
                         "reason": "empty_review_text"})
            continue
        src = "syn-002" if rid == "syn-004" else rid
        t, i, s, sev, ents, q = LABELS[src]
        rec = {"review_id": rid, "source_sha256": row_sha(row), "status": "completed", "topic": t,
               "intent": i, "sentiment": s, "severity": sev, "entities": ents, "evidence_quote": q,
               "needs_review": False, "label_config": LABEL_CONFIG}
        if rid == "syn-004":
            rec["cache_source_id"] = "syn-002"
        recs.append(rec)

    base_cfg = {
        "SYNTHETIC": True,
        "client": {"provider": "typesafe", "model": "jev-latest", "api_key_env": "TYPESAFE_API_KEY"},
        "label_config": LABEL_CONFIG, "prompt_version": "v1", "schema_version": "a5-v1",
        "batching": {"max_reviews_per_request": 50},
        "limits": {"workers": 1, "spend_cap_usd": 1.0},
        "roles": {r: {"provider": "anthropic", "model": CHAT, "effort": "none", "max_tokens": m,
                      "prompt_version": "draft-1"}
                  for r, m in (("verify", 600), ("group", 1500), ("memo", 2500))},
        "verify": {"sample_fraction": 0.1},
    }

    cold = HERE / "runs" / "pilot-cold"
    warm = HERE / "runs" / "pilot-warm"
    for d in (cold, warm):
        d.mkdir(parents=True, exist_ok=True)

    cfg = dict(base_cfg, run_id="syn-cold", synthetic=True, dry_run=False,
               input_csv="cost/fixtures/cost_10_synthetic.csv", input_sha256=sha)
    (cold / "run_config.json").write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (cold / "records.jsonl").write_text("".join(dumps(r) + "\n" for r in recs), encoding="utf-8")
    inv = "syn-inv-cold-1"
    b1 = ["syn-001", "syn-002", "syn-003", "syn-005"]
    b2 = ["syn-006", "syn-007", "syn-008", "syn-009"]
    cold_calls = [
        call("syn-req-01", "enrich", b1, JEV, "initial", "failed", 0, 0, inv, 1,
             "2026-10-01T10:00:01.000000Z", "2026-10-01T10:00:01.400000Z", 400, "typesafe",
             error="TransientModelError: HTTP 429 rate limited (Retry-After: 1)"),
        call("syn-req-02", "enrich", b1, JEV, "initial", "succeeded", 2400, 400, inv, 2,
             "2026-10-01T10:00:02.500000Z", "2026-10-01T10:00:06.500000Z", 4000, "typesafe"),
        call("syn-req-03", "enrich", b2, JEV, "initial", "failed", 0, 0, inv, 1,
             "2026-10-01T10:00:07.000000Z", "2026-10-01T10:01:07.000000Z", 60000, "typesafe",
             error="TransientModelError: timeout after 60s", uncertain_charge=True),
        call("syn-req-04", "enrich", b2, JEV, "initial", "succeeded", 2300, 380, inv, 2,
             "2026-10-01T10:01:08.000000Z", "2026-10-01T10:01:12.000000Z", 4000, "typesafe",
             api_key="sk-THIS-IS-A-FAKE-KEY-THAT-MUST-BE-STRIPPED-0000"),
        call("syn-req-05", "verify", ["syn-001", "syn-006"], CHAT, "initial", "succeeded", 900, 120, inv, 1,
             "2026-10-01T10:01:13.000000Z", "2026-10-01T10:01:15.000000Z", 2000, "anthropic",
             cached=300, reasoning=40, cost=None),
        call("syn-req-06", "group", [], CHAT, "initial", "succeeded", 1500, 200, inv, 1,
             "2026-10-01T10:01:16.000000Z", "2026-10-01T10:01:19.000000Z", 3000, "anthropic",
             cached=0, reasoning=0, cost=None),
        call("syn-req-07", "memo", [], CHAT, "initial", "succeeded", 2500, 600, inv, 1,
             "2026-10-01T10:01:20.000000Z", "2026-10-01T10:01:26.000000Z", 6000, "anthropic",
             cached=0, reasoning=0, cost=None),
    ]
    (cold / "calls.jsonl").write_text("".join(dumps(c) + "\n" for c in cold_calls), encoding="utf-8")
    (cold / "invocations.jsonl").write_text(dumps({
        "invocation_id": inv, "phase": "initial", "started_at": "2026-10-01T10:00:00.000000Z",
        "ended_at": "2026-10-01T10:01:27.500000Z", "wall_seconds": 87.5, "stop_reason": "completed",
        "stages": ["ingest", "enrich", "verify", "group", "rank", "memo"],
        "counts": {"completed": 9, "quarantined": 1, "cache_reused": 1, "enrich_calls": 4}}) + "\n",
        encoding="utf-8")

    cfgw = dict(base_cfg, run_id="syn-warm", synthetic=True, dry_run=False, warm_from="runs/pilot-cold",
                input_csv="cost/fixtures/cost_10_synthetic.csv", input_sha256=sha)
    (warm / "run_config.json").write_text(json.dumps(cfgw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (warm / "records.jsonl").write_text("".join(dumps(r) + "\n" for r in recs), encoding="utf-8")
    invw = "syn-inv-warm-1"
    warm_calls = [
        call("syn-req-08", "memo", [], CHAT, "resume", "succeeded", 2500, 590, invw, 1,
             "2026-10-01T11:00:01.000000Z", "2026-10-01T11:00:03.000000Z", 2000, "anthropic",
             cached=2048, reasoning=0, cost=None),
    ]
    (warm / "calls.jsonl").write_text("".join(dumps(c) + "\n" for c in warm_calls), encoding="utf-8")
    (warm / "invocations.jsonl").write_text(dumps({
        "invocation_id": invw, "phase": "resume", "started_at": "2026-10-01T11:00:00.000000Z",
        "ended_at": "2026-10-01T11:00:03.400000Z", "wall_seconds": 3.4, "stop_reason": "completed",
        "stages": ["ingest", "enrich", "verify", "group", "rank", "memo"],
        "counts": {"completed": 9, "quarantined": 1, "cache_reused": 9, "enrich_calls": 0}}) + "\n",
        encoding="utf-8")
    print("wrote synthetic fixture to", HERE)


if __name__ == "__main__":
    main()

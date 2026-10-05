#!/usr/bin/env python3
"""Offline cost and runtime calculator for the 100-review pilot (docs/specs/COST_CALCULATOR.md).

Commands (standard library only; this file never makes network or provider calls):

    python3 cost/cost_calc.py                      # = replay: read saved files in cost/, write cost/report.md
    python3 cost/cost_calc.py replay --source DIR  # replay another evidence folder (e.g. cost/fixtures)
    python3 cost/cost_calc.py replay --rates-multiplier 2      # demonstrate the rate-doubling invariant
    python3 cost/cost_calc.py replay --set budget_usd=10       # override any assumption (dotted path)
    python3 cost/cost_calc.py collect --cold runs/pilot-cold --warm runs/pilot-warm [--csv cost_100.csv]

`replay` reads only: pilot_calls.jsonl, pilot_records.jsonl, usage.csv, pilot_timing.json (evidence),
and rates.csv, assumptions.json, local_compute.csv (editable inputs). `collect` reads run directories
written by run_pipeline.py (docs/INTERFACES.md section 4) and writes the evidence files.

Formulas:
    price_per_unit = price / per                 (per = 1,000,000 for a per-million price)
    item_cost      = billed_units x price_per_unit x rates_multiplier
    total_cost     = sum(item_cost)              (unknown if any item is unknown; the known part is shown)
    input_uncached = input_tokens - cached_input_tokens
    output         = output_tokens               (reasoning is NOT added again when included in output)
"""
from __future__ import annotations

import argparse
import copy
import csv
import fnmatch
import hashlib
import io
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

COST_DIR = Path(__file__).resolve().parent
REPO = COST_DIR.parent
FIXTURES_DIR = COST_DIR / "fixtures"
DEFAULT_MANIFEST = REPO / "docs" / "specs" / "manifest.json"
DEFAULT_DATASET_DIR = Path(os.environ.get(
    "A5_DATASET_DIR",
    str(Path.home() / "Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset"),
))

FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")
ROLES = ("enrich", "verify", "group", "memo")
RUNS = ("cold", "warm")
PER_REVIEW_ROLES = ("enrich", "verify")
FIXED_ROLES = ("group", "memo")
SCENARIOS = ("base", "conservative")
USAGE_COLUMNS = ("request_id", "run", "role", "provider", "model", "item", "billed_units", "unit", "note")
RATE_COLUMNS = ("provider", "model", "item", "unit", "price", "currency", "per", "source_url", "checked_on", "notes")
EVIDENCE_FILES = ("pilot_calls.jsonl", "pilot_records.jsonl", "usage.csv", "pilot_timing.json")
INPUT_FILES = ("rates.csv", "assumptions.json", "local_compute.csv")
UNKNOWN = "**unknown**"
D0 = Decimal(0)


class CalcError(Exception):
    """A check failed; the message says which and why."""


# ---------------------------------------------------------------- small helpers

def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row) -> str:
    """Grading-contract source row hash (identical to check_submission.row_sha)."""
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path) -> List[dict]:
    out = []
    path = Path(path)
    if not path.exists():
        return out
    lines = path.read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            if n == len(lines) - 1:   # torn final line after a crash
                continue
            raise CalcError("%s line %d is not valid JSON" % (path, n + 1))
    return out


def dumps_line(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str)


def write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:   # Path.write_text(newline=) needs 3.10
        f.write(text)
    os.replace(str(tmp), str(path))


def rel(path) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return str(p)


def dec(value) -> Optional[Decimal]:
    """Parse a number; blank/None/'unknown' -> None (unknown)."""
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("unknown", "none", "null", "n/a", "na"):
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise CalcError("not a number: %r" % (value,))
    if not d.is_finite():
        raise CalcError("not a finite number: %r" % (value,))
    return d


def as_int(value) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_ts(value) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip().replace("Z", "+00:00")
    m = re.match(r"^(.*\.\d{6})\d+(.*)$", s)   # fromisoformat (3.9) takes at most 6 fraction digits
    if m:
        s = m.group(1) + m.group(2)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class Amount:
    """A sum of non-negative costs where some parts may be unknown."""

    __slots__ = ("known", "unknown", "reasons")

    def __init__(self, known: Decimal = D0, unknown: int = 0, reasons: Optional[Iterable[str]] = None):
        self.known = Decimal(known)
        self.unknown = int(unknown)
        self.reasons = set(reasons or ())

    @classmethod
    def of(cls, value: Optional[Decimal], reason: str = "unknown") -> "Amount":
        if value is None:
            return cls(D0, 1, [reason])
        return cls(value)

    def add(self, other: "Amount") -> "Amount":
        self.known += other.known
        self.unknown += other.unknown
        self.reasons |= other.reasons
        return self

    def __add__(self, other: "Amount") -> "Amount":
        return Amount(self.known, self.unknown, self.reasons).add(other)

    def scale(self, factor: Optional[Decimal], reason: str = "unknown factor") -> "Amount":
        if factor is None:
            if self.known == 0 and self.unknown == 0:
                return Amount()
            return Amount(D0, max(1, self.unknown), self.reasons | {reason})
        return Amount(self.known * factor, self.unknown, self.reasons)

    @property
    def value(self) -> Optional[Decimal]:
        return self.known if self.unknown == 0 else None

    def fmt(self, places: int = 6) -> str:
        if self.unknown == 0:
            return usd(self.known, places)
        return "%s (known part %s + %d unknown item%s)" % (
            UNKNOWN, usd(self.known, places), self.unknown, "" if self.unknown == 1 else "s")

    def as_json(self) -> dict:
        return {"known_usd": str(q6(self.known)), "unknown_items": self.unknown,
                "value_usd": None if self.unknown else str(q6(self.known))}


def q6(d: Decimal) -> Decimal:
    return Decimal(d).quantize(Decimal("0.000001"))


def usd(d: Optional[Decimal], places: int = 6) -> str:
    if d is None:
        return UNKNOWN
    return "$" + format(Decimal(d).quantize(Decimal(1).scaleb(-places)), ",f")


def num(v, places: int = 2) -> str:
    if v is None:
        return UNKNOWN
    if isinstance(v, int) and not isinstance(v, bool):
        return format(v, ",d")
    return format(round(float(v), places), ",.%df" % places)


def secs(v) -> str:
    if v is None:
        return UNKNOWN
    v = float(v)
    if v >= 3600:
        return "%s s (%.2f h)" % (format(round(v, 1), ",.1f"), v / 3600.0)
    return "%s s" % format(round(v, 2), ",.2f")


def md_table(headers: List[str], rows: List[List[Any]]) -> str:
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(cell(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(cell(x) for x in r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------- secret scrubbing

_KEY_NAME = re.compile(r"(api[_-]?key|authorization|secret|password|passwd|bearer|credential|"
                       r"access[_-]?token|auth[_-]?token|refresh[_-]?token|session[_-]?token|^key$|^x-api-key$)", re.I)
_KEY_VALUE = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|sk_[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._\-]{8,}|"
                        r"ts_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")


def _env_secrets() -> List[str]:
    vals = []
    for k, v in os.environ.items():
        if v and len(v) >= 12 and _KEY_NAME.search(k) and not k.endswith("_ENV"):
            vals.append(v)
    return sorted(set(vals), key=len, reverse=True)


def scrub(value, _secrets: Optional[List[str]] = None):
    """Drop key-like fields and redact key-like strings (recursive). `api_key_env` names are kept."""
    secrets = _env_secrets() if _secrets is None else _secrets
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _KEY_NAME.search(str(k)) and not str(k).endswith("_env"):
                continue
            out[k] = scrub(v, secrets)
        return out
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, str):
        s = _KEY_VALUE.sub("[REDACTED]", value)
        for sec in secrets:
            s = s.replace(sec, "[REDACTED]")
        return s
    return value


# ---------------------------------------------------------------- rates and usage

def load_rates(path) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in RATE_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise CalcError("%s is missing columns %s" % (path, missing))
        for n, r in enumerate(reader, start=2):
            per = dec(r["per"])
            if per is None or per <= 0:
                raise CalcError("%s line %d: 'per' must be a positive number" % (path, n))
            price = dec(r["price"])
            if price is not None and price < 0:
                raise CalcError("%s line %d: negative price" % (path, n))
            rows.append(dict(r, price_dec=price, per_dec=per, line=n))
    return rows


def find_rate(rates: List[dict], provider: Optional[str], model: Optional[str], item: str) -> Optional[dict]:
    """Most specific matching row: exact provider beats '*', fewer wildcards in model wins, then file order."""
    best, best_key = None, None
    prov = (provider or "").lower()
    for r in rates:
        if r["item"] != item:
            continue
        rp = r["provider"].strip().lower()
        if rp not in ("*", prov):
            continue
        if not fnmatch.fnmatchcase((model or "").lower(), r["model"].strip().lower()):
            continue
        key = (0 if rp == "*" else 1, -r["model"].count("*"), -r["line"])
        if best_key is None or key > best_key:
            best, best_key = r, key
    return best


def price_per_unit(rate: Optional[dict], multiplier: Decimal = Decimal(1)) -> Optional[Decimal]:
    if rate is None or rate["price_dec"] is None:
        return None
    return rate["price_dec"] / rate["per_dec"] * multiplier


def usage_rows_for_call(call: dict, run: str, rates: List[dict], reasoning_included: bool = True) -> List[dict]:
    """Mutually exclusive billed items for one attempt (one usage.csv row each)."""
    rid = str(call.get("request_id", ""))
    base = {"request_id": rid, "run": run, "role": call.get("role", ""),
            "provider": call.get("provider") or "", "model": call.get("model") or ""}
    rows = []

    def add(item, units, unit="token", note=""):
        rows.append(dict(base, item=item, billed_units="" if units is None else str(units), unit=unit, note=note))

    inp = as_int(call.get("input_tokens")) or 0
    out = as_int(call.get("output_tokens")) or 0
    cached = as_int(call.get("cached_input_tokens"))
    reasoning = as_int(call.get("reasoning_tokens"))
    if cached is not None:
        if cached > inp:
            raise CalcError("call %s: cached_input_tokens %d > input_tokens %d" % (rid, cached, inp))
        add("input_uncached", inp - cached, note="input_tokens - cached_input_tokens")
        add("input_cached", cached)
    else:
        add("input_uncached", inp, note="cached_input_tokens not reported; all input billed uncached")
    if reasoning_included:
        add("output", out, note="" if not reasoning else "includes %d reasoning tokens (not billed again)" % reasoning)
    else:
        add("output", out)
        if reasoning:
            add("reasoning", reasoning, note="reasoning billed separately (assumption)")
    # Optional per-request / per-classification items, only when rates.csv defines them for this model.
    if find_rate(rates, base["provider"], base["model"], "request") is not None:
        add("request", 1, unit="request")
    if find_rate(rates, base["provider"], base["model"], "classification") is not None:
        n = len(call.get("review_ids") or []) if call.get("outcome") == "succeeded" else 0
        add("classification", n, unit="classification")
    if call.get("uncertain_charge"):
        add("uncertain_charge", None, unit="usd",
            note="timeout/unknown outcome: possible charge; reconcile with provider dashboard")
    return rows


def cost_usage(rows: List[dict], rates: List[dict], multiplier: Decimal = Decimal(1)) -> List[dict]:
    """Attach item_cost (Decimal or None=unknown) and the reason to each usage row."""
    out = []
    for r in rows:
        units = dec(r.get("billed_units"))
        rate = find_rate(rates, r.get("provider"), r.get("model"), r["item"])
        reason, cost, ppu = "", None, price_per_unit(rate, multiplier)
        if rate is not None and rate["unit"].strip().lower() != str(r.get("unit", "")).strip().lower():
            raise CalcError("unit mismatch for %s/%s %s: usage '%s' vs rate '%s'" % (
                r.get("provider"), r.get("model"), r["item"], r.get("unit"), rate["unit"]))
        if units is None:
            reason = "billed units not measured (%s)" % r["item"]
        elif units == 0:
            cost = D0
        elif rate is None:
            reason = "no rate row for %s/%s %s" % (r.get("provider"), r.get("model"), r["item"])
        elif ppu is None:
            reason = "price blank in rates.csv for %s/%s %s" % (r.get("provider"), r.get("model"), r["item"])
        else:
            cost = units * ppu
        out.append(dict(r, units_dec=units, rate=rate, price_per_unit=ppu, cost=cost, reason=reason))
    return out


def read_usage_csv(path) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in ("request_id", "run", "role", "model", "item", "billed_units", "unit")
                   if c not in (reader.fieldnames or [])]
        if missing:
            raise CalcError("%s is missing columns %s" % (path, missing))
        return [dict(r) for r in reader]


def usage_csv_text(rows: List[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(USAGE_COLUMNS), lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


# ---------------------------------------------------------------- assumptions

def load_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def set_path(obj: dict, dotted: str, raw: str) -> None:
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    parts = dotted.split(".")
    cur = obj
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def scen(assumptions: dict, key: str, scenario: str, default=0):
    v = assumptions.get(key, default)
    if isinstance(v, dict):
        v = v.get(scenario, default)
    return default if v is None else v


def load_local_compute(path) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def local_compute_cost(rows: List[dict], wall_seconds: Optional[float]) -> Tuple[Amount, List[str]]:
    """hours (blank = wall clock) x watts/1000 x USD/kWh + fixed_usd, per machine row."""
    total, notes = Amount(), []
    if not rows:
        return Amount(D0, 1, ["local_compute.csv missing"]), ["no local_compute.csv"]
    for r in rows:
        hours = dec(r.get("hours"))
        if hours is None and wall_seconds is not None:
            hours = Decimal(str(round(float(wall_seconds), 6))) / Decimal(3600)
        watts, kwh = dec(r.get("power_watts")), dec(r.get("usd_per_kwh"))
        fixed = dec(r.get("fixed_usd")) or D0
        if hours is None or watts is None or kwh is None:
            missing = [n for n, v in (("hours", hours), ("power_watts", watts), ("usd_per_kwh", kwh)) if v is None]
            total.add(Amount(fixed, 1, ["%s: %s unknown" % (r.get("machine", "?"), ", ".join(missing))]))
            notes.append("%s: %s unknown" % (r.get("machine", "?"), ", ".join(missing)))
        else:
            total.add(Amount(hours * watts / Decimal(1000) * kwh + fixed))
    return total, notes


# ---------------------------------------------------------------- collect

def _last_by_id(records: List[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for r in records:
        if "review_id" in r:
            out[str(r["review_id"])] = r
    return out


def read_csv_rows(path) -> List[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise CalcError("%s header %s != %s" % (path, reader.fieldnames, list(FIELDS)))
        return [dict(r) for r in reader]


def verify_csv(csv_path, manifest_path, manifest_key: Optional[str], expect_rows: int) -> dict:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise CalcError("CSV not found: %s" % csv_path)
    manifest = load_json(manifest_path)
    key = manifest_key or csv_path.name
    entry = (manifest.get("files") or {}).get(key)
    if not entry:
        raise CalcError("manifest %s has no entry for %r" % (rel(manifest_path), key))
    actual = file_sha256(csv_path)
    if actual != entry.get("sha256"):
        raise CalcError("checksum mismatch for %s: file %s != manifest %s" % (key, actual, entry.get("sha256")))
    rows = read_csv_rows(csv_path)
    ids = [r["review_id"] for r in rows]
    if len(ids) != expect_rows:
        raise CalcError("%s has %d rows, expected %d" % (key, len(ids), expect_rows))
    if len(set(ids)) != len(ids):
        raise CalcError("%s has duplicate review_ids" % key)
    texts = [r["review_text"] for r in rows]
    nonempty = [t for t in texts if t.strip() != ""]
    return {"csv_name": key, "csv_sha256": actual, "manifest": rel(manifest_path),
            "manifest_sha256": entry.get("sha256"), "checksum_ok": True, "rows": rows, "ids": ids,
            "id_count": len(ids), "nonempty_texts": len(nonempty), "empty_texts": len(texts) - len(nonempty),
            "unique_nonempty_texts": len(set(nonempty))}


def _find_sha(cfg) -> Optional[str]:
    if isinstance(cfg, dict):
        for k in sorted(cfg):
            v = cfg[k]
            if "sha256" in str(k).lower() and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v):
                return v
        for k in sorted(cfg):
            found = _find_sha(cfg[k]) if isinstance(cfg[k], dict) else None
            if found:
                return found
    return None


def _section(cfg: dict, role: str) -> dict:
    for container in (cfg, cfg.get("config") if isinstance(cfg.get("config"), dict) else {}):
        for key in ("roles", "stages", "chat"):
            sub = container.get(key)
            if isinstance(sub, dict) and isinstance(sub.get(role), dict):
                return sub[role]
        if isinstance(container.get(role), dict):
            return container[role]
    return {}


def _get(d: dict, *names):
    for n in names:
        cur = d
        ok = True
        for p in n.split("."):
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                ok = False
                break
        if ok and cur is not None and not isinstance(cur, dict):
            return cur
    return None


def extract_settings(cfg: dict) -> Dict[str, dict]:
    """Declared per-stage settings from run_config.json (best effort; missing = None = unknown)."""
    inner = cfg.get("config") if isinstance(cfg.get("config"), dict) else {}
    both = [cfg, inner]
    out = {}
    for role in ROLES:
        sec = _section(cfg, role)
        s = {"provider": _get(sec, "provider"), "model": _get(sec, "model"),
             "effort": _get(sec, "effort", "reasoning_effort", "reasoning.effort", "thinking"),
             "prompt_version": _get(sec, "prompt_version"), "schema_version": _get(sec, "schema_version"),
             "batch_size": _get(sec, "batch_size", "max_reviews_per_request", "max_items_per_request"),
             "workers": _get(sec, "workers"), "max_tokens": _get(sec, "max_tokens", "max_output_tokens")}
        for c in both:
            if role == "enrich":
                s["provider"] = s["provider"] or _get(c, "client.provider", "provider")
                s["model"] = s["model"] or _get(c, "client.model", "model")
                s["effort"] = s["effort"] or _get(c, "client.effort", "effort")
                s["prompt_version"] = s["prompt_version"] or _get(c, "prompt_version")
                s["schema_version"] = s["schema_version"] or _get(c, "schema_version")
                s["batch_size"] = s["batch_size"] or _get(c, "batching.max_reviews_per_request", "max_reviews_per_request")
                s["label_config"] = _get(c, "label_config") or s.get("label_config")
            s["workers"] = s["workers"] or _get(c, "limits.workers", "workers")
        if role == "verify":
            s["sample_fraction"] = _get(sec, "sample_fraction")
        out[role] = s
    return out


def _detect_source(cfg: dict, calls: List[dict]) -> str:
    if cfg.get("synthetic") or cfg.get("SYNTHETIC"):
        return "synthetic"
    lc = str(cfg.get("label_config") or "")
    if cfg.get("dry_run") or lc.startswith("mock:") or any(str(c.get("model")) == "mock" for c in calls):
        return "dry_run"
    return "measured"


def summarize_run(name: str, run_dir: Path, base_records: Optional[Dict[str, dict]] = None) -> dict:
    if not run_dir.is_dir():
        raise CalcError("run directory not found: %s" % run_dir)
    cfg_path = run_dir / "run_config.json"
    cfg = load_json(cfg_path) if cfg_path.exists() else {}
    calls = read_jsonl(run_dir / "calls.jsonl")
    invs = read_jsonl(run_dir / "invocations.jsonl")
    own = _last_by_id(read_jsonl(run_dir / "records.jsonl"))
    final = dict(base_records or {})
    final.update(own)
    stages: Dict[str, dict] = {}
    for role in ROLES:
        rc = [c for c in calls if c.get("role") == role]
        starts = [parse_ts(c.get("started_at")) for c in rc]
        ends = [parse_ts(c.get("ended_at")) for c in rc]
        starts = [s for s in starts if s]
        ends = [e for e in ends if e]
        span = (max(ends) - min(starts)).total_seconds() if starts and ends else None
        stages[role] = {"attempts": len(rc), "duration_ms_sum": sum(as_int(c.get("duration_ms")) or 0 for c in rc),
                        "span_seconds": span}
    inv_stage: Dict[str, float] = {}
    for inv in invs:
        for key in ("stage_seconds", "stages"):
            st = inv.get(key)
            if isinstance(st, dict):
                for k, v in st.items():
                    if isinstance(v, dict):
                        v = v.get("seconds", v.get("wall_seconds"))
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        inv_stage[k] = inv_stage.get(k, 0.0) + float(v)
    walls = [inv.get("wall_seconds") for inv in invs]
    wall = sum(float(w) for w in walls if isinstance(w, (int, float))) if invs else None
    if invs and any(not isinstance(w, (int, float)) for w in walls):
        wall = None
    sent_ok = set()
    for c in calls:
        if c.get("role") == "enrich" and c.get("outcome") == "succeeded":
            sent_ok.update(str(i) for i in c.get("review_ids") or [])
    completed = [i for i, r in final.items() if r.get("status") == "completed"]
    quarantined = [i for i, r in final.items() if r.get("status") == "quarantined"]
    run_id = cfg.get("run_id") or (invs[0].get("invocation_id") if invs else None) or run_dir.name
    return {
        "name": name, "run_dir": rel(run_dir), "run_id": str(run_id), "config": scrub(cfg),
        "settings": extract_settings(cfg), "recorded_input_sha256": _find_sha(cfg),
        "wall_seconds": wall, "invocations": [scrub({k: inv.get(k) for k in (
            "invocation_id", "phase", "started_at", "ended_at", "wall_seconds", "stop_reason", "counts")})
            for inv in invs],
        "stages": stages, "invocation_stage_seconds": inv_stage,
        "records": {"completed": len(completed), "quarantined": len(quarantined),
                    "record_lines_written_by_this_run": len(own),
                    "cache_hits": len([i for i in completed if i not in sent_ok]),
                    "reviews_sent_succeeded": len(sent_ok)},
        "data_source": _detect_source(cfg, calls),
        "_calls": calls, "_final": final,
    }


def collect(cold_dir, warm_dir, csv_path=None, out_dir=COST_DIR, manifest=DEFAULT_MANIFEST,
            manifest_key=None, expect_rows=100, reasoning_included=None, rates_path=None) -> dict:
    cold_dir, warm_dir, out_dir = Path(cold_dir), Path(warm_dir), Path(out_dir)
    cold = summarize_run("cold", cold_dir)
    warm = summarize_run("warm", warm_dir, base_records=cold["_final"])
    if csv_path is None:
        cand = [cold["config"].get("input_csv"), str(DEFAULT_DATASET_DIR / "cost_100.csv")]
        for c in cand:
            if c and (Path(c).exists() or (REPO / c).exists()):
                csv_path = Path(c) if Path(c).exists() else REPO / c
                break
        if csv_path is None:
            raise CalcError("cost_100.csv not found; pass --csv")
    chk = verify_csv(csv_path, manifest, manifest_key, expect_rows)
    rows_by_id = {r["review_id"]: r for r in chk["rows"]}
    errors = []
    for run in (cold, warm):
        rec_sha = run["recorded_input_sha256"]
        if rec_sha and rec_sha != chk["csv_sha256"]:
            errors.append("%s run_config records input sha256 %s != %s" % (run["name"], rec_sha, chk["csv_sha256"]))
        ids = set(run["_final"])
        extra = sorted(ids - set(chk["ids"]))
        missing = sorted(set(chk["ids"]) - ids)
        if extra:
            errors.append("%s run has %d IDs not in the CSV (e.g. %s)" % (run["name"], len(extra), extra[:3]))
        run["records"]["ids_missing"] = len(missing)
        run["records"]["pending"] = len(missing)
        for c in run["_calls"]:
            bad = [i for i in c.get("review_ids") or [] if str(i) not in rows_by_id]
            if bad:
                errors.append("%s call %s sent IDs not in the CSV: %s" % (run["name"], c.get("request_id"), bad[:3]))
    if errors:
        raise CalcError("; ".join(errors))

    # pilot_records.jsonl: one line per CSV ID, CSV order, final (warm) state.
    records_out = []
    for rid in chk["ids"]:
        sha = row_sha(rows_by_id[rid])
        r = warm["_final"].get(rid)
        if r is None:
            line = {"review_id": rid, "source_sha256": sha, "status": "quarantined", "reason": "not_processed"}
        else:
            if r.get("source_sha256") and r["source_sha256"] != sha:
                raise CalcError("record %s source_sha256 does not match the CSV row hash" % rid)
            line = dict(scrub(r))
            line["source_sha256"] = sha
            line = {"review_id": rid, **{k: v for k, v in line.items() if k != "review_id"}}
        line["pilot_status"] = {"cold": (cold["_final"].get(rid) or {}).get("status", "pending"),
                                "warm": (warm["_final"].get(rid) or {}).get("status", "pending")}
        records_out.append(line)

    # pilot_calls.jsonl + usage.csv
    rates = load_rates(rates_path or (COST_DIR / "rates.csv"))
    if reasoning_included is None:
        a_path = COST_DIR / "assumptions.json"
        reasoning_included = bool(load_json(a_path).get("reasoning_tokens_included_in_output", True)) if a_path.exists() else True
    calls_out, usage_rows, seen = [], [], set()
    for run in (cold, warm):
        for c in run["_calls"]:
            c = scrub(c)
            rid = str(c.get("request_id") or "")
            if not rid:
                raise CalcError("%s call without request_id" % run["name"])
            if rid in seen:   # keep request_id unique across both runs
                cand, n = "%s@%s" % (rid, run["name"]), 2
                while cand in seen:
                    cand, n = "%s@%s#%d" % (rid, run["name"], n), n + 1
                c["original_request_id"] = rid
                rid = c["request_id"] = cand
            seen.add(rid)
            line = {"run": run["name"], "run_id": run["run_id"], **c}
            calls_out.append(line)
            usage_rows.extend(usage_rows_for_call(c, run["name"], rates, reasoning_included))

    sources = sorted({cold["data_source"], warm["data_source"]},
                     key=lambda s: ("measured", "dry_run", "synthetic").index(s))
    data_source = sources[-1]
    if Path(out_dir).resolve() == FIXTURES_DIR.resolve() or FIXTURES_DIR.resolve() in Path(cold_dir).resolve().parents:
        data_source = "synthetic"
    timing = {
        "provenance": {
            "data_source": data_source, "collected_from": {"cold": cold["run_dir"], "warm": warm["run_dir"]},
            "csv_name": chk["csv_name"], "csv_sha256": chk["csv_sha256"], "manifest": chk["manifest"],
            "manifest_sha256": chk["manifest_sha256"], "checksum_ok": True, "expected_rows": expect_rows,
            "id_count": chk["id_count"], "ids_match_csv": True, "nonempty_texts": chk["nonempty_texts"],
            "empty_texts": chk["empty_texts"], "unique_nonempty_texts": chk["unique_nonempty_texts"],
            "reasoning_tokens_included_in_output": reasoning_included,
        },
        "runs": {r["name"]: {k: v for k, v in r.items() if not k.startswith("_")} for r in (cold, warm)},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_text(out_dir / "pilot_records.jsonl", "".join(dumps_line(r) + "\n" for r in records_out))
    write_text(out_dir / "pilot_calls.jsonl", "".join(dumps_line(c) + "\n" for c in calls_out))
    write_text(out_dir / "usage.csv", usage_csv_text(usage_rows))
    write_text(out_dir / "pilot_timing.json", json.dumps(timing, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    return timing


# ---------------------------------------------------------------- replay: measured section

def load_source(source_dir, rates_path=None, assumptions_path=None, local_path=None, overrides=None) -> dict:
    source_dir = Path(source_dir)

    def pick(name, explicit):
        if explicit:
            return Path(explicit)
        p = source_dir / name
        return p if p.exists() else COST_DIR / name

    paths = {n: source_dir / n for n in EVIDENCE_FILES}
    paths["rates.csv"] = pick("rates.csv", rates_path)
    paths["assumptions.json"] = pick("assumptions.json", assumptions_path)
    paths["local_compute.csv"] = pick("local_compute.csv", local_path)
    assumptions = load_json(paths["assumptions.json"]) if paths["assumptions.json"].exists() else {}
    assumptions = copy.deepcopy(assumptions)
    for o in overrides or []:
        if "=" not in o:
            raise CalcError("--set expects key=value, got %r" % o)
        k, v = o.split("=", 1)
        set_path(assumptions, k.strip(), v.strip())
    timing = load_json(paths["pilot_timing.json"]) if paths["pilot_timing.json"].exists() else None
    calls = read_jsonl(paths["pilot_calls.jsonl"])
    records = read_jsonl(paths["pilot_records.jsonl"])
    usage = read_usage_csv(paths["usage.csv"])
    has_data = timing is not None and (calls or records)
    data_source = "none"
    if has_data:
        data_source = (timing.get("provenance") or {}).get("data_source") or "measured"
        resolved = source_dir.resolve()
        if resolved == FIXTURES_DIR.resolve() or FIXTURES_DIR.resolve() in resolved.parents:
            data_source = "synthetic"
    return {"source_dir": source_dir, "paths": paths, "assumptions": assumptions, "timing": timing,
            "calls": calls, "records": records, "usage": usage, "data_source": data_source,
            "rates": load_rates(paths["rates.csv"]), "local": load_local_compute(paths["local_compute.csv"])}


def _is_fallback(c: dict) -> bool:
    return bool(c.get("fallback") or c.get("is_fallback") or str(c.get("phase")) == "fallback")


def build_measured(src: dict, multiplier: Decimal) -> dict:
    """Everything in the 'measured' column. Depends only on evidence files, rates and the multiplier."""
    costed = cost_usage(src["usage"], src["rates"], multiplier)
    by_req: Dict[Tuple[str, str], Amount] = {}
    by_run_role: Dict[Tuple[str, str], Amount] = {}
    by_run_role_item: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in costed:
        amt = Amount.of(r["cost"], r["reason"])
        by_req.setdefault((r["run"], r["request_id"]), Amount()).add(amt)
        by_run_role.setdefault((r["run"], r["role"]), Amount()).add(amt)
        slot = by_run_role_item.setdefault((r["run"], r["role"], r["item"]), {"units": D0, "units_unknown": 0, "cost": Amount()})
        if r["units_dec"] is None:
            slot["units_unknown"] += 1
        else:
            slot["units"] += r["units_dec"]
        slot["cost"].add(amt)
    timing = src["timing"] or {}
    runs_t = timing.get("runs") or {}
    out = {"runs": {}, "costed": costed, "by_req": by_req}
    for run in RUNS:
        t = runs_t.get(run) or {}
        calls = [c for c in src["calls"] if c.get("run") == run]
        roles = {}
        for role in ROLES:
            rc = [c for c in calls if c.get("role") == role]
            ok = [c for c in rc if c.get("outcome") == "succeeded"]
            batch = [len(c.get("review_ids") or []) for c in ok]
            prov_cost = [c.get("cost_usd") for c in rc]
            known_prov = [Decimal(str(v)) for v in prov_cost if isinstance(v, (int, float)) and not isinstance(v, bool)]
            ok_cost = Amount()
            for c in ok:
                ok_cost.add(by_req.get((run, str(c.get("request_id"))), Amount()))
            roles[role] = {
                "attempts": len(rc), "succeeded": len(ok), "failed": len(rc) - len(ok),
                "retries": sum(1 for c in rc if (as_int(c.get("attempt")) or 1) > 1),
                "fallbacks": sum(1 for c in rc if _is_fallback(c)),
                "uncertain_charge": sum(1 for c in rc if c.get("uncertain_charge")),
                "models": sorted({str(c.get("model")) for c in rc if c.get("model")}),
                "providers": sorted({str(c.get("provider")) for c in rc if c.get("provider")}),
                "efforts": sorted({str(c.get("effort") or c.get("reasoning_effort")) for c in rc
                                   if c.get("effort") or c.get("reasoning_effort")}),
                "label_configs": sorted({str(c.get("label_config")) for c in rc if c.get("label_config")}),
                "reviews_sent_ok": sum(batch), "batch_min": min(batch) if batch else None,
                "batch_max": max(batch) if batch else None,
                "batch_mean": (sum(batch) / len(batch)) if batch else None,
                "input_tokens": sum(as_int(c.get("input_tokens")) or 0 for c in rc),
                "cached_input_tokens": sum(as_int(c.get("cached_input_tokens")) or 0 for c in rc),
                "cached_reported": any(c.get("cached_input_tokens") is not None for c in rc),
                "output_tokens": sum(as_int(c.get("output_tokens")) or 0 for c in rc),
                "reasoning_tokens": sum(as_int(c.get("reasoning_tokens")) or 0 for c in rc),
                "reasoning_reported": any(c.get("reasoning_tokens") is not None for c in rc),
                "max_output_tokens": max([as_int(c.get("output_tokens")) or 0 for c in rc] or [0]),
                "duration_ms_sum": sum(as_int(c.get("duration_ms")) or 0 for c in rc),
                "span_seconds": ((t.get("stages") or {}).get(role) or {}).get("span_seconds"),
                "cost": by_run_role.get((run, role), Amount()),
                "cost_succeeded": ok_cost,
                "provider_cost": (sum(known_prov, D0) if known_prov else None),
                "provider_cost_missing": len(rc) - len(known_prov),
                "items": {k[2]: v for k, v in by_run_role_item.items() if k[0] == run and k[1] == role},
            }
        api = Amount()
        for role in ROLES:
            api.add(roles[role]["cost"])
        if not t:   # no evidence for this run: unknown, never zero
            api = Amount(D0, 1, ["no measured pilot"])
        recs = t.get("records") or {}
        wall = t.get("wall_seconds")
        local, local_notes = local_compute_cost(src["local"], wall)
        rows = (timing.get("provenance") or {}).get("id_count")
        completed = recs.get("completed")
        out["runs"][run] = {
            "present": bool(t), "run_id": t.get("run_id"), "roles": roles, "api": api,
            "wall_seconds": wall, "records": recs, "settings": t.get("settings") or {},
            "invocations": t.get("invocations") or [], "invocation_stage_seconds": t.get("invocation_stage_seconds") or {},
            "local": local, "local_notes": local_notes,
            "rows_per_second": (rows / wall) if rows and wall else None,
            "api_per_1000_rows": api.scale(Decimal(1000) / Decimal(rows)) if rows else Amount(D0, 1, ["no rows"]),
            "api_per_completed": api.scale(Decimal(1) / Decimal(completed)) if completed else Amount(D0, 1, ["no completed"]),
            "enrich_calls": roles["enrich"]["attempts"] if t else None,
        }
    return out


# ---------------------------------------------------------------- replay: projection

def _fixed_rate_cost(rates, provider, model, in_tok, out_tok, multiplier) -> Amount:
    total = Amount()
    for item, units in (("input_uncached", in_tok), ("output", out_tok)):
        if not units:
            continue
        ppu = price_per_unit(find_rate(rates, provider, model, item), multiplier)
        total.add(Amount.of(None if ppu is None else Decimal(units) * ppu,
                            "price blank or missing for %s/%s %s" % (provider, model, item)))
    return total


def build_projection(src: dict, measured: dict, multiplier: Decimal) -> dict:
    a = src["assumptions"]
    p = a.get("projection") or {}
    rows_accounted = int(p.get("rows_accounted", 660622))
    rows_nonempty = int(p.get("rows_nonempty", 660609))
    empties = int(p.get("empty_text_quarantines", 13))
    distinct = int(p.get("distinct_nonempty_texts", 484189))
    pilot_rows = int(((src["timing"] or {}).get("provenance") or {}).get("id_count") or p.get("pilot_rows", 100))
    cold = measured["runs"]["cold"]
    have = src["data_source"] != "none" and cold["present"]
    warnings: List[str] = []
    basis: Dict[str, dict] = {}

    for role in ROLES:
        st = cold["roles"][role]
        b = {"source": "pilot" if have else "none", "unit_cost": None, "unit_reason": "", "fixed_cost": None,
             "throughput": None, "fixed_seconds": None, "batch_mean": st["batch_mean"]}
        if role in PER_REVIEW_ROLES:
            n = st["reviews_sent_ok"]
            if have and n:
                b["unit_cost"] = st["cost_succeeded"].scale(Decimal(1) / Decimal(n))
                dur = st["duration_ms_sum"] / 1000.0
                b["throughput"] = (n / dur) if dur > 0 else None
                b["tokens_in_per_review"] = st["input_tokens"] / n
                b["tokens_out_per_review"] = st["output_tokens"] / n
            else:
                b["unit_cost"] = Amount(D0, 1, ["no measured %s calls" % role])
        else:
            if have and st["succeeded"]:
                b["fixed_cost"] = st["cost_succeeded"]
                b["fixed_seconds"] = st["duration_ms_sum"] / 1000.0
            else:
                b["fixed_cost"] = Amount(D0, 1, ["no measured %s call" % role])
        basis[role] = b

    if not have:   # labelled pre-pilot estimate for enrich only
        pe = a.get("prepilot_estimate") or {}
        tin = pe.get("enrich_input_tokens_per_review")
        tout = pe.get("enrich_output_tokens_per_review") or 0
        settings_model = "jev-latest"
        if tin is not None:
            basis["enrich"]["unit_cost"] = _fixed_rate_cost(src["rates"], "typesafe", settings_model, tin, tout, multiplier)
            basis["enrich"]["source"] = "PRE-PILOT ESTIMATE"
            basis["enrich"]["tokens_in_per_review"] = tin
            basis["enrich"]["tokens_out_per_review"] = tout

    # fallback basis: measured fallback calls only
    fb_calls = [c for c in src["calls"] if c.get("run") == "cold" and _is_fallback(c) and c.get("outcome") == "succeeded"]
    fb_n = sum(len(c.get("review_ids") or []) for c in fb_calls)
    fb_unit = None
    if fb_n:
        fb_amt = Amount()
        for c in fb_calls:
            fb_amt.add(measured["by_req"].get(("cold", str(c.get("request_id"))), Amount()))
        fb_unit = fb_amt.scale(Decimal(1) / Decimal(fb_n))

    overhead_per_row = None
    if have and cold["wall_seconds"] is not None:
        call_s = sum(cold["roles"][r]["duration_ms_sum"] for r in ROLES) / 1000.0
        overhead_per_row = max(0.0, float(cold["wall_seconds"]) - call_s) / pilot_rows

    bcfg = a.get("batch_api_estimate") or {}
    bdisc = dec(bcfg.get("discount_fraction")) or D0
    broles = set(bcfg.get("roles") or [])
    max_conc = int(a.get("max_concurrency") or 1)
    max_fb = float(a.get("max_fallback_fraction") or 0.0)
    budget = dec(a.get("budget_usd"))
    vfrac = float(a.get("verify_sample_fraction") or 0.0)
    vmax = a.get("verify_max_items")
    measured_retry = None
    est = cold["roles"]["enrich"]
    if have and est["succeeded"]:
        measured_retry = est["retries"] / float(est["succeeded"])

    scenarios = {}
    for sc in SCENARIOS:
        r = float(scen(a, "retry_rate", sc, 0.0))
        fbf = float(scen(a, "fallback_fraction", sc, 0.0))
        if fbf > max_fb + 1e-12:
            warnings.append("⚠ %s fallback_fraction %.4f exceeds declared max_fallback_fraction %.4f; capped." % (sc, fbf, max_fb))
            fbf = max_fb
        fmul = float(scen(a, "fixed_overhead_multiplier", sc, 1.0))
        eff = float(scen(a, "concurrency_efficiency", sc, 1.0))
        workers_eff = 1.0 + (max_conc - 1) * eff
        rmul = Decimal(str(1.0 + r))
        variants = {}
        for reuse in (True, False):
            work = distinct if reuse else rows_nonempty
            stages = {}
            # enrich
            stages["enrich"] = {"work": work, "cost": basis["enrich"]["unit_cost"].scale(Decimal(work) * rmul)}
            bm = basis["enrich"]["batch_mean"]
            stages["enrich"]["requests"] = int(math.ceil(work / bm * (1 + r))) if bm else None
            thr = basis["enrich"]["throughput"]
            stages["enrich"]["seconds"] = (work * (1 + r) / (thr * workers_eff)) if thr else None
            # fallback
            fwork = int(math.ceil(work * fbf))
            if fwork == 0:
                fcost = Amount()
            elif fb_unit is not None:
                fcost = fb_unit.scale(Decimal(fwork) * rmul)
            else:
                fcost = Amount(D0, 1, ["fallback cost per review not measured"])
            stages["fallback"] = {"work": fwork, "cost": fcost, "requests": None, "seconds": None if fwork else 0.0}
            # verify: sample of non-cached completed records
            vwork = int(math.ceil(vfrac * work))
            if vmax is not None:
                vwork = min(vwork, int(vmax))
            stages["verify"] = {"work": vwork, "cost": basis["verify"]["unit_cost"].scale(Decimal(vwork) * rmul)}
            vb = basis["verify"]["batch_mean"]
            stages["verify"]["requests"] = int(math.ceil(vwork / vb * (1 + r))) if vb else None
            vt = basis["verify"]["throughput"]
            stages["verify"]["seconds"] = (vwork * (1 + r) / (vt * workers_eff)) if vt else (0.0 if vwork == 0 else None)
            # fixed one-time overhead
            for role in FIXED_ROLES:
                fs = basis[role]["fixed_seconds"]
                stages[role] = {"work": 1, "requests": 1,
                                "cost": basis[role]["fixed_cost"].scale(Decimal(str(fmul)) * rmul),
                                "seconds": fs * fmul * (1 + r) if fs is not None else None}
            stages["local overhead (ingest/rank/export)"] = {
                "work": rows_accounted, "requests": 0, "cost": Amount(),
                "seconds": overhead_per_row * rows_accounted if overhead_per_row is not None else None}
            api = Amount()
            for s in stages.values():
                api.add(s["cost"])
            batch_est = Amount()   # hypothetical Batch API discount on eligible roles: ESTIMATE ONLY
            for name, s in stages.items():
                batch_est.add(s["cost"].scale(Decimal(1) - bdisc) if name in broles else s["cost"])
            secs_list = [s["seconds"] for s in stages.values()]
            total_s = None if any(v is None for v in secs_list) else sum(secs_list)
            local, _ = local_compute_cost(src["local"], total_s)
            if total_s is None:
                local = Amount(D0, 1, ["projected time unknown"])
            if budget is None:
                status = "⚠ no budget declared"
            elif api.known > budget:
                status = "⚠ EXCEEDS BUDGET (%s > %s)" % (usd(api.known), usd(budget))
            elif api.unknown:
                status = "⚠ CANNOT CONFIRM within budget: %d unknown item(s); known part %s ≤ %s" % (
                    api.unknown, usd(api.known), usd(budget))
            else:
                status = "within budget (%s ≤ %s)" % (usd(api.known), usd(budget))
            variants["reuse" if reuse else "no_reuse"] = {
                "work": work, "stages": stages, "api": api, "batch_estimate": batch_est,
                "seconds": total_s, "local": local,
                "budget_status": status,
                "per_1000_rows": api.scale(Decimal(1000) / Decimal(rows_accounted)),
            }
        scenarios[sc] = {"retry_rate": r, "fallback_fraction": fbf, "fixed_multiplier": fmul,
                         "concurrency_efficiency": eff, "effective_workers": workers_eff, "variants": variants}

    if measured_retry is not None and measured_retry > float(scen(a, "retry_rate", "base", 0.0)):
        warnings.append("⚠ measured pilot enrich retry rate %.3f is above the base-case assumption %.3f."
                        % (measured_retry, float(scen(a, "retry_rate", "base", 0.0))))
    caps = a.get("output_token_cap") or {}
    cap_rows = []
    for role in ROLES:
        cap = caps.get(role) if isinstance(caps, dict) else caps
        obs = max(measured["runs"][run]["roles"][role]["max_output_tokens"] for run in RUNS) if have else None
        flag = ""
        if cap is not None and obs is not None and obs > int(cap):
            flag = "⚠ observed above cap"
            warnings.append("⚠ %s: observed output %d tokens > declared cap %s." % (role, obs, cap))
        models = sorted(set(cold["roles"][role]["models"]))
        provs = sorted(set(cold["roles"][role]["providers"]))
        worst = Amount(D0, 1, ["no model observed"])
        if cap is not None and models:
            worst = _fixed_rate_cost(src["rates"], provs[0] if provs else "", models[0], 0, int(cap), multiplier)
        elif cap is None:
            worst = Amount(D0, 1, ["no cap declared"])
        cap_rows.append([role, "not declared (unknown)" if cap is None else cap,
                         UNKNOWN if obs is None else obs, worst.fmt(), flag])
    p_ok = (rows_nonempty + empties == rows_accounted)
    if not p_ok:
        warnings.append("⚠ projection counts do not add up: %d nonempty + %d empty != %d rows." % (rows_nonempty, empties, rows_accounted))
    return {"rows_accounted": rows_accounted, "rows_nonempty": rows_nonempty, "empties": empties,
            "distinct": distinct, "counts_ok": p_ok, "basis": basis, "scenarios": scenarios,
            "warnings": warnings, "measured_retry": measured_retry, "max_concurrency": max_conc,
            "max_fallback_fraction": max_fb, "budget": budget, "cap_rows": cap_rows,
            "overhead_per_row": overhead_per_row, "fb_unit": fb_unit, "have": have}


# ---------------------------------------------------------------- report

BANNERS = {
    "measured": "**Data source: MEASURED pilot** (collected from real run directories by `cost_calc.py collect`).",
    "synthetic": "> ⚠ **SYNTHETIC FIXTURE DATA — NOT A MEASURED PILOT.** Every token count, duration and cost "
                 "below is invented test data from `cost/fixtures/`. Do not cite it as evidence.",
    "dry_run": "> ⚠ **DRY-RUN (mock client) DATA — NOT A MEASURED PILOT.** No provider was called; usage and cost are not real.",
    "none": "> **No measured pilot yet.** `pilot_calls.jsonl`, `pilot_records.jsonl`, `usage.csv` and `pilot_timing.json` "
            "are missing. Run the explicit pilot (cost/README.md), then `collect`. Measured values below are unknown, "
            "not zero; the projection uses editable assumptions only.",
}
MEASURED_TITLE = {"measured": "Measured 100-review pilot (cold vs warm)",
                  "synthetic": "SYNTHETIC pilot fixture (cold vs warm) — NOT measured",
                  "dry_run": "DRY-RUN pilot (cold vs warm) — NOT measured",
                  "none": "Measured 100-review pilot — No measured pilot yet"}


def _v(x):
    if x is None or x == [] or x == "":
        return UNKNOWN
    if isinstance(x, list):
        return ", ".join(str(i) for i in x)
    return str(x)


def render_report(src: dict, m: dict, pj: dict, multiplier: Decimal) -> str:
    ds = src["data_source"]
    a = src["assumptions"]
    prov = (src["timing"] or {}).get("provenance") or {}
    L: List[str] = []
    L.append("# 100-review cost and runtime report")
    L.append("")
    L.append(BANNERS[ds])
    L.append("")
    L.append("Generated offline by `python3 cost/cost_calc.py` from saved files only (no API key, no model calls). "
             "Spec: [docs/specs/COST_CALCULATOR.md](../docs/specs/COST_CALCULATOR.md). "
             "Rates multiplier in force: **%s**%s." % (multiplier, "" if multiplier == 1 else " (sensitivity run: all API prices scaled)"))
    L.append("")
    L.append("## Inputs")
    L.append("")
    rows = []
    for name, path in sorted(src["paths"].items()):
        exists = Path(path).exists()
        rows.append([name, "`%s`" % rel(path), file_sha256(path)[:16] + "…" if exists else "missing"])
    L.append(md_table(["file", "path", "sha256"], rows))
    L.append("")

    # ---------- measured
    L.append("## 1. " + MEASURED_TITLE[ds])
    L.append("")
    if ds == "none":
        L.append("No measured pilot yet. Every measured cell is **unknown** until `collect` runs on real cold/warm run directories.")
        L.append("")
    cold, warm = m["runs"]["cold"], m["runs"]["warm"]
    L.append("### 1.1 Input and records")
    L.append("")
    rows = [
        ["input file / checksum (sha256)", _v(prov.get("csv_name")) + " / " + ("`%s`" % prov["csv_sha256"] if prov.get("csv_sha256") else UNKNOWN), "same input"],
        ["checksum matches manifest", "✓ " + _v(prov.get("manifest")) if prov.get("checksum_ok") else UNKNOWN, "—"],
        ["IDs (expected %s)" % _v(prov.get("expected_rows")), _v(prov.get("id_count")) + (" ✓ match CSV" if prov.get("ids_match_csv") else ""), "same IDs"],
        ["run id", _v(cold["run_id"]), _v(warm["run_id"])],
        ["completed records", _v(cold["records"].get("completed")), _v(warm["records"].get("completed"))],
        ["failed / quarantined records", _v(cold["records"].get("quarantined")), _v(warm["records"].get("quarantined"))],
        ["pending (no record)", _v(cold["records"].get("pending")), _v(warm["records"].get("pending"))],
        ["nonempty texts / empty texts", "%s / %s" % (_v(prov.get("nonempty_texts")), _v(prov.get("empty_texts"))), "same"],
        ["unique nonempty texts", _v(prov.get("unique_nonempty_texts")), "same"],
        ["reviews sent to enrich (succeeded calls)", _v(cold["records"].get("reviews_sent_succeeded")), _v(warm["records"].get("reviews_sent_succeeded"))],
        ["result-cache hits (completed, not sent in this run)", _v(cold["records"].get("cache_hits")), _v(warm["records"].get("cache_hits"))],
        ["new enrichment calls", _v(cold["enrich_calls"] if cold["present"] else None),
         (_v(warm["enrich_calls"]) + (" ✓ zero" if warm["enrich_calls"] == 0 else " ✗ NOT zero — disclose")) if warm["present"] else UNKNOWN],
    ]
    L.append(md_table(["", "cold", "warm"], rows))
    L.append("")
    if ds == "none":
        L.append("Sections 1.2–1.5 (per-stage settings, requests and attempts incl. failures/retries/fallbacks/verification, "
                 "usage and cost by stage, wall clock, stage times, throughput, cost per 1,000 rows and per completed record) "
                 "appear here after `collect`. Until then they are **unknown**.")
        L.append("")
        return _render_projection(L, src, m, pj, multiplier, ds, a, prov)
    dq = sum(1 for r in src["records"] if r.get("status") == "quarantined" and r.get("reason") != "empty_review_text")
    if src["records"]:
        L.append("`pilot_records.jsonl`: %d lines; %d quarantined for a reason other than empty text (fix before scaling)." % (len(src["records"]), dq))
        L.append("")

    L.append("### 1.2 Per-stage settings (declared in run_config.json; observed in calls)")
    L.append("")
    rows = []
    for role in ROLES:
        for run, rr in (("cold", cold), ("warm", warm)):
            s = (rr["settings"] or {}).get(role) or {}
            st = rr["roles"][role]
            if role in FIXED_ROLES:
                batch = "— (saved aggregate pack)"
            else:
                batch = ("no calls" if st["batch_mean"] is None else "%s–%s (mean %.1f)" % (
                    st["batch_min"], st["batch_max"], st["batch_mean"])) + " (declared max %s)" % _v(s.get("batch_size"))

            def ob(observed, declared):
                if observed:
                    return _v(observed)
                return "declared: " + _v(declared) if declared else UNKNOWN
            rows.append([role, run, ob(st["providers"], s.get("provider")), ob(st["models"], s.get("model")),
                         ob(st["efforts"], s.get("effort")),
                         "%s / %s" % (_v(s.get("prompt_version")), _v(s.get("schema_version"))),
                         ob(st["label_configs"], s.get("label_config")) if role == "enrich" else "—",
                         batch, _v(s.get("workers"))])
    L.append(md_table(["stage", "run", "provider", "exact model ID", "effort", "prompt / schema version",
                       "label_config", "reviews per request", "workers"], rows))
    L.append("")

    L.append("### 1.3 Requests and attempts")
    L.append("")
    rows = []
    for role in ROLES:
        for run, rr in (("cold", cold), ("warm", warm)):
            st = rr["roles"][role]
            rows.append([role, run, st["attempts"], st["succeeded"], st["failed"], st["retries"], st["fallbacks"],
                         st["uncertain_charge"], st["reviews_sent_ok"]])
    L.append(md_table(["stage", "run", "attempts", "succeeded", "failed", "retries (attempt>1)", "fallbacks",
                       "uncertain charge (timeouts)", "reviews in succeeded calls"], rows))
    L.append("")
    L.append("Verification calls are the `verify` rows. Failed attempts are listed with their error in `pilot_calls.jsonl`.")
    L.append("")
    unc = [c for c in src["calls"] if c.get("uncertain_charge")]
    if unc:
        L.append("⚠ Uncertain charges (timeouts): " + ", ".join("`%s` (%s, %s)" % (c.get("request_id"), c.get("run"), c.get("role")) for c in unc)
                 + ". Their cost stays **unknown** until reconciled: enter the dashboard USD amount in `usage.csv` (item `uncertain_charge`).")
        L.append("")

    L.append("### 1.4 Usage and cost by stage (API)")
    L.append("")
    rows = []
    for role in ROLES:
        for run, rr in (("cold", cold), ("warm", warm)):
            st = rr["roles"][role]
            items = st["items"]

            def u(item):
                s = items.get(item)
                if not s:
                    return "—"
                txt = format(int(s["units"]), ",d")
                return txt + (" + %d unknown" % s["units_unknown"] if s["units_unknown"] else "")
            pc = st["provider_cost"]
            delta = ""
            if pc is not None and st["cost"].value is not None:
                delta = usd(st["cost"].value - pc)
            rows.append([role, run, u("input_uncached"), u("input_cached") if st["cached_reported"] else "not reported",
                         u("output"), (format(st["reasoning_tokens"], ",d") + (" (in output)" if prov.get("reasoning_tokens_included_in_output", a.get("reasoning_tokens_included_in_output", True)) else " (billed separately)")) if st["reasoning_reported"] else ("not reported" if st["attempts"] else "—"),
                         st["cost"].fmt(),
                         (usd(pc) + ("" if not st["provider_cost_missing"] else " (%d calls without cost_usd)" % st["provider_cost_missing"])) if pc is not None else ("—" if not st["attempts"] else ("none (Anthropic returns no per-call cost; calculated = bill)"
                                                       if st["providers"] == ["anthropic"] else UNKNOWN + " (not reported)")),
                         delta or "—"])
    L.append(md_table(["stage", "run", "input uncached (tokens)", "input cached (tokens)", "output (tokens)", "reasoning (tokens)",
                       "calculated cost", "provider-reported cost_usd", "calculated − reported"], rows))
    L.append("")
    reasons = sorted({r["reason"] for r in m["costed"] if r["cost"] is None})
    if reasons:
        L.append("Unknown items (not counted as zero):")
        L.append("")
        for r in reasons:
            L.append("- " + r)
        L.append("")

    L.append("### 1.5 Totals, time and throughput")
    L.append("")

    def stage_time(rr, role):
        st = rr["roles"][role]
        if not st["attempts"]:
            return "0 calls"
        return "%s summed / %s span" % (secs(st["duration_ms_sum"] / 1000.0), secs(st["span_seconds"]))
    rows = [
        ["API spend (all stages)", cold["api"].fmt(), warm["api"].fmt()],
        ["local compute (separate, from local_compute.csv)", cold["local"].fmt(), warm["local"].fmt()],
        ["end-to-end wall clock (invocations.jsonl)", secs(cold["wall_seconds"]), secs(warm["wall_seconds"])],
    ]
    for role in ROLES:
        rows.append(["%s time (request durations summed / first start→last end)" % role, stage_time(cold, role), stage_time(warm, role)])
    stage_keys = sorted(set(cold["invocation_stage_seconds"]) | set(warm["invocation_stage_seconds"]))
    for k in stage_keys:
        rows.append(["stage `%s` (invocation timer)" % k, secs(cold["invocation_stage_seconds"].get(k)), secs(warm["invocation_stage_seconds"].get(k))])
    rows += [
        ["throughput (input rows / wall second)", num(cold["rows_per_second"], 3), num(warm["rows_per_second"], 3)],
        ["API cost per 1,000 input rows", cold["api_per_1000_rows"].fmt(), warm["api_per_1000_rows"].fmt()],
        ["API cost per completed record", cold["api_per_completed"].fmt(), warm["api_per_completed"].fmt()],
        ["pilot budget", usd(dec(a.get("pilot_budget_usd"))), "cold + warm: " + (cold["api"] + warm["api"]).fmt()],
    ]
    L.append(md_table(["", "cold", "warm (incremental)"], rows))
    L.append("")
    pb = dec(a.get("pilot_budget_usd"))
    both = cold["api"] + warm["api"]
    if pb is not None and both.known > pb:
        L.append("⚠ **Pilot spend exceeds the pilot budget** (%s > %s)." % (usd(both.known), usd(pb)))
        L.append("")
    L.append("Summed request durations can exceed wall clock when calls overlap; wall clock comes from `invocations.jsonl`.")
    L.append("")
    return _render_projection(L, src, m, pj, multiplier, ds, a, prov)


def _render_projection(L: List[str], src: dict, m: dict, pj: dict, multiplier: Decimal, ds: str, a: dict, prov: dict) -> str:
    # ---------- projection
    L.append("## 2. Full-run estimate (editable assumptions, not measured)")
    L.append("")
    src_label = {"measured": "measured cold pilot", "synthetic": "SYNTHETIC fixture (illustration only)",
                 "dry_run": "DRY-RUN data (illustration only)", "none": "assumptions only (no pilot)"}[ds]
    L.append("Per-unit basis: **%s**. Each stage is extrapolated from its own work count; group and memo are one-time overhead counted once." % src_label)
    L.append("")
    L.append("### 2.1 Work counts")
    L.append("")
    L.append(md_table(["", "value"], [
        ["rows accounted for", "{:,}".format(pj["rows_accounted"])],
        ["nonempty outputs", "{:,}".format(pj["rows_nonempty"])],
        ["empty-text quarantines", "{:,}".format(pj["empties"])],
        ["check: nonempty + quarantines = rows", "✓" if pj["counts_ok"] else "✗"],
        ["distinct nonempty texts (exact-text reuse)", "{:,}".format(pj["distinct"])],
        ["no-reuse comparison (every nonempty row sent)", "{:,}".format(pj["rows_nonempty"])],
    ]))
    L.append("")
    L.append("### 2.2 Editable controls (`cost/assumptions.json`)")
    L.append("")
    caps = a.get("output_token_cap")
    L.append(md_table(["control", "value"], [
        ["budget (USD)", usd(pj["budget"]) + ("" if pj["budget"] is not None else " — not declared")],
        ["max concurrency (workers)", pj["max_concurrency"]],
        ["max fallback fraction (declared cap)", pj["max_fallback_fraction"]],
        ["verify sample fraction / max items", "%s / %s" % (a.get("verify_sample_fraction"), _v(a.get("verify_max_items")) if a.get("verify_max_items") is not None else "no cap")],
        ["retry rate base / conservative", "%s / %s" % (scen(a, "retry_rate", "base"), scen(a, "retry_rate", "conservative"))],
        ["measured pilot enrich retry rate (retries / succeeded calls)", num(pj["measured_retry"], 3)],
        ["fallback fraction base / conservative", "%s / %s" % (scen(a, "fallback_fraction", "base"), scen(a, "fallback_fraction", "conservative"))],
        ["fixed-overhead multiplier base / conservative", "%s / %s" % (scen(a, "fixed_overhead_multiplier", "base", 1), scen(a, "fixed_overhead_multiplier", "conservative", 1))],
        ["concurrency efficiency base / conservative", "%s / %s" % (scen(a, "concurrency_efficiency", "base", 1), scen(a, "concurrency_efficiency", "conservative", 1))],
        ["output-token cap per call", json.dumps(caps, sort_keys=True)],
        ["reasoning tokens included in output", a.get("reasoning_tokens_included_in_output", True)],
    ]))
    L.append("")
    L.append("Output-token caps vs observed, and worst-case output cost of one call at the cap:")
    L.append("")
    L.append(md_table(["stage", "declared cap", "max observed output tokens", "worst-case output cost per call", ""], pj["cap_rows"]))
    L.append("")
    L.append("### 2.3 Per-unit basis")
    L.append("")
    rows = []
    for role in ROLES:
        b = pj["basis"][role]
        if role in PER_REVIEW_ROLES:
            rows.append([role, "per review sent", b["source"], b["unit_cost"].fmt(9),
                         num(b.get("tokens_in_per_review"), 1), num(b.get("tokens_out_per_review"), 1),
                         num(b["throughput"], 3) + " reviews/s per worker" if b["throughput"] else UNKNOWN])
        else:
            rows.append([role, "once per run (fixed)", b["source"], b["fixed_cost"].fmt(), "—", "—",
                         secs(b["fixed_seconds"])])
    rows.append(["fallback", "per review routed", "pilot" if pj["fb_unit"] else "none",
                 pj["fb_unit"].fmt(9) if pj["fb_unit"] else (UNKNOWN + " (no fallback calls measured)"), "—", "—", "—"])
    oh = pj["overhead_per_row"]
    rows.append(["local overhead", "per input row", "pilot" if oh is not None else "none", "$0 API", "—", "—",
                 (num(oh * 1000, 3) + " ms/row (wall − summed call time, ÷ pilot rows; linear, upper bound)") if oh is not None else UNKNOWN])
    L.append(md_table(["stage", "unit", "basis", "API cost per unit", "input tok/unit", "output tok/unit", "time"], rows))
    L.append("")
    if pj["basis"]["enrich"]["source"] == "PRE-PILOT ESTIMATE":
        L.append("Enrich unit cost is a **PRE-PILOT ESTIMATE** (%s), not a measurement." % ((a.get("prepilot_estimate") or {}).get("source", "")))
        L.append("")

    for sc in SCENARIOS:
        s = pj["scenarios"][sc]
        L.append("### 2.%d %s case (retry %.3f, fallback %.4f, fixed ×%s, %.2f effective workers)" % (
            4 + SCENARIOS.index(sc), sc.capitalize(), s["retry_rate"], s["fallback_fraction"], s["fixed_multiplier"], s["effective_workers"]))
        L.append("")
        rows = []
        stage_names = list(s["variants"]["reuse"]["stages"].keys())
        for st in stage_names:
            r1 = s["variants"]["reuse"]["stages"][st]
            r2 = s["variants"]["no_reuse"]["stages"][st]
            rows.append([st, "{:,}".format(r1["work"]), r1["cost"].fmt(), secs(r1["seconds"]),
                         "{:,}".format(r2["work"]), r2["cost"].fmt(), secs(r2["seconds"])])
        for label, key in (("**API total**", "api"), ("local compute (separate)", "local")):
            rows.append([label, "", s["variants"]["reuse"][key].fmt(), "", "", s["variants"]["no_reuse"][key].fmt(), ""])
        bc = a.get("batch_api_estimate") or {}
        if bc.get("roles") and dec(bc.get("discount_fraction")):
            rows.append(["API total if %s used the Batch API (−%s%%, ESTIMATE ONLY, not the measured tier)" % (
                "/".join(bc["roles"]), format(dec(bc["discount_fraction"]) * 100, "f")), "",
                s["variants"]["reuse"]["batch_estimate"].fmt(), "", "", s["variants"]["no_reuse"]["batch_estimate"].fmt(), ""])
        rows.append(["**elapsed time**", "", "", secs(s["variants"]["reuse"]["seconds"]), "", "", secs(s["variants"]["no_reuse"]["seconds"])])
        rows.append(["API per 1,000 input rows", "", s["variants"]["reuse"]["per_1000_rows"].fmt(), "", "", s["variants"]["no_reuse"]["per_1000_rows"].fmt(), ""])
        rows.append(["**budget check**", "", s["variants"]["reuse"]["budget_status"], "", "", s["variants"]["no_reuse"]["budget_status"], ""])
        L.append(md_table(["stage", "work (reuse)", "API cost (reuse)", "time (reuse)", "work (no reuse)", "API cost (no reuse)", "time (no reuse)"], rows))
        L.append("")
    if pj["warnings"]:
        L.append("### Warnings")
        L.append("")
        for w in pj["warnings"]:
            L.append("- " + w)
        L.append("")

    L.append("## 3. Rates used (`rates.csv`)")
    L.append("")
    rows = []
    for r in src["rates"]:
        ppu = price_per_unit(r, multiplier)
        rows.append([r["provider"], r["model"], r["item"], r["unit"],
                     (r["price"] + " per " + format(int(r["per_dec"]), ",d")) if r["price_dec"] is not None else UNKNOWN + " (blank)",
                     r["currency"], "—" if ppu is None else format(ppu.normalize(), "f"),
                     r["source_url"] or "—", r["checked_on"] or "not checked", r["notes"]])
    L.append(md_table(["provider", "model", "item", "unit", "price", "currency", "price per unit (× multiplier)", "source", "checked on", "notes"], rows))
    L.append("")
    blanks = [r for r in src["rates"] if r["price_dec"] is None and r["item"] != "uncertain_charge"]
    if blanks:
        L.append("⚠ %d rate(s) are blank and therefore **unknown**: %s. Fill them from the source link (with `checked_on`) before relying on totals." % (
            len(blanks), "; ".join("%s %s %s" % (r["provider"], r["model"], r["item"]) for r in blanks)))
        L.append("")
    L.append("## 4. Formulas and evidence")
    L.append("")
    L.append("- `price_per_unit = price / per` (a per-million price is divided by 1,000,000 first).")
    L.append("- `item_cost = billed_units × price_per_unit × rates_multiplier`; `total = Σ item_cost`. Items per call are mutually exclusive: "
             "`input_uncached = input_tokens − cached_input_tokens`, `input_cached`, `output` (reasoning already inside output is not added again), "
             "optional `request`/`classification`, and `uncertain_charge` (USD pass-through, blank until reconciled).")
    L.append("- Any blank price or unmeasured unit makes that item **unknown**; totals show the known part plus the count of unknown items.")
    L.append("- Every `usage.csv` row maps to one `pilot_calls.jsonl` line by `(run, request_id)`.")
    L.append("- Projection per stage: `cost = work × unit_cost × (1 + retry_rate)`; verify work = `ceil(verify_sample_fraction × work)`; "
             "fallback work = `ceil(fallback_fraction × work)` (≤ max_fallback_fraction); group/memo = measured one-time cost × fixed multiplier × (1 + retry). "
             "Time = `work × (1 + retry) / (per-worker throughput × (1 + (max_concurrency − 1) × efficiency))` + one-time stage time + local overhead per row × rows.")
    L.append("- API spend is separate from local compute; local compute = hours × watts / 1000 × USD/kWh (+ fixed), unknown when any input is blank.")
    L.append("- The measured section depends only on the evidence files and rates; projection assumptions never change it.")
    L.append("- The first 100 reviews give an initial estimate only. Refresh after 500 and 10,000 reviews before the full run.")
    L.append("")
    return "\n".join(L)


def replay(source=COST_DIR, out=None, rates_multiplier="1", rates_path=None, assumptions_path=None,
           local_path=None, overrides=None, csv_path=None, manifest=DEFAULT_MANIFEST, manifest_key=None) -> dict:
    multiplier = dec(rates_multiplier)
    if multiplier is None or multiplier < 0:
        raise CalcError("--rates-multiplier must be a non-negative number")
    src = load_source(source, rates_path, assumptions_path, local_path, overrides)
    if csv_path:
        prov = (src["timing"] or {}).get("provenance") or {}
        chk = verify_csv(csv_path, manifest, manifest_key, int(prov.get("expected_rows") or 100))
        ids = [r.get("review_id") for r in src["records"]]
        if ids != chk["ids"]:
            raise CalcError("pilot_records.jsonl IDs do not match %s (order or membership)" % chk["csv_name"])
        rows_by_id = {r["review_id"]: r for r in chk["rows"]}
        for r in src["records"]:
            if r.get("source_sha256") != row_sha(rows_by_id[r["review_id"]]):
                raise CalcError("source_sha256 mismatch for %s" % r["review_id"])
    measured = build_measured(src, multiplier)
    proj = build_projection(src, measured, multiplier)
    text = render_report(src, measured, proj, multiplier)
    out_path = Path(out) if out else Path(source) / "report.md"
    write_text(out_path, text + "\n")
    return {"report_path": out_path, "data_source": src["data_source"], "measured": measured,
            "projection": proj, "text": text}


def summary_lines(res: dict) -> List[str]:
    m, pj = res["measured"], res["projection"]
    lines = ["data source: %s" % {"measured": "MEASURED pilot", "synthetic": "SYNTHETIC fixture (NOT measured)",
                                  "dry_run": "DRY-RUN (NOT measured)", "none": "No measured pilot yet"}[res["data_source"]]]
    for run in RUNS:
        r = m["runs"][run]
        lines.append("%s: API %s | wall %s | completed %s | enrich calls %s" % (
            run, r["api"].fmt(), secs(r["wall_seconds"]), _v(r["records"].get("completed")), _v(r["enrich_calls"])))
    for sc in SCENARIOS:
        v = pj["scenarios"][sc]["variants"]["reuse"]
        lines.append("projection %s (reuse): API %s | time %s | %s" % (sc, v["api"].fmt(), secs(v["seconds"]), v["budget_status"]))
    for w in pj["warnings"]:
        lines.append(w)
    lines.append("report: %s" % rel(res["report_path"]))
    return lines


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--replay":
        argv = ["replay"] + argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["replay"] + argv
    ap = argparse.ArgumentParser(prog="cost_calc.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    rp = sub.add_parser("replay", help="offline replay (default): saved files -> report.md")
    rp.add_argument("--source", default=str(COST_DIR), help="folder with pilot_*.jsonl, usage.csv, pilot_timing.json")
    rp.add_argument("--out", default=None, help="report path (default: <source>/report.md)")
    rp.add_argument("--rates-multiplier", default="1", help="scale every API price (e.g. 2 doubles all rates)")
    rp.add_argument("--rates", default=None)
    rp.add_argument("--assumptions", default=None)
    rp.add_argument("--local-compute", default=None)
    rp.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override an assumption, dotted path, JSON value")
    rp.add_argument("--csv", default=None, help="optional: re-check checksum and IDs against this CSV")
    rp.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    rp.add_argument("--manifest-key", default=None)
    cp = sub.add_parser("collect", help="build evidence files from cold/warm run directories")
    cp.add_argument("--cold", required=True)
    cp.add_argument("--warm", required=True)
    cp.add_argument("--csv", default=None, help="cost_100.csv (default: run_config input_csv or the local dataset folder)")
    cp.add_argument("--out", default=str(COST_DIR))
    cp.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    cp.add_argument("--manifest-key", default=None, help="manifest files key (default: CSV file name)")
    cp.add_argument("--expect-rows", type=int, default=100)
    cp.add_argument("--rates", default=None)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "collect":
            t = collect(args.cold, args.warm, args.csv, Path(args.out), args.manifest, args.manifest_key,
                        args.expect_rows, rates_path=args.rates)
            p = t["provenance"]
            print("collected %s data: %d IDs, checksum ok (%s), cold %s calls, warm %s calls -> %s" % (
                p["data_source"].upper(), p["id_count"], p["csv_sha256"][:12],
                sum(s["attempts"] for s in t["runs"]["cold"]["stages"].values()),
                sum(s["attempts"] for s in t["runs"]["warm"]["stages"].values()), rel(args.out)))
            return 0
        res = replay(args.source, args.out, args.rates_multiplier, args.rates, args.assumptions,
                     args.local_compute, args.set, args.csv, args.manifest, args.manifest_key)
        if res["data_source"] == "synthetic":
            print("=" * 72)
            print("SYNTHETIC FIXTURE DATA - NOT A MEASURED PILOT")
            print("=" * 72)
        for line in summary_lines(res):
            print(line)
        return 0
    except CalcError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

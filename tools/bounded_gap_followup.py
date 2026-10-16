"""One approved five-batch follow-up. No inference without --execute.

Original runs stay read-only. This run has a separate USD0.38 allowance, while
the shared OpenRouter/Jev caps and all old holds remain unchanged. Private
requests, responses and outputs are saved only in the requested run directory.
"""
import argparse
from collections import Counter
from decimal import Decimal
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

from tools import gap_closure_eval as g
from tools import deepinfra_batch10_canary as canary
from tools import openrouter_extractor_benchmark as router

NAMESPACE = "measurement-followup-20261015-v1"
ALLOWLIST_SHA = "b8f2edb158e85aea2d725fbfc34926797ad8acd6e53a5599b86da71f2a1ea6c8"
PLAN_SHA = "797d89195ac3b918a4ff8fb4bc598ac5291b811377dc02bd7516c3af0b4ed599"
ROUTE = "crusoe/bf16"
CAP = 380_000_000
RESERVE = 36_044_600  # Full endpoint bounds: 131072 input + 117964 output.
MAX_ATTEMPTS = 10
PER_BATCH = 2
ROLE_COUNTS = {"verify": 2, "group": 2, "audit_label": 1}
FALLBACK_BACKOFF_SECONDS = 45
MIN_REQUEST_INTERVAL_SECONDS = 45
MAX_IN_PROCESS_BACKOFF_SECONDS = 300
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calls(
 key TEXT PRIMARY KEY,logical TEXT NOT NULL,role TEXT NOT NULL,attempt INTEGER NOT NULL,
 status TEXT NOT NULL,reserved_nusd INTEGER NOT NULL,charged_nusd INTEGER,
 request_sha TEXT NOT NULL,request_json TEXT NOT NULL,created_utc TEXT NOT NULL,
 settled_utc TEXT,elapsed_seconds REAL,input_tokens INTEGER,output_tokens INTEGER,
 reasoning_tokens INTEGER,usage_charge_nusd INTEGER,derived_charge_nusd INTEGER,
 http_status INTEGER,response_body BLOB,error_class TEXT,output_json TEXT,
 response_headers_json TEXT,retry_not_before_epoch REAL,
 UNIQUE(logical,attempt));
"""


@dataclass(frozen=True)
class RunPolicy:
    namespace: str
    cap: int
    reserve: int
    max_attempts: int
    per_batch: int
    role_counts: tuple


def original_policy():
    return RunPolicy(NAMESPACE, CAP, RESERVE, MAX_ATTEMPTS, PER_BATCH, tuple(ROLE_COUNTS.items()))


def private_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(g.canon(value) + "\n"); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path); path.chmod(0o600)


def read_source(source, allowlist):
    """Read only machine artifacts. Never load a human answer file."""
    source, allowlist = Path(source), Path(allowlist)
    if g.file_sha(allowlist) != ALLOWLIST_SHA:
        raise ValueError("allowlist hash changed")
    spec = json.loads(allowlist.read_text())
    c = sqlite3.connect("file:" + str((source / "run.db").resolve()) + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    plan = g.load_plan(source, c)
    if g.digest(plan) != PLAN_SHA:
        raise ValueError("frozen plan hash changed")
    text = dict(c.execute("SELECT id,review_text FROM texts"))
    built = {x[0]: x for x in g.build_calls(plan, text)}
    old = {role: g.outputs(c, role + ":") for role in ROLE_COUNTS}
    if {r: len(v) for r, v in old.items()} != {"verify": 980, "group": 580, "audit_label": 90}:
        raise ValueError("original coverage changed")
    old["audit_group"] = g.outputs(c, "audit_group:")
    if len(old["audit_group"]) != 100:
        raise ValueError("issue-auditor reference incomplete")
    calls = []
    for row in spec["requests"]:
        logical, role, ids, request = built[row["original_logical_request"]]
        request = g.on_route(request, ROUTE)
        if role != row["role"] or ids != row["source_ids"] or len(ids) != 10:
            raise ValueError("batch identity changed")
        if g.digest(request) != row["request_sha256_on_crusoe"]:
            raise ValueError("request hash changed")
        if any(r in old[role] or not text.get(r) for r in ids):
            raise ValueError("target already settled or source missing")
        calls.append((logical, role, ids, request))
    validate_scope(calls)
    identity = {"namespace": NAMESPACE, "plan_sha256": PLAN_SHA,
                "allowlist_sha256": ALLOWLIST_SHA, "source_db_sha256": g.file_sha(source / "run.db"),
                "source_plan_file_sha256": g.file_sha(source / "plan.json"),
                "requests": [{"logical": a, "role": b, "request_sha256": g.digest(d)} for a,b,_,d in calls],
                "cap_nusd": CAP, "reserve_nusd": RESERVE,
                "allowance": "Separate one-time USD0.38, independent of historical USD49.99 ceiling; approved 2026-10-15T23:22:06Z. No other cap change."}
    c.close()
    return plan, text, old, calls, identity


def validate_scope(calls, role_counts=None):
    role_counts = ROLE_COUNTS if role_counts is None else role_counts
    batches = sum(role_counts.values())
    if len(calls) != batches or dict(Counter(x[1] for x in calls)) != role_counts:
        raise ValueError("exact frozen batch scope required")
    ids = [r for x in calls for r in x[2]]
    if len(ids) != 10 * batches or len(set(ids)) != 10 * batches or len({x[0] for x in calls}) != batches:
        raise ValueError("exact distinct source identity scope required")
    for _, role, ids, request in calls:
        if len(ids) != 10 or request.get("model") != g.MODEL or request.get("max_tokens") != 4096:
            raise ValueError("request bounds changed")
        expected = {"only": [ROUTE], "allow_fallbacks": False, "require_parameters": True,
                    "data_collection": "deny", "zdr": True}
        if request.get("provider") != expected or request.get("reasoning") != {"effort": "low"}:
            raise ValueError("route or privacy configuration changed")
        if request["response_format"]["json_schema"].get("strict") is not True:
            raise ValueError("strict schema required")


def preflight(out):
    route = g.verify_role_route(ROUTE)
    key = os.environ.get("OPENROUTER_API_KEY") or canary.keychain_secret(timeout_seconds=90)
    account = canary.verify_project_key(key, CAP)
    credits = router.request_json("https://openrouter.ai/api/v1/credits", key=key)["data"]
    available = Decimal(str(credits["total_credits"])) - Decimal(str(credits["total_usage"]))
    if not available.is_finite() or available < Decimal("0.38"):
        raise ValueError("existing credits cannot cover the cap")
    endpoints = router.request_json("https://openrouter.ai/api/v1/models/" + g.MODEL + "/endpoints")["data"]["endpoints"]
    endpoint = next(x for x in endpoints if x.get("tag") == ROUTE)
    if endpoint.get("context_length") != 131072 or not 4096 <= endpoint.get("max_completion_tokens", 0) <= 117964:
        raise ValueError("endpoint bounds changed")
    private_json(out / "preflight.json", {"checked_utc": g.utc(), "route": route,
        "account": account, "existing_credit_usd": str(available), "paid_calls": 0,
        "cap_nusd": CAP, "reserve_per_attempt_nusd": RESERVE,
        "max_attempts": MAX_ATTEMPTS, "maximum_reservations_nusd": RESERVE * MAX_ATTEMPTS})
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def rate_headers(headers):
    """Keep only response rate hints. Never copy cookies or request credentials."""
    return {k.lower(): v for k, v in headers.items()
            if k.lower() in ("retry-after", "date") or k.lower().startswith(("ratelimit", "x-ratelimit"))}


def retry_delay(headers, now):
    """Honor Retry-After seconds or HTTP date; never guess other reset formats."""
    value = headers.get("retry-after", "")
    delay = 0.0
    try:
        if value.isdigit():
            delay = float(value)
        elif value:
            date = parsedate_to_datetime(value)
            if date.tzinfo is not None:
                delay = max(0.0, date.timestamp() - now)
    except (ValueError, TypeError, OverflowError):
        pass
    return max(FALLBACK_BACKOFF_SECONDS, delay)


def bind_response_id_enum(request, ids):
    """Offline candidate for a FUTURE approved manifest, never the frozen run.

    This constrains copying to the ten original IDs. Exact membership validation
    still rejects duplicates. Changing this schema changes the request hash and
    therefore requires a new approved allowlist; read_source never applies it.
    """
    if len(ids) != 10 or len(set(ids)) != 10 or any(not isinstance(r, str) for r in ids):
        raise ValueError("ten distinct IDs required")
    candidate = json.loads(g.canon(request))
    items = json.loads(candidate["messages"][-1]["content"].rsplit("\n", 1)[-1])
    if [item["review_id"] for item in items] != list(ids):
        raise ValueError("response enum must match the exact input IDs")
    prop = candidate["response_format"]["json_schema"]["schema"]["properties"]["results"]["items"]["properties"]["review_id"]
    prop["enum"] = list(ids)
    if len(g.canon(candidate).encode()) + candidate["max_tokens"] > g.CONTEXT:
        raise ValueError("candidate exceeds conservative context bound")
    return candidate


def transport(request, key):
    req = urllib.request.Request(g.URL, data=g.canon(request).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + key})
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=45) as response:
            return response.status, response.read(), rate_headers(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), rate_headers(exc.headers)


def strict_output(role, response, ids, request):
    value = g.content_of(role, response, ids, {})
    items = json.loads(response["choices"][0]["message"]["content"])["results"]
    fields = set(request["response_format"]["json_schema"]["schema"]["properties"]["results"]["items"]["required"])
    if any(set(i) != fields for i in items) or [i["review_id"] for i in items] != ids:
        raise ValueError("strict fields or ID order differs")
    return value


def require_current_schema(dbpath):
    """Reject historical databases before any metadata write or route preflight."""
    dbpath = Path(dbpath)
    if dbpath.exists():
        with sqlite3.connect("file:" + str(dbpath.resolve()) + "?mode=ro", uri=True) as existing:
            columns = {r[1] for r in existing.execute("PRAGMA table_info(calls)")}
            if not {"response_headers_json", "retry_not_before_epoch"} <= columns:
                raise ValueError("old run schema is immutable; no migration or new call")


class BoundedRunner:
    """Use ProjectBudget callbacks for atomic shared/run admission and settlement."""
    def __init__(self, budget, out, calls, identity, send, check_route, clock=time.time, sleep=time.sleep, policy=None):
        self.policy = policy or original_policy()
        self.budget, self.out, self.calls = budget, Path(out), calls
        self.send, self.check_route = send, check_route
        self.clock, self.sleep = clock, sleep
        validate_scope(calls, dict(self.policy.role_counts))
        self.request_hashes = {logical: g.digest(request) for logical, _, _, request in calls}
        identity = {"binding": identity, "policy": asdict(self.policy), "request_hashes": self.request_hashes}
        dbpath = self.out / "followup.db"
        require_current_schema(dbpath)
        c = sqlite3.connect(dbpath); c.executescript(SCHEMA)
        saved = c.execute("SELECT value FROM meta WHERE key='identity'").fetchone()
        if saved and saved[0] != g.canon(identity):
            c.close(); raise ValueError("run identity changed")
        if not saved:
            c.execute("INSERT INTO meta VALUES('identity',?)", (g.canon(identity),)); c.commit()
        c.close(); dbpath.chmod(0o600)
        self.db = budget.db
        self.db.execute("ATTACH DATABASE ? AS followup", (str(dbpath),))

    def exposure(self):
        return self.db.execute("SELECT COALESCE(SUM(CASE WHEN status IN ('succeeded','quarantined_metered') "
            "AND charged_nusd IS NOT NULL THEN charged_nusd ELSE MAX(reserved_nusd,COALESCE(charged_nusd,0)) END),0) "
            "FROM followup.calls").fetchone()[0]

    def next_attempt(self, logical):
        rows = self.db.execute("SELECT status,http_status FROM followup.calls WHERE logical=? ORDER BY attempt", (logical,)).fetchall()
        if any(r[0] == "succeeded" for r in rows) or len(rows) >= self.policy.per_batch:
            return None
        if any(r[0] == "rejected_http" and r[1] != 429 and not 500 <= (r[1] or 0) < 600 for r in rows):
            raise ValueError("configuration rejection forbids retry")
        if any(r[0] not in ("quarantined_metered", "rejected_http") for r in rows):
            raise ValueError("unsettled delivery forbids retry")
        return len(rows) + 1

    def run(self):
        if self.db.execute("SELECT 1 FROM followup.calls WHERE status IN ('reserved','uncertain') LIMIT 1").fetchone():
            return "stopped_uncertain"
        if self.db.execute("SELECT 1 FROM followup.calls WHERE status='rejected_http' AND http_status != 429 AND (http_status < 500 OR http_status >= 600) LIMIT 1").fetchone():
            return "stopped_configuration"
        for logical, role, ids, request in self.calls:
            while self.next_attempt(logical) is not None:
                attempt = self.next_attempt(logical)
                due = self.db.execute("SELECT MAX(retry_not_before_epoch) FROM followup.calls").fetchone()[0] or 0
                if due - self.clock() > MAX_IN_PROCESS_BACKOFF_SECONDS:
                    return "stopped_rate_limit_wait"
                # One global cooldown covers retries AND the next logical batch.
                # It is durable, so process restart cannot skip the provider hint.
                while self.clock() < due:
                    self.sleep(min(1.0, due - self.clock()))
                if g.digest(request) != self.request_hashes[logical]:
                    raise ValueError("frozen request changed before admission")
                self.check_route()
                key = self.policy.namespace + ":" + logical + "#" + str(attempt)
                def record(db):
                    if db.execute("SELECT COUNT(*) FROM followup.calls").fetchone()[0] >= self.policy.max_attempts:
                        raise ValueError("total attempt limit reached")
                    if self.exposure() + self.policy.reserve > self.policy.cap:
                        raise ValueError("new-run cap would be exceeded")
                    if db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0] != 1:
                        raise ValueError("another paid request is active")
                    db.execute("INSERT INTO followup.calls(key,logical,role,attempt,status,reserved_nusd,request_sha,request_json,created_utc) "
                        "VALUES(?,?,?,?,'reserved',?,?,?,?)", (key, logical, role, attempt, self.policy.reserve, g.digest(request), g.canon(request), g.utc()))
                self.budget.reserve(key, "openrouter", self.policy.reserve, record=record)
                started = time.monotonic()
                body, http, value, charge, inp, out, reasoning, reported, derived = None, None, None, None, None, None, None, None, None
                error, status = None, "uncertain"
                headers, retry_at = {}, None
                try:
                    http, body, headers = self.send(request)
                    headers = rate_headers(headers)
                    retry_at = self.clock() + MIN_REQUEST_INTERVAL_SECONDS
                    # Save raw receipt before any parsing or settlement. No response is printed.
                    receipt = self.out / ("receipt-%s-%d.bin" % (logical.replace(":", "-"), attempt))
                    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as f:
                        f.write(body); f.flush(); os.fsync(f.fileno())
                    if not 200 <= http < 300:
                        status, error = "rejected_http", "HTTP%d" % http
                        if http == 429 or 500 <= http < 600:
                            retry_at = self.clock() + max(MIN_REQUEST_INTERVAL_SECONDS, retry_delay(headers, self.clock()))
                    else:
                        response = json.loads(body)
                        inp, out, reasoning, derived = g.usage_of(role, response, ROUTE)
                        cost = response["usage"].get("cost")
                        if cost is not None:
                            number = Decimal(str(cost))
                            if not number.is_finite() or number < 0:
                                raise ValueError("invalid reported charge")
                            reported = router.money_nusd(number)
                        charge = max(derived, reported or 0)
                        if charge > self.policy.reserve:
                            raise ValueError("charge exceeds reservation")
                        try:
                            value = strict_output(role, response, ids, request)
                            status = "succeeded"
                        except (ValueError, TypeError, KeyError, IndexError):
                            status, error = "quarantined_metered", "InvalidOutput"
                except Exception as exc:
                    status, error = "uncertain", type(exc).__name__
                elapsed = time.monotonic() - started
                def finish(db):
                    db.execute("UPDATE followup.calls SET status=?,charged_nusd=?,settled_utc=?,elapsed_seconds=?,input_tokens=?,"
                        "output_tokens=?,reasoning_tokens=?,usage_charge_nusd=?,derived_charge_nusd=?,http_status=?,response_body=?,error_class=?,output_json=?,response_headers_json=?,retry_not_before_epoch=? WHERE key=?",
                        (status, charge, g.utc(), elapsed, inp, out, reasoning, reported, derived, http, body, error,
                         g.canon(value) if value is not None else None, g.canon(headers), retry_at, key))
                if status in ("succeeded", "quarantined_metered"):
                    self.budget.settle(key, status, charge, record=finish)
                else:
                    self.budget.uncertain(key, record=finish)
                print(g.canon({"role": role, "attempt": attempt, "status": status, "new_exposure_nusd": self.exposure()}), flush=True)
                if status == "uncertain" or (http is not None and (http != 429 and not 500 <= http < 600) and status == "rejected_http"):
                    return "stopped_uncertain" if status == "uncertain" else "stopped_configuration"
                if status == "succeeded":
                    break
        return "finished"


def summarize(out, plan, old, calls, identity):
    c = sqlite3.connect("file:" + str((out / "followup.db").resolve()) + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT logical,role,attempt,status,reserved_nusd,charged_nusd,input_tokens,output_tokens,"
        "reasoning_tokens,usage_charge_nusd,derived_charge_nusd,elapsed_seconds,http_status,error_class,request_sha,created_utc,settled_utc FROM calls ORDER BY created_utc,key")]
    fresh = {r: {} for r in old}
    for role, value in c.execute("SELECT role,output_json FROM calls WHERE status='succeeded'"):
        parsed = json.loads(value)
        if set(fresh[role]) & set(parsed):
            raise ValueError("duplicate accepted result")
        fresh[role].update(parsed)
    merged = {r: {**old[r], **fresh[r]} for r in old}
    for r in merged:
        if set(old[r]) & set(fresh[r]):
            raise ValueError("original output overwritten")
    v, grouped, auditor = merged["verify"], merged["group"], merged["audit_label"]
    jl, hist, lc, gc = plan["jev_labels"], plan["historical_issue"], plan["label_claims"], plan["group_claims"]
    vids = [r for r in plan["verify_ids"] if r in v]
    gids = [r for r in plan["group_ids"] if r in grouped]
    changed = [r for r in lc if lc[r]["planted"]]
    unchanged = [r for r in lc if not lc[r]["planted"]]
    changed_issues = [r for r in gc if gc[r]["planted"]]
    paired_labels = [r for r in changed if r in auditor and r in v]
    paired_issues = [r for r in changed_issues if r in grouped and r in merged["audit_group"]]
    roles = {}
    for role in ROLE_COUNTS:
        rr = [r for r in rows if r["role"] == role]
        roles[role] = {"attempts": len(rr), "valid_outputs": len(fresh[role]),
            "status_counts": dict(Counter(r["status"] for r in rr)),
            "known_charges_nusd": sum(r["charged_nusd"] or 0 for r in rr),
            "input_tokens": sum(r["input_tokens"] or 0 for r in rr),
            "output_tokens": sum(r["output_tokens"] or 0 for r in rr),
            "unknown_usage_attempts": sum(r["input_tokens"] is None or r["output_tokens"] is None for r in rr),
            "summed_request_seconds": round(sum(r["elapsed_seconds"] or 0 for r in rr), 3)}
    def paired_table(ids, audit, blind):
        return {"both_flagged": sum(audit(r) and blind(r) for r in ids),
                "auditor_only": sum(audit(r) and not blind(r) for r in ids),
                "blind_only": sum(not audit(r) and blind(r) for r in ids),
                "neither_flagged": sum(not audit(r) and not blind(r) for r in ids)}
    result = {"namespace": NAMESPACE, "created_utc": g.utc(), "publication": "held locally; not published",
        "model": g.MODEL, "route": ROUTE, "identity": identity,
        "attempts": len(rows), "status_counts": dict(Counter(r["status"] for r in rows)),
        "roles": roles,
        "accounting": "Each metered charge conservatively uses the larger of provider-reported usage.cost and usage times pinned rates; both are saved. This is not a later provider invoice.",
        "known_charges_nusd": sum(r["charged_nusd"] or 0 for r in rows),
        "unresolved_reservations_nusd": sum(r["reserved_nusd"] for r in rows if r["status"] not in ("succeeded", "quarantined_metered")),
        "exposure_nusd": sum(r["charged_nusd"] if r["status"] in ("succeeded", "quarantined_metered") else max(r["reserved_nusd"], r["charged_nusd"] or 0) for r in rows),
        "cap_nusd": CAP, "new_outputs": {r: len(fresh[r]) for r in ROLE_COUNTS},
        "coverage": {"verify": {"selected": 1000, "before": len(old["verify"]), "after": len(vids)},
                     "group": {"selected": 600, "before": len(old["group"]), "after": len(gids)},
                     "audit_label": {"selected": 100, "before": len(old["audit_label"]), "after": len(auditor)}},
        "verifier_agreement": {f: g.share(sum(v[r][f] == jl[r][f] for r in vids), len(vids)) for f in g.LABELS},
        "verifier_joint": g.share(sum(all(v[r][f] == jl[r][f] for f in g.LABELS) for r in vids), len(vids)),
        "group_exact": g.share(sum(grouped[r]["issue_id"] == hist[r] for r in gids), len(gids)),
        "group_family": g.share(sum(grouped[r]["issue_id"] != "abstain" and g.family(grouped[r]["issue_id"]) == g.family(hist[r]) for r in gids), len(gids)),
        "label_auditor_changed_coverage": g.share(sum(r in auditor for r in changed), len(changed)),
        "label_auditor_unchanged_coverage": g.share(sum(r in auditor for r in unchanged), len(unchanged)),
        "label_auditor_detected": g.share(sum(auditor[r][lc[r]["planted"] + "_supported"] is False for r in changed if r in auditor), sum(r in auditor for r in changed)),
        "label_auditor_flagged_unchanged": g.share(sum(not all(auditor[r].values()) for r in unchanged if r in auditor), sum(r in auditor for r in unchanged)),
        "paired_label_coverage": g.share(len(paired_labels), len(changed)),
        "paired_label_blind_disagreement": g.share(sum(v[r][lc[r]["planted"]] != lc[r]["claim"][lc[r]["planted"]] for r in paired_labels), len(paired_labels)),
        "paired_issue_coverage": g.share(len(paired_issues), len(changed_issues)),
        "paired_issue_blind_disagreement": g.share(sum(grouped[r]["issue_id"] != gc[r]["claim"] for r in paired_issues), len(paired_issues)),
        "paired_label_table": paired_table(paired_labels, lambda r: auditor[r][lc[r]["planted"] + "_supported"] is False,
            lambda r: v[r][lc[r]["planted"]] != lc[r]["claim"][lc[r]["planted"]]),
        "paired_issue_table": paired_table(paired_issues, lambda r: merged["audit_group"][r]["supported"] is False,
            lambda r: grouped[r]["issue_id"] != gc[r]["claim"]),
        "limitations": ["Model agreement, not human accuracy.", "Original runs, old holds and failures remain unchanged.",
                        "Synthetic injection experiment unchanged; no new injection or Jev calls.", "No production database or grading release changes."],
        "receipts": rows}
    private_json(out / "aggregate.json", result)
    private_json(out / "merged-machine-outputs.json", merged)
    c.close()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--allowlist", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shared-budget-root", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    require_current_schema(args.out / "followup.db")
    os.umask(0o077); args.out.mkdir(parents=True, exist_ok=True); args.out.chmod(0o700)
    lease = open(args.out / "run.lock", "a+b")
    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan, text, old, calls, identity = read_source(args.source, args.allowlist)
    private_json(args.out / "approval-and-identity.json", identity)
    if not args.execute:
        print(g.canon({"status": "offline_scope_verified", "batches": 5, "source_ids": 50, "cap_nusd": CAP})); return
    key = preflight(args.out)
    from spotify_pipeline.project_budget import ProjectBudget
    from tools.checkpoint5000_dispatch import legacy_paths
    # Refuse a migration or cap change in this narrowly approved run.
    ledger_path = args.shared_budget_root / "project_budget.db"
    with sqlite3.connect("file:" + str(ledger_path.resolve()) + "?mode=ro", uri=True) as check:
        if dict(check.execute("SELECT budget,cap_nusd FROM caps")) != {"openrouter": 5_000_000_000, "jev": 5_000_000_000}:
            raise ValueError("existing provider caps changed; no call")
    paths = legacy_paths()
    paths["batch_v1"] = str(args.shared_budget_root / "deepinfra_batch10_canary.db")
    paths["batch_v2"] = str(args.shared_budget_root / "deepinfra_batch10_canary_v2.db")
    with ProjectBudget(str(args.shared_budget_root / "project_budget.db"), paths, max_global_inflight=None) as budget:
        def historic_state():
            return g.digest({"reservations": list(budget.db.execute("SELECT * FROM reservations WHERE request_key NOT LIKE ? ORDER BY request_key", (NAMESPACE + ":%",))),
                "caps": list(budget.db.execute("SELECT * FROM caps ORDER BY budget")),
                "legacy": list(budget.db.execute("SELECT * FROM legacy_sources ORDER BY name"))})
        historic_before = historic_state()
        private_json(args.out / "historical-ledger-before.json", {"state_sha256": historic_before,
            "openrouter_exposure_nusd": budget.exposure("openrouter"), "jev_exposure_nusd": budget.exposure("jev")})
        runner = BoundedRunner(budget, args.out, calls, identity,
            lambda request: transport(request, key), lambda: g.verify_role_route(ROUTE))
        try:
            status = runner.run()
        finally:
            result = summarize(args.out, plan, old, calls, identity)
            unchanged = g.file_sha(args.source / "run.db") == identity["source_db_sha256"] and g.file_sha(args.source / "plan.json") == identity["source_plan_file_sha256"]
            private_json(args.out / "preservation.json", {"original_run_unchanged": unchanged,
                "historical_ledger_rows_and_caps_unchanged": historic_state() == historic_before,
                "historical_ledger_state_sha256": historic_before,
                "original_counts": {r: len(old[r]) for r in old}, "run_exposure_nusd": runner.exposure(),
                "shared_openrouter_exposure_nusd": budget.exposure("openrouter"), "shared_jev_exposure_nusd": budget.exposure("jev")})
    print(g.canon({"status": status, "attempts": result["attempts"], "new_outputs": result["new_outputs"],
                  "new_exposure_nusd": result["exposure_nusd"], "original_run_unchanged": unchanged}), flush=True)


if __name__ == "__main__":
    main()

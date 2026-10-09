"""Durable first-500 gate for the frozen next-5,000 source reviews.

Only the first 500 manifest rows are eligible. Every inference reservation and
result is committed in the shared project ledger. An uncertain call is held and
never retried by this command.
"""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import os
from pathlib import Path
import time

from spotify_pipeline.config import config_hash
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline import jev
from spotify_pipeline.jev_pilot import NANODOLLARS_PER_INPUT_TOKEN, RESERVATION_NANODOLLARS
from spotify_pipeline.project_budget import ProjectBudget
from tools import deepinfra_batch10_canary as canary
from tools import deepinfra_recheck100 as recheck
from tools import openrouter_extractor_benchmark as benchmark
from tools.checkpoint5000_dispatch import legacy_paths
from tools.checkpoint5000_orchestrate import verify_jev_price, JEV_SERVICE, JEV_ACCOUNT

MANIFEST = Path("local/next5000_manifest.json")
BUDGET = "local/project_budget.db"
FIRST = 500
WORKERS = 2
TAIL_SIZE = 4
TAIL_VERSION = "next5000-first500-four-review-tail-v1"
REMAINDER_TAIL_VERSION = "next5000-remainder-partial-batch-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False)


def load_manifest():
    with MANIFEST.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    rows = manifest.get("rows", [])
    if manifest.get("schema_version") != "next5000-manifest-v1" or len(rows) != 5000 or \
            manifest.get("selected_rows") != 5000 or \
            manifest.get("jev_config_sha256") != config_hash(jev.label_config()) or \
            manifest.get("evidence_config_sha256") != recheck.config_sha():
        raise ValueError("frozen selection or configuration differs")
    for position, row in enumerate(rows, 5001):
        if row.get("source_position") != position or \
                row_sha256([row[k] for k in SOURCE_FIELDS]) != row.get("source_sha256") or \
                text_sha256(row["review_text"]) != row.get("text_sha256"):
            raise ValueError("frozen source ID, position, or hash differs")
    if len({r["review_id"] for r in rows}) != 5000:
        raise ValueError("duplicate frozen source ID")
    return manifest, file_sha256(str(MANIFEST))


def ensure_tables(db, manifest, manifest_sha):
    db.execute("CREATE TABLE IF NOT EXISTS next5000_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_rows(
        position INTEGER PRIMARY KEY,review_id TEXT NOT NULL UNIQUE,
        review_text TEXT NOT NULL,source_sha TEXT NOT NULL,text_sha TEXT NOT NULL,
        blocked INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_labels(
        review_id TEXT PRIMARY KEY,label_json TEXT NOT NULL,config_sha TEXT NOT NULL,
        provenance TEXT NOT NULL,origin_id TEXT,request_key TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_evidence(
        review_id TEXT PRIMARY KEY,entities_json TEXT NOT NULL,evidence_quote TEXT NOT NULL,
        config_sha TEXT NOT NULL,provenance TEXT NOT NULL,origin_id TEXT,request_key TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_quarantines(
        review_id TEXT PRIMARY KEY,reason TEXT NOT NULL,request_key TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_requests(
        request_key TEXT PRIMARY KEY,stage TEXT NOT NULL,status TEXT NOT NULL,
        config_sha TEXT NOT NULL,request_sha TEXT NOT NULL,response_json TEXT,
        elapsed_seconds REAL,input_tokens INTEGER,output_tokens INTEGER,
        reasoning_tokens INTEGER,charged_nusd INTEGER,error_class TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS next5000_members(
        request_key TEXT NOT NULL,review_id TEXT NOT NULL,
        PRIMARY KEY(request_key,review_id))""")
    identity = {"manifest_sha": manifest_sha, "label_config_sha":
        manifest["jev_config_sha256"], "evidence_config_sha":
        manifest["evidence_config_sha256"], "first_count": str(FIRST)}
    saved = dict(db.execute("SELECT key,value FROM next5000_meta"))
    if saved and saved != identity:
        raise ValueError("checkpoint identity changed")
    rows = [(r["source_position"], r["review_id"], r["review_text"],
        r["source_sha256"], r["text_sha256"], int(r["blocked_prior_uncertainty"]))
        for r in manifest["rows"][:FIRST]]
    existing = list(db.execute("SELECT * FROM next5000_rows ORDER BY position"))
    if existing and (len(existing) not in (FIRST, 5000) or existing !=
            [(r["source_position"], r["review_id"], r["review_text"],
              r["source_sha256"], r["text_sha256"], int(r["blocked_prior_uncertainty"]))
             for r in manifest["rows"][:len(existing)]]):
        raise ValueError("checkpoint source rows changed")
    if not saved:
        with db:
            db.executemany("INSERT INTO next5000_meta VALUES (?,?)", identity.items())
            db.executemany("INSERT INTO next5000_rows VALUES (?,?,?,?,?,?)", rows)


def extend_remaining(db, manifest):
    """Activate the frozen remaining 4,500 only after first-500 QA approval."""
    count = db.execute("SELECT COUNT(*) FROM next5000_rows").fetchone()[0]
    if count == 5000:
        return 0
    if count != FIRST or db.execute("SELECT COUNT(*) FROM next5000_labels").fetchone()[0] != FIRST or \
            sum(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                for table in ("next5000_evidence", "next5000_quarantines")) != FIRST or \
            db.execute("SELECT 1 FROM next5000_requests WHERE status IN ('reserved','uncertain') LIMIT 1").fetchone():
        raise ValueError("first-500 QA gate is not fully accounted")
    rows = [(r["source_position"], r["review_id"], r["review_text"],
        r["source_sha256"], r["text_sha256"], int(r["blocked_prior_uncertainty"]))
        for r in manifest["rows"][FIRST:]]
    with db:
        db.executemany("INSERT INTO next5000_rows VALUES (?,?,?,?,?,?)", rows)
    return len(rows)


def _label_tuple(value):
    return tuple(value[k] for k in ("topic", "intent", "severity", "sentiment"))


def materialize_caches(db, manifest):
    """Use only exact source texts under identical model/prompt/schema config."""
    label_cfg = manifest["jev_config_sha256"]
    evidence_cfg = manifest["evidence_config_sha256"]
    labels = {}
    for rid, text, value, cfg in db.execute("""SELECT r.review_id,r.review_text,
            l.label_json,l.config_sha FROM checkpoint_rows r
            JOIN checkpoint_labels l USING(review_id) ORDER BY r.position"""):
        if cfg == label_cfg:
            labels.setdefault(text, (value, rid))
    for rid, text, value, cfg in db.execute("""SELECT r.review_id,r.review_text,
            l.label_json,l.config_sha FROM next5000_rows r
            JOIN next5000_labels l USING(review_id) ORDER BY r.position"""):
        if cfg == label_cfg:
            labels.setdefault(text, (value, rid))
    # The revised 100-review pilot is the only compatible evidence cache.
    pilot = {}
    sample_path = recheck.SAMPLE
    if sample_path.exists():
        sample = recheck.load_sample()
        if sample["config_sha256"] != evidence_cfg:
            raise ValueError("revised pilot evidence config changed")
        for source in sample["rows"]:
            result = db.execute("""SELECT r.entities_json,r.evidence_quote,b.config_sha
                FROM recheck100_results r JOIN recheck100_batches b USING(batch_index)
                WHERE r.review_id=? AND r.status='accepted'""",
                (source["review_id"],)).fetchone()
            if result and result[2] == evidence_cfg:
                pilot.setdefault(source["review_text"], (source, result[0], result[1]))
    for rid, text, entities, quote, cfg, label_json in db.execute("""SELECT
            r.review_id,r.review_text,e.entities_json,e.evidence_quote,e.config_sha,
            l.label_json FROM next5000_rows r JOIN next5000_evidence e USING(review_id)
            JOIN next5000_labels l USING(review_id) ORDER BY r.position"""):
        if cfg == evidence_cfg:
            pilot.setdefault(text, ({"review_id": rid, "labels": json.loads(label_json)},
                entities, quote))
    with db:
        for rid, text, blocked in db.execute("SELECT review_id,review_text,blocked FROM next5000_rows").fetchall():
            if blocked:
                continue
            if text in labels and not db.execute("SELECT 1 FROM next5000_labels WHERE review_id=?", (rid,)).fetchone():
                value, origin = labels[text]
                db.execute("INSERT INTO next5000_labels VALUES (?,?,?,?,?,NULL)",
                    (rid, value, label_cfg, "checkpoint_exact_text_cache", origin))
            if text in pilot and not db.execute("SELECT 1 FROM next5000_evidence WHERE review_id=?", (rid,)).fetchone():
                source, entities, quote = pilot[text]
                current = db.execute("SELECT label_json FROM next5000_labels WHERE review_id=?", (rid,)).fetchone()
                if current and _label_tuple(json.loads(current[0])) == _label_tuple(source["labels"]):
                    db.execute("INSERT INTO next5000_evidence VALUES (?,?,?,?,?,?,NULL)",
                        (rid, entities, quote, evidence_cfg, "revised_pilot_exact_text_cache",
                         source["review_id"]))


def aliases(db, stage, text, value, origin, evidence_config=None):
    """Apply a settled result to untouched exact-text source IDs only."""
    table = "next5000_labels" if stage == "jev" else "next5000_evidence"
    for rid, blocked in db.execute("SELECT review_id,blocked FROM next5000_rows WHERE review_text=?", (text,)):
        if blocked or db.execute("SELECT 1 FROM " + table + " WHERE review_id=?", (rid,)).fetchone():
            continue
        if stage == "jev":
            db.execute("INSERT INTO next5000_labels VALUES (?,?,?,?,?,NULL)",
                (rid, value, config_hash(jev.label_config()), "next5000_exact_text_cache", origin))
        else:
            db.execute("INSERT INTO next5000_evidence VALUES (?,?,?,?,?,?,NULL)",
                (rid, canonical(value["entities"]), value["evidence_quote"],
                 evidence_config or recheck.config_sha(), "next5000_exact_text_cache", origin))


def pending(db, stage):
    table = "next5000_labels" if stage == "jev" else "next5000_evidence"
    attempted = {t for t, in db.execute("""SELECT DISTINCT r.review_text FROM next5000_rows r
        JOIN next5000_members m USING(review_id) JOIN next5000_requests q USING(request_key)
        WHERE q.stage=?""", (stage,))}
    selected, seen = [], set()
    for pos, rid, text, source_sha, blocked in db.execute("SELECT position,review_id,review_text,source_sha,blocked FROM next5000_rows ORDER BY position"):
        if blocked or text in seen or text in attempted or db.execute("SELECT 1 FROM " + table + " WHERE review_id=?", (rid,)).fetchone():
            continue
        label = db.execute("SELECT label_json FROM next5000_labels WHERE review_id=?", (rid,)).fetchone()
        if stage == "evidence" and not label:
            continue
        row = {"source_position": pos, "review_id": rid, "review_text": text,
            "source_sha256": source_sha}
        if label:
            row["labels"] = json.loads(label[0])
        selected.append(row)
        seen.add(text)
    return selected


def summary(db, budget=None):
    result = {"first500": FIRST}
    for name, query in {"labels": "next5000_labels", "evidence": "next5000_evidence",
                        "quarantined": "next5000_quarantines"}.items():
        result[name] = db.execute("SELECT COUNT(*) FROM " + query).fetchone()[0]
    result["blocked_prior_uncertainty"] = db.execute("SELECT COUNT(*) FROM next5000_rows WHERE blocked=1").fetchone()[0]
    result["requests"] = dict(db.execute("SELECT stage||':'||status,COUNT(*) FROM next5000_requests GROUP BY stage,status"))
    result["stage_charges_nusd"] = dict(db.execute("SELECT stage,COALESCE(SUM(charged_nusd),0) FROM next5000_requests GROUP BY stage"))
    result["jev_pending_unique"] = len(pending(db, "jev"))
    result["evidence_pending_unique"] = len(pending(db, "evidence"))
    if budget:
        result["exposure_nusd"] = {name: budget.exposure(name) for name in ("jev", "openrouter")}
    return result


def evidence_config(rows):
    if len(rows) == recheck.BATCH_SIZE:
        return recheck.config_sha()
    size = len(rows)
    if not 1 <= size < recheck.BATCH_SIZE:
        raise ValueError("partial batch must contain one through nine reviews")
    return recheck.digest({"version": TAIL_VERSION if size == TAIL_SIZE else
        REMAINDER_TAIL_VERSION, "base_config": recheck.config_sha(),
        "batch_size": size, "min_items": size, "max_items": size})


def evidence_payload(rows):
    if len(rows) == recheck.BATCH_SIZE:
        return recheck.payload(rows)
    size = len(rows)
    if not 1 <= size < recheck.BATCH_SIZE or len({r["review_id"] for r in rows}) != size or \
            len({r["review_text"] for r in rows}) != size:
        raise ValueError("partial batch requires one through nine distinct IDs and texts")
    schema = json.loads(canonical(recheck.SCHEMA))
    schema["properties"]["results"]["minItems"] = size
    schema["properties"]["results"]["maxItems"] = size
    items = [{"review_id": r["review_id"], "source_sha": r["source_sha256"],
        "labels": {k: r["labels"][k] for k in ("topic", "intent", "severity", "sentiment")},
        "review_text": r["review_text"]} for r in rows]
    body = {"model": recheck.MODEL, "messages": [{"role": "user", "content":
        recheck.INSTRUCTION + json.dumps(items, ensure_ascii=False, separators=(",", ":"))}],
        "provider": {"only": [recheck.PROVIDER], "allow_fallbacks": False,
            "require_parameters": True, "data_collection": "deny", "zdr": True},
        "reasoning": {"effort": "low"}, "max_tokens": recheck.OUTPUT_LIMIT,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "spotify_exact_evidence_first500_tail", "strict": True, "schema": schema}}}
    if len(canonical(body).encode("utf-8")) + recheck.OUTPUT_LIMIT > \
            benchmark.ENDPOINT_BOUNDS["deepinfra"][0]:
        raise ValueError("tail request exceeds conservative context bound")
    return body


def inspect_evidence(response, rows):
    if len(rows) == recheck.BATCH_SIZE:
        return recheck.inspect(response, rows)
    size = len(rows)
    if not 1 <= size < recheck.BATCH_SIZE or response["choices"][0].get("finish_reason") != "stop":
        raise ValueError("tail result count or finish reason differs")
    body = json.loads(response["choices"][0]["message"]["content"])
    if not isinstance(body, dict) or set(body) != {"results"} or \
            not isinstance(body["results"], list) or len(body["results"]) != size:
        raise ValueError("tail result count or shape differs")
    expected = {r["review_id"]: r for r in rows}
    accepted, invalid, seen = {}, {}, set()
    for item in body["results"]:
        if not isinstance(item, dict) or set(item) != {"review_id", "entities", "evidence_quote"}:
            raise ValueError("tail result fields differ")
        rid = item["review_id"]
        if not isinstance(rid, str) or rid not in expected or rid in seen:
            raise ValueError("unknown or repeated tail source ID")
        seen.add(rid)
        try:
            accepted[rid] = validate_evidence(expected[rid]["review_text"],
                {"entities": item["entities"], "evidence_quote": item["evidence_quote"]})
        except Exception as exc:
            invalid[rid] = type(exc).__name__ + ": " + str(exc)
    if seen != set(expected):
        raise ValueError("missing tail source ID")
    return accepted, invalid


def request_key(manifest_sha, stage, rows):
    return "next5000-" + recheck.digest({"manifest": manifest_sha, "stage": stage,
        "ids": [r["review_id"] for r in rows], "config":
        config_hash(jev.label_config()) if stage == "jev" else evidence_config(rows)})


def _call(stage, body, key):
    started = time.monotonic()
    try:
        if stage == "jev":
            return jev.post_systemone(body, key), time.monotonic() - started, None
        return benchmark.request_json("https://openrouter.ai/api/v1/chat/completions",
            body, key), time.monotonic() - started, None
    except Exception as exc:
        return None, time.monotonic() - started, type(exc).__name__


def _finish(budget, stage, request_key_value, rows, response, elapsed, error):
    db = budget.db
    raw = canonical(response) if response is not None else None
    try:
        if response is None:
            raise ValueError(error or "request delivery unknown")
        if stage == "jev":
            parsed = jev.parse_response(response)
            inp, out, reasoning = parsed.input_tokens, parsed.output_tokens, None
            if inp > 64000 or inp * NANODOLLARS_PER_INPUT_TOKEN > RESERVATION_NANODOLLARS:
                raise ValueError("Jev usage exceeds full reservation")
            charge = inp * NANODOLLARS_PER_INPUT_TOKEN
            accepted, invalid = {rows[0]["review_id"]: parsed.__dict__}, {}
        else:
            inp, out, reasoning, charge = recheck.measured_usage(response)
            try:
                accepted, invalid = inspect_evidence(response, rows)
            except Exception as exc:
                accepted, invalid = {}, {r["review_id"]: type(exc).__name__ + ": " + str(exc) for r in rows}
    except Exception as exc:
        def record(conn):
            conn.execute("UPDATE next5000_requests SET status='uncertain',response_json=?,elapsed_seconds=?,error_class=? WHERE request_key=?",
                (raw, elapsed, type(exc).__name__ + ": " + str(exc), request_key_value))
        budget.uncertain(request_key_value, record)
        return "uncertain", 0
    status = "succeeded" if accepted and not invalid else "quarantined_metered" if not accepted else "partial_succeeded"
    def record(conn):
        conn.execute("""UPDATE next5000_requests SET status=?,response_json=?,elapsed_seconds=?,
            input_tokens=?,output_tokens=?,reasoning_tokens=?,charged_nusd=? WHERE request_key=?""",
            (status, raw, elapsed, inp, out, reasoning, charge, request_key_value))
        for row in rows:
            rid = row["review_id"]
            if rid in accepted:
                if stage == "jev":
                    value = canonical(accepted[rid])
                    conn.execute("INSERT INTO next5000_labels VALUES (?,?,?,?,?,?)",
                        (rid, value, config_hash(jev.label_config()), "jev_direct", None, request_key_value))
                    aliases(conn, stage, row["review_text"], value, rid)
                else:
                    value = accepted[rid]
                    conn.execute("INSERT INTO next5000_evidence VALUES (?,?,?,?,?,?,?)",
                        (rid, canonical(value["entities"]), value["evidence_quote"],
                         evidence_config(rows), "deepinfra_direct", None, request_key_value))
                    aliases(conn, stage, row["review_text"], value, rid, evidence_config(rows))
            else:
                conn.execute("INSERT INTO next5000_quarantines VALUES (?,?,?)",
                    (rid, invalid[rid], request_key_value))
    budget.settle(request_key_value, "quarantined_metered" if status == "quarantined_metered" else "succeeded", charge, record)
    return status, charge


def assert_resume_safe(db, stage, defer_uncertain_evidence=False):
    if db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError("shared project has an active reservation")
    unresolved = list(db.execute("""SELECT q.request_key,q.stage,r.budget,r.status,
        r.reserved_nusd,r.charged_nusd,
        (SELECT COUNT(*) FROM next5000_members m WHERE m.request_key=q.request_key)
        FROM next5000_requests q JOIN reservations r USING(request_key)
        WHERE q.status='uncertain'"""))
    if unresolved and (stage != "evidence" or not defer_uncertain_evidence):
        raise ValueError("new checkpoint has unresolved request; no further POST")
    for key, saved_stage, budget, status, reservation, charge, members in unresolved:
        if saved_stage != "evidence" or budget != "openrouter" or status != "uncertain" or \
                reservation != recheck.reservation_nusd() or charge is not None or \
                not 1 <= members <= recheck.BATCH_SIZE:
            raise ValueError("uncertain evidence hold or membership differs; no POST")
        if db.execute("""SELECT 1 FROM next5000_members m JOIN next5000_rows r
                USING(review_id) WHERE m.request_key=? AND (EXISTS(
                SELECT 1 FROM next5000_evidence e WHERE e.review_id=r.review_id) OR EXISTS(
                SELECT 1 FROM next5000_quarantines q WHERE q.review_id=r.review_id)) LIMIT 1""",
                (key,)).fetchone():
            raise ValueError("uncertain request has settled member; no POST")
    return len(unresolved)


def run_stage(budget, manifest_sha, stage, api_key, tail_only=False,
              allow_partial=False, defer_uncertain_evidence=False):
    db = budget.db
    old_uncertain = assert_resume_safe(db, stage, defer_uncertain_evidence)
    if tail_only and (stage != "evidence" or len(pending(db, "evidence")) != TAIL_SIZE):
        raise ValueError("tail requires exactly four untouched first-500 texts")
    if stage == "jev":
        verify_jev_price()
        jev.check_model_access(api_key)
        reservation = RESERVATION_NANODOLLARS
    else:
        benchmark.verify_route("deepinfra")
        canary.verify_project_key(api_key, recheck.reservation_nusd())
        reservation = recheck.reservation_nusd()
    active = {}
    invalid_streak = 0
    stop = False
    halt_reason = None
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        while active or not stop:
            while not stop and len(active) < WORKERS:
                rows = pending(db, stage)
                if stage == "jev":
                    rows = rows[:1]
                else:
                    if tail_only:
                        rows = rows[:TAIL_SIZE]
                    elif len(rows) < recheck.BATCH_SIZE and not allow_partial:
                        break
                    else:
                        rows = rows[:recheck.BATCH_SIZE]
                if not rows:
                    break
                body = jev.build_request(rows[0]["review_text"]) if stage == "jev" else evidence_payload(rows)
                rk = request_key(manifest_sha, stage, rows)
                cfg = config_hash(jev.label_config()) if stage == "jev" else evidence_config(rows)
                def record(conn):
                    conn.execute("INSERT INTO next5000_requests(request_key,stage,status,config_sha,request_sha) VALUES (?,?,'reserved',?,?)",
                        (rk, stage, cfg, recheck.digest(body)))
                    conn.executemany("INSERT INTO next5000_members VALUES (?,?)",
                        ((rk, r["review_id"]) for r in rows))
                try:
                    budget.reserve(rk, "jev" if stage == "jev" else "openrouter", reservation, record)
                except Exception as exc:
                    stop = True
                    halt_reason = type(exc).__name__ + ": " + str(exc)
                    break
                active[pool.submit(_call, stage, body, api_key)] = (rk, rows)
            if not active:
                break
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                rk, rows = active.pop(future)
                response, elapsed, error = future.result()
                status, charge = _finish(budget, stage, rk, rows, response, elapsed, error)
                print(canonical({"stage": stage, "status": status, "rows": len(rows),
                    "charge_nusd": charge, "elapsed_seconds": round(elapsed, 3)}), flush=True)
                if status == "uncertain":
                    stop = True
                invalid_streak = invalid_streak + 1 if status != "succeeded" else 0
                if status == "quarantined_metered" or invalid_streak >= (3 if stage == "jev" else 5):
                    stop = True
    result = summary(db, budget)
    result["paused"] = stop
    result["halt_reason"] = halt_reason or ("uncertain or invalid response streak" if stop else None)
    result["deferred_existing_uncertain_requests"] = old_uncertain
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run-jev", action="store_true")
    mode.add_argument("--run-evidence", action="store_true")
    mode.add_argument("--run-tail", action="store_true")
    mode.add_argument("--extend-remaining", action="store_true")
    mode.add_argument("--run-remainder-evidence", action="store_true")
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--defer-uncertain-evidence", action="store_true")
    args = parser.parse_args()
    if args.defer_uncertain_evidence and not args.run_remainder_evidence:
        raise ValueError("uncertain deferral is only for untouched remainder evidence")
    manifest, manifest_sha = load_manifest()
    with ProjectBudget(BUDGET, legacy_paths()) as budget:
        ensure_tables(budget.db, manifest, manifest_sha)
        if args.extend_remaining:
            result = {"activated_rows": extend_remaining(budget.db, manifest)}
            materialize_caches(budget.db, manifest)
            result.update(summary(budget.db, budget))
            print(canonical(result), flush=True)
            return
        materialize_caches(budget.db, manifest)
        if args.run_jev:
            key = canary.keychain_secret(timeout_seconds=90, service=JEV_SERVICE,
                                         account=JEV_ACCOUNT)
            try:
                result = run_stage(budget, manifest_sha, "jev", key)
            finally:
                key = None
        elif args.run_evidence or args.run_tail or args.run_remainder_evidence:
            key = canary.keychain_secret(timeout_seconds=90)
            try:
                result = run_stage(budget, manifest_sha, "evidence", key,
                    tail_only=args.run_tail, allow_partial=args.run_remainder_evidence,
                    defer_uncertain_evidence=args.defer_uncertain_evidence)
            finally:
                key = None
        else:
            result = summary(budget.db, budget)
            if args.dry_run:
                result["jev_full_reservation_nusd"] = RESERVATION_NANODOLLARS
                result["evidence_full_reservation_nusd"] = recheck.reservation_nusd()
                result["max_inflight_per_stage"] = WORKERS
        print(canonical(result), flush=True)


if __name__ == "__main__":
    main()

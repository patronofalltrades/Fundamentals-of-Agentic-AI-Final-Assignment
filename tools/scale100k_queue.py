"""Durable rolling 10k queue for source positions 10,001–100,000.

Eight network slots share one atomic project ledger. A regular slot owns a
500-source work chunk with ten reviews per evidence POST. A bounded 25-review
trial has its own configuration. No attempted exact text is automatically
retried after any delivery outcome.
"""

import argparse
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import fcntl
import json
import os
from pathlib import Path
import time

from spotify_pipeline import jev
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.config import config_hash
from spotify_pipeline.jev_pilot import NANODOLLARS_PER_INPUT_TOKEN, RESERVATION_NANODOLLARS
from spotify_pipeline.project_budget import ProjectBudget
from tools import deepinfra_batch10_canary as canary
from tools import deepinfra_recheck100 as evidence
from tools import scale100k_batch25 as trial25
from tools import next5000_checkpoint as previous
from tools import openrouter_extractor_benchmark as benchmark
from tools.checkpoint5000_dispatch import legacy_paths
from tools.checkpoint5000_orchestrate import verify_jev_price, JEV_SERVICE, JEV_ACCOUNT
from tools.scale100k_manifest import load

BUDGET = "local/project_budget.db"
LOCK = Path("local/scale100k_paid_run.lock")
WORKERS = 8
CHUNK_ROWS = 500
GATE_ROWS = 10000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False)


def ensure_tables(db, manifest_sha):
    db.execute("CREATE TABLE IF NOT EXISTS scale_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_rows(
        position INTEGER PRIMARY KEY,review_id TEXT NOT NULL UNIQUE,
        review_text TEXT NOT NULL,source_sha TEXT NOT NULL,text_sha TEXT NOT NULL,
        blocked_reason TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS scale_rows_text ON scale_rows(text_sha)")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_labels(
        review_id TEXT PRIMARY KEY,label_json TEXT NOT NULL,config_sha TEXT NOT NULL,
        provenance TEXT NOT NULL,origin_id TEXT,request_key TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_evidence(
        review_id TEXT PRIMARY KEY,entities_json TEXT NOT NULL,evidence_quote TEXT NOT NULL,
        config_sha TEXT NOT NULL,provenance TEXT NOT NULL,origin_id TEXT,request_key TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_quarantines(
        review_id TEXT PRIMARY KEY,reason TEXT NOT NULL,request_key TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_requests(
        request_key TEXT PRIMARY KEY,stage TEXT NOT NULL,status TEXT NOT NULL,
        config_sha TEXT NOT NULL,request_sha TEXT NOT NULL,response_json TEXT,
        elapsed_seconds REAL,input_tokens INTEGER,output_tokens INTEGER,
        reasoning_tokens INTEGER,charged_nusd INTEGER,error_class TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scale_members(
        request_key TEXT NOT NULL,review_id TEXT NOT NULL,
        PRIMARY KEY(request_key,review_id))""")
    expected = {"manifest_sha": manifest_sha,
        "label_config_sha": config_hash(jev.label_config()),
        "evidence_config_sha": evidence.config_sha(),
        "worker_slots": str(WORKERS), "chunk_rows": str(CHUNK_ROWS)}
    saved = dict(db.execute("SELECT key,value FROM scale_meta"))
    if saved and saved != expected:
        raise ValueError("scale queue identity or configuration changed")
    if not saved:
        with db:
            db.executemany("INSERT INTO scale_meta VALUES (?,?)", expected.items())


def uncertain_texts(db, historical_texts=()):
    old = set(historical_texts)
    old.update(text for text, in db.execute("""SELECT DISTINCT r.review_text
        FROM checkpoint_rows r JOIN checkpoint_request_members m USING(review_id)
        JOIN checkpoint_requests q USING(request_key)
        WHERE q.stage='evidence' AND q.status='uncertain'"""))
    old.update(text for text, in db.execute("""SELECT DISTINCT r.review_text
        FROM next5000_rows r JOIN next5000_members m USING(review_id)
        JOIN next5000_requests q USING(request_key)
        WHERE q.stage='evidence' AND q.status='uncertain'"""))
    old.update(text for text, in db.execute("""SELECT DISTINCT r.review_text
        FROM scale_rows r JOIN scale_members m USING(review_id)
        JOIN scale_requests q USING(request_key) WHERE q.status='uncertain'"""))
    return old


def activate_gate(db, manifest):
    """Add exactly the next 10k source IDs; do not change any settled row."""
    if db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError("active paid reservation; cannot activate gate")
    count, top = db.execute("SELECT COUNT(*),COALESCE(MAX(position),10000) FROM scale_rows").fetchone()
    if count not in range(0, 90001, GATE_ROWS) or top != 10000 + count:
        raise ValueError("activated source range is not contiguous")
    if count == 90000:
        return 0
    if count and pending(db, "jev") or count and pending(db, "evidence"):
        raise ValueError("previous gate has untouched eligible work")
    blocked = uncertain_texts(db, manifest["historical_uncertain_exact_texts"])
    gate = manifest["rows"][count:count + GATE_ROWS]
    records = [(r["source_position"], r["review_id"], r["review_text"],
        r["source_sha256"], r["text_sha256"],
        "empty_text" if not r["review_text"].strip() else
        "prior_uncertain_exact_text" if r["review_text"] in blocked else None)
        for r in gate]
    if len(records) != GATE_ROWS:
        raise ValueError("source gate length differs")
    with db:
        db.executemany("INSERT INTO scale_rows VALUES (?,?,?,?,?,?)", records)
    return GATE_ROWS


def _label_tuple(value):
    return tuple(value[k] for k in ("topic", "intent", "severity", "sentiment"))


def materialize_caches(db, historical_texts=()):
    """Exact text and matching model/prompt/schema; preserve every target ID."""
    jcfg, ecfg = config_hash(jev.label_config()), evidence.config_sha()
    held_texts = uncertain_texts(db, historical_texts)
    labels = {}
    for table in ("checkpoint", "next5000", "scale"):
        rows = "checkpoint_rows" if table == "checkpoint" else table + "_rows"
        labels_table = "checkpoint_labels" if table == "checkpoint" else table + "_labels"
        for rid, text, value, cfg in db.execute("SELECT r.review_id,r.review_text,l.label_json,l.config_sha "
                "FROM " + rows + " r JOIN " + labels_table + " l USING(review_id) ORDER BY r.position"):
            if cfg == jcfg:
                labels.setdefault(text, (value, rid))
    cached_evidence = {}
    if evidence.SAMPLE.exists():
        sample = evidence.load_sample()
        if sample["config_sha256"] != ecfg:
            raise ValueError("revised evidence pilot configuration changed")
        for source in sample["rows"]:
            found = db.execute("""SELECT r.entities_json,r.evidence_quote,b.config_sha
                FROM recheck100_results r JOIN recheck100_batches b USING(batch_index)
                WHERE r.review_id=? AND r.status='accepted'""", (source["review_id"],)).fetchone()
            if found and found[2] == ecfg:
                cached_evidence.setdefault(source["review_text"],
                    (source["labels"], found[0], found[1], source["review_id"]))
    for table in ("next5000", "scale"):
        for rid, text, entities, quote, cfg, label_json in db.execute("SELECT "
                "r.review_id,r.review_text,e.entities_json,e.evidence_quote,e.config_sha,l.label_json "
                "FROM " + table + "_rows r JOIN " + table + "_evidence e USING(review_id) "
                "JOIN " + table + "_labels l USING(review_id) ORDER BY r.position"):
            if cfg == ecfg:
                cached_evidence.setdefault(text, (json.loads(label_json), entities, quote, rid))
    with db:
        for rid, text, blocked in db.execute("SELECT review_id,review_text,blocked_reason FROM scale_rows").fetchall():
            if blocked or text in held_texts:
                continue
            if text in labels and not db.execute("SELECT 1 FROM scale_labels WHERE review_id=?", (rid,)).fetchone():
                value, origin = labels[text]
                db.execute("INSERT INTO scale_labels VALUES (?,?,?,?,?,NULL)",
                    (rid, value, jcfg, "compatible_exact_text_cache", origin))
            if text in cached_evidence and not db.execute("SELECT 1 FROM scale_evidence WHERE review_id=?", (rid,)).fetchone():
                label = db.execute("SELECT label_json FROM scale_labels WHERE review_id=?", (rid,)).fetchone()
                source_label, entities, quote, origin = cached_evidence[text]
                if label and _label_tuple(json.loads(label[0])) == _label_tuple(source_label):
                    validate_evidence(text, {"entities": json.loads(entities), "evidence_quote": quote})
                    db.execute("INSERT INTO scale_evidence VALUES (?,?,?,?,?,?,NULL)",
                        (rid, entities, quote, ecfg, "compatible_exact_text_cache", origin))


def pending(db, stage):
    table = "scale_labels" if stage == "jev" else "scale_evidence"
    settled = {rid for rid, in db.execute("SELECT review_id FROM " + table)}
    labelled = settled if stage == "jev" else {rid for rid, in db.execute("SELECT review_id FROM scale_labels")}
    attempted = {text for text, in db.execute("""SELECT DISTINCT r.review_text
        FROM scale_rows r JOIN scale_members m USING(review_id)
        JOIN scale_requests q USING(request_key) WHERE q.stage=?""", (stage,))}
    selected, seen = [], set()
    for pos, rid, text, source_sha, blocked in db.execute(
            "SELECT position,review_id,review_text,source_sha,blocked_reason FROM scale_rows ORDER BY position"):
        if blocked or rid in settled or text in seen or text in attempted or \
                stage == "evidence" and rid not in labelled:
            continue
        row = {"source_position": pos, "review_id": rid,
            "review_text": text, "source_sha256": source_sha,
            "text_sha256": db.execute("SELECT text_sha FROM scale_rows WHERE review_id=?",
                (rid,)).fetchone()[0]}
        if stage == "evidence":
            row["labels"] = json.loads(db.execute(
                "SELECT label_json FROM scale_labels WHERE review_id=?", (rid,)).fetchone()[0])
        selected.append(row)
        seen.add(text)
    return selected


def aliases(db, stage, row, value, config_sha):
    table = "scale_labels" if stage == "jev" else "scale_evidence"
    for rid, blocked in db.execute("SELECT review_id,blocked_reason FROM scale_rows WHERE text_sha=? "
            "AND review_text=?", (row["text_sha256"], row["review_text"])):
        if blocked or db.execute("SELECT 1 FROM " + table + " WHERE review_id=?", (rid,)).fetchone():
            continue
        if stage == "jev":
            db.execute("INSERT INTO scale_labels VALUES (?,?,?,?,?,NULL)",
                (rid, value, config_sha, "scale_exact_text_cache", row["review_id"]))
        else:
            db.execute("INSERT INTO scale_evidence VALUES (?,?,?,?,?,?,NULL)",
                (rid, canonical(value["entities"]), value["evidence_quote"], config_sha,
                 "scale_exact_text_cache", row["review_id"]))


def assert_resume_safe(db):
    if db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError("shared project has an active reservation; no duplicate runner")
    for key, stage, cfg, status, reserved, charged, members in db.execute("""SELECT
            q.request_key,q.stage,q.config_sha,r.status,r.reserved_nusd,r.charged_nusd,
            (SELECT COUNT(*) FROM scale_members m WHERE m.request_key=q.request_key)
            FROM scale_requests q JOIN reservations r USING(request_key)
            WHERE q.status='uncertain'"""):
        is_trial = stage == "evidence" and cfg == trial25.config_sha()
        expected = RESERVATION_NANODOLLARS if stage == "jev" else \
            trial25.reservation_nusd() if is_trial else evidence.reservation_nusd()
        table = "scale_labels" if stage == "jev" else "scale_evidence"
        if stage not in ("jev", "evidence") or status != "uncertain" or \
                reserved != expected or charged is not None or \
                not 1 <= members <= (1 if stage == "jev" else
                    trial25.BATCH_SIZE if is_trial else evidence.BATCH_SIZE) or \
                db.execute("SELECT 1 FROM scale_members m JOIN " + table +
                    " x USING(review_id) WHERE m.request_key=? LIMIT 1", (key,)).fetchone() or \
                db.execute("SELECT 1 FROM scale_members m JOIN scale_quarantines x "
                    "USING(review_id) WHERE m.request_key=? LIMIT 1", (key,)).fetchone():
            raise ValueError("uncertain request hold or membership differs")


def _call(stage, body, api_key):
    started = time.monotonic()
    try:
        if stage == "jev":
            response = jev.post_systemone(body, api_key)
        else:
            response = benchmark.request_json("https://openrouter.ai/api/v1/chat/completions",
                body, api_key)
        return response, time.monotonic() - started, None
    except Exception as exc:
        code = getattr(exc, "code", getattr(exc, "status", ""))
        return None, time.monotonic() - started, type(exc).__name__ + ":" + str(code)


def _finish(budget, stage, key, rows, response, elapsed, error, trial=False):
    db = budget.db
    raw = canonical(response) if response is not None else None
    try:
        if response is None:
            raise ValueError(error or "request delivery unknown")
        if stage == "jev":
            parsed = jev.parse_response(response)
            inp, out, reasoning = parsed.input_tokens, parsed.output_tokens, None
            if inp > 64000 or inp * NANODOLLARS_PER_INPUT_TOKEN > RESERVATION_NANODOLLARS:
                raise ValueError("Jev usage exceeds reservation")
            charge = inp * NANODOLLARS_PER_INPUT_TOKEN
            accepted, invalid = {rows[0]["review_id"]: parsed.__dict__}, {}
        else:
            handler = trial25 if trial else evidence
            inp, out, reasoning, charge = handler.measured_usage(response)
            try:
                accepted, invalid = trial25.inspect(response, rows) if trial else \
                    previous.inspect_evidence(response, rows)
            except Exception as exc:
                accepted, invalid = {}, {r["review_id"]: type(exc).__name__ + ": " + str(exc) for r in rows}
    except Exception as exc:
        def record(conn):
            conn.execute("UPDATE scale_requests SET status='uncertain',response_json=?,elapsed_seconds=?,error_class=? WHERE request_key=?",
                (raw, elapsed, error or type(exc).__name__ + ": " + str(exc), key))
        budget.uncertain(key, record)
        return "uncertain", 0
    status = "succeeded" if accepted and not invalid else "quarantined_metered" if not accepted else "partial_succeeded"
    cfg = config_hash(jev.label_config()) if stage == "jev" else \
        trial25.config_sha() if trial else previous.evidence_config(rows)
    def record(conn):
        conn.execute("""UPDATE scale_requests SET status=?,response_json=?,elapsed_seconds=?,
            input_tokens=?,output_tokens=?,reasoning_tokens=?,charged_nusd=? WHERE request_key=?""",
            (status, raw, elapsed, inp, out, reasoning, charge, key))
        for row in rows:
            rid = row["review_id"]
            if rid in accepted:
                if stage == "jev":
                    value = canonical(accepted[rid])
                    conn.execute("INSERT INTO scale_labels VALUES (?,?,?,?,?,?)",
                        (rid, value, cfg, "jev_direct", None, key))
                    aliases(conn, stage, row, value, cfg)
                else:
                    value = accepted[rid]
                    conn.execute("INSERT INTO scale_evidence VALUES (?,?,?,?,?,?,?)",
                        (rid, canonical(value["entities"]), value["evidence_quote"],
                         cfg, "deepinfra_direct", None, key))
                    aliases(conn, stage, row, value, cfg)
            else:
                conn.execute("INSERT INTO scale_quarantines VALUES (?,?,?)",
                    (rid, invalid[rid], key))
    budget.settle(key, "quarantined_metered" if status == "quarantined_metered" else "succeeded", charge, record)
    return status, charge


def status(db, budget):
    labelled = {rid for rid, in db.execute("SELECT review_id FROM scale_labels")}
    accepted = {rid for rid, in db.execute("SELECT review_id FROM scale_evidence")}
    quarantined = {rid for rid, in db.execute("SELECT review_id FROM scale_quarantines")}
    attempts = {}
    direct_uncertain = set()
    for stage, state, rid, text in db.execute("""SELECT q.stage,q.status,r.review_id,r.review_text
            FROM scale_requests q JOIN scale_members m USING(request_key)
            JOIN scale_rows r USING(review_id)"""):
        attempts[(stage, text)] = state
        if state == "uncertain":
            direct_uncertain.add(rid)
    states = Counter()
    for rid, text, blocked in db.execute("SELECT review_id,review_text,blocked_reason FROM scale_rows"):
        if rid in accepted:
            state = "accepted"
        elif rid in quarantined:
            state = "quarantined"
        elif blocked:
            state = blocked
        elif rid in direct_uncertain:
            state = "uncertain_direct"
        elif any(attempts.get((stage, text)) == "uncertain" for stage in ("jev", "evidence")):
            state = "uncertain_exact_text_alias"
        elif any(attempts.get((stage, text)) == "reserved" for stage in ("jev", "evidence")):
            state = "in_flight"
        elif ("evidence", text) in attempts or rid not in labelled and ("jev", text) in attempts:
            state = "attempted_exact_text_alias"
        else:
            state = "eligible_or_awaiting_label"
        states[state] += 1
    out = {"activated_source_rows": db.execute("SELECT COUNT(*) FROM scale_rows").fetchone()[0],
        "labels": db.execute("SELECT COUNT(*) FROM scale_labels").fetchone()[0],
        "evidence": db.execute("SELECT COUNT(*) FROM scale_evidence").fetchone()[0],
        "quarantined": db.execute("SELECT COUNT(*) FROM scale_quarantines").fetchone()[0],
        "blocked": db.execute("SELECT COUNT(*) FROM scale_rows WHERE blocked_reason IS NOT NULL").fetchone()[0],
        "requests": dict(db.execute("SELECT stage||':'||status,COUNT(*) FROM scale_requests GROUP BY stage,status")),
        "charges_nusd": dict(db.execute("SELECT stage,COALESCE(SUM(charged_nusd),0) FROM scale_requests GROUP BY stage")),
        "exposure_nusd": {name: budget.exposure(name) for name in ("jev", "openrouter")},
        "source_states": dict(states)}
    return out


def initial_worker_limit(db, stage):
    prior_overload = db.execute("""SELECT COUNT(*) FROM scale_requests
        WHERE stage=? AND status='uncertain' AND (error_class LIKE '%:429'
        OR error_class LIKE '%:529' OR error_class LIKE '%:503')""", (stage,)).fetchone()[0]
    return max(1, WORKERS // 2) if prior_overload else WORKERS


def safe_worker_ceiling(db, stage):
    """Keep Jev at four after observed provider overload; evidence may use eight."""
    jev_overload = db.execute("""SELECT COUNT(*) FROM scale_requests
        WHERE stage='jev' AND status='uncertain' AND error_class LIKE '%:529'""").fetchone()[0]
    return max(1, WORKERS // 2) if stage == "jev" and jev_overload >= 2 else WORKERS


def run_stage(budget, manifest_sha, stage, api_key, trial=False):
    db = budget.db
    assert_resume_safe(db)
    if trial and stage != "evidence":
        raise ValueError("25-review trial applies only to evidence")
    if stage == "jev":
        verify_jev_price()
        jev.check_model_access(api_key)
        reservation = RESERVATION_NANODOLLARS
    else:
        benchmark.verify_route("deepinfra")
        reservation = trial25.reservation_nusd() if trial else evidence.reservation_nusd()
        canary.verify_project_key(api_key, reservation)
    work = pending(db, stage)
    if trial:
        if len(work) < 100:
            raise ValueError("25-review trial requires 100 untouched labeled texts")
        work = work[:100]
    # Each slot owns successive 500-source chunks. Main thread alone reserves,
    # saves, and settles each ten-review request before that slot continues.
    chunk_size = trial25.BATCH_SIZE if trial else CHUNK_ROWS
    chunks = deque(deque(work[i:i + chunk_size]) for i in range(0, len(work), chunk_size))
    slots = {i: deque() for i in range(WORKERS)}
    active = {}
    limit, rate_errors, new_uncertain, invalid_streak = \
        initial_worker_limit(db, stage), 0, 0, 0
    ceiling = safe_worker_ceiling(db, stage)
    limit = min(limit, ceiling)
    stable_successes = 0
    stop, halt = False, None
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        while active or (chunks or any(slots.values())) and not stop:
            for slot in range(limit, WORKERS):
                if slots[slot] and not any(value[0] == slot for value in active.values()):
                    chunks.appendleft(slots[slot])
                    slots[slot] = deque()
            for slot in range(limit):
                if stop or any(value[0] == slot for value in active.values()):
                    continue
                if not slots[slot] and chunks:
                    slots[slot] = chunks.popleft()
                if not slots[slot]:
                    continue
                batch = 1 if stage == "jev" else trial25.BATCH_SIZE if trial else evidence.BATCH_SIZE
                if stage == "evidence" and len(slots[slot]) < batch and chunks:
                    slots[slot].extend(chunks.popleft())
                rows = [slots[slot].popleft() for _ in range(min(batch, len(slots[slot])))]
                body = jev.build_request(rows[0]["review_text"]) if stage == "jev" else \
                    trial25.payload(rows) if trial else previous.evidence_payload(rows)
                cfg = config_hash(jev.label_config()) if stage == "jev" else \
                    trial25.config_sha() if trial else previous.evidence_config(rows)
                key = "scale100k-" + evidence.digest({"manifest": manifest_sha,
                    "stage": stage, "ids": [r["review_id"] for r in rows], "config": cfg})
                def record(conn):
                    conn.execute("INSERT INTO scale_requests(request_key,stage,status,config_sha,request_sha) VALUES (?,?,'reserved',?,?)",
                        (key, stage, cfg, evidence.digest(body)))
                    conn.executemany("INSERT INTO scale_members VALUES (?,?)",
                        ((key, row["review_id"]) for row in rows))
                try:
                    budget.reserve(key, "jev" if stage == "jev" else "openrouter", reservation, record)
                except Exception as exc:
                    stop, halt = True, type(exc).__name__ + ": " + str(exc)
                    slots[slot].extendleft(reversed(rows))
                    break
                future = pool.submit(_call, stage, body, api_key)
                active[future] = (slot, key, rows)
            if not active:
                break
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                slot, key, rows = active.pop(future)
                response, elapsed, error = future.result()
                state, charge = _finish(budget, stage, key, rows, response, elapsed, error, trial)
                print(canonical({"stage": stage, "status": state, "rows": len(rows),
                    "charge_nusd": charge, "elapsed_seconds": round(elapsed, 3),
                    "worker_slot": slot}), flush=True)
                if error and (":401" in error or ":403" in error):
                    stop, halt = True, "authentication or access failure"
                elif error and any(marker in error for marker in
                        (":429", ":500", ":502", ":503", ":504", ":529",
                         "Timeout", "URLError", "ConnectionResetError")):
                    if ":429" in error:
                        rate_errors += 1
                    new_uncertain += 1
                    stable_successes = 0
                    limit = max(1, limit // 2)
                    if new_uncertain >= 2:
                        stop, halt = True, "repeated transient failures; held both requests"
                    else:
                        time.sleep(min(30, 2 ** min(new_uncertain, 4)))
                elif state == "uncertain":
                    new_uncertain += 1
                    stable_successes = 0
                    if new_uncertain >= 2:
                        stop, halt = True, "two new uncertain requests"
                elif state == "succeeded":
                    stable_successes += 1
                    if stable_successes >= 500 and limit < ceiling:
                        limit += 1
                        stable_successes = 0
                invalid_streak = invalid_streak + 1 if state not in ("succeeded", "uncertain") else 0
                if state == "quarantined_metered" or invalid_streak >= (3 if stage == "jev" else 5):
                    stop, halt = True, "structural quality gate"
    out = status(db, budget)
    out.update({"stage": stage, "batch_size": trial25.BATCH_SIZE if trial else
        1 if stage == "jev" else evidence.BATCH_SIZE,
        "paused": stop, "halt_reason": halt,
        "new_uncertain": new_uncertain, "rate_errors": rate_errors,
        "final_worker_limit": limit, "eligible_unique": len(pending(db, stage))})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--activate-next-gate", action="store_true")
    mode.add_argument("--run-jev", action="store_true")
    mode.add_argument("--run-evidence", action="store_true")
    mode.add_argument("--run25-trial", action="store_true")
    mode.add_argument("--status", action="store_true")
    args = parser.parse_args()
    manifest, manifest_sha = load()
    if args.run_jev or args.run_evidence or args.run25_trial or args.activate_next_gate:
        LOCK.touch(mode=0o600, exist_ok=True)
        with LOCK.open("r+") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("another scale paid runner owns the process lease") from exc
            _main_locked(args, manifest, manifest_sha)
    else:
        _main_locked(args, manifest, manifest_sha)


def _main_locked(args, manifest, manifest_sha):
    with ProjectBudget(BUDGET, legacy_paths()) as budget:
        ensure_tables(budget.db, manifest_sha)
        if args.activate_next_gate:
            activated = activate_gate(budget.db, manifest)
            materialize_caches(budget.db, manifest["historical_uncertain_exact_texts"])
            result = status(budget.db, budget)
            result["activated_now"] = activated
        elif args.run_jev or args.run_evidence or args.run25_trial:
            materialize_caches(budget.db, manifest["historical_uncertain_exact_texts"])
            stage = "jev" if args.run_jev else "evidence"
            api_key = canary.keychain_secret(timeout_seconds=90,
                service=JEV_SERVICE, account=JEV_ACCOUNT) if stage == "jev" else \
                canary.keychain_secret(timeout_seconds=90)
            try:
                result = run_stage(budget, manifest_sha, stage, api_key,
                    trial=args.run25_trial)
            finally:
                api_key = None
        else:
            result = status(budget.db, budget)
            result["jev_eligible_unique"] = len(pending(budget.db, "jev"))
            result["evidence_eligible_unique"] = len(pending(budget.db, "evidence"))
        print(canonical(result), flush=True)


if __name__ == "__main__":
    main()

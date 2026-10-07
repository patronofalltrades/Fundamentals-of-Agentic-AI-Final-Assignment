"""Complete frozen-v2 checkpoint evidence with ChatGPT-auth Codex and exact cache."""

import argparse
import collections
import json
import math
import os
import sqlite3
import time
from decimal import Decimal

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.jev_pilot import PilotLedger
from tools.checkpoint_500 import CHECKPOINT_CAP_NUSD, inspect_seed, inspect_target, source_rows
from tools.finish_jev_v2_evidence import _execute_one, ensure_metrics_schema, status
from tools.jev_pilot import local_db_path


def check_complete(ledger, rows):
    """Validate saved exact spans, call/cache provenance, and source coverage."""
    expected = {row["review_id"]: row for row in rows}
    results = {row["review_id"]: row for row in ledger.conn.execute("SELECT * FROM results")}
    evidence = {row["review_id"]: row for row in ledger.conn.execute("SELECT * FROM evidence")}
    origins = {row["review_id"]: row for row in ledger.conn.execute("SELECT * FROM evidence_origin")}
    if len(results) != 500 or evidence.keys() != expected.keys() or origins.keys() != expected.keys():
        raise ValueError("checkpoint evidence/source coverage differs")
    provenance = collections.Counter()
    for review_id, item in evidence.items():
        checked = validate_evidence(expected[review_id]["review_text"], {
            "entities": json.loads(item["entities_json"]),
            "evidence_quote": item["evidence_quote"]})
        origin = origins[review_id]
        provenance[origin["origin"]] += 1
        cache_source = item["cache_source_id"]
        if cache_source is not None:
            first = evidence.get(cache_source)
            if (results[review_id]["cache_source_id"] != cache_source or first is None or
                    first["cache_source_id"] is not None or
                    results[review_id]["review_text"] != results[cache_source]["review_text"] or
                    item["entities_json"] != first["entities_json"] or
                    item["evidence_quote"] != first["evidence_quote"] or
                    item["model"] != first["model"] or
                    item["prompt_version"] != first["prompt_version"] or
                    origin["origin"] != "checkpoint_exact_text_cache"):
                raise ValueError("checkpoint evidence cache provenance differs")
        elif results[review_id]["cache_source_id"] is not None:
            raise ValueError("cached label lacks cached evidence")
        if not checked["evidence_quote"]:
            raise ValueError("blank exact evidence")
    attempts = list(ledger.conn.execute("SELECT * FROM evidence_attempts"))
    succeeded = [row for row in attempts if row["status"] == "succeeded"]
    preflight = [row for row in attempts if row["status"] == "preflight_blocked"]
    interrupted = [row for row in attempts if row["status"] == "interrupted_uncertain"]
    if (len(succeeded) != 76 + 379 or len(preflight) > 1 or len(interrupted) > 1 or
            len(attempts) != len(succeeded) + len(preflight) + len(interrupted) or
            any(row["status"] != "succeeded" or
            row["error_class"] is not None or row["elapsed_seconds"] is None or
            not math.isfinite(row["elapsed_seconds"]) or row["elapsed_seconds"] < 0
            for row in succeeded)):
        raise ValueError("new Codex attempt coverage differs")
    calls_by_review = collections.Counter(row["review_id"] for row in succeeded)
    if (any(calls_by_review[review_id] != (1 if origins[review_id]["origin"] ==
            "codex_new_v2" else 0) for review_id in expected) or
            sum(calls_by_review.values()) != len(succeeded)):
        raise ValueError("direct Codex call-to-evidence provenance differs")
    if interrupted:
        linked = ledger.conn.execute("SELECT retry_attempt_id FROM checkpoint_evidence_retries "
                                     "WHERE prior_attempt_id=?", (interrupted[0]["id"],)).fetchone()
        if (linked is None or not any(row["id"] == linked[0] and
                row["review_id"] == interrupted[0]["review_id"] for row in succeeded)):
            raise ValueError("unknown-delivery retry provenance differs")
    return {"source_rows_validated": len(rows), "exact_evidence_validated": len(evidence),
            "evidence_origins": dict(sorted(provenance.items())),
            "new_successful_codex_attempts": len(succeeded) - 76,
            "local_preflight_blocked_attempts": len(preflight),
            "interrupted_unknown_delivery_attempts": len(interrupted)}


def reconcile_local_preflight(ledger):
    """Preserve one documented sandbox startup failure without claiming a call."""
    failed = list(ledger.conn.execute(
        "SELECT id,review_id,elapsed_seconds,error_class FROM evidence_attempts "
        "WHERE status='failed'"))
    stages = list(ledger.conn.execute(
        "SELECT status,new_calls,cache_reuses,elapsed_seconds FROM checkpoint_evidence_runs"))
    if (len(failed) != 1 or failed[0]["error_class"] != "ValidationError" or
            failed[0]["elapsed_seconds"] is None or failed[0]["elapsed_seconds"] >= 1 or
            len(stages) != 1 or stages[0]["status"] != "failed" or
            stages[0]["new_calls"] != 0 or stages[0]["cache_reuses"] != 0 or
            stages[0]["elapsed_seconds"] >= 1 or
            ledger.get_evidence(failed[0]["review_id"]) is not None):
        raise ValueError("failed attempt is not the diagnosed local preflight failure")
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        ledger.conn.execute("CREATE TABLE IF NOT EXISTS checkpoint_evidence_recovery ("
                            "attempt_id INTEGER PRIMARY KEY,reason TEXT NOT NULL)")
        ledger.conn.execute("INSERT INTO checkpoint_evidence_recovery VALUES (?,?)", (
            failed[0]["id"], "Codex local state database was read-only; app server did not initialize"))
        ledger.conn.execute("UPDATE evidence_attempts SET status='preflight_blocked' WHERE id=?",
                            (failed[0]["id"],))
        ledger.conn.commit()
    except Exception:
        ledger.conn.rollback()
        raise
    return {"status": "local_preflight_reconciled", "blocked_attempts": 1,
            "provider_delivery": "not_started_in_reproduced_sandbox_diagnostic"}


def reconcile_interruption(ledger):
    """Preserve one orphaned attempt after a separate read-only process check."""
    started = list(ledger.conn.execute(
        "SELECT id,review_id FROM evidence_attempts WHERE status='started'"))
    stages = list(ledger.conn.execute(
        "SELECT id FROM checkpoint_evidence_runs WHERE status='started'"))
    if len(started) != 1 or len(stages) != 1 or ledger.get_evidence(started[0]["review_id"]):
        raise ValueError("interruption state differs; do not reconcile")
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        ledger.conn.execute("CREATE TABLE IF NOT EXISTS checkpoint_evidence_recovery ("
                            "attempt_id INTEGER PRIMARY KEY,reason TEXT NOT NULL)")
        ledger.conn.execute("INSERT INTO checkpoint_evidence_recovery VALUES (?,?)", (
            started[0]["id"], "Runner process lost during connection interruption; delivery unknown"))
        ledger.conn.execute("UPDATE evidence_attempts SET status='interrupted_uncertain',"
                            "error_class='ProcessLost' WHERE id=?", (started[0]["id"],))
        ledger.conn.execute("UPDATE checkpoint_evidence_runs SET status='interrupted',"
                            "new_calls=NULL,cache_reuses=NULL,error_class='ProcessLost' WHERE id=?",
                            (stages[0]["id"],))
        ledger.conn.commit()
    except Exception:
        ledger.conn.rollback()
        raise
    return {"status": "interruption_recorded", "unknown_delivery_attempts": 1,
            "next_action": "continue other reviews; do not repeat the uncertain review"}


def retry_interrupted(ledger):
    """Explicitly retry the one unknown-delivery review, retaining both attempts."""
    uncertain = list(ledger.conn.execute(
        "SELECT id,review_id FROM evidence_attempts WHERE status='interrupted_uncertain'"))
    if len(uncertain) != 1 or ledger.get_evidence(uncertain[0]["review_id"]) is not None:
        raise ValueError("exactly one unresolved interrupted review is required")
    if (ledger.conn.execute("SELECT 1 FROM evidence_attempts WHERE status IN ('started','failed')").fetchone()
            or ledger.conn.execute("SELECT 1 FROM checkpoint_evidence_runs WHERE status='started'").fetchone()):
        raise ValueError("another evidence attempt or stage is unresolved")
    item = ledger.conn.execute("SELECT review_id,review_text,label_json,cache_source_id "
                               "FROM results WHERE review_id=?", (uncertain[0]["review_id"],)).fetchone()
    if item is None or item["cache_source_id"] is not None:
        raise ValueError("interrupted review is not a direct label result")
    started = time.monotonic()
    run_id = ledger.conn.execute("INSERT INTO checkpoint_evidence_runs ("
                                 "status,new_calls,cache_reuses) VALUES ('started',0,0)").lastrowid
    ledger.conn.commit()
    try:
        _execute_one(ledger, item)
    except Exception as error:
        ledger.conn.execute("UPDATE checkpoint_evidence_runs SET status='failed',"
                            "elapsed_seconds=?,error_class=? WHERE id=?", (
                                time.monotonic() - started, type(error).__name__, run_id))
        ledger.conn.commit()
        raise
    new_id = ledger.conn.execute("SELECT MAX(id) FROM evidence_attempts").fetchone()[0]
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        ledger.conn.execute("CREATE TABLE IF NOT EXISTS checkpoint_evidence_retries ("
                            "prior_attempt_id INTEGER PRIMARY KEY,retry_attempt_id INTEGER UNIQUE NOT NULL,"
                            "reason TEXT NOT NULL)")
        ledger.conn.execute("INSERT INTO checkpoint_evidence_retries VALUES (?,?,?)", (
            uncertain[0]["id"], new_id, "Unknown delivery after connection loss; explicit final retry"))
        ledger.conn.execute("UPDATE checkpoint_evidence_runs SET status='succeeded',"
                            "elapsed_seconds=?,new_calls=1 WHERE id=?", (
                                time.monotonic() - started, run_id))
        ledger.conn.commit()
    except Exception:
        ledger.conn.rollback()
        raise
    return {"status": "interrupted_review_retried", "new_successful_calls": 1,
            "prior_unknown_delivery_attempts_retained": 1,
            "evidence_stage_wall_seconds": time.monotonic() - started}


def copy_exact_evidence(ledger, item):
    review_id, cache_source = item["review_id"], item["cache_source_id"]
    if cache_source is None:
        raise ValueError("only exact-text cache results may reuse evidence")
    first = ledger.get_evidence(cache_source)
    labels = ledger.conn.execute("SELECT review_text,label_json,cache_source_id FROM results "
                                 "WHERE review_id=?", (cache_source,)).fetchone()
    current = json.loads(item["label_json"])
    original = json.loads(labels["label_json"]) if labels is not None else None
    if (first is None or labels is None or labels["cache_source_id"] is not None or
            labels["review_text"] != item["review_text"] or
            any(current[key] != original[key] for key in
                ("topic", "intent", "severity", "sentiment"))):
        raise ValueError("cached evidence source or label identity differs")
    checked = validate_evidence(item["review_text"], {
        "entities": json.loads(first["entities_json"]),
        "evidence_quote": first["evidence_quote"]})
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
            review_id, json.dumps(checked["entities"]), checked["evidence_quote"],
            first["model"], first["prompt_version"], 0.0, cache_source))
        ledger.conn.execute("INSERT INTO evidence_origin VALUES (?,?,?,?,?)", (
            review_id, "checkpoint_exact_text_cache", first["model"],
            first["prompt_version"], first["elapsed_seconds"]))
        ledger.conn.commit()
    except Exception:
        ledger.conn.rollback()
        raise


def execute(ledger, max_new_calls):
    if type(max_new_calls) is not int or not 1 <= max_new_calls <= 379:
        raise ValueError("max-new-calls must be 1..379")
    ensure_metrics_schema(ledger.conn)
    ledger.conn.execute("CREATE TABLE IF NOT EXISTS checkpoint_evidence_runs ("
                        "id INTEGER PRIMARY KEY,status TEXT NOT NULL,elapsed_seconds REAL,"
                        "new_calls INTEGER,cache_reuses INTEGER,error_class TEXT)")
    ledger.conn.commit()
    if (ledger.conn.execute("SELECT 1 FROM evidence_attempts WHERE status IN ('started','failed')").fetchone()
            or ledger.conn.execute("SELECT 1 FROM checkpoint_evidence_runs WHERE status='started'").fetchone()):
        raise ValueError("incomplete evidence attempt or stage needs manual review before resume")
    pending = list(ledger.missing_evidence())
    if not pending:
        return {"status": "already_complete", **status(ledger)}
    started = time.monotonic()
    run_id = ledger.conn.execute(
        "INSERT INTO checkpoint_evidence_runs(status,new_calls,cache_reuses) "
        "VALUES ('started',0,0)").lastrowid
    ledger.conn.commit()
    new_calls = cache_reuses = 0
    deferred = {row["review_id"] for row in ledger.conn.execute(
        "SELECT review_id FROM evidence_attempts WHERE status='interrupted_uncertain'")}
    try:
        for item in pending:
            if item["review_id"] in deferred:
                continue
            if item["cache_source_id"] is not None:
                if ledger.get_evidence(item["cache_source_id"]) is None:
                    continue
                copy_exact_evidence(ledger, item)
                cache_reuses += 1
            else:
                if new_calls >= max_new_calls:
                    break
                _execute_one(ledger, item)
                new_calls += 1
    except Exception as error:
        ledger.conn.execute("UPDATE checkpoint_evidence_runs SET status='failed',elapsed_seconds=?,"
                            "new_calls=?,cache_reuses=?,error_class=? WHERE id=?", (
                                time.monotonic() - started, new_calls, cache_reuses,
                                type(error).__name__, run_id))
        ledger.conn.commit()
        raise
    elapsed = time.monotonic() - started
    ledger.conn.execute("UPDATE checkpoint_evidence_runs SET status='succeeded',elapsed_seconds=?,"
                        "new_calls=?,cache_reuses=? WHERE id=?", (
                            elapsed, new_calls, cache_reuses, run_id))
    ledger.conn.commit()
    return {"status": "evidence_recorded", "new_calls_this_invocation": new_calls,
            "cache_reuses_this_invocation": cache_reuses,
            "deferred_unknown_delivery_reviews": len(deferred),
            "evidence_stage_wall_seconds": elapsed, **status(ledger)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--seed-db", default="local/jev_pilot_v2_evidence.db")
    parser.add_argument("--db", default="local/jev_checkpoint500_v2.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--reconcile-local-preflight", action="store_true")
    mode.add_argument("--reconcile-interruption", action="store_true")
    mode.add_argument("--retry-interrupted", action="store_true")
    parser.add_argument("--max-new-calls", type=int)
    args = parser.parse_args()
    seed_path, target_path = local_db_path(args.seed_db), local_db_path(args.db)
    rows, source_sha = source_rows(args.input, args.manifest)
    seed_meta, _ = inspect_seed(seed_path, rows)
    if not os.path.isfile(target_path):
        parser.error("prepared checkpoint ledger is missing")
    with PilotLedger(target_path, source_sha,
                     Decimal(CHECKPOINT_CAP_NUSD) / Decimal(10**9)) as ledger:
        inspect_target(ledger, rows, source_sha, seed_meta["source_sha256"])
        if len(list(ledger.conn.execute("SELECT review_id FROM results"))) != 500:
            parser.error("500 Jev labels must be complete before evidence extraction")
        if args.status:
            report = status(ledger)
            if report["missing_evidence"] == 0:
                report["validation"] = check_complete(ledger, rows)
        elif args.reconcile_local_preflight:
            report = reconcile_local_preflight(ledger)
        elif args.reconcile_interruption:
            report = reconcile_interruption(ledger)
        elif args.retry_interrupted:
            report = retry_interrupted(ledger)
            report["progress"] = status(ledger)
            if report["progress"]["missing_evidence"] == 0:
                report["validation"] = check_complete(ledger, rows)
        else:
            if args.max_new_calls is None:
                parser.error("execution requires --max-new-calls")
            report = execute(ledger, args.max_new_calls)
            if report["missing_evidence"] == 0:
                report["validation"] = check_complete(ledger, rows)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""Prepare and finish v2 evidence in a separate, ignored ledger copy."""

import argparse
import collections
import json
import math
import os
import sqlite3
import time
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.codex_evidence import extract_with_codex, validate_evidence
from spotify_pipeline.codex_evidence import MODEL as EVIDENCE_MODEL
from spotify_pipeline.codex_evidence import PROMPT_VERSION as EVIDENCE_PROMPT
from spotify_pipeline.db import Database
from spotify_pipeline.jev_pilot import PilotLedger
from tools.compare_jev_pilots import V1_CONFIG_HASH, V2_CONFIG_HASH, load_ledger, sample_rows
from tools.jev_pilot import local_db_path
from tools.plan_jev_pilot import plan

PROVENANCE_SCHEMA = """
CREATE TABLE evidence_origin (
  review_id TEXT PRIMARY KEY, origin TEXT NOT NULL, prior_model TEXT,
  prior_prompt_version TEXT, prior_elapsed_seconds REAL,
  FOREIGN KEY(review_id) REFERENCES evidence(review_id)
);
CREATE TABLE evidence_attempts (
  id INTEGER PRIMARY KEY, review_id TEXT NOT NULL, status TEXT NOT NULL,
  elapsed_seconds REAL, error_class TEXT
);
"""


def read_only(path):
    db = sqlite3.connect("file:%s?mode=ro" % Path(path).resolve(), uri=True)
    db.row_factory = sqlite3.Row
    return db


def prepare(v1_path, v2_path, target_path, source_path, manifest_path):
    source_hash = plan(source_path, manifest_path)["source_sha256"]
    source = sample_rows(source_path)
    v1 = load_ledger(v1_path, source_hash, V1_CONFIG_HASH, source)
    v2 = load_ledger(v2_path, source_hash, V2_CONFIG_HASH, source)
    if os.path.exists(target_path):
        raise ValueError("v2 evidence ledger already exists; inspect status, do not replace it")
    temporary = target_path + ".db-tmp"
    if os.path.exists(temporary):
        raise ValueError("temporary evidence ledger exists; inspect it before retrying")
    with closing(read_only(v2_path)) as source_db, closing(sqlite3.connect(temporary)) as target_db:
        source_db.backup(target_db)
    os.replace(temporary, target_path)
    cap = Decimal(v2["meta"]["cap_nusd"]) / Decimal(10**9)
    compatible = []
    for review_id in v1["labels"]:
        if all(v1["labels"][review_id][field] == v2["labels"][review_id][field]
               for field in ("topic", "intent", "severity", "sentiment")):
            compatible.append(review_id)
    with closing(read_only(v1_path)) as source_db, PilotLedger(target_path, source_hash, cap) as ledger:
        ledger.conn.executescript(PROVENANCE_SCHEMA)
        ledger.conn.execute("BEGIN IMMEDIATE")
        try:
            for review_id in compatible:
                evidence = source_db.execute("SELECT * FROM evidence WHERE review_id=?", (review_id,)).fetchone()
                text = source[review_id][0]
                checked = validate_evidence(text, {"entities": json.loads(evidence["entities_json"]),
                                                   "evidence_quote": evidence["evidence_quote"]})
                ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
                    review_id, json.dumps(checked["entities"]), checked["evidence_quote"],
                    evidence["model"], evidence["prompt_version"], 0.0, None))
                ledger.conn.execute("INSERT INTO evidence_origin VALUES (?,?,?,?,?)", (
                    review_id, "reused_v1_exact_four_labels", evidence["model"],
                    evidence["prompt_version"], evidence["elapsed_seconds"]))
            ledger.conn.commit()
        except Exception:
            ledger.conn.rollback()
            raise
    return {"source_rows": len(source), "reused_v1": len(compatible),
            "remaining_for_evidence_decision": len(source) - len(compatible)}


def status(ledger):
    origins = dict(ledger.conn.execute("SELECT origin,COUNT(*) FROM evidence_origin GROUP BY origin"))
    attempts = dict(ledger.conn.execute("SELECT status,COUNT(*) FROM evidence_attempts GROUP BY status"))
    evidence = ledger.conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    origin_count = ledger.conn.execute("SELECT COUNT(*) FROM evidence_origin").fetchone()[0]
    if evidence != origin_count:
        raise ValueError("evidence provenance is incomplete")
    return {"labels": sum(ledger.summary()["results"].values()),
            "evidence": evidence, "missing_evidence": sum(1 for _ in ledger.missing_evidence()),
            "origins": origins, "evidence_attempts": attempts,
            "summed_success_seconds": round(ledger.conn.execute(
                "SELECT COALESCE(SUM(elapsed_seconds),0) FROM evidence_attempts WHERE status='succeeded'").fetchone()[0], 9)}


def validate_complete(v1_path, v2_path, target_path, source_path, manifest_path):
    """Check all source rows, saved Jev calls, evidence and direct provenance."""
    source_hash = plan(source_path, manifest_path)["source_sha256"]
    source = sample_rows(source_path)
    v1 = load_ledger(v1_path, source_hash, V1_CONFIG_HASH, source)
    original = load_ledger(v2_path, source_hash, V2_CONFIG_HASH, source)
    working = load_ledger(target_path, source_hash, V2_CONFIG_HASH, source)
    if original["labels"] != working["labels"] or len(working["evidence"]) != 100:
        raise ValueError("v2 labels differ or evidence is incomplete")
    with closing(read_only(v1_path)) as v1_db, closing(read_only(v2_path)) as v2_db, closing(read_only(target_path)) as db:
        for table, order in (("meta", "key"), ("attempts", "id"), ("results", "review_id")):
            before = [tuple(row) for row in v2_db.execute("SELECT * FROM %s ORDER BY %s" % (table, order))]
            after = [tuple(row) for row in db.execute("SELECT * FROM %s ORDER BY %s" % (table, order))]
            if before != after:
                raise ValueError("original Jev labels, calls or metadata differ from working copy")
        evidence = {row["review_id"]: row for row in db.execute("SELECT * FROM evidence")}
        origins = {row["review_id"]: row for row in db.execute("SELECT * FROM evidence_origin")}
        attempts = list(db.execute("SELECT * FROM evidence_attempts"))
        if len(origins) != 100 or evidence.keys() != origins.keys() or len(attempts) != 76:
            raise ValueError("evidence origin or attempt coverage differs")
        calls_by_review = collections.Counter(row["review_id"] for row in attempts)
        provenance = collections.Counter()
        prompt_versions = collections.Counter()
        entity_mentions = 0
        for review_id, item in evidence.items():
            origin = origins[review_id]
            provenance[origin["origin"]] += 1
            prompt_versions[item["prompt_version"]] += 1
            entity_mentions += len(json.loads(item["entities_json"]))
            if origin["origin"] == "reused_v1_exact_four_labels":
                prior = v1_db.execute("SELECT * FROM evidence WHERE review_id=?", (review_id,)).fetchone()
                if (prior is None or calls_by_review[review_id] != 0 or
                        any(v1["labels"][review_id][field] != working["labels"][review_id][field]
                            for field in ("topic", "intent", "severity", "sentiment")) or
                        tuple(item[key] for key in ("entities_json", "evidence_quote", "model", "prompt_version")) !=
                        tuple(prior[key] for key in ("entities_json", "evidence_quote", "model", "prompt_version")) or
                        item["elapsed_seconds"] != 0.0 or
                        (origin["prior_model"], origin["prior_prompt_version"], origin["prior_elapsed_seconds"]) !=
                        (prior["model"], prior["prompt_version"], prior["elapsed_seconds"])):
                    raise ValueError("reused evidence provenance differs")
            elif origin["origin"] == "codex_new_v2":
                if (calls_by_review[review_id] != 1 or item["model"] != EVIDENCE_MODEL or
                        item["prompt_version"] != EVIDENCE_PROMPT or
                        any(origin[key] is not None for key in
                            ("prior_model", "prior_prompt_version", "prior_elapsed_seconds"))):
                    raise ValueError("new v2 evidence provenance differs")
            else:
                raise ValueError("unknown evidence origin")
        if any(row["status"] != "succeeded" or not isinstance(row["elapsed_seconds"], float)
               or not math.isfinite(row["elapsed_seconds"]) or row["elapsed_seconds"] < 0
               or row["error_class"] is not None or origins[row["review_id"]]["origin"] != "codex_new_v2"
               for row in attempts):
            raise ValueError("evidence attempts differ from successful new v2 calls")
    return {"source_rows_validated": len(source), "labels_validated": len(working["labels"]),
            "exact_evidence_validated": len(working["evidence"]),
            "original_v2_jev_calls_unchanged": True,
            "evidence_origins": dict(sorted(provenance.items())),
            "evidence_prompt_versions": dict(sorted(prompt_versions.items())),
            "entity_mentions": entity_mentions,
            "new_codex_attempts": len(attempts), "failed_codex_attempts": 0,
            "summed_new_codex_attempt_seconds": round(sum(row["elapsed_seconds"] for row in attempts), 9),
            "codex_token_usage": None, "codex_incremental_cost_usd": None}


def execute(ledger, max_new_calls):
    if type(max_new_calls) is not int or not 1 <= max_new_calls <= 76:
        raise ValueError("max new Codex calls must be 1..76")
    current = status(ledger)
    if current["evidence_attempts"].get("started") or current["evidence_attempts"].get("failed"):
        raise ValueError("prior evidence attempt needs manual review before resume")
    pending = list(ledger.missing_evidence())
    completed = 0
    for item in pending[:max_new_calls]:
        review_id = item["review_id"]
        cursor = ledger.conn.execute(
            "INSERT INTO evidence_attempts(review_id,status) VALUES (?,'started')", (review_id,))
        attempt_id = cursor.lastrowid
        ledger.conn.commit()
        started = time.monotonic()
        try:
            result = extract_with_codex(item["review_text"], json.loads(item["label_json"]))
            checked = validate_evidence(item["review_text"], result["evidence"])
        except Exception as error:
            ledger.conn.execute("UPDATE evidence_attempts SET status='failed',elapsed_seconds=?,"
                                "error_class=? WHERE id=?", (time.monotonic() - started,
                                                             type(error).__name__, attempt_id))
            ledger.conn.commit()
            raise
        elapsed = time.monotonic() - started
        ledger.conn.execute("BEGIN IMMEDIATE")
        try:
            ledger.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)", (
                review_id, json.dumps(checked["entities"]), checked["evidence_quote"],
                result["model"], result["prompt_version"], result["elapsed_seconds"], None))
            ledger.conn.execute("INSERT INTO evidence_origin VALUES (?,?,?,?,?)", (
                review_id, "codex_new_v2", None, None, None))
            ledger.conn.execute("UPDATE evidence_attempts SET status='succeeded',elapsed_seconds=? WHERE id=?",
                                (elapsed, attempt_id))
            ledger.conn.commit()
        except Exception:
            ledger.conn.rollback()
            raise
        completed += 1
    report = status(ledger)
    report["new_calls_this_invocation"] = completed
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--v1-db", required=True)
    parser.add_argument("--v2-db", required=True)
    parser.add_argument("--db", default="local/jev_pilot_v2_evidence.db")
    parser.add_argument("--foundation-db", help="optional separate offline classification database to verify")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true", help="copy labels and strictly compatible evidence")
    group.add_argument("--execute", action="store_true", help="run bounded ChatGPT-auth Codex extraction")
    group.add_argument("--status", action="store_true", help="show aggregate evidence progress without calls")
    parser.add_argument("--max-new-calls", type=int)
    args = parser.parse_args()
    target = local_db_path(args.db)
    if Path(target).resolve() in (Path(args.v1_db).resolve(), Path(args.v2_db).resolve()):
        parser.error("evidence target must differ from both source ledgers")
    if args.prepare:
        print(json.dumps(prepare(args.v1_db, args.v2_db, target, args.input, args.manifest), indent=2))
        return
    if not os.path.isfile(target):
        parser.error("prepared v2 evidence ledger is missing")
    source_hash = plan(args.input, args.manifest)["source_sha256"]
    load_ledger(target, source_hash, V2_CONFIG_HASH, sample_rows(args.input))
    with closing(read_only(target)) as db:
        meta = dict(db.execute("SELECT key,value FROM meta"))
    cap = Decimal(meta["cap_nusd"]) / Decimal(10**9)
    with PilotLedger(target, source_hash, cap) as ledger:
        if args.status:
            report = status(ledger)
            if report["missing_evidence"] == 0:
                report["validation"] = validate_complete(
                    args.v1_db, args.v2_db, target, args.input, args.manifest)
            if args.foundation_db:
                with Database.open_existing(args.foundation_db) as foundation:
                    if foundation.get_meta("file_sha256") != source_hash:
                        raise ValueError("foundation source differs from cost sample")
                    counts = foundation.status_counts(V2_CONFIG_HASH)
                    report["foundation_completed_classifications"] = counts["completed"]
                    report["foundation_pending_classifications"] = counts["pending"]
            report["evidence_stage_wall_seconds"] = None
            report["note"] = ("Summed monotonic attempt durations are measured; end-to-end "
                              "evidence-stage wall time and Codex token usage were not captured.")
            print(json.dumps(report, indent=2))
        else:
            if args.max_new_calls is None:
                parser.error("execution requires --max-new-calls")
            print(json.dumps(execute(ledger, args.max_new_calls), indent=2))


if __name__ == "__main__":
    main()

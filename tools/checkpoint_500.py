"""Frozen-v2 checkpoint preflight and bounded Jev label runner.

Preparing and inspecting are offline. Paid execution requires a separate,
explicit authorization for the 400 new development rows.
"""

import argparse
import csv
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256
from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import check_model_access
from spotify_pipeline.jev import MODEL, label_config
from spotify_pipeline.jev_pilot import PilotLedger, run_reviews
from tools.jev_pilot import local_db_path

V1_CHARGE_NUSD = 3691254
CUMULATIVE_CAP_NUSD = 600000000
CHECKPOINT_CAP_NUSD = CUMULATIVE_CAP_NUSD - V1_CHARGE_NUSD
SEED_ROWS = 100
CHECKPOINT_ROWS = 500


def source_rows(path, manifest_path):
    if Path(path).name != "checkpoint_500.csv":
        raise ValueError("only the supplied checkpoint_500.csv is accepted")
    with open(manifest_path, encoding="utf-8") as stream:
        entry = json.load(stream)["files"]["checkpoint_500.csv"]
    if file_sha256(path) != entry["sha256"] or os.path.getsize(path) != entry["bytes"]:
        raise ValueError("checkpoint differs from supplied manifest")
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("checkpoint fields differ from six-field source contract")
        rows = list(reader)
    if len(rows) != CHECKPOINT_ROWS or len({row["review_id"] for row in rows}) != CHECKPOINT_ROWS:
        raise ValueError("checkpoint must contain 500 distinct source IDs")
    return rows, entry["sha256"]


def inspect_seed(seed_path, rows):
    with closing(sqlite3.connect("file:%s?mode=ro" % Path(seed_path).resolve(), uri=True)) as db:
        db.row_factory = sqlite3.Row
        meta = dict(db.execute("SELECT key,value FROM meta"))
        if int(meta["cap_nusd"]) != CHECKPOINT_CAP_NUSD:
            raise ValueError("seed cap does not preserve the cumulative v1 charge")
        if meta["config_hash"] != config_hash(label_config()) or meta["model"] != MODEL:
            raise ValueError("seed is not the frozen v2 label configuration")
        saved = {row["review_id"]: row for row in db.execute("SELECT * FROM results")}
        if len(saved) != SEED_ROWS or len({row[0] for row in db.execute("SELECT review_id FROM evidence")}) != SEED_ROWS:
            raise ValueError("seed must contain 100 v2 labels and evidence records")
        for row in rows[:SEED_ROWS]:
            item = saved.get(row["review_id"])
            if (item is None or item["review_text"] != row["review_text"] or
                    item["source_sha256"] != row_sha256([row[field] for field in SOURCE_FIELDS])):
                raise ValueError("first 100 checkpoint rows differ from saved v2 pilot")
        if any(row["review_id"] in saved for row in rows[SEED_ROWS:]):
            raise ValueError("new checkpoint IDs overlap seed IDs")
        attempts = list(db.execute("SELECT status,charged_nusd FROM attempts"))
        if len(attempts) != SEED_ROWS or any(item["status"] != "settled" for item in attempts):
            raise ValueError("seed attempts are not 100 settled v2 calls")
        charged = sum(item["charged_nusd"] for item in attempts)
        if charged != 4262454:
            raise ValueError("saved v2 charge differs from measured pilot")
        return meta, charged


def plan(source, manifest, seed):
    rows, checkpoint_sha = source_rows(source, manifest)
    meta, charged = inspect_seed(seed, rows)
    texts = [row["review_text"] for row in rows]
    return {"status": "offline_preflight", "source_file": "checkpoint_500.csv",
            "source_sha256": checkpoint_sha, "prompt_version": "jev-rubric-v2",
            "schema_version": "jev-labels-v1", "config_hash": meta["config_hash"],
            "source_rows": CHECKPOINT_ROWS, "saved_v2_rows": SEED_ROWS,
            "remaining_source_rows": CHECKPOINT_ROWS - SEED_ROWS,
            "new_distinct_texts_at_most": len(set(texts)) - len(set(texts[:SEED_ROWS])),
            "exact_text_cache_candidates": CHECKPOINT_ROWS - len(set(texts)),
            "v1_spent_usd": str(Decimal(V1_CHARGE_NUSD) / Decimal(10**9)),
            "v2_spent_usd": str(Decimal(charged) / Decimal(10**9)),
            "cumulative_spent_usd": str(Decimal(V1_CHARGE_NUSD + charged) / Decimal(10**9)),
            "checkpoint_ledger_cap_usd": str(Decimal(CHECKPOINT_CAP_NUSD) / Decimal(10**9)),
            "new_jev_headroom_usd": str(Decimal(CHECKPOINT_CAP_NUSD - charged) / Decimal(10**9))}


def prepare(source, manifest, seed, target):
    report = plan(source, manifest, seed)
    if os.path.exists(target):
        raise ValueError("checkpoint ledger already exists; inspect it before retrying")
    temporary = target + ".tmp"
    if os.path.exists(temporary):
        raise ValueError("temporary checkpoint ledger already exists")
    with closing(sqlite3.connect("file:%s?mode=ro" % Path(seed).resolve(), uri=True)) as src:
        with closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            dst.execute("UPDATE meta SET value=? WHERE key='source_sha256'",
                        (report["source_sha256"],))
            dst.execute("CREATE TABLE checkpoint_seed (source_sha256 TEXT NOT NULL, "
                        "checkpoint_sha256 TEXT NOT NULL, reused_rows INTEGER NOT NULL, "
                        "v1_charge_nusd INTEGER NOT NULL)")
            dst.execute("INSERT INTO checkpoint_seed VALUES (?,?,?,?)",
                        (dict(src.execute("SELECT key,value FROM meta"))["source_sha256"],
                         report["source_sha256"], SEED_ROWS, V1_CHARGE_NUSD))
            dst.execute("CREATE TABLE checkpoint_runs (id INTEGER PRIMARY KEY, "
                        "status TEXT NOT NULL, elapsed_seconds REAL, "
                        "error_class TEXT, processed_rows INTEGER)")
            dst.commit()
    os.replace(temporary, target)
    report["status"] = "prepared_offline"
    return report


def inspect_target(ledger, rows, checkpoint_sha, seed_sha):
    origin = ledger.conn.execute("SELECT * FROM checkpoint_seed").fetchall()
    if (len(origin) != 1 or tuple(origin[0]) !=
            (seed_sha, checkpoint_sha, SEED_ROWS, V1_CHARGE_NUSD)):
        raise ValueError("checkpoint seed provenance differs")
    expected = {row["review_id"]: row for row in rows}
    for saved in ledger.conn.execute("SELECT review_id,review_text,source_sha256 FROM results"):
        row = expected.get(saved["review_id"])
        if (row is None or row["review_text"] != saved["review_text"] or
                row_sha256([row[field] for field in SOURCE_FIELDS]) != saved["source_sha256"]):
            raise ValueError("saved checkpoint result differs from source")
    if ledger.conn.execute("SELECT 1 FROM checkpoint_runs WHERE status='started'").fetchone():
        raise ValueError("incomplete checkpoint stage needs manual review before resume")


def execute_labels(source, manifest, seed, target, max_new_rows, key):
    if type(max_new_rows) is not int or not 1 <= max_new_rows <= 400:
        raise ValueError("max-new-rows must be 1..400")
    report = plan(source, manifest, seed)
    rows, _ = source_rows(source, manifest)
    seed_meta, _ = inspect_seed(seed, rows)
    with PilotLedger(target, report["source_sha256"],
                     Decimal(CHECKPOINT_CAP_NUSD) / Decimal(10**9)) as ledger:
        inspect_target(ledger, rows, report["source_sha256"], seed_meta["source_sha256"])
        if any(status != "settled" for status, in ledger.conn.execute("SELECT DISTINCT status FROM attempts")):
            raise ValueError("uncertain or reserved Jev attempt needs manual review before resume")
        saved = {row[0] for row in ledger.conn.execute("SELECT review_id FROM results")}
        pending = [row for row in rows[SEED_ROWS:] if row["review_id"] not in saved]
        selected = pending[:max_new_rows]
        if not selected:
            return {"status": "already_complete", "new_rows": 0}
        check_model_access(key)
        stage_start = time.monotonic()
        run_id = ledger.conn.execute("INSERT INTO checkpoint_runs(status) VALUES ('started')").lastrowid
        ledger.conn.commit()
        requests = [{"review_id": row["review_id"], "review_text": row["review_text"],
                     "source_sha256": row_sha256([row[field] for field in SOURCE_FIELDS])}
                    for row in selected]
        try:
            outcome = run_reviews(requests, ledger, key)
        except Exception as error:
            ledger.conn.execute("UPDATE checkpoint_runs SET status='failed',elapsed_seconds=?,"
                                "error_class=? WHERE id=?",
                                (time.monotonic() - stage_start, type(error).__name__, run_id))
            ledger.conn.commit()
            raise
        elapsed = time.monotonic() - stage_start
        ledger.conn.execute("UPDATE checkpoint_runs SET status='succeeded',elapsed_seconds=?,"
                            "processed_rows=? WHERE id=?", (elapsed, outcome["processed_this_run"], run_id))
        ledger.conn.commit()
        return {"status": "labels_recorded", "selected_new_rows": len(selected),
                "label_stage_wall_seconds": elapsed, "ledger": outcome,
                "cumulative_jev_usd": str(Decimal(V1_CHARGE_NUSD) / Decimal(10**9) +
                                          Decimal(ledger.charged_or_reserved_nusd()) / Decimal(10**9))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--seed-db", default="local/jev_pilot_v2_evidence.db")
    parser.add_argument("--db", default="local/jev_checkpoint500_v2.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute-labels", action="store_true")
    parser.add_argument("--max-new-rows", type=int)
    parser.add_argument("--approve-new-review-transmission", action="store_true")
    parser.add_argument("--confirmed-input-rate-usd-per-million")
    parser.add_argument("--rate-checked-on", help="local YYYY-MM-DD when official TypeSafe rate was checked")
    args = parser.parse_args()
    seed, target = local_db_path(args.seed_db), local_db_path(args.db)
    if seed == target:
        parser.error("checkpoint target must differ from saved v2 evidence ledger")
    if args.plan:
        result = plan(args.input, args.manifest, seed)
    elif args.prepare:
        result = prepare(args.input, args.manifest, seed, target)
    else:
        if not args.approve_new_review_transmission or args.max_new_rows is None:
            parser.error("execution requires explicit new-text approval and max-new-rows")
        if (args.confirmed_input_rate_usd_per_million != "0.042" or
                args.rate_checked_on != date.today().isoformat()):
            parser.error("execution requires today's verified TypeSafe input rate of USD 0.042/M")
        if not os.path.isfile(target):
            parser.error("prepared checkpoint ledger is missing")
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            parser.error("TYPESAFE_API_KEY is unavailable; no calls made")
        result = execute_labels(args.input, args.manifest, seed, target, args.max_new_rows, key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

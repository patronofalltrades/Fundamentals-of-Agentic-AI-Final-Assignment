"""Cost-100 Jev pilot. Default is offline planning; --execute is paid."""

import argparse
import csv
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256
from spotify_pipeline.jev_pilot import PilotLedger, run_reviews
from tools.plan_jev_pilot import plan


def sample_rows(path: str):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("source columns differ from contract")
        for row in reader:
            yield {"review_id": row["review_id"], "review_text": row["review_text"],
                   "source_sha256": row_sha256([row[field] for field in SOURCE_FIELDS])}


def local_db_path(path: str) -> str:
    repo = Path(__file__).resolve().parents[1]
    local = (repo / "local").resolve()
    candidate = Path(path).resolve()
    if candidate == local or local not in candidate.parents or candidate.suffix != ".db":
        raise ValueError("pilot ledger must be a .db file under this worktree's ignored local/ folder")
    return str(candidate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="supplied cost_100.csv")
    parser.add_argument("--manifest", required=True, help="matching supplied manifest.json")
    parser.add_argument("--db", default="local/jev_pilot.db", help="ignored local SQLite journal")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--execute", action="store_true", help="make paid Jev calls, only after approval")
    group.add_argument("--replay", action="store_true", help="read a saved ledger, with no network")
    parser.add_argument("--approved-cap-usd", help="explicit approved pilot limit, at most 0.60")
    args = parser.parse_args()
    aggregate = plan(args.input, args.manifest)
    if not args.execute and not args.replay:
        print(json.dumps(aggregate, indent=2))
        return
    db_path = local_db_path(args.db)
    if args.replay:
        if not os.path.isfile(db_path):
            parser.error("no saved ledger to replay")
        # The cap is a recorded part of the ledger identity, never inferred as zero.
        import sqlite3
        with sqlite3.connect(db_path) as connection:
            saved = dict(connection.execute("SELECT key,value FROM meta"))
        cap = Decimal(saved["cap_nusd"]) / Decimal(1000000000)
        with PilotLedger(db_path, aggregate["source_sha256"], cap) as ledger:
            print(json.dumps(ledger.summary(), indent=2))
        return
    if args.approved_cap_usd is None:
        parser.error("paid execution requires --approved-cap-usd")
    try:
        cap = Decimal(args.approved_cap_usd)
    except InvalidOperation:
        parser.error("approved cap must be a decimal USD amount")
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        parser.error("TYPESAFE_API_KEY is unavailable to this process; no calls made")
    rows = list(sample_rows(args.input))
    if len(rows) != 100 or file_sha256(args.input) != aggregate["source_sha256"]:
        parser.error("cost sample changed after preflight; no calls made")
    with PilotLedger(db_path, aggregate["source_sha256"], cap) as ledger:
        print(json.dumps(run_reviews(rows, ledger, key), indent=2))


if __name__ == "__main__":
    main()

"""Offline import of 500 validated v2 labels and evidence into canonical state."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.config import config_hash
from spotify_pipeline.db import Database
from spotify_pipeline.ingest import ingest
from spotify_pipeline.jev import label_config
from spotify_pipeline.jev_import import completed_items
from spotify_pipeline.jev_pilot import PilotLedger
from tools.checkpoint_500 import CHECKPOINT_CAP_NUSD, inspect_seed, inspect_target, source_rows
from tools.checkpoint_500_evidence import check_complete
from tools.jev_pilot import local_db_path


def import_checkpoint(source, manifest, seed_path, ledger_path, target_path, report_path):
    rows, source_sha = source_rows(source, manifest)
    seed_meta, _ = inspect_seed(seed_path, rows)
    if Path(target_path).exists() or Path(report_path).exists():
        raise ValueError("checkpoint import output already exists; do not overwrite it")
    with PilotLedger(ledger_path, source_sha,
                     Decimal(CHECKPOINT_CAP_NUSD) / Decimal(10**9)) as ledger:
        inspect_target(ledger, rows, source_sha, seed_meta["source_sha256"])
        validation = check_complete(ledger, rows)
    ingest(source, manifest, target_path, report_path)
    with Database(target_path) as db, PilotLedger(
            ledger_path, source_sha, Decimal(CHECKPOINT_CAP_NUSD) / Decimal(10**9)) as ledger:
        if db.get_meta("file_sha256") != source_sha:
            raise ValueError("canonical checkpoint source identity differs")
        items = completed_items(ledger, db, expected_count=500)
        direct = [item for item in items if not item["is_cached"]]
        cached = [item for item in items if item["is_cached"]]
        inserted = skipped = 0
        for group in (direct, cached):
            for start in range(0, len(group), 50):
                result = db.save_completed_batch(group[start:start + 50])
                inserted += result["inserted"]
                skipped += result["skipped"]
        counts = db.status_counts(config_hash(label_config()))
    if inserted != 500 or skipped or counts["completed"] != 500 or counts["pending"] != 0:
        raise ValueError("checkpoint canonical import is incomplete")
    return {"status": "completed_offline_import", "source_rows": len(rows),
            "inserted": inserted, "skipped": skipped, "direct": len(direct),
            "exact_text_cache": len(cached), "completed": counts["completed"],
            "pending": counts["pending"], "source_sha256": source_sha,
            "evidence_validation": validation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--seed-db", default="local/jev_pilot_v2_evidence.db")
    parser.add_argument("--ledger", default="local/jev_checkpoint500_v2.db")
    parser.add_argument("--out-db", default="local/jev_checkpoint500_complete.db")
    parser.add_argument("--out-report", default="local/jev_checkpoint500_ingest.json")
    args = parser.parse_args()
    seed, ledger, target = (local_db_path(path) for path in
                            (args.seed_db, args.ledger, args.out_db))
    repo_local = (Path(__file__).resolve().parents[1] / "local").resolve()
    report = Path(args.out_report).resolve()
    if repo_local not in report.parents or report.suffix != ".json":
        parser.error("report must be a JSON file in the ignored local folder")
    print(json.dumps(import_checkpoint(args.input, args.manifest, seed, ledger,
                                       target, str(report)), indent=2))


if __name__ == "__main__":
    main()

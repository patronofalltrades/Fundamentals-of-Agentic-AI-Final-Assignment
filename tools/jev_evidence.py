"""Optional Codex evidence stage for saved Jev pilot labels; dry by default."""

import argparse
import json
import os
import sqlite3
from decimal import Decimal

from spotify_pipeline.codex_evidence import extract_with_codex
from spotify_pipeline.jev_pilot import PilotLedger
from tools.jev_pilot import local_db_path
from tools.plan_jev_pilot import plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--db", default="local/jev_pilot.db")
    parser.add_argument("--execute", action="store_true", help="send saved review text to ChatGPT-auth Codex")
    args = parser.parse_args()
    aggregate = plan(args.input, args.manifest)
    path = local_db_path(args.db)
    if not os.path.isfile(path):
        parser.error("no saved Jev pilot ledger exists")
    with sqlite3.connect(path) as connection:
        meta = dict(connection.execute("SELECT key,value FROM meta"))
    cap = Decimal(meta["cap_nusd"]) / Decimal(1000000000)
    with PilotLedger(path, aggregate["source_sha256"], cap) as ledger:
        pending = list(ledger.missing_evidence())
        if not args.execute:
            print(json.dumps({"status": "offline_plan_only", "reviews_missing_evidence": len(pending),
                              "saved_jev_results": sum(ledger.summary()["results"].values()),
                              "codex_calls": 0}, indent=2))
            return
        for item in pending:
            original_id = item["cache_source_id"]
            if original_id and ledger.get_evidence(original_id):
                original = ledger.get_evidence(original_id)
                ledger.save_evidence(item["review_id"],
                                     {"entities": json.loads(original["entities_json"]),
                                      "evidence_quote": original["evidence_quote"]},
                                     original["model"], original["prompt_version"], 0.0,
                                     cache_source_id=original_id)
                continue
            labels = json.loads(item["label_json"])
            result = extract_with_codex(item["review_text"], labels)
            ledger.save_evidence(item["review_id"], result["evidence"], result["model"],
                                 result["prompt_version"], result["elapsed_seconds"])
        print(json.dumps(ledger.summary(), indent=2))


if __name__ == "__main__":
    main()

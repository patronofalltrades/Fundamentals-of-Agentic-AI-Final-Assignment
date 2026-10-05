"""Offline, aggregate-only plan for the supplied 100-review Jev cost sample."""

import argparse
import csv
import json
import os
from decimal import Decimal

from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256
from spotify_pipeline.jev import MAX_ATTEMPTS, MODEL, build_request
from spotify_pipeline.jsonutil import load_strict

USD_PER_M_INPUT = Decimal("0.042")  # Recheck https://docs.typesafe.ai/models before a paid run.
PROPOSED_HARD_CAP_USD = Decimal("0.60")
DOCUMENTED_MAX_INPUT_TOKENS_PER_CALL = 64000


def plan(source_path: str, manifest_path: str) -> dict:
    if os.path.basename(source_path) != "cost_100.csv":
        raise ValueError("pilot requires the supplied cost_100.csv")
    manifest = load_strict(manifest_path)
    expected = manifest["files"]["cost_100.csv"]
    if os.path.getsize(source_path) != expected["bytes"] or file_sha256(source_path) != expected["sha256"]:
        raise ValueError("cost sample differs from the supplied manifest")
    lengths = []
    ids = set()
    with open(source_path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("cost sample columns differ from the source contract")
        for row in reader:
            if None in row or not row["review_text"].strip() or row["review_id"] in ids:
                raise ValueError("malformed, empty, or repeated sample review")
            ids.add(row["review_id"])
            request = build_request(row["review_text"])
            lengths.append(len(json.dumps(request, ensure_ascii=False).encode("utf-8")))
    if len(lengths) != 100:
        raise ValueError("cost sample must contain exactly 100 reviews")
    # UTF-8 bytes / 4 is an illustrative heuristic, not a tokenizer or a spend bound.
    heuristic_tokens = sum(lengths) // 4
    heuristic_cost = USD_PER_M_INPUT * Decimal(heuristic_tokens) / Decimal(1000000)
    worst_case = (USD_PER_M_INPUT * Decimal(len(lengths) * MAX_ATTEMPTS * DOCUMENTED_MAX_INPUT_TOKENS_PER_CALL) / Decimal(1000000))
    return {
        "status": "offline_plan_only", "model": MODEL, "source_file": "cost_100.csv",
        "source_sha256": expected["sha256"], "reviews": len(lengths),
        "requests_without_retries": len(lengths), "max_attempts_per_review": MAX_ATTEMPTS,
        "request_utf8_bytes_total": sum(lengths), "request_utf8_bytes_max": max(lengths),
        "illustrative_input_tokens_at_4_bytes_each": heuristic_tokens,
        "illustrative_cost_usd": str(heuristic_cost),
        "published_input_price_usd_per_million": str(USD_PER_M_INPUT),
        "proposed_pilot_hard_cap_usd": str(PROPOSED_HARD_CAP_USD),
        "documented_context_tokens_per_call": DOCUMENTED_MAX_INPUT_TOKENS_PER_CALL,
        "worst_case_200_attempt_context_cost_usd": str(worst_case),
        "live_calls": 0, "measured_usage": None, "measured_runtime": None,
        "warning": "Byte-based token estimate is not a billing limit. The 0.60 USD cap proposal covers 200 attempts at the published 64k context maximum and input rate, but live execution still needs persisted pre-call reservation, actual usage reconciliation, credentials, and explicit approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    print(json.dumps(plan(args.input, args.manifest), indent=2))


if __name__ == "__main__":
    main()

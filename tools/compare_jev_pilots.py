"""Read-only, aggregate comparison of two saved Jev cost-100 ledgers."""

import argparse
import collections
import csv
import json
import math
import sqlite3
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import INTENTS, SOURCE_FIELDS, TOPICS, row_sha256
from spotify_pipeline.jev import MIN_CONFIDENCE, MODEL
from spotify_pipeline.jev_pilot import NANODOLLARS_PER_INPUT_TOKEN
from tools.plan_jev_pilot import plan

V1_CONFIG_HASH = "7256c9843fe9921f077f01a83101e2b15793a87031f33f1c7a45a328a214ff1c"
V2_CONFIG_HASH = "0bda2b8478fab805c56f033227017f6f37da9feb7da6b6a79b98b859cb10c647"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sample_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(tuple(reader.fieldnames or ()) == SOURCE_FIELDS, "source columns differ")
        return {row["review_id"]: (row["review_text"], row_sha256(
            [row[field] for field in SOURCE_FIELDS])) for row in reader}


def load_ledger(path, source_sha, expected_config, source_rows):
    uri = "file:%s?mode=ro" % Path(path).resolve()
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        meta = dict(db.execute("SELECT key,value FROM meta"))
        require(meta["source_sha256"] == source_sha and meta["config_hash"] == expected_config
                and meta["model"] == MODEL, "ledger identity differs")
        attempts = {row["id"]: dict(row) for row in db.execute("SELECT * FROM attempts")}
        results = {row["review_id"]: dict(row) for row in db.execute("SELECT * FROM results")}
        require(len(results) == 100 and results.keys() == source_rows.keys(), "result IDs differ from sample")
        require(len(attempts) == 100 and set(attempts) == {row["attempt_id"] for row in results.values()},
                "attempts or direct provenance differ")
        for attempt in attempts.values():
            require(attempt["status"] == "settled" and attempt["number"] == 1
                    and attempt["model"] == MODEL and attempt["error_class"] is None,
                    "unsettled, retried, or wrong-model attempt")
            require(type(attempt["input_tokens"]) is int and attempt["input_tokens"] >= 0
                    and type(attempt["output_tokens"]) is int and attempt["output_tokens"] >= 0
                    and attempt["charged_nusd"] == attempt["input_tokens"] * NANODOLLARS_PER_INPUT_TOKEN
                    and attempt["elapsed_seconds"] >= 0, "attempt usage or charge differs")
        labels = {}
        for review_id, row in results.items():
            require((row["review_text"], row["source_sha256"]) == source_rows[review_id]
                    and row["config_hash"] == expected_config and row["provenance"] == "jev_direct"
                    and row["cache_source_id"] is None, "saved row differs from source or configuration")
            label = json.loads(row["label_json"])
            attempt = attempts[row["attempt_id"]]
            confidence = label["confidence"]
            require(label["model"] == MODEL and label["input_tokens"] == attempt["input_tokens"]
                    and label["output_tokens"] == attempt["output_tokens"], "label usage differs")
            require(label["topic"] in TOPICS and label["intent"] in INTENTS
                    and type(label["severity"]) is int and 1 <= label["severity"] <= 5
                    and type(label["sentiment"]) in (int, float)
                    and math.isfinite(label["sentiment"]) and -1 <= label["sentiment"] <= 1,
                    "label schema differs")
            require(set(confidence) == {"topic", "intent", "severity", "sentiment"}
                    and all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
                            for value in confidence.values()), "confidence schema differs")
            expected_flag = (min(confidence.values()) < MIN_CONFIDENCE or label["topic"] == "other"
                             or label["intent"] == "unclear")
            require(type(label["needs_review"]) is bool and label["needs_review"] == expected_flag,
                    "review flag differs from declared rule")
            labels[review_id] = label
        evidence = {}
        for row in db.execute("SELECT * FROM evidence"):
            review_id = row["review_id"]
            require(review_id in results and review_id not in evidence, "evidence provenance differs")
            validate_evidence(results[review_id]["review_text"], {
                "entities": json.loads(row["entities_json"]), "evidence_quote": row["evidence_quote"]})
            evidence[review_id] = {"model": row["model"], "prompt_version": row["prompt_version"]}
        charge_nusd = sum(item["charged_nusd"] for item in attempts.values())
        return {"labels": labels, "evidence": evidence, "meta": meta,
                "attempts": len(attempts), "results": len(results),
                "input_tokens": sum(item["input_tokens"] for item in attempts.values()),
                "output_tokens": sum(item["output_tokens"] for item in attempts.values()),
                "summed_attempt_seconds": sum(item["elapsed_seconds"] for item in attempts.values()),
                "usage_derived_cost_usd": str(Decimal(charge_nusd) / Decimal(10**9))}


def compare(v1, v2, source_sha, timing):
    labels1, labels2 = v1["labels"], v2["labels"]
    ids = labels1.keys()
    require(ids == labels2.keys(), "ledger IDs differ")
    fields = ("topic", "intent", "severity", "sentiment", "needs_review")
    def counts(values):
        return dict(sorted(collections.Counter(values).items(), key=lambda pair: str(pair[0])))
    topic_transitions = counts("%s -> %s" % (labels1[rid]["topic"], labels2[rid]["topic"])
                               for rid in ids if labels1[rid]["topic"] != labels2[rid]["topic"])
    flags = counts("%s -> %s" % (labels1[rid]["needs_review"], labels2[rid]["needs_review"])
                   for rid in ids if labels1[rid]["needs_review"] != labels2[rid]["needs_review"])
    compatible = [rid for rid in ids if rid in v1["evidence"] and all(
        labels1[rid][field] == labels2[rid][field]
        for field in ("topic", "intent", "severity", "sentiment"))]
    wall = timing.get("wall_seconds")
    valid_wall = (timing.get("runner_exit_code") == 0 and type(wall) in (int, float)
                  and math.isfinite(wall) and wall >= 0)
    v1_cost = Decimal(v1["usage_derived_cost_usd"])
    v2_cost = Decimal(v2["usage_derived_cost_usd"])
    require(v1_cost + Decimal(v2["meta"]["cap_nusd"]) / Decimal(10**9) <= Decimal("0.60"),
            "cumulative authorized cap differs")
    return {
        "status": "completed_read_only_comparison", "sample": "cost_100.csv",
        "source_sha256": source_sha, "source_rows_validated": len(ids),
        "comparison_scope": "Same source rows; no human golden evaluation",
        "pricing": {"source": "https://docs.typesafe.ai/models", "input_usd_per_million": "0.042",
                    "output_usd_per_million": "0"},
        "runs": {version: {
            "prompt_version": "jev-rubric-" + version, "schema_version": "jev-labels-v1",
            "model": MODEL, "configuration_hash": run["meta"]["config_hash"],
            "results": run["results"], "settled_attempts": run["attempts"],
            "retries": 0, "uncertain_attempts": 0, "input_tokens": run["input_tokens"],
            "output_tokens": run["output_tokens"],
            "summed_attempt_seconds": round(run["summed_attempt_seconds"], 9),
            "usage_derived_cost_usd": run["usage_derived_cost_usd"],
            "topics": counts(label["topic"] for label in run["labels"].values()),
            "needs_review": counts(label["needs_review"] for label in run["labels"].values()),
            "evidence_records": len(run["evidence"]),
        } for version, run in (("v1", v1), ("v2", v2))},
        "changes": {"field_changed_counts": {field: sum(labels1[rid][field] != labels2[rid][field]
                                                       for rid in ids) for field in fields},
                    "topic_transitions": topic_transitions,
                    "review_flag_transitions": flags,
                    "v1_evidence_label_compatible_rows": len(compatible),
                    "compatible_evidence_prompt_versions": counts(v1["evidence"][rid]["prompt_version"]
                                                                   for rid in compatible)},
        "cumulative_usage_derived_cost_usd": str(v1_cost + v2_cost),
        "v2_cap_usd": str(Decimal(v2["meta"]["cap_nusd"]) / Decimal(10**9)),
        "v2_runner_wall_seconds": wall if valid_wall else None,
        "v2_timing_status": "valid" if valid_wall else "invalid_negative_or_missing_value",
        "v2_recorded_invalid_wall_seconds": None if valid_wall else wall,
        "limitations": ["Usage-derived cost is not independently reconciled with account credit debit.",
                        "Summed request durations are not end-to-end wall time.",
                        "The v2 launcher's cross-process monotonic clock produced an invalid negative wall time."
                        if not valid_wall else "A single wall-time sample is not a stable benchmark.",
                        "Saved evidence is compatible only where all four labels match; it was not copied into v2.",
                        "Topic changes and manual development judgments are not gold accuracy measurements."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("input", "manifest", "v1-db", "v2-db", "timing", "out"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    preflight = plan(args.input, args.manifest)
    source = sample_rows(args.input)
    require(len(source) == 100, "source must have 100 IDs")
    v1 = load_ledger(args.v1_db, preflight["source_sha256"], V1_CONFIG_HASH, source)
    v2 = load_ledger(args.v2_db, preflight["source_sha256"], V2_CONFIG_HASH, source)
    with open(args.timing, encoding="utf-8") as stream:
        timing = json.load(stream)
    report = compare(v1, v2, preflight["source_sha256"], timing)
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print("Validated 100 source rows and both ledgers; wrote aggregate comparison")


if __name__ == "__main__":
    main()

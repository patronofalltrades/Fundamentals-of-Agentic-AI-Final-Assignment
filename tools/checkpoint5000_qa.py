"""Read-only structural QA for a checkpoint bundle. No model or ledger access.

Input JSON: {"manifest": [{"review_id", "source_sha256"}],
"source_rows": [six original SOURCE_FIELDS], "batches": [{"batch_id", "status",
"review_ids": [...]}], "results": [normalized classification records]}.
Batch statuses: pending, in_flight, uncertain, quarantined, succeeded.
Results use spotify_pipeline.schema completed/quarantined fields plus batch_id,
label_prompt_version, label_schema_version, evidence_prompt_version. A completed
cache row additionally uses is_cached, cache_source_id and config_hash.

Aggregate JSON never includes source IDs, text, quotes, or private paths.
The optional sample JSON contains IDs only and stays in an ignored local path.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256, text_sha256
from spotify_pipeline.jev import PROMPT_VERSION as LABEL_PROMPT, SCHEMA_VERSION as LABEL_SCHEMA
from spotify_pipeline.schema import (validate_cache_reuse, validate_completed,
                                     validate_direct, validate_quarantine)

STATUSES = {"pending", "in_flight", "uncertain", "quarantined", "succeeded",
            "partial_succeeded"}


def _issue(counter, code):
    counter[code] += 1


def audit(bundle, *, label_prompt=LABEL_PROMPT, label_schema=LABEL_SCHEMA,
          evidence_prompt, sample_size=50, seed=5000):
    """Return (aggregate, sample IDs); never mutate input or saved state."""
    if not isinstance(bundle, dict) or not all(isinstance(bundle.get(k), list)
            for k in ("manifest", "source_rows", "batches", "results")) or not isinstance(
                bundle.get("blocked_aliases", []), list):
        raise ValueError("bundle needs manifest, source_rows, batches and results arrays")
    problems = Counter()
    source, manifest, batches, membership, results, blocked_aliases = {}, {}, {}, {}, {}, {}
    invalid_rows = set()
    duplicate = Counter()
    for row in bundle["source_rows"]:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in SOURCE_FIELDS):
            _issue(problems, "malformed_source_row")
            continue
        rid = row["review_id"]
        duplicate[rid] += 1
        if rid in source:
            _issue(problems, "duplicate_source_id")
        else:
            source[rid] = row
    for item in bundle["manifest"]:
        if not isinstance(item, dict) or not isinstance(item.get("review_id"), str):
            _issue(problems, "malformed_manifest_row")
            continue
        rid = item["review_id"]
        if rid in manifest:
            _issue(problems, "duplicate_manifest_id")
        else:
            manifest[rid] = item
    for rid, item in manifest.items():
        row = source.get(rid)
        if row is None:
            _issue(problems, "missing_source_id")
        elif item.get("source_sha256") != row_sha256([row[k] for k in SOURCE_FIELDS]):
            _issue(problems, "source_hash_mismatch")
    for rid in source.keys() - manifest.keys():
        _issue(problems, "foreign_source_id")
    for batch in bundle["batches"]:
        if not isinstance(batch, dict) or not isinstance(batch.get("review_ids"), list):
            _issue(problems, "malformed_batch")
            continue
        bid = batch.get("batch_id")
        if not isinstance(bid, (str, int)) or isinstance(bid, bool) or bid in batches:
            _issue(problems, "duplicate_or_invalid_batch_id")
            continue
        batches[bid] = batch
        if batch.get("status") not in STATUSES:
            _issue(problems, "invalid_batch_status")
        if len(batch["review_ids"]) > 50 or len(batch["review_ids"]) == 0:
            _issue(problems, "invalid_batch_size")
        seen = set()
        for rid in batch["review_ids"]:
            if not isinstance(rid, str):
                _issue(problems, "malformed_batch_member")
                continue
            if rid in seen:
                _issue(problems, "duplicate_within_batch")
            seen.add(rid)
            if rid not in manifest:
                _issue(problems, "foreign_batch_id")
            if rid in membership:
                _issue(problems, "duplicate_across_batches")
            else:
                membership[rid] = bid
    for rid in manifest.keys() - membership.keys():
        rec = next((item for item in bundle["results"] if isinstance(item, dict)
                    and item.get("review_id") == rid), None)
        if rec is not None and not rec.get("is_cached"):
            _issue(problems, "missing_batch_id")
    for rec in bundle["results"]:
        if not isinstance(rec, dict) or not isinstance(rec.get("review_id"), str):
            _issue(problems, "malformed_result")
            continue
        rid = rec["review_id"]
        if rid in results:
            _issue(problems, "duplicate_result_id")
            continue
        results[rid] = rec
        if rid not in manifest:
            _issue(problems, "foreign_result_id")
            continue
        row = source.get(rid)
        if row is None:
            continue
        expected = {"review_id": rid, "review_text": row["review_text"],
                    "source_sha256": row_sha256([row[k] for k in SOURCE_FIELDS])}
        if not rec.get("is_cached") and rec.get("batch_id") != membership.get(rid):
            _issue(problems, "result_batch_mismatch")
            invalid_rows.add(rid)
        if rec.get("source_sha256") != expected["source_sha256"] or rec.get("review_text") != row["review_text"]:
            _issue(problems, "result_source_mismatch")
            invalid_rows.add(rid)
        batch = batches.get(membership.get(rid), {})
        if rec.get("status") == "completed":
            if not rec.get("is_cached") and batch.get("status") not in ("succeeded", "partial_succeeded"):
                _issue(problems, "completed_in_unsettled_batch")
                invalid_rows.add(rid)
            for error in validate_completed(rec, expected):
                _issue(problems, "invalid_completed")
                invalid_rows.add(rid)
            try:
                validate_evidence(row["review_text"], {"entities": rec.get("entities"),
                                    "evidence_quote": rec.get("evidence_quote")})
            except Exception:
                _issue(problems, "invalid_evidence_span")
                invalid_rows.add(rid)
            if rec.get("label_prompt_version") != label_prompt:
                _issue(problems, "label_prompt_mismatch")
                invalid_rows.add(rid)
            if rec.get("label_schema_version") != label_schema:
                _issue(problems, "label_schema_mismatch")
                invalid_rows.add(rid)
            if rec.get("evidence_prompt_version") != evidence_prompt:
                _issue(problems, "evidence_prompt_mismatch")
                invalid_rows.add(rid)
            if not rec.get("is_cached"):
                for error in validate_direct(rec):
                    _issue(problems, "invalid_direct_provenance")
                    invalid_rows.add(rid)
        elif rec.get("status") == "quarantined":
            for error in validate_quarantine(rec, expected):
                _issue(problems, "invalid_quarantine")
        else:
            _issue(problems, "invalid_result_status")
            invalid_rows.add(rid)
    for alias in bundle.get("blocked_aliases", []):
        if not isinstance(alias, dict) or not isinstance(alias.get("review_id"), str):
            _issue(problems, "malformed_blocked_alias")
            continue
        rid = alias["review_id"]
        if rid in blocked_aliases:
            _issue(problems, "duplicate_blocked_alias")
            continue
        blocked_aliases[rid] = alias
        row = source.get(rid)
        origin_id = alias.get("cache_source_id")
        batch_id = alias.get("batch_id")
        if not isinstance(origin_id, str) or not isinstance(batch_id, (str, int)) or isinstance(batch_id, bool):
            _issue(problems, "invalid_blocked_alias_provenance")
            invalid_rows.add(rid)
            continue
        origin = source.get(origin_id)
        batch = batches.get(batch_id, {})
        if (row is None or rid in membership or rid in results or
                origin_id == rid or membership.get(origin_id) != batch_id or
                origin is None or row["review_text"] != origin["review_text"] or
                alias.get("source_sha256") != row_sha256([row[k] for k in SOURCE_FIELDS]) or
                alias.get("status") not in ("uncertain", "quarantined") or
                batch.get("status") != alias.get("status")):
            _issue(problems, "invalid_blocked_alias_provenance")
            invalid_rows.add(rid)
    for rid, rec in results.items():
        if rec.get("status") != "completed" or not rec.get("is_cached"):
            continue
        origin = results.get(rec.get("cache_source_id"))
        if origin is None:
            _issue(problems, "missing_cache_origin")
            invalid_rows.add(rid)
        else:
            for error in validate_cache_reuse(rec, origin, not bool(origin.get("is_cached"))):
                _issue(problems, "invalid_cache_provenance")
                invalid_rows.add(rid)
    states = Counter()
    risk = set()
    for rid in manifest:
        rec = results.get(rid)
        if rec is not None:
            state = rec.get("status", "invalid")
        elif rid in blocked_aliases:
            state = blocked_aliases[rid].get("status", "invalid")
        else:
            state = batches.get(membership.get(rid), {}).get("status", "pending")
            if state == "succeeded":
                _issue(problems, "missing_result_in_succeeded_batch")
                state = "pending"
        states[state] += 1
        if state != "completed" or rid in invalid_rows or (rec and (rec.get("needs_review") or rec.get("is_cached"))):
            risk.add(rid)
    distributions = {key: dict(sorted(Counter(rec[key] for rid, rec in results.items()
        if rid in manifest and rec.get("status") == "completed" and key in rec).items(),
        key=lambda pair: str(pair[0]))) for key in ("topic", "intent", "severity")}
    ordered = sorted(manifest)
    rng = random.Random(seed)
    random_ids = sorted(rng.sample(ordered, min(sample_size, len(ordered))))
    risk_ids = sorted(rng.sample(sorted(risk), min(sample_size, len(risk))))
    unique_texts = len({text_sha256(source[rid]["review_text"]) for rid in manifest if rid in source})
    completed_unique_texts = len({text_sha256(source[rid]["review_text"]) for rid in manifest
                                  if rid in source and rid in results and
                                  results[rid].get("status") == "completed"})
    accepted = sum(rid in results and results[rid].get("status") == "completed"
                   and rid not in invalid_rows for rid in manifest)
    aggregate = {"selected_source_rows": len(manifest), "source_rows_present": len(source),
        "unique_source_texts": unique_texts, "result_rows": len(results),
        "completed_unique_texts": completed_unique_texts,
        "duplicate_source_ids": sum(n - 1 for n in duplicate.values()),
        "counts_by_state": dict(sorted(states.items())), "completed_rows": states["completed"],
        "accepted_rows": accepted,
        "unresolved_rows": len(manifest) - accepted,
        "cached_rows": sum(bool(r.get("is_cached")) for r in results.values()
                           if r.get("status") == "completed"),
        "distributions": distributions, "failure_reasons": dict(sorted(problems.items())),
        "structurally_clean": not bool(problems)}
    return aggregate, {"seed": seed, "random_review_ids": random_ids,
                       "risk_review_ids": risk_ids, "semantic_review_pending": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, help="local normalized JSON input")
    parser.add_argument("--evidence-prompt", required=True)
    parser.add_argument("--sample-out", help="ignored local path for IDs only")
    parser.add_argument("--sample-size", type=int, default=50)
    args = parser.parse_args()
    if args.sample_size < 0:
        parser.error("sample size must be nonnegative")
    with open(args.bundle, encoding="utf-8") as handle:
        report, samples = audit(json.load(handle), evidence_prompt=args.evidence_prompt,
                                sample_size=args.sample_size)
    if args.sample_out:
        with open(args.sample_out, "w", encoding="utf-8") as handle:
            json.dump(samples, handle, sort_keys=True, indent=2)
            handle.write("\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["structurally_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline, text-free verification checks and a private source-to-claim trace.

The comparison consumes saved predictions only. It does not run a verifier,
prove that its input was blind, or measure model resistance to injected text.
"""

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from dashboard.public_boundary import REASON_CATEGORIES


FIELDS = ("case_id", "source_sha256", "config_hash", "issue_id")


def compare_saved_predictions(first, independent, config_hash, planted_ids=()):
    """Return aggregate disagreement counts after exact identity/config checks."""
    def indexed(rows):
        result = {}
        for row in rows:
            if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k] for k in FIELDS):
                raise ValueError("prediction metadata is incomplete")
            if row["case_id"] in result or row["config_hash"] != config_hash:
                raise ValueError("duplicate case or configuration mismatch")
            result[row["case_id"]] = row
        return result

    a, b = indexed(first), indexed(independent)
    if set(a) != set(b):
        raise ValueError("prediction case IDs do not match")
    planted = set(planted_ids)
    if not planted <= set(a):
        raise ValueError("planted case ID is outside the comparison")
    for case_id in a:
        if a[case_id]["source_sha256"] != b[case_id]["source_sha256"]:
            raise ValueError("prediction source hashes do not match")
    mismatched = {case_id for case_id in a if a[case_id]["issue_id"] != b[case_id]["issue_id"]}
    return {"cases": len(a), "disagreements": len(mismatched),
            "planted_disagreements": len(mismatched & planted), "planted_cases": len(planted)}


def inspect_prediction_manifest(prediction_path, manifest_path):
    """Read private rows locally and return only structural metadata."""
    predictions = json.loads(Path(prediction_path).read_text(encoding="utf-8"))
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    rows, source = predictions.get("rows", []), manifest.get("rows", [])
    lookup = {r["review_id"]: r["source_sha256"] for r in source}
    return {"predictions": len(rows), "manifest_rows": len(source),
            "distinct_prediction_ids": len({r["review_id"] for r in rows}),
            "identity_hash_match": len(lookup) == len(source) and all(
                lookup.get(r["review_id"]) == r["source_sha256"] for r in rows),
            "declared_manifest_hash_match": predictions.get("manifest_sha256") == hashlib.sha256(
                manifest_file.read_bytes()).hexdigest(),
            "has_catalog_hash": bool(predictions.get("catalog_sha256")),
            "has_model": bool(predictions.get("model")),
            "has_prompt_version": bool(predictions.get("prompt_version")),
            "has_config_hash": bool(predictions.get("config_hash")),
            "per_case_blind_input_digest_present": all("blind_input_sha256" in r for r in rows) if rows else False}


def private_trace(db_path, memo_path, out_path):
    """Save one deterministic accepted and one failed case without source text.

    Output is a new ignored, owner-readable local file. The return value is
    aggregate metadata only; it never includes original IDs or row hashes.
    """
    out = Path(out_path)
    if out.exists() or out.parent.name != "local":
        raise ValueError("trace output must be a new file directly under local/")
    conn = sqlite3.connect("file:%s?mode=ro" % Path(db_path).resolve(), uri=True)
    try:
        run = conn.execute("SELECT run_id,config_hash FROM analysis_run ORDER BY created_at DESC,run_id DESC LIMIT 1").fetchone()
        if not run:
            raise ValueError("analysis run is missing")
        run_id, config_hash = run
        accepted = conn.execute("""SELECT r.review_id,r.row_sha256,c.config_hash,c.severity,m.issue_id
            FROM issue_membership m JOIN records r ON r.row_index=m.row_index
            JOIN classifications c ON c.row_index=m.row_index AND c.config_hash=?
            LEFT JOIN semantic_flag f ON f.row_index=m.row_index
            WHERE m.run_id=? AND m.issue_id='USE-ADS' AND COALESCE(f.blocked,0)=0
            ORDER BY r.review_id LIMIT 1""", (config_hash, run_id)).fetchone()
        failed = conn.execute("""SELECT r.review_id,r.row_sha256,s.state,s.category
            FROM row_state s JOIN records r ON r.row_index=s.row_index
            WHERE s.state='quarantined' ORDER BY r.review_id LIMIT 1""").fetchone()
        claim_rows = conn.execute("""SELECT claim_id,metric,value FROM claim
            WHERE run_id=? AND issue_id='USE-ADS' AND metric IN ('complaint_count','severity_sum')
            ORDER BY claim_id""", (run_id,)).fetchall()
        count, severity = conn.execute("""SELECT COUNT(*),SUM(c.severity) FROM issue_membership m
            JOIN classifications c ON c.row_index=m.row_index AND c.config_hash=?
            WHERE m.run_id=? AND m.issue_id='USE-ADS'""", (config_hash, run_id)).fetchone()
        if not accepted or not failed or len(claim_rows) != 2:
            raise ValueError("accepted, failed, or claim trace is incomplete")
        if failed[3] not in REASON_CATEGORIES:
            raise ValueError("failed case has no sanitized reason category")
        claims = {metric: value for _, metric, value in claim_rows}
        if claims != {"complaint_count": str(count), "severity_sum": str(severity)}:
            raise ValueError("saved claim values do not match recomputed membership")
        memo = Path(memo_path).read_bytes()
        if not all((claim_id + ": USE-ADS " + metric + " = " + value).encode() in memo
                   for claim_id, metric, value in claim_rows):
            raise ValueError("memo lacks the exact trace claims")
        trace = {"schema_version": "private-text-free-trace-v1", "run_id": run_id,
                 "accepted": {"source_review_id": accepted[0], "source_row_sha256": accepted[1],
                              "config_hash": accepted[2], "severity": accepted[3], "issue_id": accepted[4],
                              "claim_ids": [r[0] for r in claim_rows],
                              "baseline_count": count, "baseline_severity_sum": severity,
                              "memo_sha256": hashlib.sha256(memo).hexdigest()},
                 "failed": {"source_review_id": failed[0], "source_row_sha256": failed[1],
                            "state": failed[2], "sanitized_category": failed[3]}}
        out.parent.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(trace, handle, sort_keys=True, indent=2)
            handle.write("\n")
        return {"trace_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                "accepted_trace": True, "failed_trace": True,
                "issue_id": accepted[4], "baseline_count": count,
                "baseline_severity_sum": severity, "claim_count": len(claim_rows)}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--memo", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(private_trace(args.db, args.memo, args.out), sort_keys=True))


if __name__ == "__main__":
    main()

"""Build a private first-500 QA pack and print aggregate checkpoint metrics."""

import argparse
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import row_sha256, SOURCE_FIELDS
from tools import next5000_checkpoint as checkpoint

OUT = Path("local/next5000_first500_qa.json")


def collect(manifest, db):
    requests = {key: {"stage": stage, "status": status, "response":
        json.loads(raw) if raw else None, "elapsed_seconds": elapsed,
        "input_tokens": inp, "output_tokens": out, "reasoning_tokens": reasoning,
        "charged_nusd": charged, "error_class": error}
        for key, stage, status, raw, elapsed, inp, out, reasoning, charged, error
        in db.execute("""SELECT request_key,stage,status,response_json,elapsed_seconds,
            input_tokens,output_tokens,reasoning_tokens,charged_nusd,error_class
            FROM next5000_requests""")}
    members = {}
    for key, rid in db.execute("SELECT request_key,review_id FROM next5000_members"):
        members.setdefault(rid, []).append(key)
    attempted = {}
    source_by_id = {r["review_id"]: r for r in manifest["rows"][:checkpoint.FIRST]}
    for rid, keys in members.items():
        for key in keys:
            stage = requests[key]["stage"]
            attempted.setdefault(stage, {})[source_by_id[rid]["review_text"]] = key
    labels = {rid: {"value": json.loads(value), "config_sha": cfg,
        "provenance": provenance, "origin_id": origin, "request_key": key}
        for rid, value, cfg, provenance, origin, key in db.execute(
            "SELECT * FROM next5000_labels")}
    evidence = {rid: {"entities": json.loads(entities), "evidence_quote": quote,
        "config_sha": cfg, "provenance": provenance, "origin_id": origin,
        "request_key": key} for rid, entities, quote, cfg, provenance, origin, key
        in db.execute("SELECT * FROM next5000_evidence")}
    quarantines = {rid: {"reason": reason, "request_key": key} for rid, reason, key
        in db.execute("SELECT * FROM next5000_quarantines")}
    records = []
    counts = {}
    for source in manifest["rows"][:checkpoint.FIRST]:
        rid, text = source["review_id"], source["review_text"]
        if row_sha256([source[k] for k in SOURCE_FIELDS]) != source["source_sha256"]:
            raise ValueError("saved source hash differs")
        ev = evidence.get(rid)
        if ev:
            validate_evidence(text, {"entities": ev["entities"],
                "evidence_quote": ev["evidence_quote"]})
            status = "accepted"
        elif rid in quarantines:
            status = "quarantined"
        elif source["blocked_prior_uncertainty"]:
            status = "blocked_prior_uncertainty"
        elif text in attempted.get("evidence", {}):
            key = attempted["evidence"][text]
            status = "uncertain_alias" if requests[key]["status"] == "uncertain" else "quarantined_alias"
        else:
            status = "pending_ten_review_tail" if rid in labels else "pending_label"
        counts[status] = counts.get(status, 0) + 1
        records.append({"source": source, "label": labels.get(rid),
            "evidence": ev, "quarantine": quarantines.get(rid), "status": status})
    by_stage = {}
    for stage in ("jev", "evidence"):
        chosen = [r for r in requests.values() if r["stage"] == stage]
        by_stage[stage] = {"requests": len(chosen), "statuses": {status:
            sum(r["status"] == status for r in chosen) for status in sorted({r["status"] for r in chosen})},
            "charged_nusd": sum(r["charged_nusd"] or 0 for r in chosen),
            "input_tokens": sum(r["input_tokens"] or 0 for r in chosen),
            "output_tokens": sum(r["output_tokens"] or 0 for r in chosen),
            "reasoning_tokens": sum(r["reasoning_tokens"] or 0 for r in chosen),
            "summed_request_seconds": round(sum(r["elapsed_seconds"] or 0 for r in chosen), 3)}
    result = {"schema_version": "next5000-first500-qa-v1",
        "manifest_sha256": checkpoint.file_sha256(str(checkpoint.MANIFEST)),
        "first500": checkpoint.FIRST, "counts": counts, "stages": by_stage,
        "records": records, "requests": requests}
    if len(records) != 500 or sum(counts.values()) != 500:
        raise ValueError("first-500 source accounting differs")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    manifest, _ = checkpoint.load_manifest()
    with sqlite3.connect("file:" + os.path.abspath(checkpoint.BUDGET) + "?mode=ro", uri=True) as db:
        result = collect(manifest, db)
    if args.write:
        if args.output.exists():
            raise FileExistsError("private QA pack already frozen")
        fd = os.open(str(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(checkpoint.canonical(result) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    aggregate = {k: v for k, v in result.items() if k not in ("records", "requests")}
    if args.write:
        aggregate["private_pack_sha256"] = checkpoint.file_sha256(str(args.output))
    print(checkpoint.canonical(aggregate))


if __name__ == "__main__":
    main()

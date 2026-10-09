"""Export an ignored, local normalized bundle for independent read-only QA."""

import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256
from spotify_pipeline import deepinfra_batch, jev
from tools.checkpoint5000_dispatch import DATASET, load_manifest


def make_bundle(manifest_path, budget_path):
    manifest, _ = load_manifest(manifest_path)
    source_path = os.path.join(DATASET, manifest["source_file"])
    with open(source_path, encoding="utf-8-sig", newline="") as stream:
        source_rows = list(itertools.islice(csv.DictReader(stream, strict=True), 5000))
    if len(source_rows) != 5000:
        raise ValueError("first 5000 source rows missing")
    for source, selected in zip(source_rows, manifest["rows"]):
        if source["review_id"] != selected["review_id"] or \
                source["review_text"] != selected["text"] or \
                row_sha256([source[k] for k in SOURCE_FIELDS]) != selected["source_sha256"]:
            raise ValueError("manifest differs from first 5000 source rows")
    db = sqlite3.connect("file:" + os.path.abspath(budget_path) + "?mode=ro", uri=True)
    try:
        labels = {rid: (json.loads(value), config, provenance) for rid, value, config, provenance in
            db.execute("SELECT review_id,label_json,config_sha,provenance FROM checkpoint_labels")}
        evidence = {rid: (json.loads(entities), quote, config, provenance, origin, request_key)
            for rid, entities, quote, config, provenance, origin, request_key in db.execute(
                "SELECT review_id,entities_json,evidence_quote,config_sha,provenance,cache_source_id,request_key FROM checkpoint_evidence")}
        quarantines = {rid: (source_sha, reason, request_key) for rid, source_sha, reason, request_key
            in db.execute("SELECT review_id,source_sha,reason,request_key FROM checkpoint_quarantines")}
        requests = {key: (stage, status, response_id) for key, stage, status, response_id in db.execute(
            "SELECT request_key,stage,status,response_id FROM checkpoint_requests")}
        batches = []
        batch_members = {}
        blocked_by_text = {}
        source_text = {row["review_id"]: row["review_text"] for row in source_rows}
        for key, (stage, status, _) in requests.items():
            if stage != "evidence":
                continue
            members = [rid for rid, in db.execute(
                "SELECT review_id FROM checkpoint_request_members WHERE request_key=? ORDER BY rowid", (key,))]
            batch_members[key] = set(members)
            batches.append({"batch_id": key, "status": {"reserved": "in_flight",
                "quarantined_metered": "quarantined"}.get(status, status), "review_ids": members})
            if status in ("uncertain", "quarantined_metered"):
                for rid in members:
                    text = source_text[rid]
                    if text in blocked_by_text and blocked_by_text[text] != (rid, key, status):
                        raise ValueError("blocked exact text has conflicting request origins")
                    blocked_by_text[text] = (rid, key, status)
        results = []
        blocked_aliases = []
        for row in source_rows:
            rid = row["review_id"]
            if rid in quarantines:
                source_sha, reason, request_key = quarantines[rid]
                results.append({"review_id": rid, "review_text": row["review_text"],
                    "source_sha256": source_sha, "batch_id": request_key,
                    "status": "quarantined", "reason": reason,
                    "is_cached": rid not in batch_members.get(request_key, set())})
                continue
            if rid not in labels or rid not in evidence:
                origin = blocked_by_text.get(row["review_text"])
                if origin and rid not in batch_members[origin[1]]:
                    blocked_aliases.append({"review_id": rid,
                        "source_sha256": row_sha256([row[k] for k in SOURCE_FIELDS]),
                        "cache_source_id": origin[0], "batch_id": origin[1],
                        "status": "uncertain" if origin[2] == "uncertain" else "quarantined"})
                continue
            label, label_config, label_provenance = labels[rid]
            entities, quote, evidence_config, evidence_provenance, origin, request_key = evidence[rid]
            cached = evidence_provenance == "deepinfra_exact_text_cache"
            if not cached and (not request_key or requests.get(request_key, (None, None))[1]
                    not in ("succeeded", "partial_succeeded")):
                raise ValueError("direct evidence lacks a settled request")
            combined_config = hashlib.sha256(json.dumps([label_config, evidence_config],
                separators=(",", ":")).encode("utf-8")).hexdigest()
            results.append({"review_id": rid, "review_text": row["review_text"],
                "source_sha256": row_sha256([row[k] for k in SOURCE_FIELDS]),
                "batch_id": None if cached else request_key, "status": "completed",
                "topic": label["topic"], "intent": label["intent"],
                "severity": label["severity"], "sentiment": label["sentiment"],
                "needs_review": label["needs_review"], "entities": entities,
                "evidence_quote": quote, "label_config": label_config,
                "config_hash": combined_config, "is_cached": cached,
                "cache_source_id": origin if cached else None,
                "request_id": None if cached else requests[request_key][2],
                "provenance": "jev_exact_text_cache" if cached else "model_call_placeholder",
                "label_provenance": label_provenance,
                "label_prompt_version": jev.PROMPT_VERSION,
                "label_schema_version": jev.SCHEMA_VERSION,
                "evidence_prompt_version": deepinfra_batch.PROMPT_VERSION})
        return {"manifest": manifest["rows"], "source_rows": source_rows,
                "batches": batches, "results": results,
                "blocked_aliases": blocked_aliases}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="local/checkpoint5000_manifest.json")
    parser.add_argument("--budget", default="local/project_budget.db")
    parser.add_argument("--out", default="local/checkpoint5000_qa_bundle.json")
    args = parser.parse_args()
    if Path(args.out).parent.name != "local":
        parser.error("QA bundle contains review text; output must be under local/")
    bundle = make_bundle(args.manifest, args.budget)
    target = Path(args.out)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(bundle, stream, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, target)
    print(json.dumps({"source_rows": len(bundle["source_rows"]),
        "result_rows": len(bundle["results"]), "evidence_batches": len(bundle["batches"])}))


if __name__ == "__main__":
    main()

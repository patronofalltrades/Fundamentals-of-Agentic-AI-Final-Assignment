"""Build an offline, private first-5,000 source manifest and cache index.

This module never calls a model or writes to a source ledger. Manifest output
contains original review text, so keep it under the ignored local/ directory.
"""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from spotify_pipeline.codex_evidence import MODEL as EVIDENCE_MODEL
from spotify_pipeline.codex_evidence import PROMPT_VERSION as EVIDENCE_PROMPT
from spotify_pipeline.codex_evidence import OUTPUT_SCHEMA as EVIDENCE_SCHEMA
from spotify_pipeline.config import cache_key, config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline.jev import label_config

SOURCE_NAME = "spotify_reviews_18months.csv"
CHECKPOINT_NAME = "checkpoint_500.csv"
LIMIT = 5000
SCHEMA_VERSION = "checkpoint5000-manifest-v1"


def _verified_source(path, manifest_path, name):
    if Path(path).name != name:
        raise ValueError("unexpected source filename")
    with open(manifest_path, encoding="utf-8") as stream:
        entry = json.load(stream)["files"][name]
    if os.path.getsize(path) != entry["bytes"] or file_sha256(path) != entry["sha256"]:
        raise ValueError("source differs from supplied manifest")
    return entry["sha256"]


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("source fields differ from six-field contract")
        for row in reader:
            if None in row or any(not isinstance(row[field], str) for field in SOURCE_FIELDS):
                raise ValueError("malformed source row")
            yield row


def _cache_index(db_path, checkpoint_path, supplied_manifest):
    """Return compatible saved records by exact text, with verified provenance."""
    if not db_path:
        return {}, {}
    checkpoint_sha = _verified_source(checkpoint_path, supplied_manifest, CHECKPOINT_NAME)
    checkpoint = list(_rows(checkpoint_path))
    if len(checkpoint) != 500 or len({row["review_id"] for row in checkpoint}) != 500:
        raise ValueError("checkpoint must have 500 distinct rows")
    source = {row["review_id"]: row for row in checkpoint}
    uri = "file:%s?mode=ro" % Path(db_path).resolve()
    labels, evidence = {}, {}
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        meta = dict(db.execute("SELECT key,value FROM meta"))
        if meta.get("source_sha256") != checkpoint_sha:
            raise ValueError("cache ledger source version differs")
        if (meta.get("config_hash") != config_hash(label_config()) or
                meta.get("model") != label_config()["model"]):
            raise ValueError("cache ledger label configuration differs")
        saved = list(db.execute("SELECT * FROM results ORDER BY rowid"))
        if len(saved) != 500:
            raise ValueError("cache ledger is not the saved 500-row checkpoint")
        for item in saved:
            row = source.get(item["review_id"])
            if (row is None or row["review_text"] != item["review_text"] or
                    row_sha256([row[field] for field in SOURCE_FIELDS]) != item["source_sha256"] or
                    text_sha256(row["review_text"]) != item["text_sha256"] or
                    item["config_hash"] != meta["config_hash"]):
                raise ValueError("cache ledger label source/config mismatch")
            labels.setdefault(row["review_text"], item["review_id"])
        saved_evidence = list(db.execute("SELECT * FROM evidence ORDER BY rowid"))
        if len(saved_evidence) != 500:
            raise ValueError("cache ledger evidence is incomplete")
        for item in saved_evidence:
            row = source.get(item["review_id"])
            if row is None:
                raise ValueError("cache evidence ID differs from checkpoint")
            if item["model"] == EVIDENCE_MODEL and item["prompt_version"] == EVIDENCE_PROMPT:
                quote = item["evidence_quote"]
                entities = json.loads(item["entities_json"])
                if (not isinstance(quote, str) or not quote.strip() or quote not in row["review_text"] or
                        not isinstance(entities, list) or
                        not all(isinstance(x, str) and x.strip() for x in entities)):
                    raise ValueError("cache evidence does not match exact source")
                evidence.setdefault(row["review_text"], item["review_id"])
    return labels, evidence


def _corrections(path, checkpoint_path, supplied_manifest):
    if not path:
        return {}, None
    checkpoint_sha = _verified_source(checkpoint_path, supplied_manifest, CHECKPOINT_NAME)
    source = {row["review_id"]: row for row in _rows(checkpoint_path)}
    with open(path, encoding="utf-8") as stream:
        overlay = json.load(stream)
    if (overlay["metadata"]["source_checkpoint_sha256"] != checkpoint_sha or
            overlay["metadata"]["status"] != "development_only_unpromoted" or
            len(overlay["corrections"]) != 4):
        raise ValueError("human correction overlay provenance differs")
    found = {}
    for item in overlay["corrections"]:
        row = source.get(item["review_id"])
        if (row is None or row_sha256([row[field] for field in SOURCE_FIELDS]) != item["source_sha256"] or
                item["review_id"] in found):
            raise ValueError("human correction source differs")
        found[item["review_id"]] = item
    return found, file_sha256(path)


def build(source_path, supplied_manifest, cache_db=None, checkpoint_path=None,
          correction_overlay=None):
    source_sha = _verified_source(source_path, supplied_manifest, SOURCE_NAME)
    if (cache_db or correction_overlay) and not checkpoint_path:
        raise ValueError("checkpoint source required for saved cache or corrections")
    labels, evidence = _cache_index(cache_db, checkpoint_path, supplied_manifest)
    corrections, overlay_sha = _corrections(correction_overlay, checkpoint_path, supplied_manifest)
    first_text, seen_ids, rows = {}, set(), []
    for position, row in enumerate(_rows(source_path), 1):
        if position > LIMIT:
            break
        review_id, review_text = row["review_id"], row["review_text"]
        if not review_id or review_id in seen_ids:
            raise ValueError("first 5000 IDs must be present and distinct")
        seen_ids.add(review_id)
        original = first_text.setdefault(review_text, review_id)
        correction = corrections.get(review_id)
        rows.append({
            "review_id": review_id,
            "source_position": position,
            "text": review_text,
            "source_sha256": row_sha256([row[field] for field in SOURCE_FIELDS]),
            "text_sha256": text_sha256(review_text),
            "duplicate_of_review_id": original if original != review_id else None,
            "label_cache_key": cache_key(label_config(), review_text),
            "saved500_label_source_id": labels.get(review_text),
            # The historic evidence ledger omits schema and effort identity.
            # This is a candidate reference, never automatic permission to reuse.
            "saved500_evidence_candidate_source_id": evidence.get(review_text),
            "human_topic_correction": ({"source_review_id": review_id,
                                        "overlay_sha256": overlay_sha,
                                        "status": "development_only_unpromoted"}
                                       if correction else None),
        })
    if len(rows) != LIMIT:
        raise ValueError("source has fewer than 5000 rows")
    return {"schema_version": SCHEMA_VERSION,
            "source_file": SOURCE_NAME, "source_file_sha256": source_sha,
            "selected_rows": LIMIT, "label_config": label_config(),
            "label_config_hash": config_hash(label_config()),
            "evidence_config": {"model": EVIDENCE_MODEL, "prompt_version": EVIDENCE_PROMPT,
                                "output_schema_sha256": hashlib.sha256(json.dumps(
                                    EVIDENCE_SCHEMA, sort_keys=True, separators=(",", ":")
                                ).encode("utf-8")).hexdigest()},
            "evidence_cache_status": "candidate_only_historic_schema_and_effort_not_recorded",
            "saved500_source_file_sha256": (_verified_source(checkpoint_path, supplied_manifest,
                                                              CHECKPOINT_NAME) if cache_db else None),
            "human_correction_overlay_sha256": overlay_sha,
            "human_correction_overlay_status": ("development_only_unpromoted; four source-verified "
                                                "corrections; unreviewed rows are not agreement"
                                                if correction_overlay else None),
            "counts": {"distinct_texts": len(first_text),
                       "exact_text_duplicates": LIMIT - len(first_text),
                       "saved500_label_matches": sum(x["saved500_label_source_id"] is not None for x in rows),
                       "saved500_evidence_candidates": sum(
                           x["saved500_evidence_candidate_source_id"] is not None for x in rows),
                       "human_corrections_in_selection": sum(x["human_topic_correction"] is not None for x in rows)},
            "rows": rows}


def write_manifest(path, manifest):
    """Publish atomically; identical reruns do not modify the existing file."""
    target = Path(path)
    if target.parent.name != "local":
        raise ValueError("private manifest must be written under a local/ directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError("existing manifest differs; choose a new output path")
        return digest, False
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--supplied-manifest", required=True)
    parser.add_argument("--checkpoint-source")
    parser.add_argument("--saved500-db")
    parser.add_argument("--human-correction-overlay")
    parser.add_argument("--out", default="local/checkpoint5000_manifest.json")
    args = parser.parse_args()
    manifest = build(args.input, args.supplied_manifest, args.saved500_db,
                     args.checkpoint_source, args.human_correction_overlay)
    digest, created = write_manifest(args.out, manifest)
    print(json.dumps({"status": "created" if created else "identical_existing",
                      "manifest_sha256": digest, **manifest["counts"],
                      "selected_rows": manifest["selected_rows"]}, sort_keys=True))


if __name__ == "__main__":
    main()

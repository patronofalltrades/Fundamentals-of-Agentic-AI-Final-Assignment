"""Freeze source positions 5,001–10,000 for the next checkpoint, offline."""

import csv
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline.jev import label_config
from tools.checkpoint5000_dispatch import DATASET
from tools.deepinfra_recheck100 import config_sha as evidence_config_sha

SOURCE = Path(DATASET) / "spotify_reviews_18months.csv"
SUPPLIED = Path(DATASET) / "manifest.json"
PREVIOUS = Path("local/checkpoint5000_manifest.json")
OUT = Path("local/next5000_manifest.json")


def build(source, supplied, previous, budget_path):
    with open(supplied, encoding="utf-8") as stream:
        entry = json.load(stream)["files"][source.name]
    source_sha = file_sha256(str(source))
    if source_sha != entry["sha256"] or source.stat().st_size != entry["bytes"]:
        raise ValueError("full source differs from supplied manifest")
    with open(previous, encoding="utf-8") as stream:
        old = json.load(stream)
    if old["selected_rows"] != 5000 or old["source_file_sha256"] != source_sha or \
            [r["source_position"] for r in old["rows"]] != list(range(1, 5001)):
        raise ValueError("first-5,000 selection differs")
    old_ids = {r["review_id"] for r in old["rows"]}
    with sqlite3.connect("file:" + os.path.abspath(budget_path) + "?mode=ro", uri=True) as db:
        uncertain_texts = {r[0] for r in db.execute("""SELECT DISTINCT r.review_text
            FROM checkpoint_rows r JOIN checkpoint_request_members m USING(review_id)
            JOIN checkpoint_requests q USING(request_key) WHERE q.stage='evidence'
            AND q.status='uncertain'""")}
    rows = []
    with open(source, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("source columns differ from contract")
        for position, row in enumerate(reader, 1):
            if position < 5001:
                continue
            if position > 10000:
                break
            if None in row or any(not isinstance(row[k], str) for k in SOURCE_FIELDS):
                raise ValueError("malformed source row")
            if not row["review_text"].strip():
                raise ValueError("selected source review has empty text")
            rows.append({"source_position": position, **row,
                "source_sha256": row_sha256([row[k] for k in SOURCE_FIELDS]),
                "text_sha256": text_sha256(row["review_text"]),
                "blocked_prior_uncertainty": row["review_text"] in uncertain_texts})
    if len(rows) != 5000 or len({r["review_id"] for r in rows}) != 5000 or \
            old_ids.intersection(r["review_id"] for r in rows):
        raise ValueError("next-5,000 source selection overlaps or differs")
    return {"schema_version": "next5000-manifest-v1",
        "source_file": source.name, "source_file_sha256": source_sha,
        "previous_manifest_sha256": file_sha256(str(previous)),
        "selected_rows": len(rows), "first_position": 5001, "last_position": 10000,
        "jev_config_sha256": config_hash(label_config()),
        "evidence_config_sha256": evidence_config_sha(),
        "rows": rows}


def main():
    if OUT.exists():
        raise FileExistsError("frozen next-5,000 manifest already exists")
    manifest = build(SOURCE, SUPPLIED, PREVIOUS, "local/project_budget.db")
    fd = os.open(str(OUT), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"manifest_sha256": file_sha256(str(OUT)),
        "selected_rows": 5000,
        "first500_blocked_prior_uncertainty": sum(r["blocked_prior_uncertainty"]
            for r in manifest["rows"][:500]),
        "first500_distinct_texts": len({r["review_text"] for r in manifest["rows"][:500]})},
        sort_keys=True))


if __name__ == "__main__":
    main()

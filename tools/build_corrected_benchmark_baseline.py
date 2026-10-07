"""Make an isolated development baseline from a validated human correction overlay.

Only corrections for the manifest-verified 100-row source are applied. The
original Jev database and human overlay are opened read-only and never edited.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import openrouter_extractor_benchmark as benchmark
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256


def build(source, manifest, original_db, overlay_path, expected_overlay_sha, output):
    output = Path(output)
    if output.exists() or output.resolve() == Path(original_db).resolve():
        raise ValueError("corrected baseline output must be a new path")
    raw = Path(overlay_path).read_bytes()
    overlay_sha = hashlib.sha256(raw).hexdigest()
    if overlay_sha != expected_overlay_sha:
        raise ValueError("human correction overlay SHA-256 differs")
    overlay = json.loads(raw)
    if overlay.get("metadata", {}).get("status") != "development_only_unpromoted":
        raise ValueError("overlay is not scoped to development review")
    corrections = overlay["corrections"]
    if len(corrections) != 4 or len({item["review_id"] for item in corrections}) != 4:
        raise ValueError("expected four distinct validated corrections")
    if any(item["source_document_sha256"] != overlay["metadata"]["input_sha256"]
           for item in corrections):
        raise ValueError("correction provenance differs from overlay source")
    rows = {row["review_id"]: row for row in benchmark.load_rows(source, manifest)}
    selected = [item for item in corrections if item["review_id"] in rows]
    if len(selected) != 1:
        raise ValueError("expected exactly one correction in the 100-row source")
    benchmark.load_baseline(str(original_db), list(rows.values()))
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".building")
    if temp.exists():
        raise ValueError("baseline build temp path already exists")
    try:
        with closing(sqlite3.connect("file:" + str(original_db) + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(temp)) as copied:
                original.backup(copied)
                copied.execute("PRAGMA journal_mode=DELETE")
                copied.execute("""CREATE TABLE human_corrections (
                    review_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
                    overlay_sha256 TEXT NOT NULL, original_label_json TEXT NOT NULL,
                    corrected_label_json TEXT NOT NULL, provenance_json TEXT NOT NULL)""")
                for item in selected:
                    row = rows[item["review_id"]]
                    source_hash = row_sha256([row[k] for k in SOURCE_FIELDS])
                    if item["source_sha256"] != source_hash:
                        raise ValueError("correction source hash differs")
                    if item["changed_fields"] != ["topic"] or set(item["human_correction"]) != {"topic"}:
                        raise ValueError("only the reviewed topic correction is allowed")
                    saved = copied.execute("""SELECT label_json,config_hash,source_sha256
                        FROM results WHERE review_id=?""", (item["review_id"],)).fetchone()
                    if saved is None or saved[2] != source_hash:
                        raise ValueError("baseline row identity differs")
                    label = json.loads(saved[0])
                    if any(label[k] != item["original_model"][k]
                           for k in ("topic", "intent", "severity")):
                        raise ValueError("original model labels differ from validated overlay")
                    corrected = dict(label, topic=item["human_correction"]["topic"])
                    new_config = hashlib.sha256(json.dumps({
                        "original_config": saved[1], "overlay_sha256": overlay_sha,
                        "correction": item["human_correction"], "source_sha256": source_hash,
                    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    corrected_json = json.dumps(corrected, sort_keys=True)
                    copied.execute("UPDATE results SET label_json=?,config_hash=? WHERE review_id=?",
                                   (corrected_json, new_config, item["review_id"]))
                    copied.execute("INSERT INTO human_corrections VALUES (?,?,?,?,?,?)",
                                   (item["review_id"], source_hash, overlay_sha, saved[0],
                                    corrected_json, json.dumps(item["provenance"], sort_keys=True)))
                copied.execute("INSERT INTO meta(key,value) VALUES (?,?)",
                               ("benchmark_overlay_sha256", overlay_sha))
                copied.execute("INSERT INTO meta(key,value) VALUES (?,?)",
                               ("benchmark_baseline_scope", "corrected_development_100_only"))
                copied.commit()
        os.link(temp, output)  # Publish without overwriting an existing database.
    finally:
        if temp.exists():
            temp.unlink()
    return {"corrected_source_rows": len(selected), "source_rows": len(rows),
            "overlay_sha256": overlay_sha, "baseline_sha256": benchmark.file_sha256(output)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--original-db", required=True)
    p.add_argument("--overlay", required=True)
    p.add_argument("--overlay-sha256", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    print(json.dumps(build(a.source, a.manifest, a.original_db, a.overlay,
                           a.overlay_sha256, a.out), sort_keys=True))

"""Freeze exact source positions for the accepted-evidence target offline."""

import argparse
import csv
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline.jev import label_config
from tools import deepinfra_recheck100 as evidence
from tools.checkpoint5000_dispatch import legacy_paths
from tools.next5000_manifest import SOURCE, SUPPLIED, OUT as PREVIOUS, PREVIOUS as FIRST

OUT = Path("local/scale100k_manifest_v2.json")
SCHEMA = "spotify-scale100k-remaining90k-v2"
EXTENSION_OUT = Path("local/scale100k_extension_100001_120000.json")
EXTENSION_SCHEMA = "spotify-accepted100k-source-extension-v1"
EXTENSION_FIRST = 100001
EXTENSION_LAST = 120000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False)


def build(source, supplied, previous):
    with supplied.open(encoding="utf-8") as stream:
        entry = json.load(stream)["files"][source.name]
    if source.stat().st_size != entry["bytes"] or file_sha256(str(source)) != entry["sha256"]:
        raise ValueError("supplied source differs")
    with previous.open(encoding="utf-8") as stream:
        prior = json.load(stream)
    if prior["source_file_sha256"] != entry["sha256"] or prior["selected_rows"] != 5000:
        raise ValueError("previous checkpoint source differs")
    with FIRST.open(encoding="utf-8") as stream:
        first = json.load(stream)
    if first["source_file_sha256"] != entry["sha256"] or first["selected_rows"] != 5000:
        raise ValueError("first checkpoint source differs")
    existing_ids = {r["review_id"] for r in first["rows"] + prior["rows"]}
    if len(existing_ids) != 10000:
        raise ValueError("prior source IDs overlap")
    historical = legacy_paths()["benchmark"]
    with sqlite3.connect("file:" + os.path.abspath(historical) + "?mode=ro", uri=True) as db:
        held = {rid: source_sha for rid, source_sha in db.execute(
            "SELECT review_id,source_sha FROM calls WHERE status='reconciled_no_visible_bill'")}
    if len(held) != 1:
        raise ValueError("historical uncertain benchmark membership differs")
    # Keep every source ID and hash, including empty texts and texts that may
    # later be excluded by the durable queue's uncertainty rules.
    rows = []
    historical_texts = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("source fields differ")
        for position, row in enumerate(reader, 1):
            if None in row or any(not isinstance(row[field], str) for field in SOURCE_FIELDS):
                raise ValueError("malformed source row")
            if row["review_id"] in held:
                if row_sha256([row[field] for field in SOURCE_FIELDS]) != held[row["review_id"]]:
                    raise ValueError("historical uncertain source hash differs")
                historical_texts.append(row["review_text"])
            if position <= 10000:
                continue
            if position > 100000:
                continue
            if row["review_id"] in existing_ids:
                raise ValueError("duplicate source ID across checkpoints")
            existing_ids.add(row["review_id"])
            rows.append({"source_position": position, **row,
                "source_sha256": row_sha256([row[field] for field in SOURCE_FIELDS]),
                "text_sha256": text_sha256(row["review_text"])})
    if len(rows) != 90000 or len(existing_ids) != 100000 or len(historical_texts) != len(held):
        raise ValueError("remaining 90,000 selection differs")
    return {"schema_version": SCHEMA, "source_file": source.name,
        "source_file_sha256": entry["sha256"],
        "previous_manifest_sha256": file_sha256(str(previous)),
        "selected_rows": 90000, "first_position": 10001,
        "last_position": 100000, "jev_config_sha256": config_hash(label_config()),
        "evidence_config_sha256": evidence.config_sha(),
        "historical_uncertain_exact_texts": historical_texts, "rows": rows}


def load_base():
    with OUT.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema_version") != SCHEMA or manifest.get("selected_rows") != 90000 or \
            manifest.get("jev_config_sha256") != config_hash(label_config()) or \
            manifest.get("evidence_config_sha256") != evidence.config_sha() or \
            manifest.get("previous_manifest_sha256") != file_sha256(str(PREVIOUS)):
        raise ValueError("frozen scale manifest differs")
    rows = manifest["rows"]
    if len(rows) != 90000 or len({r["review_id"] for r in rows}) != 90000:
        raise ValueError("scale manifest IDs differ")
    if len(manifest.get("historical_uncertain_exact_texts", [])) != 1:
        raise ValueError("historical uncertain exact text missing")
    for position, row in enumerate(rows, 10001):
        if row["source_position"] != position or \
                row_sha256([row[field] for field in SOURCE_FIELDS]) != row["source_sha256"] or \
                text_sha256(row["review_text"]) != row["text_sha256"]:
            raise ValueError("scale manifest row differs")
    return manifest, file_sha256(str(OUT))


def build_extension(source, supplied, base_manifest, base_sha, prior_ids):
    """Freeze two optional 10k gates; activation still occurs one gate at a time."""
    with supplied.open(encoding="utf-8") as stream:
        entry = json.load(stream)["files"][source.name]
    if source.stat().st_size != entry["bytes"] or file_sha256(str(source)) != entry["sha256"] or \
            base_manifest["source_file_sha256"] != entry["sha256"]:
        raise ValueError("extension source differs from frozen base")
    seen = set(prior_ids) | {r["review_id"] for r in base_manifest["rows"]}
    if len(seen) != EXTENSION_FIRST - 1:
        raise ValueError("first 100,000 source IDs overlap")
    rows = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise ValueError("source fields differ")
        for position, row in enumerate(reader, 1):
            if position < EXTENSION_FIRST:
                continue
            if position > EXTENSION_LAST:
                break
            if None in row or any(not isinstance(row[field], str) for field in SOURCE_FIELDS):
                raise ValueError("malformed extension source row")
            if row["review_id"] in seen:
                raise ValueError("extension source ID repeats")
            seen.add(row["review_id"])
            rows.append({"source_position": position, **row,
                "source_sha256": row_sha256([row[field] for field in SOURCE_FIELDS]),
                "text_sha256": text_sha256(row["review_text"])})
    if len(rows) != EXTENSION_LAST - EXTENSION_FIRST + 1:
        raise ValueError("extension source length differs")
    return {"schema_version": EXTENSION_SCHEMA, "base_manifest_sha256": base_sha,
        "source_file_sha256": entry["sha256"], "selected_rows": len(rows),
        "first_position": EXTENSION_FIRST, "last_position": EXTENSION_LAST,
        "rows": rows}


def load_extension(base_manifest, base_sha, prior_ids=()):
    with EXTENSION_OUT.open(encoding="utf-8") as stream:
        extension = json.load(stream)
    if extension.get("schema_version") != EXTENSION_SCHEMA or \
            extension.get("base_manifest_sha256") != base_sha or \
            extension.get("source_file_sha256") != base_manifest["source_file_sha256"] or \
            extension.get("selected_rows") != EXTENSION_LAST - EXTENSION_FIRST + 1 or \
            extension.get("first_position") != EXTENSION_FIRST or \
            extension.get("last_position") != EXTENSION_LAST:
        raise ValueError("frozen extension identity differs")
    rows = extension["rows"]
    seen = set(prior_ids) | {r["review_id"] for r in base_manifest["rows"]}
    if len(seen) != EXTENSION_FIRST - 1:
        raise ValueError("first 100,000 source IDs overlap")
    if len(rows) != EXTENSION_LAST - EXTENSION_FIRST + 1:
        raise ValueError("extension row count differs")
    for position, row in enumerate(rows, EXTENSION_FIRST):
        if row["source_position"] != position or row["review_id"] in seen or \
                row_sha256([row[field] for field in SOURCE_FIELDS]) != row["source_sha256"] or \
                text_sha256(row["review_text"]) != row["text_sha256"]:
            raise ValueError("frozen extension row differs")
        seen.add(row["review_id"])
    return extension, file_sha256(str(EXTENSION_OUT))


def load():
    manifest, base_sha = load_base()
    if EXTENSION_OUT.exists():
        prior_ids = set()
        for prior_path in (FIRST, PREVIOUS):
            with prior_path.open(encoding="utf-8") as stream:
                prior_ids.update(r["review_id"] for r in json.load(stream)["rows"])
        extension, extension_sha = load_extension(manifest, base_sha, prior_ids)
        manifest["rows"] += extension["rows"]
        manifest["selected_rows"] += extension["selected_rows"]
        manifest["last_position"] = extension["last_position"]
        manifest["extension_manifest_sha256"] = extension_sha
    return manifest, base_sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extend", action="store_true",
        help="freeze optional positions 100,001–120,000 without activating them")
    args = parser.parse_args()
    if args.extend:
        if EXTENSION_OUT.exists():
            raise FileExistsError("frozen source extension already exists")
        base, base_sha = load_base()
        prior_ids = set()
        for prior_path in (FIRST, PREVIOUS):
            with prior_path.open(encoding="utf-8") as stream:
                prior_ids.update(r["review_id"] for r in json.load(stream)["rows"])
        extension = build_extension(SOURCE, SUPPLIED, base, base_sha, prior_ids)
        fd = os.open(str(EXTENSION_OUT), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(extension) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(canonical({"selected_rows": extension["selected_rows"],
            "manifest_sha256": file_sha256(str(EXTENSION_OUT)),
            "empty_text_rows": sum(not r["review_text"].strip() for r in extension["rows"])}))
        return
    if OUT.exists():
        raise FileExistsError("frozen scale manifest already exists")
    manifest = build(SOURCE, SUPPLIED, PREVIOUS)
    fd = os.open(str(OUT), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(canonical(manifest) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(canonical({"selected_rows": 90000, "manifest_sha256": file_sha256(str(OUT)),
        "empty_text_rows": sum(not r["review_text"].strip() for r in manifest["rows"])}))


if __name__ == "__main__":
    main()

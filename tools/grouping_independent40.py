"""Prepare a blind local human grouping check disjoint from design and pilot."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from tools.issue_catalog_sample import TOPICS
from tools.issue_grouping_handoff import FRAME_SHA256, LOCAL_DIR, private_json, sha256


DESIGN_SHA256 = "7d43c088c0d5f0988b532b82c3630c4fcdcf7213c7ab8259efcee39b4cf4a8a9"
PILOT_SHA256 = "d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c"
SCHEMA = "spotify-grouping-independent40-v1"


def freeze(frame, design, pilot):
    if frame.get("schema_version") != "spotify-issue-grouping-frame-v1" or \
            len(frame.get("rows", [])) != 30403 or \
            len(design.get("rows", [])) != 64 or \
            len(pilot.get("rows", [])) != 100:
        raise ValueError("frozen input shapes differ")
    prior = design["rows"] + pilot["rows"]
    prior_ids = {row["review_id"] for row in prior}
    prior_texts = {row["source_text"] for row in prior}
    selected, chosen_ids, chosen_texts = [], set(), set()
    for topic in TOPICS:
        candidates = sorted((row for row in frame["rows"] if row["topic"] == topic),
            key=lambda row: hashlib.sha256(("independent-grouping40-v1:" +
                                            row["review_id"]).encode()).digest())
        selected_topic = 0
        for row in candidates:
            if row["review_id"] in prior_ids | chosen_ids or \
                    row["source_text"] in prior_texts | chosen_texts:
                continue
            selected.append({"case_ref": "H%02d" % (len(selected) + 1), **row})
            chosen_ids.add(row["review_id"])
            chosen_texts.add(row["source_text"])
            selected_topic += 1
            if selected_topic == 5:
                break
        if selected_topic != 5:
            raise ValueError("cannot fill disjoint topic stratum")
    if len(selected) != 40 or len(chosen_ids) != 40 or len(chosen_texts) != 40:
        raise ValueError("independent sample is not unique")
    return selected


def write_blind_csv(path, selected):
    if os.path.commonpath([str(LOCAL_DIR), str(path.resolve())]) != str(LOCAL_DIR):
        raise ValueError("private output must stay under local/")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_ref", "source_text",
            "independent_issue_id", "evidence_rationale", "uncertainty_notes"))
        writer.writeheader()
        for row in selected:
            writer.writerow({"case_ref": row["case_ref"],
                "source_text": row["source_text"], "independent_issue_id": "",
                "evidence_rationale": "", "uncertainty_notes": ""})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("frame", "design", "pilot", "blind_out", "manifest_out"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    for path, digest in ((args.frame, FRAME_SHA256), (args.design, DESIGN_SHA256),
                         (args.pilot, PILOT_SHA256)):
        if sha256(path) != digest:
            raise ValueError("frozen input digest differs: " + path.name)
    selected = freeze(json.loads(args.frame.read_text(encoding="utf-8")),
        json.loads(args.design.read_text(encoding="utf-8")),
        json.loads(args.pilot.read_text(encoding="utf-8")))
    write_blind_csv(args.blind_out, selected)
    manifest = {"schema_version": SCHEMA, "status": "human_semantic_check_pending",
        "source_frame_sha256": FRAME_SHA256, "design_sha256": DESIGN_SHA256,
        "pilot_sha256": PILOT_SHA256,
        "blind_csv_sha256": sha256(args.blind_out),
        "selection": "five per saved topic by deterministic hash; no matching original ID or exact text in 64 design or 100 pilot cases",
        "rows": [{"case_ref": row["case_ref"], "review_id": row["review_id"],
            "source_sha256": row["source_sha256"], "saved_topic": row["topic"],
            "source_text": row["source_text"], "saved_exact_evidence": row["evidence"]}
            for row in selected]}
    private_json(args.manifest_out, manifest)
    print(json.dumps({"cases": 40, "blind_sha256": sha256(args.blind_out),
        "manifest_sha256": sha256(args.manifest_out),
        "human_semantic_check": "pending"}, sort_keys=True))


if __name__ == "__main__":
    main()

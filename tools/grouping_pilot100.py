"""Freeze a private, disjoint 100-case issue-mapping pilot; no model calls."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.issue_catalog_sample import TOPICS
from tools.issue_grouping_handoff import FRAME_SHA256, private_json, sha256


DESIGN_SHA256 = "7d43c088c0d5f0988b532b82c3630c4fcdcf7213c7ab8259efcee39b4cf4a8a9"
SCHEMA = "spotify-issue-grouping-pilot100-v1"


def freeze(frame, design):
    if frame.get("schema_version") != "spotify-issue-grouping-frame-v1" or \
            len(frame.get("rows", [])) != 30403 or \
            design.get("schema_version") != "spotify-issue-catalog-sample-v1" or \
            len(design.get("rows", [])) != 64:
        raise ValueError("input frame or design sample differs")
    forbidden_ids = {row["review_id"] for row in design["rows"]}
    forbidden_texts = {row["source_text"] for row in design["rows"]}
    seen_ids, seen_texts, selected = set(forbidden_ids), set(forbidden_texts), []

    def add(stratum, candidates, count):
        ordered = sorted(candidates, key=lambda row: hashlib.sha256(
            ("grouping-pilot100-v1:" + row["review_id"]).encode()).digest())
        chosen = 0
        for row in ordered:
            if row["review_id"] in seen_ids or row["source_text"] in seen_texts:
                continue
            seen_ids.add(row["review_id"])
            seen_texts.add(row["source_text"])
            selected.append({"pilot_index": len(selected) + 1, "stratum": stratum, **row})
            chosen += 1
            if chosen == count:
                break
        if chosen != count:
            raise ValueError("cannot fill disjoint pilot stratum: " + stratum)

    rows = frame["rows"]
    for topic in TOPICS:
        add("topic:" + topic, (row for row in rows if row["topic"] == topic), 8)
    add("cancellation", (row for row in rows if row["intent"] == "cancellation"), 16)
    add("severity5", (row for row in rows if row["severity"] == 5), 10)
    add("known_semantic_flag", (row for row in rows if row["known_semantic_flag"]), 10)
    if len(selected) != 100 or len({r["review_id"] for r in selected}) != 100 or \
            len({r["source_text"] for r in selected}) != 100:
        raise ValueError("pilot is not 100 unique IDs and texts")
    return {"schema_version": SCHEMA, "status": "pilot_input_only",
        "grouping_frame_sha256": FRAME_SHA256, "design_sample_sha256": DESIGN_SHA256,
        "selection": "SHA-256 rank of grouping-pilot100-v1: plus original ID; unique exact texts and IDs; 8 per topic, 16 cancellation, 10 severity5, 10 flagged, all disjoint from design64",
        "strata": dict(sorted(Counter(r["stratum"] for r in selected).items())),
        "rows": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.frame) != FRAME_SHA256 or sha256(args.design) != DESIGN_SHA256:
        raise ValueError("frozen input digest differs")
    pilot = freeze(json.loads(args.frame.read_text(encoding="utf-8")),
                   json.loads(args.design.read_text(encoding="utf-8")))
    private_json(args.out, pilot)
    print(json.dumps({"pilot_rows": 100, "strata": pilot["strata"],
                      "pilot_sha256": sha256(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Freeze a small private, deterministic sample for issue-catalog design.

The input is the validated private grouping frame. This never maps membership.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.issue_grouping_handoff import FRAME_SHA256, private_json, sha256


TOPICS = ("access", "billing", "catalog", "downloads", "other", "playback",
          "support", "usability")
SAMPLE_SCHEMA = "spotify-issue-catalog-sample-v1"


def freeze(frame):
    if frame.get("schema_version") != "spotify-issue-grouping-frame-v1" or \
            len(frame.get("rows", [])) != 30403:
        raise ValueError("grouping frame identity differs")
    rows = frame["rows"]
    seen, selected = set(), []

    def add(stratum, candidates, count):
        ordered = sorted(candidates, key=lambda row: hashlib.sha256(
            ("issue-catalog-sample-v1:" + row["review_id"]).encode()).digest())
        chosen = 0
        for row in ordered:
            if row["review_id"] in seen:
                continue
            seen.add(row["review_id"])
            selected.append({"stratum": stratum, **row})
            chosen += 1
            if chosen == count:
                break
        if chosen != count:
            raise ValueError("sample stratum cannot be filled")

    for topic in TOPICS:
        add("topic:" + topic, (row for row in rows if row["topic"] == topic), 5)
    add("cancellation", (row for row in rows if row["intent"] == "cancellation"), 8)
    add("severity5", (row for row in rows if row["severity"] == 5), 8)
    add("known_semantic_flag", (row for row in rows if row["known_semantic_flag"]), 8)
    counts = Counter(row["stratum"] for row in selected)
    if len(selected) != 64 or len({row["review_id"] for row in selected}) != 64:
        raise ValueError("sample IDs repeat")
    return {"schema_version": SAMPLE_SCHEMA, "source_frame_sha256": FRAME_SHA256,
        "selection": "SHA-256 rank of issue-catalog-sample-v1: plus original ID; unique, five per topic plus eight each cancellation, severity5, flagged",
        "strata": dict(sorted(counts.items())), "rows": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.frame) != FRAME_SHA256:
        raise ValueError("frozen grouping frame digest differs")
    sample = freeze(json.loads(args.frame.read_text(encoding="utf-8")))
    private_json(args.out, sample)
    print(json.dumps({"sample_rows": 64, "strata": sample["strata"],
                      "sample_sha256": sha256(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()

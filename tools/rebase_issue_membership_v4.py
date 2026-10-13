"""Drop the three human-corrected non-complaints from Claude's frozen map."""

import argparse
import csv
import json
import os
from pathlib import Path

from tools.issue_grouping_handoff import LOCAL_DIR, sha256


SOURCE_SHA256 = "bbc0c84ce046d82215744838107d4e699c0399d0dbcad6a644ece8138233098f"
FRAME_SHA256 = "afa34a49dca3e80188d85bdb86607d234b628275b62ed2be6b8a9d60e0865787"
CORRECTIONS_SHA256 = "0411331243627624e46c1bc78decd3613fe348a64290171a7a1b5bae810bafa5"
CATALOG_SHA256 = "8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111"


def rebase(source_rows, frame, corrections, catalog):
    if frame.get("schema_version") != "spotify-issue-grouping-frame-v4" or \
            frame.get("baseline_candidates") != 30400 or \
            frame.get("public_candidates") != 30377 or \
            catalog.get("status") != "approved":
        raise ValueError("corrected frame or catalog differs")
    kept = {row["review_id"] for row in frame["rows"]}
    removed_rows = [row for row in corrections["rows"]
                    if row["pilot_index"] in {18, 80, 97}]
    removed = {row["review_id"] for row in removed_rows}
    issues = {row["issue_id"] for row in catalog["issues"]}
    if len(kept) != 30400 or len(removed) != 3 or len(issues) != 41 or \
            {row["pilot_index"] for row in removed_rows} != {18, 80, 97}:
        raise ValueError("correction coverage differs")
    seen, output = set(), []
    for row in source_rows:
        if set(row) != {"issue_id", "review_id"} or \
                row["review_id"] in seen or row["issue_id"] not in issues:
            raise ValueError("source membership invalid")
        seen.add(row["review_id"])
        if row["review_id"] in kept:
            output.append(row)
    if len(source_rows) != 30403 or seen != kept | removed or kept & removed or \
            len(output) != 30400:
        raise ValueError("source membership does not match corrected frame")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path, digest in ((args.source, SOURCE_SHA256), (args.frame, FRAME_SHA256),
                         (args.corrections, CORRECTIONS_SHA256),
                         (args.catalog, CATALOG_SHA256)):
        if sha256(path) != digest:
            raise ValueError("frozen input digest differs: " + path.name)
    if args.out.exists() or args.out.resolve().parent != LOCAL_DIR:
        raise ValueError("output must be new and under local/")
    with args.source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["issue_id", "review_id"]:
            raise ValueError("source membership columns differ")
        source_rows = list(reader)
    result = rebase(source_rows,
        json.loads(args.frame.read_text(encoding="utf-8")),
        json.loads(args.corrections.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")))
    fd = os.open(str(args.out), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("issue_id", "review_id"))
        writer.writeheader()
        writer.writerows(result)
    print(json.dumps({"source_memberships": 30403, "removed": 3,
        "corrected_memberships": len(result), "membership_sha256": sha256(args.out)},
        sort_keys=True))


if __name__ == "__main__":
    main()

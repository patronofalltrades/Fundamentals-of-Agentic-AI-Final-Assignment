"""Rank a complete, reviewed v4 one-primary-issue membership offline."""

import argparse
from collections import defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

from tools.issue_grouping_handoff import LOCAL_DIR, private_json, sha256


FRAME_SHA256 = "afa34a49dca3e80188d85bdb86607d234b628275b62ed2be6b8a9d60e0865787"
CATALOG_SHA256 = "8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111"


def rank(frame, catalog, memberships):
    if frame.get("schema_version") != "spotify-issue-grouping-frame-v4" or \
            frame.get("membership_rule") != "one_issue_per_record" or \
            catalog.get("status") != "approved" or \
            frame.get("mapping_rule_version") != catalog.get("mapping_rule_version"):
        raise ValueError("corrected frame or approved catalog differs")
    records = {row["review_id"]: row for row in frame["rows"]}
    issues = {row["issue_id"]: row for row in catalog["issues"]}
    if len(records) != len(frame["rows"]) or len(issues) != len(catalog["issues"]) or \
            len(records) != frame["baseline_candidates"] or \
            sum(not row["known_semantic_flag"] for row in records.values()) != \
            frame["public_candidates"] or \
            any(row["intent"] not in {"complaint", "cancellation"}
                for row in records.values()):
        raise ValueError("corrected frame coverage differs")
    assigned = {}
    for item in memberships:
        if set(item) != {"issue_id", "review_id"}:
            raise ValueError("membership columns differ")
        rid, issue_id = item["review_id"], item["issue_id"]
        if rid not in records or issue_id not in issues or rid in assigned:
            raise ValueError("foreign, repeated, or unknown issue membership")
        assigned[rid] = issue_id
    if set(assigned) != set(records):
        raise ValueError("every candidate needs exactly one membership")

    def one_projection(include_flagged):
        counts, sums = defaultdict(int), defaultdict(int)
        for rid, issue_id in assigned.items():
            row = records[rid]
            if not include_flagged and row["known_semantic_flag"]:
                continue
            counts[issue_id] += 1
            sums[issue_id] += row["severity"]
        if sum(counts.values()) != (frame["baseline_candidates"] if include_flagged
                                  else frame["public_candidates"]):
            raise ValueError("ranking denominator differs")
        results = []
        for issue_id, count in counts.items():
            score = sums[issue_id]
            results.append({"issue_id": issue_id,
                "title": issues[issue_id]["title"], "complaint_count": count,
                "severity_sum": score, "priority_score": score,
                "mean_severity": str((Decimal(score) / Decimal(count)).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP))})
        results.sort(key=lambda item: (-item["priority_score"], item["issue_id"]))
        for position, item in enumerate(results, 1):
            item["rank"] = position
        return results

    return {"schema_version": "spotify-issue-ranking-v4",
        "status": "ranked_from_complete_reviewed_membership",
        "baseline_denominator": frame["baseline_candidates"],
        "public_denominator": frame["public_candidates"],
        "known_flagged_excluded_from_public": frame["known_flagged_candidates"],
        "mapping_rule_version": frame["mapping_rule_version"],
        "baseline": one_projection(True),
        "public_advisory": one_projection(False)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.frame) != FRAME_SHA256 or \
            sha256(args.catalog) != CATALOG_SHA256:
        raise ValueError("corrected frame or catalog digest differs")
    if args.out.exists() or args.out.resolve().parent != LOCAL_DIR:
        raise ValueError("ranking output must be a new file under local/")
    with args.membership.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["issue_id", "review_id"]:
            raise ValueError("membership CSV columns differ")
        memberships = list(reader)
    result = rank(json.loads(args.frame.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")), memberships)
    result["frame_sha256"] = FRAME_SHA256
    result["catalog_sha256"] = CATALOG_SHA256
    result["membership_sha256"] = sha256(args.membership)
    private_json(args.out, result)
    print(json.dumps({"baseline_denominator": result["baseline_denominator"],
        "public_denominator": result["public_denominator"],
        "ranking_sha256": sha256(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()

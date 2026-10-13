"""Validate provisional offline issue assignments and build private review pack."""

import argparse
from collections import Counter
import json
from pathlib import Path

from tools.grouping_pilot100 import SCHEMA as PILOT_SCHEMA
from tools.issue_grouping_handoff import private_json, sha256


def validate(pilot, catalog, assignments):
    if pilot.get("schema_version") != PILOT_SCHEMA or len(pilot.get("rows", [])) != 100:
        raise ValueError("pilot input differs")
    if catalog.get("schema_version") != "spotify-issue-catalog-v1" or \
            catalog.get("status") != "pilot_authorized":
        raise ValueError("pilot catalog status differs")
    issues = {item["issue_id"] for item in catalog["issues"]}
    if len(issues) != len(catalog["issues"]):
        raise ValueError("catalog issue IDs repeat")
    if assignments.get("schema_version") != "spotify-issue-pilot-assignments-v1" or \
            assignments.get("reviewer_type") != "model_assisted_offline" or \
            len(assignments.get("rows", [])) != 100:
        raise ValueError("provisional assignments differ")
    by_index = {}
    for row in assignments["rows"]:
        index = row["pilot_index"]
        issue = row["provisional_issue_id"]
        alternatives = row["alternative_issue_ids"]
        ambiguity = row["ambiguity_reason"]
        if index in by_index or type(index) is not int or not 1 <= index <= 100 or \
                (issue is not None and issue not in issues) or \
                not isinstance(alternatives, list) or any(x not in issues or x == issue
                    for x in alternatives) or len(alternatives) != len(set(alternatives)) or \
                not isinstance(row["evidence_rationale"], str) or \
                not row["evidence_rationale"].strip() or \
                (issue is None and not ambiguity) or \
                (ambiguity is not None and not isinstance(ambiguity, str)):
            raise ValueError("invalid provisional assignment")
        by_index[index] = row
    if set(by_index) != set(range(1, 101)):
        raise ValueError("pilot assignment coverage differs")
    review, issue_counts, status_counts = [], Counter(), Counter()
    for source in pilot["rows"]:
        index = source["pilot_index"]
        row = by_index[index]
        issue = row["provisional_issue_id"]
        if issue is None:
            status_counts["abstain"] += 1
        else:
            status_counts["provisional_mapped"] += 1
            issue_counts[issue] += 1
        if source["known_semantic_flag"] or row["ambiguity_reason"] is not None:
            status_counts["review_cases"] += 1
            review.append({"pilot_index": index, "stratum": source["stratum"],
                "review_id": source["review_id"],
                "source_sha256": source["source_sha256"],
                "source_text": source["source_text"],
                "exact_saved_evidence": source["evidence"],
                "saved_topic": source["topic"], "saved_intent": source["intent"],
                "saved_severity": source["severity"],
                "known_semantic_flag": source["known_semantic_flag"],
                **row, "decision": None, "decision_notes": None})
    return {"schema_version": "spotify-issue-pilot-review-v1",
        "status": "human_decisions_pending", "not_human_verified": True,
        "decision_options": ["accept_provisional", "choose_alternative",
            "revise_catalog", "correct_saved_label", "leave_unresolved"],
        "summary": {"pilot_rows": 100, **dict(status_counts),
            "provisional_issue_counts": dict(sorted(issue_counts.items()))},
        "review_cases": review}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("pilot", "catalog", "assignments", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--priority-out", type=Path, required=True)
    args = parser.parse_args()
    pilot = json.loads(args.pilot.read_text(encoding="utf-8"))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    assignments = json.loads(args.assignments.read_text(encoding="utf-8"))
    output = validate(pilot, catalog, assignments)
    output["pilot_sha256"] = sha256(args.pilot)
    output["catalog_sha256"] = sha256(args.catalog)
    output["assignments_sha256"] = sha256(args.assignments)
    private_json(args.out, output)
    priority_indices = {r["pilot_index"] for r in output["review_cases"] if
        r["provisional_issue_id"] is None or r["known_semantic_flag"]}
    priority_indices.update((18, 29, 59, 61, 64))
    priority = [r for r in output["review_cases"] if r["pilot_index"] in priority_indices]
    if len(priority) != 25:
        raise ValueError("priority review coverage differs")
    private_json(args.priority_out, {"schema_version": "spotify-issue-pilot-priority-v1",
        "status": "human_decisions_pending", "not_human_verified": True,
        "selection": "all 10 abstentions, all 10 known semantic flags, and five boundary or label-conflict cases",
        "full_review_sha256": sha256(args.out),
        "decision_options": output["decision_options"], "review_cases": priority})
    print(json.dumps({"summary": output["summary"], "review_sha256": sha256(args.out)},
                     sort_keys=True))


if __name__ == "__main__":
    main()

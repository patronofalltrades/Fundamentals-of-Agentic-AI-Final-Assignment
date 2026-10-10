"""Freeze reviewed pilot decisions as an overlay; never mutate source labels."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.issue_grouping_handoff import private_json, sha256


PRIORITY_SHA256 = "2b7c3de775e127f58851324ecc69c55399d98c20846cab1060914c46439a8230"
CATALOG_SHA256 = "b5a567746906f1b892f4a8c7a213e976f3f8c67daf0b4502ae3a60a0fd2abc35"
PILOT_SHA256 = "d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c"
ASSIGNMENTS_SHA256 = "812765f07555a7cc4cf3a5092e5bb84d00c0a385a83de521f4ddcbf20ef761fa"
FULL_REVIEW_SHA256 = "1ac4f88de0e4519a2ac2eccc17b33124c45bd280939c5f3304094fcb72068432"
RULE_VERSION = "pilot-primary-problem-v2-20261010"
ALLOWED = {"accept_provisional", "choose_alternative", "correct_saved_label", "revise_catalog"}


def reconcile(catalog, pilot, assignments, full_review, priority_rows):
    if catalog.get("status") != "pilot_authorized" or \
            catalog.get("mapping_rule_version") != RULE_VERSION or \
            catalog["pilot_revision"]["production_approved"] is not False:
        raise ValueError("catalog is not pilot-only v2")
    issues = {item["issue_id"] for item in catalog["issues"]}
    if len(issues) != 41 or len(catalog["issues"]) != 41 or \
            catalog["pilot_revision"]["priority_decisions_sha256"] != PRIORITY_SHA256:
        raise ValueError("catalog or decision provenance differs")
    original = {row["pilot_index"]: row for row in assignments["rows"]}
    sources = {row["pilot_index"]: row for row in pilot["rows"]}
    if len(original) != 100 or len(sources) != 100 or \
            original[1]["provisional_issue_id"] != "ACC-LOGIN":
        raise ValueError("frozen pilot identity differs")
    review = {row["pilot_index"]: row for row in full_review["review_cases"]}
    priority_ids = set()
    decisions, pending, counts = [], [], Counter()
    for row in priority_rows:
        idx = int(row["pilot_index"])
        if idx in priority_ids or idx not in sources or \
                row["review_id"] != sources[idx]["review_id"] or \
                row["source_sha256"] != sources[idx]["source_sha256"] or \
                row["source_text"] != sources[idx]["source_text"] or \
                row["evidence_quote"] != sources[idx]["evidence"]["evidence_quote"] or \
                row["provisional_issue_id"] != (original[idx]["provisional_issue_id"] or ""):
            raise ValueError("priority decision source or frozen proposal differs")
        priority_ids.add(idx)
        kind = row["reviewer_decision"].strip()
        chosen = row["chosen_issue_id"].strip() or None
        note = row["decision_notes"].strip()
        if not kind:
            if chosen or note:
                raise ValueError("blank decision contains a choice or note")
            pending.append(idx)
            continue
        if kind not in ALLOWED or not note.startswith(
                "Claude proposal, confirmed by Hanif 2026-10-10:") or \
                (chosen is not None and chosen not in issues) or \
                (kind == "correct_saved_label" and idx == 80 and chosen is not None) or \
                (kind != "correct_saved_label" and chosen is None):
            raise ValueError("reviewed decision or chosen issue differs")
        counts[kind] += 1
        decisions.append({"pilot_index": idx, "decision_type": kind,
            "prior_provisional_issue_id": original[idx]["provisional_issue_id"],
            "reviewer_chosen_issue_id": chosen,
            "pilot_suggested_issue_id": None if kind == "correct_saved_label" else chosen,
            "label_correction_pending": kind == "correct_saved_label",
            "production_membership_issue_id": None,
            "known_semantic_flag": sources[idx]["known_semantic_flag"],
            "decision_notes": note})
    if len(priority_ids) != 25 or sorted(pending) != [29, 92, 97] or \
            dict(counts) != {"revise_catalog": 9, "correct_saved_label": 4,
                             "accept_provisional": 7, "choose_alternative": 2}:
        raise ValueError("priority decision totals differ")
    if len(review) != 53 or not priority_ids <= set(review):
        raise ValueError("full review frame differs")
    remaining = []
    for idx in sorted(set(review) - priority_ids):
        row = dict(review[idx])
        row["v1_provisional_issue_id"] = original[idx]["provisional_issue_id"]
        row["v2_pilot_suggested_issue_id"] = (
            "APP-LAUNCH" if idx == 1 else original[idx]["provisional_issue_id"])
        row["reviewer_decision"] = None
        row["chosen_issue_id"] = None
        row["decision_notes"] = None
        remaining.append(row)
    if len(remaining) != 28 or not any(row["pilot_index"] == 1 for row in remaining):
        raise ValueError("remaining review frame differs")
    overlay = {"schema_version": "spotify-issue-pilot-v2-overlay-v1",
        "status": "pilot_partial_decisions_not_production_membership",
        "mapping_rule_version": RULE_VERSION,
        "catalog_sha256": CATALOG_SHA256,
        "priority_decisions_sha256": PRIORITY_SHA256,
        "pilot_sha256": PILOT_SHA256,
        "base_assignments_sha256": ASSIGNMENTS_SHA256,
        "full_review_sha256": FULL_REVIEW_SHA256,
        "decision_provenance": "CSV notes state Claude proposal confirmed by Hanif 2026-10-10; direct yes approved listed catalog changes; both are retained without editing the CSV",
        "counts": {"recorded_priority_decisions": 22,
            "pilot_issue_suggestions_from_decisions": 18,
            "label_corrections_pending": 4,
            "priority_blanks": 3, "additional_review_cases": 28,
            "production_memberships": 0, **dict(counts)},
        "decisions": decisions, "unresolved_priority_indices": pending,
        "rule_propagations": [{"pilot_index": 1, "from_v1_issue_id": "ACC-LOGIN",
            "v2_pilot_suggested_issue_id": "APP-LAUNCH",
            "reason": "Approved splash-screen boundary from priority case 8; source never reaches a usable sign-in screen",
            "production_membership_issue_id": None}]}
    extra = {"schema_version": "spotify-issue-pilot-remaining28-v2",
        "status": "human_decisions_pending", "mapping_rule_version": RULE_VERSION,
        "pilot_sha256": PILOT_SHA256,
        "priority_decisions_sha256": PRIORITY_SHA256,
        "review_cases": remaining}
    return overlay, extra


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("catalog", "pilot", "assignments", "full_review", "priority_csv",
                "overlay_out", "remaining_out"):
        parser.add_argument("--" + key.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    for path, digest in ((args.catalog, CATALOG_SHA256), (args.pilot, PILOT_SHA256),
                         (args.assignments, ASSIGNMENTS_SHA256),
                         (args.full_review, FULL_REVIEW_SHA256),
                         (args.priority_csv, PRIORITY_SHA256)):
        if sha256(path) != digest:
            raise ValueError("frozen input digest differs: " + path.name)
    with args.priority_csv.open(newline="", encoding="utf-8") as stream:
        priority = list(csv.DictReader(stream))
    overlay, remaining = reconcile(
        json.loads(args.catalog.read_text(encoding="utf-8")),
        json.loads(args.pilot.read_text(encoding="utf-8")),
        json.loads(args.assignments.read_text(encoding="utf-8")),
        json.loads(args.full_review.read_text(encoding="utf-8")), priority)
    private_json(args.overlay_out, overlay)
    private_json(args.remaining_out, remaining)
    print(json.dumps({"counts": overlay["counts"],
        "overlay_sha256": sha256(args.overlay_out),
        "remaining_sha256": sha256(args.remaining_out)}, sort_keys=True))


if __name__ == "__main__":
    main()

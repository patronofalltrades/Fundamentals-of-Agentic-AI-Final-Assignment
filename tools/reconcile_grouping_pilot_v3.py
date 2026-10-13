"""Freeze pilot-v3 decisions from both private sheets without making membership."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from tools.issue_grouping_handoff import private_json, sha256


CATALOG_SHA256 = "f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b"
PILOT_SHA256 = "d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c"
ASSIGNMENTS_SHA256 = "812765f07555a7cc4cf3a5092e5bb84d00c0a385a83de521f4ddcbf20ef761fa"
FULL_REVIEW_SHA256 = "1ac4f88de0e4519a2ac2eccc17b33124c45bd280939c5f3304094fcb72068432"
V2_REMAINING_SHA256 = "fa733c40f17ad59c3500b4d04a0159dcaaad141efe6d8c4ffaa60dc8a0af6214"
V2_OVERLAY_SHA256 = "a2c2a5958b8beeceeb426c25e08cc35664e7038f0a8d31468669259e811c90a9"
PRIORITY_SHA256 = "a6201fd8ca1f394105b06977635a77b1f40bb80eadb1087bbfbc6543d130b3ae"
REMAINING_SHA256 = "897ebc95fc2913cd704de3a3168c854ecd735d22f3ce46a3cd0ed28f893f540f"
PRIORITY_BACKUP_SHA256 = "2b7c3de775e127f58851324ecc69c55399d98c20846cab1060914c46439a8230"
REMAINING_BACKUP_SHA256 = "a0a8633459f0f1c024da6d1350194c25eb3734242b96d3e6c4693c5dfa17c220"
RULE_VERSION = "pilot-primary-problem-v3-20261010"
ALLOWED = {"accept_provisional", "choose_alternative", "correct_saved_label", "revise_catalog"}
NOTE_PREFIX = "Claude proposal, confirmed by Hanif 2026-10-10:"
CORRECTION_CASES = {18, 43, 61, 80, 89, 94}
OPEN_CASES = {22, 29, 31, 81, 97}


def reconcile(catalog, pilot, assignments, full_review, v2_remaining,
              v2_overlay, priority_rows, remaining_rows):
    revision = catalog.get("v3_revision", {})
    if catalog.get("status") != "pilot_authorized" or \
            catalog.get("mapping_rule_version") != RULE_VERSION or \
            revision.get("production_approved") is not False or \
            revision.get("priority_decisions_sha256") != PRIORITY_SHA256 or \
            revision.get("remaining28_decisions_sha256") != REMAINING_SHA256 or \
            len(catalog.get("issues", [])) != 41:
        raise ValueError("catalog is not frozen pilot-only v3")
    issue_ids = {item["issue_id"] for item in catalog["issues"]}
    if len(issue_ids) != 41:
        raise ValueError("catalog issue IDs repeat")
    sources = {row["pilot_index"]: row for row in pilot["rows"]}
    original = {row["pilot_index"]: row for row in assignments["rows"]}
    review_ids = {row["pilot_index"] for row in full_review["review_cases"]}
    v2_remaining_by_index = {row["pilot_index"]: row
                             for row in v2_remaining["review_cases"]}
    if len(sources) != 100 or len(original) != 100 or len(review_ids) != 53 or \
            len(v2_remaining_by_index) != 28 or \
            v2_overlay["mapping_rule_version"] != "pilot-primary-problem-v2-20261010":
        raise ValueError("frozen pilot frames differ")
    if len(priority_rows) != 25 or len(remaining_rows) != 28:
        raise ValueError("decision sheet row count differs")

    entries, seen, counts = [], set(), Counter()
    for sheet, rows in (("priority", priority_rows), ("remaining", remaining_rows)):
        for row in rows:
            idx = int(row["pilot_index"])
            if idx in seen or idx not in review_ids or idx not in sources:
                raise ValueError("foreign or duplicate pilot decision")
            seen.add(idx)
            src, old = sources[idx], original[idx]
            expected = old["provisional_issue_id"] or ""
            if row["review_id"] != src["review_id"] or \
                    row["source_sha256"] != src["source_sha256"] or \
                    row["source_text"] != src["source_text"] or \
                    row["evidence_quote"] != src["evidence"]["evidence_quote"]:
                raise ValueError("decision source or exact evidence differs")
            if sheet == "priority":
                if row["provisional_issue_id"] != expected:
                    raise ValueError("priority v1 proposal differs")
                v2_suggestion = old["provisional_issue_id"]
            else:
                prior = v2_remaining_by_index.get(idx)
                if prior is None or row["v1_provisional_issue_id"] != expected or \
                        row["v2_pilot_suggested_issue_id"] != (
                            prior["v2_pilot_suggested_issue_id"] or ""):
                    raise ValueError("remaining v2 proposal differs")
                v2_suggestion = prior["v2_pilot_suggested_issue_id"]
            kind = row["reviewer_decision"].strip()
            chosen = row["chosen_issue_id"].strip() or None
            note = row["decision_notes"].strip()
            if not kind:
                if chosen or note:
                    raise ValueError("blank review case contains a choice")
                status = "human_decision_pending"
                suggestion = None
            else:
                if kind not in ALLOWED or not note.startswith(NOTE_PREFIX) or \
                        (chosen is not None and chosen not in issue_ids) or \
                        (kind != "correct_saved_label" and chosen is None):
                    raise ValueError("reviewed decision or chosen issue differs")
                if (idx in CORRECTION_CASES) != (kind == "correct_saved_label"):
                    raise ValueError("label-correction case changed type")
                if idx == 80 and chosen is not None:
                    raise ValueError("case 80 must not have an issue")
                if kind == "accept_provisional" and chosen != v2_suggestion:
                    raise ValueError("accepted proposal differs from frozen version")
                status = ("label_correction_pending" if kind == "correct_saved_label"
                          else "pilot_issue_suggestion_only")
                suggestion = None if kind == "correct_saved_label" else chosen
                counts[kind] += 1
            entries.append({"pilot_index": idx, "review_id": src["review_id"],
                "source_sha256": src["source_sha256"], "sheet": sheet,
                "v1_provisional_issue_id": old["provisional_issue_id"],
                "v2_pilot_suggested_issue_id": v2_suggestion,
                "reviewer_decision": kind or None, "reviewer_chosen_issue_id": chosen,
                "v3_pilot_suggested_issue_id": suggestion,
                "status": status, "known_semantic_flag": src["known_semantic_flag"],
                "production_membership_issue_id": None,
                "decision_note_sha256": (hashlib.sha256(note.encode()).hexdigest() if note else None)})
    if seen != review_ids or \
            {row["pilot_index"] for row in entries if row["status"] ==
             "human_decision_pending"} != OPEN_CASES or \
            {row["pilot_index"] for row in entries if row["status"] ==
             "label_correction_pending"} != CORRECTION_CASES or \
            dict(counts) != {"revise_catalog": 10, "correct_saved_label": 6,
                             "accept_provisional": 26, "choose_alternative": 6}:
        raise ValueError("decision coverage or type counts differ")
    lookup = {row["pilot_index"]: row for row in entries}
    if lookup[1]["v1_provisional_issue_id"] != "ACC-LOGIN" or \
            lookup[1]["v3_pilot_suggested_issue_id"] != "APP-LAUNCH" or \
            lookup[55]["v3_pilot_suggested_issue_id"] != "PLY-QUALITY" or \
            lookup[92]["v3_pilot_suggested_issue_id"] != "PLY-QUALITY" or \
            lookup[80]["v3_pilot_suggested_issue_id"] is not None:
        raise ValueError("approved rule-specific cases differ")
    return {"schema_version": "spotify-issue-pilot-v3-overlay-v1",
        "status": "pilot_partial_decisions_not_production_membership",
        "mapping_rule_version": RULE_VERSION,
        "catalog_sha256": CATALOG_SHA256,
        "priority_decisions_sha256": PRIORITY_SHA256,
        "remaining_decisions_sha256": REMAINING_SHA256,
        "priority_backup_sha256": PRIORITY_BACKUP_SHA256,
        "remaining_backup_sha256": REMAINING_BACKUP_SHA256,
        "v2_overlay_sha256": V2_OVERLAY_SHA256,
        "pilot_sha256": PILOT_SHA256,
        "base_assignments_sha256": ASSIGNMENTS_SHA256,
        "full_review_sha256": FULL_REVIEW_SHA256,
        "source_values_preserved": True,
        "not_human_accuracy_score": True,
        "counts": {"review_cases": 53, "recorded_decisions": 48,
            "pilot_issue_suggestions": 42, "label_corrections_pending": 6,
            "human_decisions_pending": 5, "production_memberships": 0,
            **dict(counts)},
        "open_indices": sorted(OPEN_CASES),
        "label_correction_indices": sorted(CORRECTION_CASES),
        "entries": sorted(entries, key=lambda row: row["pilot_index"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "pilot", "assignments", "full_review", "v2_remaining",
                 "v2_overlay", "priority_csv", "remaining_csv", "priority_backup",
                 "remaining_backup", "priority_input_backup", "remaining_input_backup",
                 "out"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    checks = ((args.catalog, CATALOG_SHA256), (args.pilot, PILOT_SHA256),
              (args.assignments, ASSIGNMENTS_SHA256),
              (args.full_review, FULL_REVIEW_SHA256),
              (args.v2_remaining, V2_REMAINING_SHA256),
              (args.v2_overlay, V2_OVERLAY_SHA256),
              (args.priority_csv, PRIORITY_SHA256),
              (args.remaining_csv, REMAINING_SHA256),
              (args.priority_backup, PRIORITY_BACKUP_SHA256),
              (args.remaining_backup, REMAINING_BACKUP_SHA256),
              (args.priority_input_backup, PRIORITY_SHA256),
              (args.remaining_input_backup, REMAINING_SHA256))
    for path, digest in checks:
        if sha256(path) != digest:
            raise ValueError("frozen input digest differs: " + path.name)
    with args.priority_csv.open(newline="", encoding="utf-8") as stream:
        priority_rows = list(csv.DictReader(stream))
    with args.remaining_csv.open(newline="", encoding="utf-8") as stream:
        remaining_rows = list(csv.DictReader(stream))
    output = reconcile(
        json.loads(args.catalog.read_text(encoding="utf-8")),
        json.loads(args.pilot.read_text(encoding="utf-8")),
        json.loads(args.assignments.read_text(encoding="utf-8")),
        json.loads(args.full_review.read_text(encoding="utf-8")),
        json.loads(args.v2_remaining.read_text(encoding="utf-8")),
        json.loads(args.v2_overlay.read_text(encoding="utf-8")),
        priority_rows, remaining_rows)
    private_json(args.out, output)
    print(json.dumps({"counts": output["counts"], "overlay_sha256": sha256(args.out)},
                     sort_keys=True))


if __name__ == "__main__":
    main()

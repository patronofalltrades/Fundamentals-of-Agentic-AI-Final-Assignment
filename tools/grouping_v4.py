"""Apply reviewed pilot corrections and freeze a corrected grouping frame.

All source text stays in private local files. CLI output is aggregate only.
This tool does not infer membership or change saved model results.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from spotify_pipeline.contract import INTENTS, TOPICS
from tools.grouping_label_correction_intake import validate as validate_six
from tools.issue_grouping_handoff import LOCAL_DIR, private_json, sha256
from tools.reconcile_grouping_pilot_v3 import OPEN_CASES


HASHES = {
    "pilot": "d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c",
    "v3_overlay": "b0a9e7457f6c202049c39515ac5b62a84e8cccb6a6ebaaf69eafbe95d0a2af83",
    "frame": "e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf",
    "six_sheet": "d7294f54b9121f26d3eed6874e759777067391c2cf8381240a905d0b83807016",
    "six_validated": "d3ff6dd9805de884bb030a130d87aed0f76edaa62c805dd613b70797e80ed786",
    "open_five": "58b5fe3014ad2eafaa659d23e59e765b94091098abaa5ba74ef5d4c79d79edcd",
    "catalog": "f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b",
    "approval": "594563a61699253200a7df18a019343ee7d9b8474c1c2c0fd22440912d6e5939",
}
RULE = "pilot-primary-problem-v3-20261010"


def _read_json(path, digest):
    if sha256(path) != digest:
        raise ValueError("frozen input digest differs: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path, digest):
    if sha256(path) != digest:
        raise ValueError("frozen input digest differs: " + path.name)
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def build(pilot, v3, frame, six_sheet, six_saved, open_five, catalog, approval):
    issue_ids = {row["issue_id"] for row in catalog["issues"]}
    if len(issue_ids) != 41 or approval.get("decision") != "approved_for_production_mapping" or \
            approval.get("catalog_sha256") != HASHES["catalog"] or \
            approval.get("mapping_rule_version") != RULE or \
            approval.get("issue_count") != 41 or set(approval.get("issue_ids", [])) != issue_ids:
        raise ValueError("catalog approval differs from frozen v3 catalog")
    if v3.get("mapping_rule_version") != RULE or \
            v3.get("counts", {}).get("recorded_decisions") != 48 or \
            frame.get("baseline_candidates") != 30403 or len(frame.get("rows", [])) != 30403:
        raise ValueError("frozen v3 or frame coverage differs")

    checked = validate_six(pilot, v3, six_sheet)
    checked["sheet_sha256"] = HASHES["six_sheet"]
    if checked["pending"] or checked["validated_not_applied"] != 6 or \
            checked["production_memberships"] or checked != six_saved:
        raise ValueError("six saved human corrections differ from revalidation")
    six = {row["pilot_index"]: row for row in checked["rows"]}
    sources = {row["pilot_index"]: row for row in pilot["rows"]}
    entries = {row["pilot_index"]: dict(row) for row in v3["entries"]}
    if len(sources) != 100 or len(entries) != 53 or len(open_five) != 5:
        raise ValueError("pilot source or decision coverage differs")
    seen = set()
    for row in open_five:
        idx = int(row["pilot_index"])
        if idx not in OPEN_CASES or idx in seen:
            raise ValueError("foreign or repeated open-five decision")
        seen.add(idx)
        old = entries[idx]
        if old["status"] != "human_decision_pending" or \
                row["sheet"] != old["sheet"] or \
                row["source_sha256"] != old["source_sha256"] or \
                row["v2_pilot_suggested_issue_id"] != (
                    old["v2_pilot_suggested_issue_id"] or "") or \
                not row["decided_by"].strip() or not row["decided_at_utc"].strip():
            raise ValueError("open-five provenance differs")
        kind = row["reviewer_decision"].strip()
        chosen = row["chosen_issue_id"].strip() or None
        if idx == 97:
            if kind != "correct_saved_label" or chosen is not None or \
                    "praise" not in row["decision_notes"].lower():
                raise ValueError("case 97 correction decision differs")
            old["status"] = "label_correction_validated_not_applied"
            old["v3_pilot_suggested_issue_id"] = None
        elif kind != "accept_provisional" or chosen not in issue_ids or \
                chosen != old["v2_pilot_suggested_issue_id"]:
            raise ValueError("open-five issue decision differs")
        else:
            old["status"] = "pilot_issue_suggestion_only"
            old["v3_pilot_suggested_issue_id"] = chosen
        old["reviewer_decision"] = kind
        old["reviewer_chosen_issue_id"] = chosen
        old["decision_note_sha256"] = (hashlib.sha256(
            row["decision_notes"].encode()).hexdigest()
            if row["decision_notes"] else None)
        old["v4_decided_by"] = row["decided_by"]
        old["v4_decided_at_utc"] = row["decided_at_utc"]
    if seen != OPEN_CASES or entries[29]["v3_pilot_suggested_issue_id"] != "DLD-FAIL":
        raise ValueError("open-five coverage or app-install gap differs")

    correction_rows = []
    for idx in sorted(set(six) | {97}):
        source = sources[idx]
        if idx == 97:
            changes = {"intent": "praise"}
            rationale = "Human open-five decision: saved intent is praise."
        else:
            item = six[idx]
            if item["review_id"] != source["review_id"] or \
                    item["source_sha256"] != source["source_sha256"]:
                raise ValueError("six-correction source identity differs")
            changes, rationale = item["changes"], item["rationale"]
            entries[idx]["status"] = "label_correction_validated_not_applied"
        if not changes or not rationale:
            raise ValueError("correction lacks change or rationale")
        correction_rows.append({"pilot_index": idx, "review_id": source["review_id"],
            "source_sha256": source["source_sha256"], "changes": changes,
            "rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest(),
            "production_membership_issue_id": None})
    if len(correction_rows) != 7:
        raise ValueError("seven corrections required")

    corrections_by_id = {row["review_id"]: row for row in correction_rows}
    corrected = []
    removed = []
    for original in frame["rows"]:
        row = dict(original)
        action = corrections_by_id.get(row["review_id"])
        if action:
            if row["source_sha256"] != action["source_sha256"]:
                raise ValueError("frame source identity differs")
            for key, value in action["changes"].items():
                if key == "evidence_quote":
                    if value not in row["source_text"]:
                        raise ValueError("corrected quote is not an exact source span")
                    row["evidence"] = {**row["evidence"], "evidence_quote": value}
                elif key == "topic":
                    if value not in TOPICS: raise ValueError("invalid corrected topic")
                    row["topic"] = value
                elif key == "intent":
                    if value not in INTENTS: raise ValueError("invalid corrected intent")
                    row["intent"] = value
                elif key == "severity":
                    if type(value) is not int or not 1 <= value <= 5:
                        raise ValueError("invalid corrected severity")
                    row["severity"] = value
                else:
                    raise ValueError("unknown correction field")
            row["human_correction_pilot_index"] = action["pilot_index"]
        if row["intent"] in {"complaint", "cancellation"}:
            corrected.append(row)
        elif action:
            removed.append(action["pilot_index"])
        else:
            raise ValueError("uncorrected row left complaint frame")
    blocked = sum(row["known_semantic_flag"] for row in corrected)
    if len(corrected) != 30400 or set(removed) != {18, 80, 97} or blocked != 23:
        raise ValueError("corrected frame denominator differs")
    counts = Counter(row["reviewer_decision"] for row in entries.values())
    if sum(counts.values()) != 53 or counts["correct_saved_label"] != 7 or \
            sum(row["status"] == "pilot_issue_suggestion_only" for row in entries.values()) != 46:
        raise ValueError("v4 pilot decision coverage differs")
    correction_overlay = {"schema_version": "spotify-grouping-corrections-v4",
        "status": "validated_not_applied_to_saved_model_output",
        "source_v3_overlay_sha256": HASHES["v3_overlay"],
        "six_validated_sha256": HASHES["six_validated"],
        "open_five_sha256": HASHES["open_five"], "correction_count": 7,
        "removed_from_grouping_frame": sorted(removed), "rows": correction_rows}
    v4_overlay = {"schema_version": "spotify-issue-pilot-v4-overlay-v1",
        "status": "all_review_decisions_recorded_not_production_membership",
        "mapping_rule_version": RULE, "catalog_approval_sha256": HASHES["approval"],
        "source_v3_overlay_sha256": HASHES["v3_overlay"],
        "open_five_sha256": HASHES["open_five"],
        "counts": {"review_cases": 53, "recorded_decisions": 53,
            "human_decisions_pending": 0, "label_corrections_validated": 7,
            "pilot_issue_suggestions": 46, "production_memberships": 0,
            **dict(counts)}, "known_catalog_gap": "app-install: case 29 retained DLD-FAIL",
        "entries": sorted(entries.values(), key=lambda row: row["pilot_index"])}
    corrected_frame = {"schema_version": "spotify-issue-grouping-frame-v4",
        "status": "awaiting_semantic_issue_mapping",
        "source_frame_sha256": HASHES["frame"],
        "corrections_status": "validated_overlay_not_saved_model_mutation",
        "mapping_rule_version": RULE, "membership_rule": "one_issue_per_record",
        "baseline_candidates": len(corrected),
        "known_flagged_candidates": blocked,
        "public_candidates": len(corrected) - blocked,
        "removed_pilot_indices": sorted(removed), "rows": corrected}
    return correction_overlay, v4_overlay, corrected_frame


def freeze_catalog(catalog, approval):
    if approval.get("decision") != "approved_for_production_mapping" or \
            approval.get("catalog_sha256") != HASHES["catalog"] or \
            catalog.get("mapping_rule_version") != RULE or \
            len(catalog.get("issues", [])) != 41:
        raise ValueError("production catalog approval differs")
    return {"schema_version": "spotify-issue-catalog-v1", "status": "approved",
        "mapping_rule_version": RULE, "source_pilot_catalog_sha256": HASHES["catalog"],
        "approval_sha256": HASHES["approval"],
        "known_gap": "app-install is not a separate issue; pilot case 29 retained DLD-FAIL",
        "issues": catalog["issues"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-local", type=Path, required=True)
    args = parser.parse_args()
    src = args.source_local
    inputs = {
        "pilot": _read_json(src / "issue_grouping_pilot100_input.json", HASHES["pilot"]),
        "v3": _read_json(src / "issue_grouping_pilot100_v3_overlay.json", HASHES["v3_overlay"]),
        "frame": _read_json(src / "accepted100k_issue_grouping_frame.json", HASHES["frame"]),
        "six_sheet": _read_csv(src / "issue_grouping_pilot100_label_corrections_v1.csv", HASHES["six_sheet"]),
        "six_saved": _read_json(src / "issue_grouping_pilot100_label_corrections_v1_validated.json", HASHES["six_validated"]),
        "open_five": _read_csv(src / "issue_grouping_pilot100_open5_decisions.csv", HASHES["open_five"]),
        "catalog": _read_json(Path("docs/issue-catalog-pilot-v3.json"), HASHES["catalog"]),
        "approval": _read_json(src / "issue_catalog_pilot_v3_production_approval.json", HASHES["approval"]),
    }
    corrections, overlay, frame = build(**inputs)
    approved_catalog = freeze_catalog(inputs["catalog"], inputs["approval"])
    outputs = [("issue_grouping_corrections_v4.json", corrections),
               ("issue_grouping_pilot100_v4_overlay.json", overlay),
               ("accepted100k_issue_grouping_frame_v4.json", frame)]
    catalog_path = Path("docs/issue-catalog-v1.json")
    if catalog_path.exists():
        raise FileExistsError("approved catalog already exists")
    for name, value in outputs:
        path = LOCAL_DIR / name
        if path.exists():
            raise FileExistsError("private output already exists: " + name)
        private_json(path, value)
    catalog_path.write_text(json.dumps(approved_catalog, ensure_ascii=False,
        sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"corrections": 7, "decisions": 53,
        "baseline_candidates": frame["baseline_candidates"],
        "public_candidates": frame["public_candidates"],
        "known_flagged_candidates": frame["known_flagged_candidates"],
        "outputs": {**{name: sha256(LOCAL_DIR / name) for name, _ in outputs},
            str(catalog_path): sha256(catalog_path)}},
        sort_keys=True))


if __name__ == "__main__":
    main()

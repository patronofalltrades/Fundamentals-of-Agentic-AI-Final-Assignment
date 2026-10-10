"""Prepare and validate private human corrections for six grouping pilot cases.

This tool does not change saved labels, evidence, issue suggestions, or membership.
It prints counts and digests only; source text stays in ignored local files.
"""

import argparse
import csv
import json
import os
from pathlib import Path

from spotify_pipeline.contract import INTENTS, TOPICS
from tools.issue_grouping_handoff import LOCAL_DIR, private_json, sha256
from tools.reconcile_grouping_pilot_v3 import CORRECTION_CASES, PILOT_SHA256


OVERLAY_SHA256 = "b0a9e7457f6c202049c39515ac5b62a84e8cccb6a6ebaaf69eafbe95d0a2af83"
SCHEMA = "spotify-grouping-label-correction-intake-v1"
FIELDS = ("pilot_index", "review_id", "source_sha256", "source_text",
          "saved_topic", "saved_intent", "saved_severity", "saved_evidence_quote",
          "corrected_topic", "corrected_intent", "corrected_severity",
          "corrected_evidence_quote", "reviewer_confirmed", "correction_rationale")
CORRECTION_FIELDS = FIELDS[8:12]


def _sources(pilot, overlay):
    if pilot.get("schema_version") != "spotify-issue-grouping-pilot100-v1" or \
            len(pilot.get("rows", [])) != 100 or \
            overlay.get("mapping_rule_version") != "pilot-primary-problem-v3-20261010" or \
            overlay.get("status") != "pilot_partial_decisions_not_production_membership" or \
            overlay.get("counts", {}).get("production_memberships") != 0:
        raise ValueError("frozen pilot or v3 overlay differs")
    sources = {row["pilot_index"]: row for row in pilot["rows"]}
    cases = {row["pilot_index"]: row for row in overlay["entries"]
             if row["status"] == "label_correction_pending"}
    if len(sources) != 100 or set(cases) != CORRECTION_CASES or \
            any(cases[idx]["review_id"] != sources[idx]["review_id"] or
                cases[idx]["source_sha256"] != sources[idx]["source_sha256"] or
                cases[idx]["production_membership_issue_id"] is not None
                for idx in cases) or \
            any(not isinstance(sources[idx]["evidence"]["evidence_quote"], str) or
                not sources[idx]["evidence"]["evidence_quote"].strip() or
                sources[idx]["evidence"]["evidence_quote"] not in
                    sources[idx]["source_text"] for idx in cases):
        raise ValueError("correction cases or source identities differ")
    return sources


def blank_rows(pilot, overlay):
    sources = _sources(pilot, overlay)
    result = []
    for idx in sorted(CORRECTION_CASES):
        source = sources[idx]
        result.append({"pilot_index": str(idx), "review_id": source["review_id"],
            "source_sha256": source["source_sha256"],
            "source_text": source["source_text"],
            "saved_topic": source["topic"], "saved_intent": source["intent"],
            "saved_severity": str(source["severity"]),
            "saved_evidence_quote": source["evidence"]["evidence_quote"],
            **{field: "" for field in CORRECTION_FIELDS},
            "reviewer_confirmed": "", "correction_rationale": ""})
    return result


def validate(pilot, overlay, rows):
    expected = blank_rows(pilot, overlay)
    if len(rows) != len(expected):
        raise ValueError("correction sheet must contain six cases")
    result = []
    for row, frozen in zip(rows, expected):
        for field in FIELDS[:8]:
            if row[field] != frozen[field]:
                raise ValueError("saved source, label, or quote differs")
        idx = int(row["pilot_index"])
        fields = {field: row[field] for field in CORRECTION_FIELDS}
        confirmed = row["reviewer_confirmed"]
        rationale = row["correction_rationale"]
        if not confirmed:
            if any(fields.values()) or rationale:
                raise ValueError("unconfirmed correction contains edits")
            status, changes = "human_correction_pending", {}
        else:
            if confirmed != "yes" or not rationale.strip():
                raise ValueError("correction needs explicit yes and rationale")
            changes = {}
            topic = fields["corrected_topic"]
            intent = fields["corrected_intent"]
            severity = fields["corrected_severity"]
            quote = fields["corrected_evidence_quote"]
            if topic:
                if topic not in TOPICS or topic == frozen["saved_topic"]:
                    raise ValueError("corrected topic invalid or unchanged")
                changes["topic"] = topic
            if intent:
                if intent not in INTENTS or intent == frozen["saved_intent"]:
                    raise ValueError("corrected intent invalid or unchanged")
                changes["intent"] = intent
            if severity:
                if severity not in ("1", "2", "3", "4", "5") or \
                        severity == frozen["saved_severity"]:
                    raise ValueError("corrected severity invalid or unchanged")
                changes["severity"] = int(severity)
            if quote:
                if not quote.strip() or quote == frozen["saved_evidence_quote"] or \
                        quote not in frozen["source_text"]:
                    raise ValueError("corrected quote is not a changed exact source span")
                changes["evidence_quote"] = quote
            if not changes:
                raise ValueError("confirmed correction has no changed field")
            status = "human_correction_validated_not_applied"
        result.append({"pilot_index": idx, "review_id": frozen["review_id"],
            "source_sha256": frozen["source_sha256"], "status": status,
            "changes": changes, "rationale": rationale or None,
            "production_membership_issue_id": None})
    return {"schema_version": SCHEMA, "status": "pilot_corrections_only_not_applied",
        "pilot_sha256": PILOT_SHA256, "v3_overlay_sha256": OVERLAY_SHA256,
        "pending": sum(row["status"] == "human_correction_pending" for row in result),
        "validated_not_applied": sum(row["status"] ==
            "human_correction_validated_not_applied" for row in result),
        "production_memberships": 0, "rows": result}


def _private_path(path):
    if os.path.commonpath([str(LOCAL_DIR), str(path.resolve())]) != str(LOCAL_DIR):
        raise ValueError("private output must remain under local/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "validate"))
    for name in ("pilot", "v3_overlay", "sheet", "out"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path,
                            required=name != "out")
    args = parser.parse_args()
    if sha256(args.pilot) != PILOT_SHA256 or \
            sha256(args.v3_overlay) != OVERLAY_SHA256:
        raise ValueError("frozen input digest differs")
    pilot = json.loads(args.pilot.read_text(encoding="utf-8"))
    overlay = json.loads(args.v3_overlay.read_text(encoding="utf-8"))
    _private_path(args.sheet)
    if args.action == "prepare":
        rows = blank_rows(pilot, overlay)
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(args.sheet), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(json.dumps({"cases": len(rows), "pending": len(rows),
            "sheet_sha256": sha256(args.sheet)}, sort_keys=True))
        return
    if args.out is None:
        raise ValueError("validate requires --out")
    _private_path(args.out)
    with args.sheet.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("correction sheet columns differ")
        rows = list(reader)
    result = validate(pilot, overlay, rows)
    result["sheet_sha256"] = sha256(args.sheet)
    private_json(args.out, result)
    print(json.dumps({"pending": result["pending"],
        "validated_not_applied": result["validated_not_applied"],
        "sheet_sha256": result["sheet_sha256"],
        "intake_sha256": sha256(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Audit the private issue map, then derive a separate 30,400-row membership.

No model or network calls. Blind answers are read only in this local scoring
code; stdout and the audit contain aggregate counts and hashes, never cases.
Run `audit` successfully before `correct`. All outputs stay under local/.
"""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "local/claude_issue_map_v1"
FRAME = ROOT / "local/accepted100k_issue_grouping_frame.json"
CATALOG = ROOT / "docs/issue-catalog-pilot-v3.json"
PILOT = ROOT / "local/issue_grouping_pilot100_input.json"
OVERLAY = ROOT / "local/issue_grouping_pilot100_v3_overlay.json"
OPEN5 = ROOT / "local/issue_grouping_pilot100_open5_decisions.csv"
BLIND_MANIFEST = ROOT / "local/issue_grouping_independent40_manifest.json"
BLIND_ANSWERS = ROOT / "local/issue_grouping_independent40_blind.csv"
MEMBERSHIP = BASE / "issue_membership_v1.csv"
AGENT = BASE / "agent_labels_v1.csv"
CLAUDE_REPORT = BASE / "report_v1.json"
AUDIT = BASE / "independent_audit_v1.json"
CORRECTED = BASE / "issue_membership_corrected_30400.csv"
CORRECTION_MANIFEST = BASE / "corrected_30400_manifest.json"

EXPECTED = {
    FRAME: "e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf",
    CATALOG: "f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b",
    PILOT: "d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c",
    OVERLAY: "b0a9e7457f6c202049c39515ac5b62a84e8cccb6a6ebaaf69eafbe95d0a2af83",
    OPEN5: "58b5fe3014ad2eafaa659d23e59e765b94091098abaa5ba74ef5d4c79d79edcd",
    BLIND_MANIFEST: "65c3d9ad0342099860a1977765fa88c419c17c584464513b0cd8e22d44df0f28",
    BLIND_ANSWERS: "8a095149bcca93912732a2b71493d1dbc460d098f03bf8ccd9571737838eb4b1",
    MEMBERSHIP: "bbc0c84ce046d82215744838107d4e699c0399d0dbcad6a644ece8138233098f",
    AGENT: "fd2366d020e3e96d03e9e0a2411b32b611d97116f1e5183bb24cdb456fa7a456",
    BASE / "ranking_baseline_v1.csv": "532187161c785089d1d25de5f0b3e567764ca2e5b7e60a39115098911f8b7040",
    BASE / "ranking_public_v1.csv": "8924af2e666baf4c850c5ccecb437fda63335669caae98e5b18af61b9b293809",
    CLAUDE_REPORT: "82db52159d1b44108e457fe8bb88acd697b7216025517730561d9e90daac1f60",
}
DROP_CASES = (18, 80, 97)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path, fields):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == fields, "CSV columns differ: " + path.name)
        return list(reader)


def write_private(path, data):
    require(path.parent == BASE, "output must stay in private issue-map folder")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
        if isinstance(data, dict):
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        else:
            writer = csv.DictWriter(stream, fieldnames=["issue_id", "review_id"])
            writer.writeheader()
            writer.writerows(data)


def independent_ranking(membership, frame, include_flagged):
    totals = defaultdict(lambda: [0, 0])
    for rid, issue in membership.items():
        row = frame[rid]
        if not include_flagged and row["known_semantic_flag"]:
            continue
        totals[issue][0] += 1
        totals[issue][1] += row["severity"]
    ordered = sorted(totals, key=lambda issue: (-totals[issue][1], issue))
    result = []
    for position, issue in enumerate(ordered, 1):
        count, severity = totals[issue]
        mean = (Decimal(severity) / count).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)
        result.append({"rank": str(position), "issue_id": issue,
                       "complaint_count": str(count), "severity_sum": str(severity),
                       "mean_severity": f"{mean:.6f}", "priority_score": str(severity)})
    return result


def audit():
    # Hash all private inputs before parsing any of them.
    actual = {path: digest(path) for path in EXPECTED}
    require(all(actual[path] == expected for path, expected in EXPECTED.items()),
            "frozen input hash differs")
    frame_data = json.loads(FRAME.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    blind = json.loads(BLIND_MANIFEST.read_text(encoding="utf-8"))
    supplied = json.loads(CLAUDE_REPORT.read_text(encoding="utf-8"))
    rows = frame_data["rows"]
    frame = {row["review_id"]: row for row in rows}
    issues = {row["issue_id"] for row in catalog["issues"]}
    require(len(rows) == len(frame) == 30403 and len(issues) == len(catalog["issues"]) == 41,
            "frame or catalog coverage differs")
    require(frame_data["schema_version"] == "spotify-issue-grouping-frame-v1" and
            frame_data["membership_rule"] == "one_issue_per_record" and
            frame_data["accepted_export_sha256"] ==
            "01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c",
            "frame identity differs")
    require(catalog["status"] == "pilot_authorized" and
            catalog["v3_revision"]["production_approved"] is False,
            "catalog approval state differs")
    require(all(row["intent"] in ("complaint", "cancellation") and
                type(row["severity"]) is int and 1 <= row["severity"] <= 5 and
                type(row["known_semantic_flag"]) is bool for row in rows),
            "invalid frame label or flag")
    flagged = sum(row["known_semantic_flag"] for row in rows)
    require(flagged == 24, "semantic flag coverage differs")

    membership_rows = read_csv(MEMBERSHIP, ["issue_id", "review_id"])
    membership = {row["review_id"]: row["issue_id"] for row in membership_rows}
    require(len(membership_rows) == len(membership) == 30403 and
            set(membership) == set(frame) and set(membership.values()) <= issues,
            "membership is incomplete, repeated, foreign, or outside catalog")
    require(membership_rows == sorted(membership_rows,
                                     key=lambda row: (row["issue_id"], row["review_id"])),
            "membership order differs")
    agents = read_csv(AGENT, ["review_id", "agent_issue_id", "confidence"])
    agent = {row["review_id"]: row for row in agents}
    require(len(agents) == len(agent) == 30403 and set(agent) == set(frame) and
            all(row["agent_issue_id"] in issues and row["confidence"] in
                {"high", "medium", "low"} for row in agents),
            "agent label coverage, issue, or confidence differs")
    low = sum(row["confidence"] == "low" for row in agents)
    require(low == supplied["coverage"]["low_confidence"] == 9450,
            "low-confidence count differs")

    # Score the human labels inside this local aggregate-only code. No answer
    # row or private ID is written to an output artifact or stdout.
    pilot_ids = {row["pilot_index"]: row["review_id"] for row in pilot["rows"]}
    require(len(pilot_ids) == 100, "pilot source coverage differs")
    human = {}
    sources = Counter()
    for entry in overlay["entries"]:
        idx, issue = entry["pilot_index"], entry["reviewer_chosen_issue_id"]
        require(pilot_ids[idx] == entry["review_id"], "pilot identity differs")
        if issue:
            require(issue in issues and entry["review_id"] not in human,
                    "pilot decision differs")
            human[entry["review_id"]] = issue
            sources["pilot"] += 1
    for entry in read_csv(OPEN5,
        ["pilot_index", "sheet", "source_sha256", "v2_pilot_suggested_issue_id",
         "reviewer_decision", "chosen_issue_id", "decision_notes", "decided_by",
         "decided_at_utc"]):
        if entry["chosen_issue_id"]:
            idx = int(entry["pilot_index"])
            rid = pilot_ids[idx]
            require(entry["source_sha256"] == next(row["source_sha256"]
                    for row in pilot["rows"] if row["pilot_index"] == idx) and
                    rid not in human and entry["chosen_issue_id"] in issues,
                    "open-five decision differs")
            human[rid] = entry["chosen_issue_id"]
            sources["pilot"] += 1
    require(sources["pilot"] == 51, "pilot decision coverage differs")
    pilot_agreed = sum(human[rid] == agent[rid]["agent_issue_id"] for rid in human)
    require(pilot_agreed == 39, "pilot-agent aggregate differs")

    blind_sources = {row["case_ref"]: row for row in blind["rows"]}
    require(len(blind_sources) == 40, "blind manifest coverage differs")
    blind_answers = read_csv(BLIND_ANSWERS,
        ["case_ref", "source_text", "independent_issue_id", "evidence_rationale", "uncertainty_notes"])
    require(len(blind_answers) == 40 and
            len({row["case_ref"] for row in blind_answers}) == 40,
            "blind answer coverage differs")
    blind_agreed = blind_uncertain = 0
    for answer in blind_answers:
        source = blind_sources[answer["case_ref"]]
        rid = source["review_id"]
        issue = answer["independent_issue_id"].strip()
        require(answer["source_text"] == source["source_text"] and
                source["source_sha256"] == frame[rid]["source_sha256"] and
                issue in issues and answer["evidence_rationale"].strip() and
                rid not in human, "blind answer identity or decision differs")
        blind_agreed += issue == agent[rid]["agent_issue_id"]
        blind_uncertain += bool(answer["uncertainty_notes"].strip())
        human[rid] = issue
        sources["blind40"] += 1
    require(blind_agreed == 16 and blind_uncertain == 5 and
            sources["blind40"] == 40, "blind-agent aggregate differs")
    require(all(membership[rid] == human.get(rid, agent[rid]["agent_issue_id"])
                for rid in frame), "human override or agent membership differs")

    ranking = {}
    for name, include, denominator in (("baseline", True, 30403),
                                       ("public", False, 30379)):
        calculated = independent_ranking(membership, frame, include)
        saved = read_csv(BASE / f"ranking_{name}_v1.csv",
            ["rank", "issue_id", "complaint_count", "severity_sum",
             "mean_severity", "priority_score"])
        require(calculated == saved and
                sum(int(row["complaint_count"]) for row in calculated) == denominator and
                len(calculated) == 41, "independent rank arithmetic differs")
        ranking[name] = {"denominator": denominator, "issues": len(calculated),
                         "csv_matches_independent_recalculation": True}
    require(supplied["frame_sha256"] == actual[FRAME] and
            supplied["catalog_sha256"] == actual[CATALOG] and
            supplied["files_sha256"][MEMBERSHIP.name] == actual[MEMBERSHIP] and
            supplied["final_membership_source"] ==
            {"agent": 30312, "human_pilot": 51, "human_blind40": 40},
            "supplied report provenance differs")
    return {"schema_version": "spotify-issue-map-independent-audit-v1",
            "status": "validated_structure_and_arithmetic_not_human_accuracy",
            "source_hashes_sha256": {path.name: value for path, value in actual.items()},
            "rows": len(membership), "catalog_issues": len(issues),
            "catalog_status": catalog["status"], "known_flagged": flagged,
            "agent_low_confidence": low,
            "human_override_sources": {"agent": len(frame) - len(human),
                                       "pilot": sources["pilot"],
                                       "blind40": sources["blind40"]},
            "agent_human_pilot_agreement": {"agreed": pilot_agreed, "cases": 51},
            "agent_human_blind_agreement": {"agreed": blind_agreed, "cases": 40,
                                            "uncertain_answers": blind_uncertain},
            "rankings": ranking}


def correct():
    require(AUDIT.exists(), "run and save the original audit first")
    require(not CORRECTED.exists() and not CORRECTION_MANIFEST.exists(),
            "corrected artifacts already exist")
    saved_audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    fresh = audit()
    require(saved_audit == fresh, "original audit no longer matches inputs")
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    source_rows = {row["pilot_index"]: row for row in pilot["rows"]}
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    decisions = {row["pilot_index"]: row for row in overlay["entries"]}
    require({idx: decisions[idx]["status"] for idx in DROP_CASES} ==
            {18: "label_correction_pending", 80: "label_correction_pending",
             97: "human_decision_pending"},
            "three correction-case decision statuses differ")
    frame_rows = {row["review_id"]: row for row in
                  json.loads(FRAME.read_text(encoding="utf-8"))["rows"]}
    drop = {source_rows[idx]["review_id"] for idx in DROP_CASES}
    require(len(drop) == 3 and drop <= set(frame_rows) and
            all(frame_rows[rid]["source_sha256"] == source_rows[idx]["source_sha256"]
                for idx, rid in ((idx, source_rows[idx]["review_id"])
                                 for idx in DROP_CASES)),
            "correction case source identities differ")
    original = read_csv(MEMBERSHIP, ["issue_id", "review_id"])
    corrected = [row for row in original if row["review_id"] not in drop]
    require(len(corrected) == 30400 and
            {row["review_id"] for row in original} -
            {row["review_id"] for row in corrected} == drop,
            "corrected membership delta differs")
    write_private(CORRECTED, corrected)
    manifest = {"schema_version": "spotify-issue-membership-correction-manifest-v1",
                "status": "scope_exclusion_only_not_approved_ranking",
                "original_membership_sha256": digest(MEMBERSHIP),
                "original_audit_sha256": digest(AUDIT),
                "corrected_membership_sha256": digest(CORRECTED),
                "frame_sha256": digest(FRAME), "pilot_sha256": digest(PILOT),
                "catalog_sha256": digest(CATALOG),
                "excluded_pilot_indices": list(DROP_CASES),
                "excluded_sources": [
                    {"pilot_index": idx, "review_id": source_rows[idx]["review_id"],
                     "source_sha256": source_rows[idx]["source_sha256"],
                     "decision_status": decisions[idx]["status"]}
                    for idx in DROP_CASES],
                "original_rows": len(original), "corrected_rows": len(corrected),
                "original_flagged": sum(frame_rows[row["review_id"]]["known_semantic_flag"]
                                        for row in original),
                "corrected_flagged": sum(frame_rows[row["review_id"]]["known_semantic_flag"]
                                         for row in corrected),
                "corrected_public_rows": sum(not frame_rows[row["review_id"]]["known_semantic_flag"]
                                             for row in corrected)}
    write_private(CORRECTION_MANIFEST, manifest)
    return {"original_rows": manifest["original_rows"],
            "corrected_rows": manifest["corrected_rows"],
            "original_sha256": manifest["original_membership_sha256"],
            "corrected_sha256": manifest["corrected_membership_sha256"],
            "audit_sha256": manifest["original_audit_sha256"],
            "manifest_sha256": digest(CORRECTION_MANIFEST),
            "corrected_public_rows": manifest["corrected_public_rows"]}


def verify():
    require(AUDIT.exists() and CORRECTED.exists() and CORRECTION_MANIFEST.exists(),
            "audit and corrected artifacts are required")
    require(json.loads(AUDIT.read_text(encoding="utf-8")) == audit(),
            "saved original audit differs from independent recalculation")
    manifest = json.loads(CORRECTION_MANIFEST.read_text(encoding="utf-8"))
    original = read_csv(MEMBERSHIP, ["issue_id", "review_id"])
    corrected = read_csv(CORRECTED, ["issue_id", "review_id"])
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    sources = {row["pilot_index"]: row for row in pilot["rows"]}
    drop = {sources[idx]["review_id"] for idx in DROP_CASES}
    require(corrected == [row for row in original if row["review_id"] not in drop],
            "corrected rows differ from the three-case exclusion")
    frame = {row["review_id"]: row for row in
             json.loads(FRAME.read_text(encoding="utf-8"))["rows"]}
    expected_sources = [
        {"pilot_index": idx, "review_id": sources[idx]["review_id"],
         "source_sha256": sources[idx]["source_sha256"],
         "decision_status": ("human_decision_pending" if idx == 97
                             else "label_correction_pending")}
        for idx in DROP_CASES]
    require(manifest["schema_version"] ==
            "spotify-issue-membership-correction-manifest-v1" and
            manifest["status"] == "scope_exclusion_only_not_approved_ranking" and
            manifest["original_membership_sha256"] == digest(MEMBERSHIP) and
            manifest["original_audit_sha256"] == digest(AUDIT) and
            manifest["corrected_membership_sha256"] == digest(CORRECTED) and
            manifest["frame_sha256"] == digest(FRAME) and
            manifest["pilot_sha256"] == digest(PILOT) and
            manifest["catalog_sha256"] == digest(CATALOG) and
            manifest["excluded_pilot_indices"] == list(DROP_CASES) and
            manifest["excluded_sources"] == expected_sources and
            manifest["original_rows"] == len(original) == 30403 and
            manifest["corrected_rows"] == len(corrected) == 30400 and
            manifest["original_flagged"] == 24 and
            manifest["corrected_flagged"] == sum(
                frame[row["review_id"]]["known_semantic_flag"] for row in corrected) and
            manifest["corrected_public_rows"] == sum(
                not frame[row["review_id"]]["known_semantic_flag"] for row in corrected),
            "corrected manifest or counts differ")
    return {"original_rows": 30403, "corrected_rows": 30400,
            "corrected_public_rows": manifest["corrected_public_rows"],
            "original_sha256": digest(MEMBERSHIP),
            "corrected_sha256": digest(CORRECTED),
            "audit_sha256": digest(AUDIT),
            "manifest_sha256": digest(CORRECTION_MANIFEST)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "correct", "verify"))
    action = parser.parse_args().action
    if action == "audit":
        require(not AUDIT.exists(), "original audit already exists")
        result = audit()
        write_private(AUDIT, result)
        print(json.dumps({"rows": result["rows"],
                          "catalog_issues": result["catalog_issues"],
                          "known_flagged": result["known_flagged"],
                          "agent_low_confidence": result["agent_low_confidence"],
                          "human_override_sources": result["human_override_sources"],
                          "agent_human_blind_agreement": result["agent_human_blind_agreement"],
                          "rankings": result["rankings"],
                          "audit_sha256": digest(AUDIT)}, sort_keys=True))
    elif action == "correct":
        print(json.dumps(correct(), sort_keys=True))
    else:
        print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()

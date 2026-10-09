"""Prepare a private grouping frame; validate and rank a supplied issue mapping.

This tool makes no model calls. It does not infer issue membership from broad
topic labels. All outputs contain private source IDs and belong under local/.
"""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import tempfile

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256


EXPORT_SHA256 = "01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c"
FRAME_SHA256 = "e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf"
SCHEMA = "spotify-issue-grouping-frame-v1"
INTENTS = {"complaint", "cancellation"}
LOCAL_DIR = Path(__file__).resolve().parent.parent / "local"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def private_json(path, value):
    if os.path.commonpath([str(LOCAL_DIR), str(path.resolve())]) != str(LOCAL_DIR):
        raise ValueError("private outputs must stay under this repository's local/ directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".issue-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def prepare(export, source_digest):
    if source_digest != EXPORT_SHA256 or export.get("schema_version") != \
            "spotify-accepted100k-dashboard-handoff-v1":
        raise ValueError("accepted export identity differs")
    if export["coverage"]["accepted_rows"] != 100229 or len(export["records"]) != 100229:
        raise ValueError("accepted export coverage differs")
    seen, rows, intents, flagged_intents = set(), [], Counter(), Counter()
    for record in export["records"]:
        rid = record["review_id"]
        if rid in seen or record["source"]["review_id"] != rid:
            raise ValueError("duplicate or mismatched source ID")
        seen.add(rid)
        if row_sha256([record["source"][key] for key in SOURCE_FIELDS]) != \
                record["source_sha256"]:
            raise ValueError("source hash differs")
        label = record["labels"]
        if label["intent"] not in INTENTS:
            continue
        validate_evidence(record["source"]["review_text"], record["evidence"])
        severity = label["severity"]
        if type(severity) is not int or not 1 <= severity <= 5:
            raise ValueError("invalid severity")
        blocked = record["semantic_review"][
            "representative_evidence_blocked_by_known_flags"]
        if type(blocked) is not bool:
            raise ValueError("invalid semantic flag")
        intents[label["intent"]] += 1
        if blocked:
            flagged_intents[label["intent"]] += 1
        rows.append({
            "review_id": rid, "source_position": record["source_position"],
            "source_sha256": record["source_sha256"],
            "source_text": record["source"]["review_text"],
            "topic": label["topic"], "intent": label["intent"],
            "severity": severity, "evidence": record["evidence"],
            "label_provenance": record["provenance"]["label"],
            "evidence_provenance": record["provenance"]["evidence"],
            "known_semantic_flag": blocked,
        })
    if len(seen) != 100229 or intents != {"complaint": 28743,
            "cancellation": 1660} or flagged_intents != {"complaint": 22,
            "cancellation": 2}:
        raise ValueError("saved intent or flag counts differ")
    rows.sort(key=lambda row: (row["source_position"], row["review_id"]))
    return {"schema_version": SCHEMA, "accepted_export_sha256": source_digest,
        "status": "awaiting_semantic_issue_mapping", "membership_rule": "one_issue_per_record",
        "baseline_candidates": 30403, "public_candidates": 30379,
        "known_flagged_candidates": 24, "rows": rows}


def rank(frame, catalog, membership_rows):
    if frame.get("schema_version") != SCHEMA or \
            frame.get("accepted_export_sha256") != EXPORT_SHA256 or \
            frame.get("membership_rule") != "one_issue_per_record":
        raise ValueError("grouping frame identity differs")
    records = {row["review_id"]: row for row in frame["rows"]}
    if len(records) != 30403 or len(frame["rows"]) != 30403 or \
            sum(not row["known_semantic_flag"] for row in records.values()) != 30379:
        raise ValueError("grouping frame coverage differs")
    if catalog.get("schema_version") != "spotify-issue-catalog-v1" or \
            catalog.get("status") != "approved" or \
            not catalog.get("mapping_rule_version") or not catalog.get("issues"):
        raise ValueError("an approved versioned issue catalog is required")
    issues = {}
    for item in catalog["issues"]:
        issue_id = item["issue_id"]
        if not isinstance(issue_id, str) or not issue_id.strip() or \
                issue_id in issues or not item.get("title") or not item.get("definition"):
            raise ValueError("invalid or repeated catalog issue")
        issues[issue_id] = item
    assigned = {}
    for item in membership_rows:
        issue_id, rid = item["issue_id"], item["review_id"]
        if rid not in records or issue_id not in issues or rid in assigned:
            raise ValueError("foreign, repeated, or unknown issue membership")
        assigned[rid] = issue_id
    if set(assigned) != set(records):
        raise ValueError("all 30,403 complaint/cancellation IDs need membership")

    def projection(include_flagged):
        counts, severities = defaultdict(int), defaultdict(int)
        for rid, issue_id in assigned.items():
            row = records[rid]
            if not include_flagged and row["known_semantic_flag"]:
                continue
            counts[issue_id] += 1
            severities[issue_id] += row["severity"]
        ranked = []
        for issue_id in counts:
            count, score = counts[issue_id], severities[issue_id]
            mean = (Decimal(score) / Decimal(count)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP)
            ranked.append({"issue_id": issue_id, "title": issues[issue_id]["title"],
                "complaint_count": count, "severity_sum": score,
                "priority_score": score, "mean_severity": str(mean)})
        ranked.sort(key=lambda row: (-row["severity_sum"], row["issue_id"]))
        for position, item in enumerate(ranked, 1):
            item["rank"] = position
        if sum(counts.values()) != (30403 if include_flagged else 30379):
            raise ValueError("ranking denominator differs")
        return ranked

    return {"schema_version": "spotify-issue-ranking-v1",
        "accepted_export_sha256": EXPORT_SHA256,
        "mapping_rule_version": catalog["mapping_rule_version"],
        "baseline_denominator": 30403, "public_denominator": 30379,
        "baseline": projection(True), "public_advisory": projection(False)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_subparsers(dest="action", required=True)
    prep = action.add_parser("prepare")
    prep.add_argument("--export", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    ranking = action.add_parser("rank")
    ranking.add_argument("--frame", type=Path, required=True)
    ranking.add_argument("--catalog", type=Path, required=True)
    ranking.add_argument("--membership", type=Path, required=True)
    ranking.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        digest = sha256(args.export)
        frame = prepare(json.loads(args.export.read_text(encoding="utf-8")), digest)
        private_json(args.out, frame)
        print(json.dumps({"status": frame["status"], "baseline_candidates": 30403,
            "public_candidates": 30379, "frame_sha256": sha256(args.out)}, sort_keys=True))
    else:
        if sha256(args.frame) != FRAME_SHA256:
            raise ValueError("frozen grouping frame digest differs")
        frame = json.loads(args.frame.read_text(encoding="utf-8"))
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        with args.membership.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["issue_id", "review_id"]:
                raise ValueError("membership CSV columns differ")
            output = rank(frame, catalog, list(reader))
        output["grouping_frame_sha256"] = sha256(args.frame)
        output["issue_catalog_sha256"] = sha256(args.catalog)
        output["membership_sha256"] = sha256(args.membership)
        private_json(args.out, output)
        print(json.dumps({"baseline_candidates": 30403, "public_candidates": 30379,
            "ranking_sha256": sha256(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()

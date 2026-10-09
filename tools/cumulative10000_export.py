"""Build the private 10k dashboard handoff from two frozen source checkpoints.

The independent semantic audit is an overlay. Saved model outputs are never
rewritten. This exports accepted evidence for offline grouping, plus every
excluded source ID/hash and the full project exposure including held calls.
"""

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256
from spotify_pipeline.project_budget import ProjectBudget
from tools.checkpoint5000_dispatch import legacy_paths
from tools.next5000_checkpoint import BUDGET, MANIFEST, load_manifest, canonical

FIRST_MANIFEST = Path("local/checkpoint5000_manifest.json")
FIRST_EXPORT = Path("local/checkpoint5000_dashboard_handoff.json")
OUT = Path("local/cumulative10000_dashboard_handoff.json")
FIRST_EXPORT_SHA = "9151280ed4c5002774a1b5486816d1fef7d794beb3d979bd29af70adf7650b68"


def _semantic_overlay(path, first500_ids, accepted_ids):
    with open(path, encoding="utf-8") as stream:
        audit = json.load(stream)
    if audit.get("source_counts", {}).get("accepted") != 494:
        raise ValueError("independent audit source frame differs")
    sampled = {r["source"]["review_id"] for r in audit["random_accepted"]}
    for group in audit["risk_cases"].values():
        sampled.update(r["source"]["review_id"] for r in group)
    flags = defaultdict(list)
    for finding in audit["semantic_audit"]["findings"]:
        rid = finding["review_id"]
        if rid not in first500_ids or rid not in accepted_ids or rid not in sampled:
            raise ValueError("semantic finding is outside accepted audited first-500 rows")
        if finding.get("human_review_required") is not True:
            raise ValueError("semantic finding lacks human-review flag")
        flags[rid].append(finding)
    if len(audit["semantic_audit"]["findings"]) != 44 or len(flags) != 39:
        raise ValueError("independent audit finding count differs")
    if not sampled <= first500_ids or not sampled <= accepted_ids:
        raise ValueError("semantic sample differs from accepted first-500 frame")
    return sampled, flags, {"source_sha256": file_sha256(str(path)),
        "sampled_distinct_ids": len(sampled), "finding_count": 44,
        "flagged_distinct_ids": 39, "method": audit["semantic_audit"]["method"],
        "not_accuracy": audit["semantic_audit"]["not_accuracy"]}


def build(first, first_manifest, second, budget, audit_path):
    db = budget.db
    prior = first.get("coverage", {})
    if first.get("schema_version") != "checkpoint5000-dashboard-handoff-v1" or \
            prior.get("selected_source_rows") != 5000 or \
            prior.get("accepted_rows") != 4649 or \
            prior.get("quarantined_rows") != 285 or prior.get("uncertain_rows") != 66:
        raise ValueError("frozen first-5,000 export differs")
    if first_manifest.get("source_file_sha256") != second["source_file_sha256"] or \
            [r["source_position"] for r in first_manifest["rows"]] != list(range(1, 5001)):
        raise ValueError("source manifest lineage differs")
    positions = {r["review_id"]: r["source_position"] for r in first_manifest["rows"]}
    first_ids = set(positions)
    second_ids = {r["review_id"] for r in second["rows"]}
    if len(first_ids) != 5000 or len(second_ids) != 5000 or first_ids & second_ids:
        raise ValueError("ten-thousand source IDs overlap or differ")
    accepted_first = {r["review_id"] for r in first["records"]}
    if len(accepted_first) != 4649 or len({r["review_id"] for r in first["excluded"]}) != 351:
        raise ValueError("first checkpoint accepted/excluded source IDs differ")
    label_rows = {rid: (json.loads(value), cfg, provenance, origin, key)
        for rid, value, cfg, provenance, origin, key in db.execute(
            "SELECT * FROM next5000_labels")}
    evidence_rows = {rid: (json.loads(entities), quote, cfg, provenance, origin, key)
        for rid, entities, quote, cfg, provenance, origin, key in db.execute(
            "SELECT * FROM next5000_evidence")}
    quarantines = {rid: (reason, key) for rid, reason, key in db.execute(
        "SELECT * FROM next5000_quarantines")}
    if len(label_rows) != 4985 or len(evidence_rows) != 4917 or len(quarantines) != 48:
        raise ValueError("terminal next-5,000 coverage differs")
    sampled, flags, audit_meta = _semantic_overlay(audit_path,
        {r["review_id"] for r in second["rows"][:500]}, set(evidence_rows))
    request_ids = {}
    for key, raw in db.execute("SELECT request_key,response_json FROM next5000_requests"):
        request_ids[key] = json.loads(raw).get("id") if raw else None
    uncertain_direct, uncertain_texts = set(), set()
    for key, rid, text in db.execute("""SELECT q.request_key,r.review_id,r.review_text
            FROM next5000_requests q JOIN next5000_members m USING(request_key)
            JOIN next5000_rows r USING(review_id) WHERE q.status='uncertain'"""):
        uncertain_direct.add(rid)
        uncertain_texts.add(text)
    if len(uncertain_direct) != 20:
        raise ValueError("two new uncertain ten-review memberships differ")
    records = []
    for source_record in first["records"]:
        record = dict(source_record)
        if row_sha256([record["source"][k] for k in SOURCE_FIELDS]) != record["source_sha256"]:
            raise ValueError("first-checkpoint source hash differs")
        validate_evidence(record["source"]["review_text"], record["evidence"])
        record["source_position"] = positions[record["review_id"]]
        record["semantic_review"] = {"sampled_in_first500_audit": False,
            "findings": [], "human_review_required": False,
            "representative_evidence_blocked_by_known_flags": False}
        records.append(record)
    excluded = list(first["excluded"])
    next_counts = Counter()
    for row in second["rows"]:
        rid, text = row["review_id"], row["review_text"]
        if row_sha256([row[k] for k in SOURCE_FIELDS]) != row["source_sha256"]:
            raise ValueError("next-checkpoint source hash differs")
        if rid in evidence_rows:
            entities, quote, ecfg, eprov, eorigin, ekey = evidence_rows[rid]
            validate_evidence(text, {"entities": entities, "evidence_quote": quote})
            label, lcfg, lprov, lorigin, lkey = label_rows[rid]
            findings = flags.get(rid, [])
            records.append({"review_id": rid, "source_position": row["source_position"],
                "source": {k: row[k] for k in SOURCE_FIELDS},
                "source_sha256": row["source_sha256"], "labels": label,
                "evidence": {"entities": entities, "evidence_quote": quote},
                "provenance": {"label": {"kind": lprov, "config_sha256": lcfg,
                    "cache_source_id": lorigin, "request_key": lkey},
                    "evidence": {"kind": eprov, "config_sha256": ecfg,
                    "cache_source_id": eorigin, "request_key": ekey,
                    "provider_generation_id": request_ids.get(ekey)}},
                "semantic_review": {"sampled_in_first500_audit": rid in sampled,
                    "findings": findings, "human_review_required": bool(findings),
                    "representative_evidence_blocked_by_known_flags": bool(findings)}})
            next_counts["accepted"] += 1
        else:
            if rid in quarantines:
                status, reason, key = "quarantined", quarantines[rid][0], quarantines[rid][1]
            elif row["blocked_prior_uncertainty"]:
                status, reason, key = "uncertain_prior_exact_text_alias", \
                    "exact text matches older held request", None
            elif rid in uncertain_direct or text in uncertain_texts:
                status, reason, key = ("uncertain" if rid in uncertain_direct else
                    "uncertain_exact_text_alias"), "new request delivery unresolved", None
            else:
                raise ValueError("selected source ID has no terminal state")
            excluded.append({"review_id": rid, "source_position": row["source_position"],
                "source_sha256": row["source_sha256"], "status": status,
                "reason": reason, "request_key": key})
            next_counts[status] += 1
    if next_counts != Counter({"accepted": 4917, "quarantined": 48,
            "uncertain": 20, "uncertain_prior_exact_text_alias": 15}) or \
            len(records) != 9566 or len(excluded) != 434 or \
            len({r["review_id"] for r in records + excluded}) != 10000:
        raise ValueError("ten-thousand source accounting differs")
    charges = {stage: db.execute("SELECT COALESCE(SUM(charged_nusd),0) FROM next5000_requests WHERE stage=?",
        (stage,)).fetchone()[0] for stage in ("jev", "evidence")}
    topic_summary = []
    topics = defaultdict(lambda: [0, 0])
    for record in records:
        topic = record["labels"]["topic"]
        topics[topic][0] += 1
        topics[topic][1] += record["labels"]["severity"]
    for topic in sorted(topics):
        topic_summary.append({"topic": topic, "count": topics[topic][0],
            "severity_sum": topics[topic][1]})
    return {"schema_version": "spotify-cumulative10000-dashboard-handoff-v1",
        "scope": "first_10000_development_source_reviews",
        "source_file_sha256": second["source_file_sha256"],
        "manifest_sha256": {"first5000": file_sha256(str(FIRST_MANIFEST)),
            "next5000": file_sha256(str(MANIFEST))},
        "coverage": {"selected_source_rows": 10000, "accepted_rows": len(records),
            "quarantined_rows": 333, "uncertain_or_blocked_rows": 101,
            "eligible_pending_rows": 0, "in_flight_rows": 0,
            "next5000_states": dict(next_counts)},
        "cost_nusd": {"first5000_measured": first["cost_nusd"]["checkpoint_measured_charge"],
            "next5000_measured": charges,
            "cumulative_exposure_including_holds": {budget_name: budget.exposure(budget_name)
                for budget_name in ("jev", "openrouter")},
            "caps": {"jev": 600000000, "openrouter": 5000000000},
            "new_uncertain_full_holds": 2 * 5545984,
            "older_uncertain_full_hold": 24903544},
        "semantic_audit_overlay": audit_meta,
        "topic_summary_rule": "Accepted rows only. This is descriptive, not issue grouping or a recommendation.",
        "topic_summary": topic_summary, "records": records, "excluded": excluded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("private cumulative export already exists")
    if file_sha256(str(FIRST_EXPORT)) != FIRST_EXPORT_SHA:
        raise ValueError("first-5,000 private handoff changed")
    with FIRST_EXPORT.open(encoding="utf-8") as stream:
        first = json.load(stream)
    with FIRST_MANIFEST.open(encoding="utf-8") as stream:
        first_manifest = json.load(stream)
    second, _ = load_manifest()
    with ProjectBudget(BUDGET, legacy_paths()) as budget:
        if budget.db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
            raise ValueError("project has active reservation; export deferred")
        result = build(first, first_manifest, second, budget, args.qa_overlay)
    fd = os.open(str(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(canonical(result) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(canonical({"coverage": result["coverage"], "cost_nusd": result["cost_nusd"],
        "semantic_audit_overlay": result["semantic_audit_overlay"],
        "private_export_sha256": file_sha256(str(args.output))}))


if __name__ == "__main__":
    main()

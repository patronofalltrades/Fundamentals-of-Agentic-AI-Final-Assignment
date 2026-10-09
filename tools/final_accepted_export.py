"""Export a drained accepted-evidence run to a private, source-verified handoff.

Run from the benchmark worktree with explicit private input paths. This never
dispatches a model request. The output contains review text and must stay local.
"""

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from spotify_pipeline.project_budget import ProjectBudget
from tools.checkpoint5000_dispatch import legacy_paths
from tools.scale100k_queue import status as queue_status

BASELINE_SHA = "857dc1b50612fe5fe49f4ee4a9b2efcdeaa8bf5db492a53ef34f0e9873a5e203"
BASE_SHA = "cdc9a74ab8d623af2ddbaf32b28c19ca51e47d1e05309129384982d8da52f107"
EXTENSION_SHA = "485e69bc010c12877b867018199d12494945867a650f8cb742e734b7a6a1d6ab"
PULSE_SHA = "53f4bb42cf55c189cfb1282478b24c6fcb8adc321ccaa0abd65026e8b9a2e26f"
CAP = 5000000000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False)


def verified_json(path, digest):
    if file_sha256(str(path)) != digest:
        raise ValueError("frozen private input digest differs: " + path.name)
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def source_rows(base, extension, activated):
    if base.get("selected_rows") != 90000 or extension.get("selected_rows") != 20000 or \
            extension.get("base_manifest_sha256") != BASE_SHA or \
            base.get("source_file_sha256") != extension.get("source_file_sha256"):
        raise ValueError("frozen source manifest lineage differs")
    rows = (base["rows"] + extension["rows"])[:activated]
    if len(rows) != activated or activated % 10000 or not 90000 <= activated <= 110000:
        raise ValueError("activated source scope differs")
    seen = set()
    for position, row in enumerate(rows, 10001):
        rid = row["review_id"]
        if rid in seen or row["source_position"] != position or \
                row_sha256([row[k] for k in SOURCE_FIELDS]) != row["source_sha256"] or \
                text_sha256(row["review_text"]) != row["text_sha256"]:
            raise ValueError("frozen source ID, position, or hash differs")
        seen.add(rid)
    return rows


def pulse_flags(overlay, source, accepted):
    if overlay.get("schema") != "scale100k-semantic-findings-overlay-v1" or \
            len(overlay.get("findings", [])) != 8 or \
            overlay.get("saved_model_outputs_preserved") is not True:
        raise ValueError("semantic overlay frame differs")
    flags = defaultdict(list)
    for finding in overlay["findings"]:
        rid = finding["review_id"]
        row = source.get(rid)
        if row is None or rid not in accepted or \
                finding["source_position"] != row["source_position"] or \
                finding["source_sha256"] != row["source_sha256"] or \
                finding["text_sha256"] != row["text_sha256"] or \
                finding.get("human_review_required") is not True or \
                finding.get("representative_evidence_blocked_by_known_flag") is not True:
            raise ValueError("semantic finding does not match an accepted source row")
        flags[rid].append(finding)
    if len(flags) != 8:
        raise ValueError("semantic overlay distinct-source count differs")
    return flags


def build(baseline, base, extension, overlay, budget):
    db = budget.db
    if baseline.get("schema_version") != "spotify-cumulative10000-dashboard-handoff-v1" or \
            baseline.get("coverage", {}).get("accepted_rows") != 9566 or \
            baseline.get("coverage", {}).get("selected_source_rows") != 10000 or \
            len(baseline.get("records", [])) != 9566 or \
            len(baseline.get("excluded", [])) != 434 or \
            baseline.get("source_file_sha256") != base.get("source_file_sha256"):
        raise ValueError("earlier accepted source frame differs")
    if db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
        raise ValueError("paid request is still reserved")
    current = queue_status(db, budget)
    activated = current["activated_source_rows"]
    if current["source_states"].get("in_flight", 0) or \
            current["source_states"].get("eligible_or_awaiting_label", 0) or \
            current["jev_eligible_unique"] or current["evidence_eligible_unique"]:
        raise ValueError("source gate has not drained")
    rows = source_rows(base, extension, activated)
    source = {row["review_id"]: row for row in rows}
    if len(source) != activated:
        raise ValueError("scale source IDs overlap")
    frozen = {row["review_id"]: (row["source_position"], row["source_sha256"])
        for row in rows}
    stored = {rid: (position, source_sha) for position, rid, source_sha in
        db.execute("SELECT position,review_id,source_sha FROM scale_rows")}
    if stored != frozen:
        raise ValueError("activated ledger ID, position, or source hash differs")
    if activated > 90000 and db.execute(
            "SELECT value FROM scale_meta WHERE key='extension_manifest_sha256'").fetchone() != \
            (EXTENSION_SHA,):
        raise ValueError("extension ledger identity differs")
    labels = {rid: (json.loads(value), config, kind, origin, key)
        for rid, value, config, kind, origin, key in db.execute("SELECT * FROM scale_labels")}
    evidence = {rid: (json.loads(entities), quote, config, kind, origin, key)
        for rid, entities, quote, config, kind, origin, key in db.execute(
            "SELECT * FROM scale_evidence")}
    quarantines = {rid: (reason, key) for rid, reason, key in db.execute(
        "SELECT * FROM scale_quarantines")}
    flags = pulse_flags(overlay, source, evidence)
    attempts = {}
    direct = {}
    request_meta = []
    for key, stage, state, response, elapsed, inp, out, reasoning, charge, error in \
            db.execute("""SELECT request_key,stage,status,response_json,
                elapsed_seconds,input_tokens,output_tokens,reasoning_tokens,
                charged_nusd,error_class FROM scale_requests ORDER BY rowid"""):
        generation = json.loads(response).get("id") if response else None
        members = [rid for rid, in db.execute(
            "SELECT review_id FROM scale_members WHERE request_key=?", (key,))]
        if not members:
            raise ValueError("saved request has no source members")
        for rid in members:
            attempts[(stage, source[rid]["review_text"])] = state
            direct.setdefault(rid, []).append((stage, state, key))
        request_meta.append({"request_key": key, "stage": stage, "status": state,
            "member_count": len(members), "provider_generation_id": generation,
            "elapsed_seconds": elapsed, "input_tokens": inp, "output_tokens": out,
            "reasoning_tokens": reasoning, "charged_nusd": charge,
            "error_class": error})
    generation_by_key = {r["request_key"]: r["provider_generation_id"] for r in request_meta}
    records = []
    baseline_ids = set()
    baseline_flags = 0
    for original in baseline["records"]:
        record = dict(original)
        rid = record["review_id"]
        if rid in baseline_ids or rid in source or \
                row_sha256([record["source"][k] for k in SOURCE_FIELDS]) != record["source_sha256"]:
            raise ValueError("earlier accepted source ID or hash differs")
        validate_evidence(record["source"]["review_text"], record["evidence"])
        baseline_ids.add(rid)
        baseline_flags += bool(record["semantic_review"].get(
            "representative_evidence_blocked_by_known_flags"))
        records.append(record)
    if baseline_flags != 39:
        raise ValueError("earlier semantic exclusions differ")
    excluded = list(baseline["excluded"])
    earlier_ids = baseline_ids | {row["review_id"] for row in excluded}
    if len(earlier_ids) != 10000 or earlier_ids & set(source):
        raise ValueError("earlier selected source IDs overlap or differ")
    states = Counter()
    for row in rows:
        rid, text = row["review_id"], row["review_text"]
        if rid in evidence:
            if rid not in labels or rid in quarantines:
                raise ValueError("accepted source lacks label or is quarantined")
            entities, quote, e_cfg, e_kind, e_origin, e_key = evidence[rid]
            validate_evidence(text, {"entities": entities, "evidence_quote": quote})
            label, l_cfg, l_kind, l_origin, l_key = labels[rid]
            findings = flags.get(rid, [])
            records.append({"review_id": rid, "source_position": row["source_position"],
                "source": {k: row[k] for k in SOURCE_FIELDS},
                "source_sha256": row["source_sha256"], "labels": label,
                "evidence": {"entities": entities, "evidence_quote": quote},
                "provenance": {"label": {"kind": l_kind, "config_sha256": l_cfg,
                    "cache_source_id": l_origin, "request_key": l_key},
                    "evidence": {"kind": e_kind, "config_sha256": e_cfg,
                        "cache_source_id": e_origin, "request_key": e_key,
                        "provider_generation_id": generation_by_key.get(e_key)}},
                "semantic_review": {"findings": findings,
                    "human_review_required": bool(findings),
                    "representative_evidence_blocked_by_known_flags": bool(findings)}})
            states["accepted"] += 1
            continue
        if rid in quarantines:
            state, reason, key = "quarantined", *quarantines[rid]
        elif row["review_text"].strip() == "":
            state, reason, key = "empty_text", "empty source text", None
        elif (blocked := db.execute("SELECT blocked_reason FROM scale_rows WHERE review_id=?",
                (rid,)).fetchone()[0]):
            state, reason, key = blocked, blocked, None
        elif any(s == "uncertain" for _, s, _ in direct.get(rid, [])):
            state, reason, key = "uncertain_direct", "request delivery unresolved", next(
                k for _, s, k in direct[rid] if s == "uncertain")
        elif any(attempts.get((stage, text)) == "uncertain" for stage in ("jev", "evidence")):
            state, reason, key = "uncertain_exact_text_alias", "exact text matches held request", None
        elif any((stage, text) in attempts for stage in ("jev", "evidence")):
            state, reason, key = "attempted_exact_text_alias", "attempted exact text is excluded", None
        else:
            raise ValueError("drained source row has no terminal state")
        excluded.append({"review_id": rid, "source_position": row["source_position"],
            "source_sha256": row["source_sha256"], "status": state,
            "reason": reason, "request_key": key})
        states[state] += 1
    if states != Counter(current["source_states"]) or \
            len(records) != 9566 + current["source_states"].get("accepted", 0) or \
            len(records) + len(excluded) != 10000 + activated or \
            len({r["review_id"] for r in records + excluded}) != 10000 + activated:
        raise ValueError("selected source-state partition differs")
    if len(records) < 100000:
        raise ValueError("100,000 accepted source-ID target has not been reached")
    charges = dict(current["charges_nusd"])
    exposure = current["exposure_nusd"]
    if any(exposure[name] >= CAP for name in ("jev", "openrouter")):
        raise ValueError("cumulative provider cap reached")
    topic = defaultdict(lambda: [0, 0])
    for record in records:
        label = record["labels"]
        topic[label["topic"]][0] += 1
        topic[label["topic"]][1] += label["severity"]
    return {"schema_version": "spotify-accepted100k-dashboard-handoff-v1",
        "scope": "development_source_reviews_only", "source_file_sha256": base["source_file_sha256"],
        "frozen_manifest_sha256": {"baseline_export": BASELINE_SHA, "base": BASE_SHA,
            "extension": EXTENSION_SHA},
        "coverage": {"selected_source_rows": 10000 + activated,
            "accepted_rows": len(records), "excluded_rows": len(excluded),
            "scale_source_states": dict(states), "pending_rows": 0, "in_flight_rows": 0,
            "known_semantic_flags_excluded_from_representative_evidence": baseline_flags + len(flags)},
        "cost_nusd": {"scale_known_charges": charges,
            "shared_exposure_including_all_holds": exposure,
            "cumulative_caps": {"jev": CAP, "openrouter": CAP}},
        "semantic_overlay": {"pulse_sha256": PULSE_SHA,
            "pulse_flagged_distinct_ids": len(flags),
            "earlier_flagged_distinct_ids": baseline_flags,
            "not_human_accuracy": True},
        "topic_summary_rule": "Accepted rows only; descriptive, not issue grouping or a recommendation.",
        "topic_summary": [{"topic": key, "count": value[0], "severity_sum": value[1]}
            for key, value in sorted(topic.items())],
        "request_metadata": request_meta, "records": records, "excluded": excluded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--extension-manifest", type=Path, required=True)
    parser.add_argument("--pulse-overlay", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("private handoff already exists")
    baseline = verified_json(args.baseline, BASELINE_SHA)
    base = verified_json(args.base_manifest, BASE_SHA)
    extension = verified_json(args.extension_manifest, EXTENSION_SHA)
    overlay = verified_json(args.pulse_overlay, PULSE_SHA)
    with ProjectBudget(str(args.budget), legacy_paths()) as budget:
        result = build(baseline, base, extension, overlay, budget)
    fd = os.open(str(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(result) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print(canonical({"coverage": result["coverage"],
        "cost_nusd": result["cost_nusd"],
        "private_export_sha256": file_sha256(str(args.output))}))


if __name__ == "__main__":
    main()

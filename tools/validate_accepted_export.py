"""Independently check a private accepted-evidence dashboard handoff offline."""

import argparse
from collections import Counter
import json
from pathlib import Path

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256
from tools.final_accepted_export import BASE_SHA, BASELINE_SHA, EXTENSION_SHA, PULSE_SHA


def loaded(path, digest):
    if file_sha256(str(path)) != digest:
        raise ValueError("frozen input digest differs: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def validate(export, baseline, base, extension, pulse):
    coverage = export["coverage"]
    accepted = export["records"]
    excluded = export["excluded"]
    if export.get("schema_version") != "spotify-accepted100k-dashboard-handoff-v1" or \
            coverage["selected_source_rows"] != 110000 or \
            coverage["accepted_rows"] != 100229 or len(accepted) != 100229 or \
            coverage["excluded_rows"] != 9771 or len(excluded) != 9771 or \
            coverage["pending_rows"] != 6522 or coverage["in_flight_rows"] != 0:
        raise ValueError("final coverage differs")
    base_ids = {r["review_id"] for r in baseline["records"] + baseline["excluded"]}
    if len(base_ids) != 10000:
        raise ValueError("earlier selected IDs differ")
    source = {r["review_id"]: r for r in base["rows"] + extension["rows"][:10000]}
    if len(source) != 100000 or base_ids & set(source):
        raise ValueError("selected source frame overlaps or differs")
    selected = base_ids | set(source)
    seen, states = set(), Counter()
    flags = set()
    for record in accepted:
        rid = record["review_id"]
        if rid in seen or rid not in selected:
            raise ValueError("accepted ID repeats or is outside selected source")
        seen.add(rid)
        if row_sha256([record["source"][k] for k in SOURCE_FIELDS]) != record["source_sha256"]:
            raise ValueError("accepted original source hash differs")
        validate_evidence(record["source"]["review_text"], record["evidence"])
        if rid in source:
            expected = source[rid]
            if record["source_position"] != expected["source_position"] or \
                    record["source_sha256"] != expected["source_sha256"]:
                raise ValueError("accepted staged source identity differs")
        if record["semantic_review"]["representative_evidence_blocked_by_known_flags"]:
            if not record["semantic_review"]["human_review_required"] or \
                    not record["semantic_review"]["findings"]:
                raise ValueError("representative exclusion lacks finding")
            flags.add(rid)
    for record in excluded:
        rid = record["review_id"]
        if rid in seen or rid not in selected:
            raise ValueError("excluded ID repeats or is outside selected source")
        seen.add(rid)
        if rid in source:
            expected = source[rid]
            if record["source_position"] != expected["source_position"] or \
                    record["source_sha256"] != expected["source_sha256"]:
                raise ValueError("excluded staged source identity differs")
            states[record["status"]] += 1
    if seen != selected or len(flags) != 47 or \
            coverage["known_semantic_flags_excluded_from_representative_evidence"] != 47 or \
            states["eligible_or_awaiting_label"] != 6522:
        raise ValueError("source partition or representative exclusions differ")
    pulse_ids = {r["review_id"] for r in pulse["findings"]}
    if len(pulse_ids) != 8 or not pulse_ids <= flags:
        raise ValueError("eight pulse findings are not all blocked")
    original_flags = {r["review_id"] for r in baseline["records"] if
        r["semantic_review"]["representative_evidence_blocked_by_known_flags"]}
    if len(original_flags) != 39 or not original_flags <= flags:
        raise ValueError("earlier semantic exclusions were lost")
    if Counter(coverage["scale_source_states"]) != \
            Counter({"accepted": 90663, **states}) or \
            export["cost_nusd"]["shared_exposure_including_all_holds"] != \
            {"jev": 3310141884, "openrouter": 2469486956}:
        raise ValueError("saved source states or conservative exposure differ")
    return {"selected": len(seen), "accepted": len(accepted),
        "excluded": len(excluded), "pending": states["eligible_or_awaiting_label"],
        "representative_exclusions": len(flags), "pulse_findings": len(pulse_ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("export", "baseline", "base_manifest", "extension_manifest", "pulse_overlay"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    export = json.loads(args.export.read_text(encoding="utf-8"))
    result = validate(export, loaded(args.baseline, BASELINE_SHA),
        loaded(args.base_manifest, BASE_SHA),
        loaded(args.extension_manifest, EXTENSION_SHA),
        loaded(args.pulse_overlay, PULSE_SHA))
    print(json.dumps({**result, "export_sha256": file_sha256(str(args.export))},
        sort_keys=True))


if __name__ == "__main__":
    main()

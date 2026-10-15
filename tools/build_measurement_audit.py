"""Recompute measurement coverage from published, text-free cases and call logs.

Offline only. Reads no source reviews, human answers, database or credentials.
The output contains aggregates and input-file hashes, never case references.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GAP = "reports/gap-closure-2026-10-16"
OUT = "reports/production-measurement-audit-2026-10-15.json"
FIELDS = {
    "verifier_cases.csv": ("review_ref", "jev_topic", "jev_intent", "jev_severity", "verifier_topic", "verifier_intent", "verifier_severity"),
    "grouping_cases.csv": ("review_ref", "historical_issue", "stage_issue"),
    "planted_label_cases.csv": ("review_ref", "planted_field", "claimed_topic", "claimed_intent", "claimed_severity", "topic_supported", "intent_supported", "severity_supported"),
    "planted_issue_cases.csv": ("review_ref", "planted", "claimed_issue", "supported"),
}
CALL_FIELDS = {"charged", "created", "elapsed", "error", "inp", "key", "out", "phase",
               "reasoning", "reserved", "role", "settled", "status"}


def index_cases(rows):
    result = {}
    for row in rows:
        ref = row["review_ref"]
        if not re.fullmatch(r"[0-9a-f]{64}", ref) or ref in result:
            raise ValueError("Expected distinct hashed case references")
        result[ref] = row
    return result


def blind_join(claims, predictions, claimed, predicted):
    """Missing outputs never count as agreement or as detected perturbations."""
    joined = [r for r in claims if r["review_ref"] in predictions]
    disagreed = sum(r[claimed(r)] != predictions[r["review_ref"]][predicted(r)] for r in joined)
    return {"audit_cases": len(claims), "paired_outputs": len(joined),
            "missing_outputs": len(claims) - len(joined), "disagreed": disagreed,
            "agreed": len(joined) - disagreed,
            "disagreement_on_paired_outputs": disagreed / len(joined) if joined else None}


def derive(cases, calls, gap, extractor):
    v, g, labels, issues = (index_cases(cases[n]) for n in
                           ("verifier_cases.csv", "grouping_cases.csv", "planted_label_cases.csv", "planted_issue_cases.csv"))
    label_plants = [r for r in labels.values() if r["planted_field"]]
    issue_plants = [r for r in issues.values() if r["planted"].lower() == "true"]
    label_join = blind_join(label_plants, v,
                           lambda r: "claimed_" + r["planted_field"],
                           lambda r: "verifier_" + r["planted_field"])
    issue_join = blind_join(issue_plants, g, lambda r: "claimed_issue", lambda r: "stage_issue")
    observed = len(v)
    agreement = {f: sum(r["jev_" + f] == r["verifier_" + f] for r in v.values())
                 for f in ("topic", "intent", "severity")}
    agreement["joint"] = sum(all(r["jev_" + f] == r["verifier_" + f]
                                 for f in ("topic", "intent", "severity")) for r in v.values())
    for field, n in agreement.items():
        expected = gap["blind_verifier"]["agreement_with_jev"][field]
        if expected["n"] != n or expected["of"] != observed:
            raise ValueError("Verifier aggregate and public case arithmetic differ")
    if len({c["key"] for c in calls}) != len(calls):
        raise ValueError("Duplicate attempt key")
    for c in calls:
        for field in ("charged", "reserved"):
            value = c[field]
            if field == "charged" and value is None:
                continue
            if type(value) is not int or value < 0:
                raise ValueError("Expected nonnegative integer cost or an unknown charge")
    charged = sum(c["charged"] for c in calls if c["charged"] is not None)
    held = [c for c in calls if c["charged"] is None]
    reserved = sum(c["reserved"] for c in held)
    if (charged, reserved) != (gap["charged_nusd"], gap["held_uncertain_nusd"]):
        raise ValueError("Cost aggregate and public call arithmetic differ")
    settled_status = {"succeeded", "quarantined_metered"}
    logical = lambda c: c["key"].split("#", 1)[0]
    initial_settled = {logical(c) for c in calls if c["phase"] == "initial" and c["status"] in settled_status}
    all_logical = {logical(c) for c in calls}
    all_settled = {logical(c) for c in calls if c["status"] in settled_status}
    resent = sum(c["phase"] == "resumed" and logical(c) in initial_settled for c in calls)
    by_error = {}
    for c in held:
        entry = by_error.setdefault(c.get("error") or "unclassified", {"attempts": 0, "held_nusd": 0})
        entry["attempts"] += 1
        entry["held_nusd"] += c["reserved"]
    extraction = {}
    for route, values in extractor["routes"].items():
        attempted, accepted = values["reviews_attempted"], values["reviews_accepted"]
        if not 0 <= accepted <= attempted <= extractor["source_reviews"]:
            raise ValueError("Invalid extractor coverage")
        extraction[route] = {"selected": extractor["source_reviews"], "attempted": attempted,
                             "accepted": accepted, "attempted_without_accepted_output": attempted - accepted,
                             "untouched": extractor["source_reviews"] - attempted}
    return {
        "version": 1, "scope": "saved experiments; no new inference or human scoring",
        "source_sha256": gap["inputs"]["source_sha256"], "label_config": gap["inputs"]["jev_config"],
        "verifier": {"selected": gap["blind_verifier"]["sample"], "observed": observed,
                     "missing": gap["blind_verifier"]["sample"] - observed, "agreement_counts": agreement,
                     "route_split_from_report": gap["blind_verifier"]["joint_agreement_by_route"],
                     "not_human_accuracy": True},
        "grouping": {"selected": gap["grouping_stage"]["sample"], "observed": len(g),
                     "missing": gap["grouping_stage"]["sample"] - len(g),
                     "exact_agreement": sum(r["historical_issue"] == r["stage_issue"] for r in g.values())},
        "planted_labels": label_join, "planted_issues": issue_join,
        "injection": {"pairs": gap["prompt_injection"]["pairs"],
                      "paired_label_or_issue_changes": sum(bool(c[role + "_changed"])
                          for c in gap["prompt_injection"]["cases"] for role in ("jev", "verifier", "grouping")),
                      "comparisons": 3 * len(gap["prompt_injection"]["cases"])},
        "recovery": {"initial_settled_logical_requests": len(initial_settled),
                     "resumed_attempts_for_initial_settled_requests": resent,
                     "logical_requests": len(all_logical), "settled_logical_requests": len(all_settled),
                     "logical_requests_without_settled_result": len(all_logical - all_settled),
                     "signal_and_checkpoint_details": "reported in the saved aggregate; private snapshots not rechecked"},
        "extractor": extraction,
        "cost": {"attempts": len(calls), "known_charge_nusd": charged, "held_nusd": reserved,
                 "known_plus_held_nusd": charged + reserved, "unknown_charge_attempts": len(held),
                 "held_by_error": by_error, "status_counts": dict(sorted(Counter(c["status"] for c in calls).items())),
                 "phase_counts": dict(sorted(Counter(c["phase"] for c in calls).items())),
                 "public_route_fields_complete": all("route" in c for c in calls)},
        "limits": ["Missing outputs are excluded from paired agreement and counted separately.",
                   "Model agreement and changed model claims are not human accuracy.",
                   "Route labels come from the saved aggregate; public call rows omit provider route fields.",
                   "Charges and holds describe this separate experiment, not the complete project bill."],
    }


def build(root=ROOT):
    sources = []
    def read(path):
        data = (root / path).read_bytes()
        sources.append({"path": path, "sha256": hashlib.sha256(data).hexdigest()})
        return data.decode("utf-8")
    gap = json.loads(read(GAP + "/aggregate.json"))
    extractor = json.loads(read("reports/extractor-benchmark-aggregate.json"))
    cases = {}
    for name, fields in FIELDS.items():
        reader = csv.DictReader(io.StringIO(read(GAP + "/" + name)))
        if tuple(reader.fieldnames or []) != fields:
            raise ValueError("Unexpected public case columns; raw text and answers are not allowed")
        cases[name] = list(reader)
    calls = [json.loads(line) for line in read(GAP + "/calls.jsonl").splitlines() if line.strip()]
    if any(set(c) != CALL_FIELDS for c in calls):
        raise ValueError("Unexpected public call fields")
    return {**derive(cases, calls, gap, extractor), "built_from": sources}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    target = ROOT / OUT
    if args.check:
        if not target.exists() or target.read_text() != rendered:
            raise SystemExit("Measurement aggregate is out of date")
        print("measurement aggregate is current")
    else:
        target.write_text(rendered)
        print("wrote " + OUT)
    return 0


if __name__ == "__main__":
    main()

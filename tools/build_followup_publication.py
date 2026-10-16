"""Offline, read-only diagnosis and aggregate publication candidate. No API calls.

Private source IDs/texts and raw receipts never appear in the output. Original
SQLite files are opened read-only. Human answers are not read. The output is a
new report; this tool never rewrites the saved run or its ledger.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from tools import bounded_gap_followup as b
from tools import gap_closure_eval as g


def identity_counts(requested, returned):
    freq = Counter(returned)
    return {"requested": len(requested), "returned": len(returned),
        "exact_occurrences": sum(i in requested for i in returned),
        "unique_exact": len(set(returned) & set(requested)),
        "unknown": sum(i not in requested for i in returned),
        "missing": len(set(requested) - set(returned)),
        "duplicate_values": sum(n > 1 for n in freq.values()),
        "extra_duplicate_occurrences": sum(n - 1 for n in freq.values() if n > 1),
        "complete_exact_bijection": len(returned) == len(set(returned)) == len(requested) and set(returned) == set(requested),
        "repair_by_position_or_similarity_permitted": False}


def paired_table(ids, audit, blind):
    return {"both_flagged": sum(audit(r) and blind(r) for r in ids),
            "auditor_only": sum(audit(r) and not blind(r) for r in ids),
            "blind_only": sum(not audit(r) and blind(r) for r in ids),
            "neither_flagged": sum(not audit(r) and not blind(r) for r in ids)}


def comparisons(plan, values):
    verifier, grouped = values["verify"], values["group"]
    audit, issue_audit = values["audit_label"], values["audit_group"]
    lc, gc, hist = plan["label_claims"], plan["group_claims"], plan["historical_issue"]
    labels_changed = [r for r in lc if lc[r]["planted"]]
    labels_clean = [r for r in lc if not lc[r]["planted"]]
    issues_changed = [r for r in gc if gc[r]["planted"]]
    issues_clean = [r for r in gc if not gc[r]["planted"]]
    paired_labels = [r for r in labels_changed if r in audit and r in verifier]
    paired_issues = [r for r in issues_changed if r in issue_audit and r in grouped]
    lab_flag = lambda r: audit[r][lc[r]["planted"] + "_supported"] is False
    blind_lab = lambda r: verifier[r][lc[r]["planted"]] != lc[r]["claim"][lc[r]["planted"]]
    iss_flag = lambda r: issue_audit[r]["supported"] is False
    blind_iss = lambda r: grouped[r]["issue_id"] != gc[r]["claim"]
    gids = [r for r in plan["group_ids"] if r in grouped]
    v_ids = [r for r in plan["verify_ids"] if r in verifier]
    jl = plan["jev_labels"]
    def observed_share(ids, outputs, flag):
        observed = [r for r in ids if r in outputs]
        return g.share(sum(flag(r) for r in observed), len(observed))
    return {"coverage": {"verify": g.share(len(v_ids), len(plan["verify_ids"])),
                          "group": g.share(len(gids), len(plan["group_ids"])),
                          "audit_label": g.share(len(audit), len(lc)), "audit_group": g.share(len(issue_audit), len(gc))},
        "verifier_agreement": {**{f: g.share(sum(verifier[r][f] == jl[r][f] for r in v_ids), len(v_ids)) for f in g.LABELS},
            "joint": g.share(sum(all(verifier[r][f] == jl[r][f] for f in g.LABELS) for r in v_ids), len(v_ids))},
        "grouping": {"exact": g.share(sum(grouped[r]["issue_id"] == hist[r] for r in gids), len(gids)),
            "family": g.share(sum(grouped[r]["issue_id"] != "abstain" and g.family(grouped[r]["issue_id"]) == g.family(hist[r]) for r in gids), len(gids)),
            "abstained": g.share(sum(grouped[r]["issue_id"] == "abstain" for r in gids), len(gids))},
        "label_auditor": {"changed_coverage": g.share(sum(r in audit for r in labels_changed), len(labels_changed)),
            "unchanged_coverage": g.share(sum(r in audit for r in labels_clean), len(labels_clean)),
            "changed_detected": observed_share(labels_changed, audit, lab_flag),
            "changed_detected_by_field": {f: observed_share([r for r in labels_changed if lc[r]["planted"] == f], audit, lab_flag) for f in ("topic", "severity")},
            "unchanged_flagged_any": observed_share(labels_clean, audit, lambda r: not all(audit[r].values())),
            "unchanged_flagged_by_field": {f: observed_share(labels_clean, audit, lambda r: audit[r][f + "_supported"] is False) for f in g.LABELS}},
        "issue_auditor": {"changed_coverage": g.share(sum(r in issue_audit for r in issues_changed), len(issues_changed)),
            "unchanged_coverage": g.share(sum(r in issue_audit for r in issues_clean), len(issues_clean)),
            "changed_detected": observed_share(issues_changed, issue_audit, iss_flag),
            "unchanged_flagged": observed_share(issues_clean, issue_audit, lambda r: issue_audit[r]["supported"] is False)},
        "paired_labels": {"coverage": g.share(len(paired_labels), len(labels_changed)),
            "missing": len(labels_changed) - len(paired_labels),
            "blind_disagreed": g.share(sum(blind_lab(r) for r in paired_labels), len(paired_labels)),
            "table": paired_table(paired_labels, lab_flag, blind_lab)},
        "paired_issues": {"coverage": g.share(len(paired_issues), len(issues_changed)),
            "missing": len(issues_changed) - len(paired_issues),
            "blind_disagreed": g.share(sum(blind_iss(r) for r in paired_issues), len(paired_issues)),
            "table": paired_table(paired_issues, iss_flag, blind_iss)}}


def build(source, allowlist, run):
    source, run = Path(source), Path(run)
    before_hashes = {"original_plan": g.file_sha(source / "plan.json"), "original_database": g.file_sha(source / "run.db"),
                     "followup_database": g.file_sha(run / "followup.db")}
    plan, _, old, calls, identity = b.read_source(source, allowlist)
    expected = {x[0]: x for x in calls}
    c = sqlite3.connect("file:" + str((run / "followup.db").resolve()) + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON"); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM calls ORDER BY created_utc,key")]
    c.close()
    if len(rows) != 10 or set(Counter(r["logical"] for r in rows).values()) != {2}:
        raise ValueError("saved attempt scope differs")
    fresh = {r: {} for r in old}; receipts, failures = [], []
    delays_after_429 = []
    for n, row in enumerate(rows):
        logical, role, ids, request = expected[row["logical"]]
        if row["request_sha"] != g.digest(request) or json.loads(row["request_json"]) != request:
            raise ValueError("request hash differs")
        receipt = run / ("receipt-%s-%d.bin" % (logical.replace(":", "-"), row["attempt"]))
        if receipt.read_bytes() != row["response_body"]:
            raise ValueError("raw receipt differs from ledger")
        response = json.loads(row["response_body"])
        if row["status"] == "succeeded":
            values = b.strict_output(role, response, ids, request)
            g.usage_of(role, response, b.ROUTE)
            if values != json.loads(row["output_json"]) or set(values) & (set(fresh[role]) | set(old[role])):
                raise ValueError("output mismatch or duplicate")
            fresh[role].update(values)
        elif row["status"] == "quarantined_metered":
            returned = json.loads(response["choices"][0]["message"]["content"])["results"]
            counts = identity_counts(ids, [r["review_id"] for r in returned])
            if counts["complete_exact_bijection"]:
                raise ValueError("recheck invalid-batch diagnosis")
            failures.append({"role": role, "attempt": row["attempt"], "identity": counts})
        elif row["status"] == "rejected_http":
            meta = response.get("error", {}).get("metadata", {})
            if row["http_status"] != 429 or meta.get("limit_source") != "upstream_provider_shared_pool" or meta.get("provider_name") != "Crusoe":
                raise ValueError("saved error differs from diagnosed provider limit")
            if n + 1 < len(rows):
                delays_after_429.append(round((datetime.fromisoformat(rows[n+1]["created_utc"]) - datetime.fromisoformat(row["settled_utc"])).total_seconds(), 6))
        else:
            raise ValueError("unexpected attempt status")
        receipts.append({"sequence": n + 1, "role": role, "attempt_within_batch": row["attempt"], "status": row["status"],
            "http_status": row["http_status"], "known_charge_nusd": row["charged_nusd"], "reservation_nusd": row["reserved_nusd"],
            "input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"], "reasoning_tokens": row["reasoning_tokens"],
            "usage_charge_nusd": row["usage_charge_nusd"], "derived_charge_nusd": row["derived_charge_nusd"],
            "elapsed_seconds": row["elapsed_seconds"], "created_utc": row["created_utc"], "settled_utc": row["settled_utc"],
            "request_sha256": row["request_sha"], "response_sha256": hashlib.sha256(row["response_body"]).hexdigest()})
    merged = {r: {**old[r], **fresh[r]} for r in old}
    known = sum(r["charged_nusd"] or 0 for r in rows)
    held = sum(r["reserved_nusd"] for r in rows if r["status"] == "rejected_http")
    preservation = json.loads((run / "preservation.json").read_text())
    if not preservation["original_run_unchanged"] or not preservation["historical_ledger_rows_and_caps_unchanged"]:
        raise ValueError("saved preservation check failed")
    after_hashes = {"original_plan": g.file_sha(source / "plan.json"), "original_database": g.file_sha(source / "run.db"),
                    "followup_database": g.file_sha(run / "followup.db")}
    if before_hashes != after_hashes:
        raise ValueError("saved input changed during diagnosis")
    return {"version": 1, "namespace": b.NAMESPACE, "recorded_through_utc": rows[-1]["settled_utc"],
        "provenance": {"plan_sha256": b.PLAN_SHA, "allowlist_sha256": b.ALLOWLIST_SHA,
            "source_artifact_sha256": before_hashes, "source_sha256": plan["source_sha256"], "label_config": plan["jev_config"],
            "execution_commit": "c9d6c4aae2a86ea4c23c141e99b970d1579fdb3f", "report_repair_commit": "f930f0427bc8e7fce7d688b24d532f8479557056",
            "original_run_and_historical_ledger_preserved": True, "raw_receipts_private": True},
        "route": {"service": "OpenRouter", "provider": "Crusoe", "model": g.MODEL, "tag": b.ROUTE,
            "fallback": False, "zdr": True, "data_collection": "deny", "reasoning": "low", "max_tokens": 4096,
            "concurrency": 1, "reviews_per_request": 10},
        "cost": {"attempts": len(rows), "batches": len(calls), "maximum_attempts": 10,
            "status_counts": dict(Counter(r["status"] for r in rows)), "known_charges_nusd": known,
            "unresolved_reservations_nusd": held, "exposure_nusd": known + held, "cap_nusd": b.CAP,
            "allowance": "Separate one-time allowance approved by the user; old project costs and holds are unchanged.",
            "accounting": "Metered charges use max(provider usage.cost, usage times pinned prices); both amounts are retained. HTTP429 charges remain unknown, with full holds. No invoice reconciliation."},
        "new_valid_outputs": {r: len(fresh[r]) for r in b.ROLE_COUNTS},
        "before": comparisons(plan, old), "after": comparisons(plan, merged),
        "diagnosis": {"http429": {"count": sum(r["http_status"] == 429 for r in rows),
            "limit_source": "upstream_provider_shared_pool", "provider": "Crusoe", "exact_rate_limit": None,
            "response_headers_saved": False, "retry_after_presence": None, "retry_after_respected": None,
            "rate_headers_respected": None, "header_handling_implemented_in_executed_version": False,
            "backoff_implemented_in_executed_version": False,
            "next_admission_seconds_after_429": delays_after_429,
            "cause_limit": "Metadata identifies the shared upstream pool; the headers and exact server reset time were not saved. Rapid retries are observed; their causal contribution is not measured."},
            "invalid_batches": failures, "deterministic_complete_id_recovery": False,
            "recovery_limit": "No complete exact one-to-one mapping exists. Position, nearest spelling and assignment by omission are guesses. Whole-batch rejection remains; no partial row salvage."},
        "limits": ["Model comparisons, not human accuracy. Flags on unchanged machine claims are disagreements, not proven false positives.",
            "Twenty verifier and ten grouping outputs remain missing; the ten-attempt limit is exhausted.",
            "The label auditor has 100 valid outputs; paired label and issue comparisons remain incomplete.",
            "Existing issue-auditor and synthetic injection outputs are unchanged. No new human answers or product outcomes.",
            "The first report join failed after receipts were saved. It was repaired offline without another request."],
        "receipts": receipts}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--allowlist", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    text = json.dumps(build(a.source, a.allowlist, a.run), indent=2, sort_keys=True) + "\n"
    if a.check:
        if a.out.read_text() != text:
            raise ValueError("publication aggregate is stale")
        print("publication aggregate is current; private inputs unchanged")
    else:
        a.out.write_text(text)
        print("aggregate-only publication candidate written; no database writes or API calls")


if __name__ == "__main__":
    main()

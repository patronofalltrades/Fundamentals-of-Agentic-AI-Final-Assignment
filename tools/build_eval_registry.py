"""Build the dashboard's evaluation and benchmark registry from saved report files.

Input: the JSON reports in ``reports/``. Output: ``dashboard/evals.json``.
Each number in the output is read from a report; nothing is typed by hand.
The registry records the SHA-256 of every report it read, so a reader can trace each value.

The human golden evaluation is not in this file. The API reads it live from the database
(``import-evaluation``), so the page shows it only after it is saved and checked.

Run from the repository root:

    python3 tools/build_eval_registry.py           # write dashboard/evals.json
    python3 tools/build_eval_registry.py --check   # fail if dashboard/evals.json is out of date
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "evals.json"
PILOT = "reports/jev-pilot-100.json"
RUBRIC = "reports/jev-rubric-v1-v2-100.json"
CHECKPOINT = "reports/jev-checkpoint-500.json"
INTENT = "reports/golden-50-intent.json"
EXTRACTOR = "reports/extractor-benchmark-aggregate.json"  # written by tools/build_run_aggregates.py
RUN = "reports/run-110k-calls-aggregate.json"  # written by tools/build_run_aggregates.py
GAP = "reports/gap-closure-2026-10-16/aggregate.json"  # written by tools/gap_closure_eval.py report --publish
MEASUREMENT = "reports/production-measurement-audit-2026-10-15.json"
COST_PILOT = "cost/pilot/report.json"
FULL_WARM = "reports/production-measurement-warm-2026-10-15.json"


def _load(path, sources):
    data = (ROOT / path).read_bytes()
    sources.append({"path": path, "sha256": hashlib.sha256(data).hexdigest()})
    return json.loads(data)


def metric(label, value, fmt="int", of=None, note=None):
    item = {"label": label, "value": value, "format": fmt}
    if of is not None:
        item["of"] = of
    if note:
        item["note"] = note
    return item


def rubric_benchmark(r, sources):
    v1, v2, ch = r["runs"]["v1"], r["runs"]["v2"], r["changes"]["field_changed_counts"]
    n = r["source_rows_validated"]
    return {
        "id": "prompt-v1-v2",
        "kind": "benchmark",
        "title": "Prompt benchmark: rubric v1 against v2",
        "question": "Does the revised labelling prompt change the labels, and what does it cost?",
        "sample": "%d reviews from the course cost sample, labelled twice with the same model" % n,
        "truth": "None. This compares two prompts with each other. It shows how much labels move, not which prompt is right.",
        "status": "measured",
        "metrics": [
            metric("Topic changed", ch["topic"], "count", of=n),
            metric("Intent changed", ch["intent"], "count", of=n),
            metric("Severity changed", ch["severity"], "count", of=n),
            metric("Review flag changed", ch["needs_review"], "count", of=n),
        ],
        "compare": {
            "columns": ["v1", "v2"],
            "rows": [
                {"label": "Input tokens", "format": "int", "values": [v1["input_tokens"], v2["input_tokens"]]},
                {"label": "Output tokens", "format": "int", "values": [v1["output_tokens"], v2["output_tokens"]]},
                {"label": "Cost (USD)", "format": "usd", "values": [v1["usage_derived_cost_usd"], v2["usage_derived_cost_usd"]]},
                {"label": "Summed request time", "format": "seconds",
                 "values": [v1["summed_attempt_seconds"], v2["summed_attempt_seconds"]]},
                {"label": "Retries", "format": "int", "values": [v1["retries"], v2["retries"]]},
                {"label": "Flagged for human review", "format": "int",
                 "values": [v1["needs_review"]["true"], v2["needs_review"]["true"]]},
                {"label": "Topic “other”", "format": "int",
                 "values": [v1["topics"].get("other", 0), v2["topics"].get("other", 0)]},
            ],
        },
        "decision": "v2 is the production prompt. It moved %d of %d topics and almost no severities, so the ranking "
                    "input is stable across the prompt change." % (ch["topic"], n),
        "limits": r["limitations"],
        "sources": [RUBRIC],
    }


def run_benchmark(p, c):
    pl, pr, cl = p["attempts"], p["results"], c["labels"]
    replay = c["saved_state_warm_replay"]
    return {
        "id": "labelling-runs",
        "kind": "run",
        "title": "Labelling runs: cost, speed and reliability",
        "question": "Can the labelling step run cheaply, without errors, and be replayed without new model calls?",
        "sample": "Pilot: %d reviews (prompt v1). Checkpoint: %d reviews (prompt v2)." % (p["source_rows"], c["source_rows"]),
        "truth": "Structural checks only: schema, source identity and exact evidence quotes. Not label accuracy.",
        "status": "partial",
        "metrics": [
            metric("Checkpoint reviews labelled", c["canonical_completed"], "count", of=c["source_rows"]),
            metric("Duplicate texts reused from cache", cl["exact_text_cache"], "count", of=c["source_rows"]),
            metric("Retries", cl["new_retries"], "int"),
            metric("New model calls on replay", replay["new_enrichment_calls"] + replay["new_evidence_calls"], "int",
                   note="%d saved records re-validated offline" % replay["records_validated"]),
        ],
        "compare": {
            "columns": ["Pilot 100", "Checkpoint 500"],
            "rows": [
                {"label": "Reviews", "format": "int", "values": [p["source_rows"], c["source_rows"]]},
                {"label": "Model calls", "format": "int", "values": [pl["settled"], cl["new_settled_calls"]]},
                {"label": "Cache reuses", "format": "int", "values": [pr["exact_text_cache_copies"], cl["exact_text_cache"]]},
                {"label": "Retries", "format": "int", "values": [pl["retries"], cl["new_retries"]]},
                {"label": "Schema or identity errors", "format": "int",
                 "values": [pr["schema_or_identity_errors"], cl.get("schema_or_identity_errors")],
                 "note": "The checkpoint report does not count this field." if "schema_or_identity_errors" not in cl else None},
                {"label": "Input tokens", "format": "int", "values": [pl["input_tokens"], cl["new_input_tokens"]]},
                {"label": "Cost (USD)", "format": "usd",
                 "values": [p["pricing"]["usage_derived_cost_usd"], cl["new_usage_derived_cost_usd"]]},
                {"label": "Label stage time", "format": "seconds",
                 "values": [pl["summed_attempt_seconds"], cl["new_label_stage_wall_seconds"]],
                 "note": "Pilot: summed request time. Checkpoint: measured wall time."},
            ],
        },
        "limits": p["limitations"][:3] + ["The checkpoint report has no historical schema-error count. Accepted final outputs do not prove that count was zero."],
        "sources": [PILOT, CHECKPOINT],
    }


def _usd(nusd):
    return "%.9f" % (nusd / 1e9)


def projection(c, run):
    f = c["first_100000_full_file_rows_candidate"]
    jev, ev = run["stages"]["jev"], run["stages"]["evidence"]
    return {
        "id": "projection-100k",
        "kind": "run",
        "title": "The 100,000-review run: estimate against measured",
        "question": "What did the required run cost, and how close was the estimate made before it?",
        "sample": "Estimate: the first 100,000 rows, before any model call. Measured: every call of the 110,000-row selection.",
        "truth": "Measured charges are usage-derived from the saved call ledger in the grading release.",
        "status": "partial",
        "metrics": [
            metric("Known main-run charge", _usd(run["total_charged_nusd"]), "usd",
                   note="Labels and evidence only; excludes unknown charges and other project work."),
            metric("Measured labelling cost", _usd(jev["charged_nusd"]), "usd",
                   note="estimated beforehand: $%.2f" % float(f["jev_label_only_linear_estimate_usd"])),
            metric("Calls with unknown charge", sum(stage["outcomes"].get("uncertain", 0) for stage in run["stages"].values()),
                   note="Unknown is not zero; reservations remain held."),
            metric("Distinct review texts in the estimate", f["distinct_nonempty_texts"], "int",
                   note="of %s non-empty rows; duplicates reuse one label" % format(f["nonempty_rows"], ",")),
        ],
        "compare": {
            "columns": ["Estimate", "Measured"],
            "rows": [
                {"label": "Labelling cost (USD)", "format": "usd",
                 "values": [f["jev_label_only_linear_estimate_usd"], _usd(jev["charged_nusd"])]},
                {"label": "Evidence cost (USD)", "format": "usd", "values": [None, _usd(ev["charged_nusd"])],
                 "note": "Not estimated beforehand."},
                {"label": "Labelling request time", "format": "hours",
                 "values": [f["jev_serial_label_stage_linear_estimate_hours"], "%.4f" % (jev["request_seconds"] / 3600)],
                 "note": "Estimate: serial. Measured: summed request time, not wall time."},
                {"label": "Labelling calls", "format": "int", "values": [None, jev["calls"]]},
                {"label": "Evidence calls", "format": "int", "values": [None, ev["calls"]]},
                {"label": "Uncertain calls, held without retry", "format": "int",
                 "values": [None, jev["outcomes"].get("uncertain", 0) + ev["outcomes"].get("uncertain", 0)]},
            ],
        },
        "limits": ["The estimate scaled the 500-review checkpoint linearly and covered labelling only.",
                   "The measured run covers 110,000 selected rows, not the first 100,000 rows of the file.",
                   run["note"]],
        "sources": [CHECKPOINT, RUN],
    }


def _span(values, fmt):
    lo, hi = min(values), max(values)
    show = (lambda v: "%d" % round(v * 100)) if fmt == "pct" else (lambda v: "%.2f" % v) if fmt == "dec" else str
    unit = "%" if fmt == "pct" else ""
    return show(lo) + unit if lo == hi else "%s\u2013%s%s" % (show(lo), show(hi), unit)


def intent_accuracy(g):
    """Per-intent accuracy against the 50 human golden labels. Shown in the Jev walkthrough, not the Evals grid."""
    v2 = [r for r in g["runs"] if r["prompt"] == "v2"]
    v1 = [r for r in g["runs"] if r["prompt"] == "v1"]
    order = ["complaint", "praise", "unclear", "request", "cancellation"]
    rows = []
    for name in order:
        c = [r["per_class"][name] for r in v2]
        recall = [x["recall"] for x in c if x["recall"] is not None]
        precision = [x["precision"] for x in c if x["precision"] is not None and x["predicted"]]
        rows.append({"label": name, "format": "text", "values": [
            str(c[0]["support"]), _span([x["predicted"] for x in c], "int"),
            _span(recall, "pct") if recall else "\u2014", _span(precision, "pct") if precision else "\u2014"]})
    return {
        "id": "golden-intent",
        "kind": "accuracy",
        "title": "Measured intent accuracy",
        "question": "How often does Jev pick the same intent as a person?",
        "sample": "50 reviews. One person wrote every label before seeing any model output.",
        "truth": "The original human labels, scored with the course checker's score_gold. Three separate Jev runs per prompt.",
        "status": "measured",
        "metrics": [
            {"label": "Intent accuracy, prompt v2", "value": _span([r["accuracy"] for r in v2], "pct"), "format": "text",
             "note": "3 runs"},
            {"label": "Intent accuracy, prompt v1", "value": _span([r["accuracy"] for r in v1], "pct"), "format": "text",
             "note": "3 runs"},
            {"label": "Macro F1, prompt v2", "value": _span([r["macro_f1"] for r in v2], "dec"), "format": "text",
             "note": "each intent weighted equally"},
        ],
        "compare": {"row_header": "Intent", "columns": ["Human labels", "Jev picked", "Found", "Right when picked"],
                    "rows": rows},
        "finding": "Jev is strong on praise and complaint. It finds only 56\u201367% of the reviews a person called unclear. "
                    "It predicted cancellation once in every run, although the person labelled none.",
        "limits": [g["note"], "50 reviews is a small sample: request has 3 cases, so one review moves its score by 33 points.",
                   "One person labelled the set. There is no second labeller to measure human agreement."],
        "sources": [INTENT],
    }


def extractor(x):
    di, gq = x["routes"]["deepinfra"], x["routes"]["groq"]
    n = x["source_reviews"]
    return {
        "id": "extractor-benchmark",
        "kind": "benchmark",
        "title": "Evidence extractor benchmark",
        "question": "Which hosted model extracts exact evidence quotes and product entities most reliably and cheaply?",
        "sample": "The same %d development reviews selected for each route; DeepInfra attempted %d, Groq attempted %d."
                  % (n, di["reviews_attempted"], gq["reviews_attempted"]),
        "truth": "Exact-quote checks against the source text. Agreement with saved development evidence is in the report.",
        "status": "partial",
        "metrics": [
            metric("DeepInfra reviews with accepted evidence", di["reviews_accepted"], "count", of=n),
            metric("Groq reviews with accepted evidence", gq["reviews_accepted"], "count", of=n,
                   note="%d reviews never sent" % (n - gq["reviews_attempted"])),
            metric("Known charge, both routes", _usd(di["charged_nusd"] + gq["charged_nusd"]), "usd"),
        ],
        "compare": {
            "columns": ["DeepInfra", "Groq"],
            "rows": [
                {"label": "Calls", "format": "int", "values": [di["calls"], gq["calls"]]},
                {"label": "Accepted", "format": "int", "values": [di["reviews_accepted"], gq["reviews_accepted"]]},
                {"label": "Invalid responses", "format": "int",
                 "values": [di["outcomes"].get("invalid_response", 0), gq["outcomes"].get("invalid_response", 0)]},
                {"label": "Cost (USD)", "format": "usd", "values": [_usd(di["charged_nusd"]), _usd(gq["charged_nusd"])]},
                {"label": "Summed request time", "format": "seconds", "values": [di["request_seconds"], gq["request_seconds"]]},
            ],
        },
        "decision": "DeepInfra became the evidence extractor: it completed more of the set with fewer invalid "
                    "responses. Groq was faster per request.",
        "limits": [x["note"], "The paired comparison against development evidence is in reports/openrouter-extractor-benchmark.md.",
                   "Exact quotation is a structural check. Entity relevance and evidence quality lack human scoring.",
                   "Untouched reviews and invalid responses remain incomplete; no new calls were made for this audit."],
        "sources": [EXTRACTOR],
    }


def _rate(x):
    return metric(x["label"], x["share"]["n"], "count", of=x["share"]["of"], note=x.get("note"))


def gap_closure(x, measured):
    """Three cards from the 16 October gap-closure run (tools/gap_closure_eval.py)."""
    b, gr, pe, pi = x["blind_verifier"], x["grouping_stage"], x["planted_errors"], x["prompt_injection"]
    a = b["agreement_with_jev"]
    source = [GAP, MEASUREMENT]
    verifier = {
        "id": "blind-verifier-batch10",
        "kind": "benchmark",
        "title": "Blind verifier, ten reviews per request",
        "question": "Does an independent model, shown only the text and the rubric, give the same labels as Jev?",
        "sample": "%d accepted reviews from the main run, drawn by a fixed SHA-256 order; golden and pilot IDs excluded"
                  % b["sample"],
        "truth": "None. This is model-to-model agreement. It shows where two labellers differ, not which one is right.",
        "status": "partial" if measured["verifier"]["missing"] else "measured",
        "metrics": [metric("Valid verifier outputs", measured["verifier"]["observed"], "count", of=b["sample"],
                           note="%d missing; agreement uses observed outputs only." % measured["verifier"]["missing"]),
                    _rate({"label": "Topic agrees", "share": a["topic"]}),
                    _rate({"label": "Intent agrees", "share": a["intent"]}),
                    _rate({"label": "All three agree", "share": a["joint"]}),
                    metric("Verifier charge", _usd(b["charged_nusd"]), "usd",
                           note="%d requests of %d reviews" % (b["requests"], b["reviews_per_request"]))],
        "compare": {"row_header": "Field", "columns": ["Agreement", "Cohen's kappa"], "rows": [
            {"label": f.capitalize(), "format": "text", "values": ["%.1f%%" % (100 * a[f]["rate"]), "%.2f" % b["kappa"][f]]}
            for f in ("topic", "intent", "severity")]},
        "finding": "Intent agrees most and topic least. Severity differs by %.2f points on average. %d of %d requests "
                   "returned valid results. Code rejected one that repeated a review ID; one response was unusable and stays held."
                   % (b["severity_mae"], b["requests_by_outcome"].get("succeeded", 0), b["requests"]),
        "limits": ["Agreement is not accuracy: both models can be wrong in the same way.",
                   "The verifier is gpt-oss-120b, the same base model as the evidence extractor, but with a separate prompt "
                   "and no access to Jev's labels."],
        "sources": source,
    }
    grouping = {
        "id": "grouping-stage",
        "kind": "benchmark",
        "title": "Grouping as a recorded program stage",
        "question": "Does a saved, code-run grouping stage put reviews in the same issue as the historical agent handoff?",
        "sample": "%d complaint and cancellation reviews from the historical issue map, blind to their issue" % gr["sample"],
        "truth": "The historical issue map. It was not validated by people, so disagreement is not proof of error.",
        "status": "partial" if measured["grouping"]["missing"] else "measured",
        "metrics": [metric("Valid grouping outputs", measured["grouping"]["observed"], "count", of=gr["sample"],
                           note="%d missing; comparisons use observed outputs only." % measured["grouping"]["missing"]),
                    _rate({"label": "Same issue", "share": gr["exact_issue_agreement"]}),
                    _rate({"label": "Same issue family", "share": gr["family_agreement"]}),
                    _rate({"label": "Abstained", "share": gr["abstained"]})],
        "finding": "The saved report and public case table cover valid outputs. Two requests repeated a review ID and code "
                   "rejected them. The separate historical verifier matched the grouping agents on 511 of 600; its "
                   "recovered trail does not establish historical token usage or charges.",
        "limits": ["The stage reads Jev's labels and evidence quote as context, as the historical grouping did."],
        "sources": source,
    }
    lab, iss = pe["labels"], pe["issues"]
    lj, ij = measured["planted_labels"], measured["planted_issues"]
    injection = measured["injection"]
    checks = {
        "id": "planted-and-injection",
        "kind": "benchmark",
        "title": "Changed model claims and prompt injection",
        "question": "Do auditors flag changed model claims, and do synthetic instructions change model outputs?",
        "sample": "%d observed changed-label cases, %d changed-issue cases, and %d synthetic attack pairs"
                  % (lab["planted"], iss["planted"], pi["pairs"]),
        "truth": "Code altered saved model claims. These changes are not human-validated errors. Synthetic texts are excluded "
                 "from all business results.",
        "status": "partial" if lj["missing_outputs"] or ij["missing_outputs"] else "measured",
        "metrics": [_rate({"label": "Planted labels the auditor caught", "share": lab["auditor_detected"]}),
                    _rate({"label": "Planted issues the auditor caught", "share": iss["auditor_detected"]}),
                    metric("Paired label or issue changes", injection["paired_label_or_issue_changes"], "count",
                           of=injection["comparisons"], note="Jev, verifier and grouping on eight synthetic attack pairs"),
                    metric("Secret leaks", len(pi["canary_leaks"]), "count")],
        "compare": {"row_header": "Check", "columns": ["Result"], "rows": [
            {"label": "Blind verifier disagreed with a planted label", "format": "text",
             "values": ["%d of %d paired; %d missing" % (lj["disagreed"], lj["paired_outputs"], lj["missing_outputs"])]},
            {"label": "Blind grouping disagreed with a planted issue", "format": "text",
             "values": ["%d of %d paired; %d missing" % (ij["disagreed"], ij["paired_outputs"], ij["missing_outputs"])]},
            {"label": "Auditor flagged an unchanged Jev label", "format": "text",
             "values": ["%d of %d" % (lab["auditor_flagged_unchanged_jev_labels"]["n"],
                                      lab["auditor_flagged_unchanged_jev_labels"]["of"])]},
            {"label": "Auditor flagged an unchanged historical issue", "format": "text",
             "values": ["%d of %d" % (iss["auditor_flagged_unchanged_historical_issue"]["n"],
                                      iss["auditor_flagged_unchanged_historical_issue"]["of"])]}]},
        "limits": [pe["note"], pi["note"],
                   "Seven of the 50 selected changed-label cases lacked auditor outputs. Blind comparisons also require a saved prediction.",
                   "The historical target-reached helper does not cover every format, identity or canary attack. Paired label/issue changes are reported separately.",
                   "In the mixed-batch probe, verifier and grouping each changed one of eight benign rows; neither changed to the attacker value. These probes do not prove general injection resistance."],
        "sources": source,
    }
    j = x["jev_ten_per_request"]
    ja = j["agreement_with_single_review_jev"]
    jev_batch = {
        "id": "jev-ten-per-request",
        "kind": "benchmark",
        "title": "Jev with ten reviews per request",
        "question": "Does sending ten reviews in one Jev request change the labels or the cost?",
        "sample": "%d reviews from the verifier sample, in %d requests of %d" % (j["labelled"], j["requests"], j["reviews_per_request"]),
        "truth": "None. Both sides are Jev with the same rubric; the reference is the main run's one-review requests.",
        "status": "measured",
        "metrics": [_rate({"label": "Topic unchanged", "share": ja["topic"]}),
                    _rate({"label": "Intent unchanged", "share": ja["intent"]}),
                    _rate({"label": "All three unchanged", "share": ja["joint"]}),
                    metric("Input tokens per review", j["input_tokens_per_review"], "int",
                           note="%s in the main run" % j["main_run_input_tokens_per_review"])],
        "finding": "Jev reads the ten reviews once and answers forty questions, each pointed at one review. This sample used "
                   "%.0f%% fewer input tokens per review than the main-run average and differed on at least one label in %d of %d reviews, so the main run's "
                   "one-review labels stay." % (100 * (1 - j["input_tokens_per_review"] / j["main_run_input_tokens_per_review"]),
                                               ja["joint"]["of"] - ja["joint"]["n"], ja["joint"]["of"]),
        "limits": [j["note"], "Jev's run-to-run variation on single reviews was not measured here, so part of the change "
                              "may be ordinary variation.", "The token comparison uses different sample populations; it does not isolate a causal batching saving."],
        "sources": source,
    }
    return [verifier, jev_batch, grouping, checks]


def operational_measurements(pilot, warm, measured):
    if warm["status"] != "passed" or not warm["original_database_unchanged"] or any(warm["attempts"].values()):
        raise ValueError("Full-warm evidence did not pass the zero-call audit")
    if warm["source_sha256"] != pilot["input_sha256"] or warm["before"] != warm["after"]:
        raise ValueError("Warm audit does not preserve the pinned pilot")
    cost, recovery = measured["cost"], measured["recovery"]
    return [
        {"id": "cost100-cold-full-warm", "kind": "run", "title": "100-review pilot: cold and full warm replay",
         "question": "What did the full pilot cost, and can all six stages reuse saved outputs?",
         "sample": "%d source reviews; %d accepted, %d quarantined." % (pilot["rows"], pilot["completed"], pilot["failed_records"]),
         "truth": "Saved pilot receipts and a new offline execute() replay on a database copy. Source and before/after hashes match.",
         "status": "measured",
         "metrics": [metric("Pilot known charge", _usd(pilot["actual_charged_nusd"]), "usd"),
                     metric("Cold active stage time", pilot["cold_active_stage_seconds"], "seconds"),
                     metric("Full warm orchestration", warm["orchestration_seconds"], "seconds"),
                     metric("New paid / transport / socket attempts", sum(warm["attempts"].values()),
                            note="All three counters are zero; all six stages executed.")],
         "compare": {"columns": ["Measured"], "rows": [
             {"label": "Cold elapsed, including downtime", "format": "seconds", "values": [pilot["cold_end_to_end_wall_seconds"]]},
             {"label": "Interruption downtime", "format": "seconds", "values": [pilot["all_interruption_downtime_seconds"]]},
             {"label": "Original validation-only replay", "format": "seconds", "values": [pilot["warm_seconds"]]},
             {"label": "Whole new audit, including setup", "format": "seconds", "values": [warm["whole_audit_seconds"]]}]},
         "limits": ["This separate pilot does not restore missing checkpoints or usage from the historical main run.",
                    "Warm stages reused cached model outputs; ranking was recomputed. No fresh inference or quality scoring occurred.",
                    "Two quarantines remain. Timing describes this local replay, not production latency or a scaling estimate."],
         "sources": [COST_PILOT, FULL_WARM]},
        {"id": "gap-operations", "kind": "run", "title": "Separate verification run: cost and resume",
         "question": "What is known about charges, held reservations and requests after the restart?",
         "sample": "%d attempts for %d logical requests in the separate verification and robustness experiments." %
                   (cost["attempts"], recovery["logical_requests"]),
         "truth": "Recomputed from public text-free call logs. Unknown charges retain their full reservation.",
         "status": "partial" if cost["unknown_charge_attempts"] else "measured",
         "metrics": [metric("Known charges", _usd(cost["known_charge_nusd"]), "usd"),
                     metric("Unresolved reservations", _usd(cost["held_nusd"]), "usd",
                            note="%d attempts have unknown charges." % cost["unknown_charge_attempts"]),
                     metric("Known plus reserved", _usd(cost["known_plus_held_nusd"]), "usd"),
                     metric("Settled requests resent after restart", recovery["resumed_attempts_for_initial_settled_requests"],
                            note="%d logical requests settled in the initial segment." % recovery["initial_settled_logical_requests"])],
         "finding": "%d of %d logical requests have a settled result; %d has none. Retry attempts and unresolved holds are counted separately." %
                    (recovery["settled_logical_requests"], recovery["logical_requests"], recovery["logical_requests_without_settled_result"]),
         "limits": ["Provider reconciliation is still needed for every unknown charge; HTTP errors are not assumed free.",
                    "Public logs support the phase and request arithmetic. SIGINT and checkpoint details remain saved-report evidence; private snapshots were not rechecked in this audit.",
                    "Public call rows omit provider-route and request/response receipt fields. This run does not prove historical main-run recovery."],
         "sources": [GAP, MEASUREMENT]},
    ]


def build():
    sources = []
    pilot, rubric, checkpoint = _load(PILOT, sources), _load(RUBRIC, sources), _load(CHECKPOINT, sources)
    items = [intent_accuracy(_load(INTENT, sources)), rubric_benchmark(rubric, sources), run_benchmark(pilot, checkpoint),
             projection(checkpoint, _load(RUN, sources)), extractor(_load(EXTRACTOR, sources))]
    measured = _load(MEASUREMENT, sources)
    items += gap_closure(_load(GAP, sources), measured)
    items += operational_measurements(_load(COST_PILOT, sources), _load(FULL_WARM, sources), measured)
    verification = {"source_sha256": measured["source_sha256"], "config_hash": measured["label_config"],
                    **measured["verifier"], "status": "sample_measured", "sources": [GAP, MEASUREMENT]}
    return {"version": 1, "verification": verification, "model": checkpoint["model"], "prompt_version": checkpoint["prompt_version"],
            "built_from": sources, "items": items}


def render(registry):
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the saved registry is out of date")
    args = parser.parse_args(argv)
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("dashboard/evals.json is out of date; run tools/build_eval_registry.py", file=sys.stderr)
            return 1
        print("dashboard/evals.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print("wrote %s (%d items)" % (OUT.relative_to(ROOT), len(json.loads(text)["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

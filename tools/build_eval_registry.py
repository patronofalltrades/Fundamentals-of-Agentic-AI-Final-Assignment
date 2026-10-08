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
EXTRACTOR = "reports/extractor-benchmark.json"  # optional; written by the extractor benchmark when final


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
        "status": "measured",
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
        "limits": p["limitations"][:3],
        "sources": [PILOT, CHECKPOINT],
    }


def projection(c):
    f = c["first_100000_full_file_rows_candidate"]
    return {
        "id": "projection-100k",
        "kind": "projection",
        "title": "Projection: the 100,000-review run",
        "question": "What will the required 100,000-review run cost and how long will labelling take?",
        "sample": "The first 100,000 rows of the full review file, counted before any model call",
        "truth": "Linear estimate from the 500-review checkpoint. Not a measurement.",
        "status": "estimate",
        "metrics": [
            metric("Distinct review texts", f["distinct_nonempty_texts"], "int",
                   note="of %s non-empty rows; duplicates reuse one label" % format(f["nonempty_rows"], ",")),
            metric("Estimated labelling cost", f["jev_label_only_linear_estimate_usd"], "usd"),
            metric("Estimated labelling time", f["jev_serial_label_stage_linear_estimate_hours"], "hours",
                   note="serial; parallel requests reduce it"),
        ],
        "limits": ["The estimate scales the checkpoint linearly. Retries, rate limits and parallelism change it.",
                   "Evidence extraction is a separate stage with its own cost."],
        "sources": [CHECKPOINT],
    }


def extractor(sources):
    if (ROOT / EXTRACTOR).exists():
        item = _load(EXTRACTOR, sources)
        item.setdefault("sources", [EXTRACTOR])
        return item
    return {
        "id": "extractor-benchmark",
        "kind": "benchmark",
        "title": "Evidence extractor benchmark",
        "question": "Which hosted model extracts exact evidence quotes and product entities most reliably and cheaply?",
        "sample": "The same 100 development reviews, sent to each candidate route",
        "truth": "Agreement with saved development evidence, plus exact-quote checks against the source text.",
        "status": "pending",
        "metrics": [],
        "limits": ["Results appear here when the benchmark saves its final report."],
        "sources": [],
    }


def build():
    sources = []
    pilot, rubric, checkpoint = _load(PILOT, sources), _load(RUBRIC, sources), _load(CHECKPOINT, sources)
    items = [rubric_benchmark(rubric, sources), run_benchmark(pilot, checkpoint), projection(checkpoint),
             extractor(sources)]
    return {"version": 1, "model": checkpoint["model"], "prompt_version": checkpoint["prompt_version"],
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

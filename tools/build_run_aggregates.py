"""Save aggregate run reports for the dashboard's Evals section. No review ID, text or quote is written.

Inputs (private or release files, passed by path):
  --calls      calls.jsonl from the grading release grading-2026-10-13 (one line per main-run model call)
  --extractor  the extractor benchmark's SQLite ledger (openrouter_extractor_benchmark.db), opened read-only

Outputs:
  reports/run-110k-calls-aggregate.json     calls, outcomes, charges, tokens and request time per stage
  reports/extractor-benchmark-aggregate.json  outcomes, charges and request time per route

Each output records the SHA-256 of the file it read. Run from the repository root:

    python3 tools/build_run_aggregates.py --calls <calls.jsonl> --extractor <benchmark.db>
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_OUT = ROOT / "reports" / "run-110k-calls-aggregate.json"
EXTRACTOR_OUT = ROOT / "reports" / "extractor-benchmark-aggregate.json"
ACCEPTED_OUTCOMES = {"succeeded", "partial_succeeded"}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_aggregate(calls_path):
    stages = defaultdict(lambda: {"calls": 0, "outcomes": defaultdict(int), "charged_nusd": 0, "input_tokens": 0,
                                  "output_tokens": 0, "request_seconds": 0.0, "model": None})
    with open(calls_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            s = stages[r["stage"]]
            s["model"] = r["model"]
            s["calls"] += 1
            s["outcomes"][r["outcome"]] += 1
            s["charged_nusd"] += r["charged_nusd"] or 0
            s["input_tokens"] += r["input_tokens"] or 0
            s["output_tokens"] += r["output_tokens"] or 0
            s["request_seconds"] += r["request_seconds"] or 0.0
    out = {}
    for name, s in sorted(stages.items()):
        out[name] = {**s, "outcomes": dict(sorted(s["outcomes"].items())), "request_seconds": round(s["request_seconds"], 3)}
    return {
        "source": {"file": "calls.jsonl in release grading-2026-10-13 (grading-110k.zip)", "sha256": _sha256(calls_path)},
        "note": "Charges are usage-derived and include every metered outcome. Uncertain calls carry no known charge. "
                "request_seconds is summed request time, not wall time.",
        "stages": out,
        "total_charged_nusd": sum(s["charged_nusd"] for s in out.values()),
    }


def extractor_aggregate(db_path):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    rows = conn.execute("SELECT route, status, COUNT(*), COALESCE(SUM(charged_nusd), 0), COALESCE(SUM(elapsed_seconds), 0) "
                        "FROM calls GROUP BY route, status ORDER BY route, status").fetchall()
    reviews = dict(conn.execute("SELECT route, COUNT(DISTINCT review_id) FROM calls GROUP BY route").fetchall())
    accepted = dict(conn.execute("SELECT route, COUNT(DISTINCT review_id) FROM calls WHERE status='succeeded' "
                                 "GROUP BY route").fetchall())
    conn.close()
    routes = defaultdict(lambda: {"calls": 0, "outcomes": {}, "charged_nusd": 0, "request_seconds": 0.0})
    for route, status, n, charged, seconds in rows:
        r = routes[route]
        r["calls"] += n
        r["outcomes"][status] = n
        r["charged_nusd"] += charged
        r["request_seconds"] = round(r["request_seconds"] + seconds, 3)
    for route, r in routes.items():
        r["reviews_attempted"], r["reviews_accepted"] = reviews.get(route, 0), accepted.get(route, 0)
    return {
        "source": {"file": "openrouter_extractor_benchmark.db (private ledger)", "sha256": _sha256(db_path)},
        "source_reviews": 100,
        "note": "The benchmark stopped before Groq finished; its untouched reviews were never sent. "
                "request_seconds is summed request time, not wall time.",
        "routes": dict(sorted(routes.items())),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", required=True)
    parser.add_argument("--extractor", required=True)
    args = parser.parse_args(argv)
    for path, data in ((RUN_OUT, run_aggregate(args.calls)), (EXTRACTOR_OUT, extractor_aggregate(args.extractor))):
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("wrote %s" % path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

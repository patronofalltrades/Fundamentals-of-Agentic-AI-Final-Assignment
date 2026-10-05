#!/usr/bin/env python3
"""Export a run directory to the grading folder (docs/INTERFACES.md §7).

    python3 export_grading.py --run runs/<name> --csv <full.csv> --out grading [--gzip]
        [--checkpoint-before P] [--checkpoint-after P] [--self-check]

--self-check builds (and caches) .local/local-reference.json with check_submission.reference(full, full),
runs check_submission.audit on the exported folder and writes self-check.json at the repo root
(outside the grading folder). Standard library only; no network calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pipeline import export as exporter  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, type=Path, help="run directory (runs/<name>)")
    ap.add_argument("--csv", required=True, type=Path, help="full input CSV")
    ap.add_argument("--out", default=ROOT / "grading", type=Path, help="grading folder (default: grading)")
    ap.add_argument("--gzip", action="store_true", help="write records.jsonl.gz and calls.jsonl.gz")
    ap.add_argument("--checkpoint-before", type=Path, help="default: first invocation's end checkpoint")
    ap.add_argument("--checkpoint-after", type=Path, help="default: last invocation's end checkpoint")
    ap.add_argument("--self-check", action="store_true", help="run check_submission.audit after export")
    ap.add_argument("--reference", type=Path, default=ROOT / ".local" / "local-reference.json",
                    help="cached reference path (default: .local/local-reference.json)")
    ap.add_argument("--self-check-out", type=Path, default=ROOT / "self-check.json",
                    help="audit report path, must be outside --out (default: ./self-check.json)")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    report = args.self_check_out.resolve()
    if out == report.parent or out in report.parents:
        ap.error("--self-check-out must be outside the grading folder")
    t0 = time.monotonic()
    summary = exporter.export(args.run, args.csv, out, use_gzip=args.gzip,
                              checkpoint_before=args.checkpoint_before, checkpoint_after=args.checkpoint_after)
    summary["export_seconds"] = round(time.monotonic() - t0, 2)
    print(json.dumps(summary, indent=2))
    if args.self_check:
        result = exporter.self_check(out, args.csv, args.reference, args.self_check_out)
        print("self-check status:", result["status"])
        print("issue_counts:", json.dumps(result["issue_counts"], sort_keys=True))
        print("coverage:", json.dumps(result["coverage"], sort_keys=True))
        print("timings:", json.dumps(result["timings_seconds"]))
        print("report:", result["report"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

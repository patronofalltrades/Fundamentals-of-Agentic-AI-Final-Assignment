"""Score a run directory against the golden 50 with the checker's own scoring code.

    python3 evals/score_gold.py --run runs/golden-dev [--out evals/reports/golden-dev.json]

Uses check_submission.score_gold (agreement, per-class F1, severity MAE). Missing or quarantined
golden predictions count as wrong, exactly as in the official check. No model calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import check_submission  # noqa: E402
from pipeline.io import read_jsonl  # noqa: E402


def latest_records(run_dir: Path) -> dict:
    latest = {}
    for row in read_jsonl(run_dir / "records.jsonl"):
        latest[row["review_id"]] = row
    return {rid: r for rid, r in latest.items() if r.get("status") == "completed"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--gold", type=Path, default=ROOT / "evals" / "gold_benchmark.json")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    ids = {c["review_id"] for c in gold["cases"]}
    expected = {rid: {} for rid in ids}
    valid = {rid: r for rid, r in latest_records(args.run).items() if rid in ids}
    result = check_submission.score_gold(gold, valid, expected)
    result["run"] = str(args.run)
    result["label_configs"] = sorted({r.get("label_config") for r in valid.values()})
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "approved_cases", "missing_or_invalid_predictions",
                                              "agreement", "severity_mae_on_valid_predictions")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

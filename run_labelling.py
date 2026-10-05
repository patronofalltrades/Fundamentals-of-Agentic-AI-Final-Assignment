#!/usr/bin/env python3
"""Enrichment only: alias of ``run_pipeline.py --stages ingest,enrich``.

    python3 run_labelling.py <csv> --config configs/pilot_cost_100.json --out runs/pilot-cold
    python3 run_labelling.py <csv> --config configs/dry_run.json --out runs/dry --dry-run --max-batches 3

All other options are passed through to run_pipeline.py (an explicit --stages wins).
"""
from __future__ import annotations

import sys

import run_pipeline


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not any(a == "--stages" or a.startswith("--stages=") for a in argv):
        argv += ["--stages", "ingest,enrich"]
    return run_pipeline.main(argv)


if __name__ == "__main__":
    sys.exit(main())

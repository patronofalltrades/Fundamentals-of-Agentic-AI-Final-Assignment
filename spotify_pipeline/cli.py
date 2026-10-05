"""Command line interface. Offline only; no paid or network commands exist."""

import argparse
import json
import sqlite3
import sys
from typing import List, Optional

from . import __version__
from .checkpoint import build_checkpoint, write_checkpoint
from .config import config_hash, load_config
from .cost import evaluate, load_measurements, load_rates, load_scenario, write_report
from .db import Database
from .errors import PipelineError
from .ingest import check_path_collisions, ingest


def _print_json(payload) -> None:
    json.dump(
        payload,
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    sys.stdout.write("\n")


def _cmd_ingest(args: argparse.Namespace) -> int:
    report = ingest(args.input, args.manifest, args.db, args.report)
    _print_json(
        {
            "status": "ok",
            "report": {
                "file_sha256": report["file_sha256"],
                "parsed_rows_sha256": report["parsed_rows_sha256"],
                "counts": report["counts"],
            },
            "extended": report["extended"],
        }
    )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    with Database.open_existing(args.db) as db:
        payload = {
            "source": {
                "basename": db.get_meta("source_basename"),
                "file_sha256": db.get_meta("file_sha256"),
                "parsed_rows_sha256": db.get_meta("parsed_rows_sha256"),
                "source_bytes": db.get_meta("source_bytes"),
            },
            "status_counts": db.status_counts(),
        }
        if args.config:
            config = load_config(args.config)
            cfg_hash = config_hash(config)
            payload["config_hash"] = cfg_hash
            payload["status_counts"] = db.status_counts(cfg_hash)
    _print_json(payload)
    return 0


def _cmd_checkpoint(args: argparse.Namespace) -> int:
    check_path_collisions(
        {"database": args.db, "out": args.out, "config": args.config}
    )
    config = load_config(args.config)
    with Database.open_existing(args.db) as db:
        checkpoint = build_checkpoint(db, config)
    write_checkpoint(checkpoint, args.out)
    _print_json(
        {
            "status": "ok",
            "out": args.out,
            "config_hash": checkpoint["config_hash"],
            "completed_count": checkpoint["completed_count"],
            "pending_count": checkpoint["pending_count"],
        }
    )
    return 0


def _cmd_cost(args: argparse.Namespace) -> int:
    check_path_collisions(
        {
            "measurements": args.measurements,
            "rates": args.rates,
            "scenario": args.scenario,
            "out": args.out,
        }
    )
    measurements = load_measurements(args.measurements)
    rates = load_rates(args.rates)
    scenario = load_scenario(args.scenario)
    report = evaluate(measurements, rates, scenario)
    write_report(report, args.out)
    _print_json(
        {
            "status": report["status"],
            "out": args.out,
            "approved_to_scale": report["approved_to_scale"],
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spotify_pipeline",
        description="Offline Spotify review ingestion, state and cost scaffold.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a source CSV offline.")
    ingest_parser.add_argument("--input", required=True)
    ingest_parser.add_argument("--manifest", required=True)
    ingest_parser.add_argument("--db", required=True)
    ingest_parser.add_argument("--report", required=True)
    ingest_parser.set_defaults(func=_cmd_ingest)

    status_parser = subparsers.add_parser("status", help="Show database status.")
    status_parser.add_argument("--db", required=True)
    status_parser.add_argument("--config", default=None)
    status_parser.set_defaults(func=_cmd_status)

    checkpoint_parser = subparsers.add_parser("checkpoint", help="Write a resume checkpoint.")
    checkpoint_parser.add_argument("--db", required=True)
    checkpoint_parser.add_argument("--out", required=True)
    checkpoint_parser.add_argument("--config", required=True)
    checkpoint_parser.set_defaults(func=_cmd_checkpoint)

    cost_parser = subparsers.add_parser("cost", help="Replay offline cost measurements.")
    cost_parser.add_argument("--measurements", required=True)
    cost_parser.add_argument("--rates", required=True)
    cost_parser.add_argument("--scenario", required=True)
    cost_parser.add_argument("--out", required=True)
    cost_parser.set_defaults(func=_cmd_cost)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except PipelineError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    except (OSError, UnicodeDecodeError, sqlite3.Error) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

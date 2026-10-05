#!/usr/bin/env python3
"""Run the review pipeline: ingest -> enrich -> verify -> group -> rank -> memo.

    python3 run_pipeline.py <csv> --config configs/dry_run.json --out runs/<name> [--dry-run]
        [--stages ingest,enrich,verify,group,rank,memo] [--max-batches N] [--workers N]
        [--limit N] [--warm-from runs/<other>]

Every invocation appends one line to <out>/invocations.jsonl and writes
<out>/checkpoints/<invocation_id>-start.json and -end.json. See docs/INTERFACES.md §4-5 and
configs/README.md. Exit codes: 0 ok (including a --max-batches stop), 2 budget stop,
3 model client error, 4 configuration / mock-guard refusal, 5 stage module unavailable or failed,
6 repeated transient failures, 130 interrupted.
"""
from __future__ import annotations

import argparse
import importlib
import json
import random
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pipeline import clients  # noqa: E402
from pipeline.context import StageContext, utc_now  # noqa: E402
from pipeline.enrich import (STOP_BUDGET, STOP_CLIENT_ERROR, STOP_COMPLETED, STOP_INTERRUPTED,  # noqa: E402
                             STOP_MAX_BATCHES, STOP_TRANSIENT, EnrichSettings, Enricher, write_empty_quarantines)
from pipeline.io import atomic_write_json  # noqa: E402
from pipeline.prepare import DuplicateReviewId, prepare  # noqa: E402
from pipeline.spend import BudgetExceeded, RateLimiter, SpendLedger  # noqa: E402
from pipeline.state import CallLog, RecordStore, append_invocation, save_checkpoint  # noqa: E402

STAGES = ("ingest", "enrich", "verify", "group", "rank", "memo")
CHAT_STAGES = ("verify", "group", "memo")
EXIT = {STOP_COMPLETED: 0, STOP_MAX_BATCHES: 0, STOP_BUDGET: 2, STOP_CLIENT_ERROR: 3, "config": 4,
        "stage_failed": 5, STOP_TRANSIENT: 6, STOP_INTERRUPTED: 130}


class RunError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", type=Path, help="input CSV (e.g. spotify_reviews_18months.csv)")
    p.add_argument("--config", required=True, type=Path, help="run config JSON (see configs/README.md)")
    p.add_argument("--out", required=True, type=Path, help="run directory, e.g. runs/pilot-cold")
    p.add_argument("--dry-run", action="store_true", help="offline mock clients; label_config gets 'mock:'")
    p.add_argument("--stages", default=",".join(STAGES), help="comma list from " + ",".join(STAGES))
    p.add_argument("--max-batches", type=int, default=None, help="stop enrich after N batches (interruption demo)")
    p.add_argument("--workers", type=int, default=None, help="override limits.workers")
    p.add_argument("--limit", type=int, default=None, help="DEV ONLY: first N rows; refused for full-run configs")
    p.add_argument("--warm-from", type=Path, default=None,
                   help="seed this (new) run's result cache from another run dir with the same label_config")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def load_config(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RunError("config", "cannot read config %s: %s" % (path, e))
    if not isinstance(value, dict):
        raise RunError("config", "config must be a JSON object")
    return value


def parse_stages(text: str):
    names = [s.strip() for s in text.split(",") if s.strip()]
    bad = [s for s in names if s not in STAGES]
    if bad or not names:
        raise RunError("config", "unknown stage(s) %s; choose from %s" % (bad or text, ",".join(STAGES)))
    return [s for s in STAGES if s in names]


def _write_run_config(run_dir: Path, args, config: dict, prepared, label_config: str, invocation_id: str,
                      warm_from=None) -> dict:
    path = run_dir / "run_config.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if existing:
        for key, now in (("input_file_sha256", prepared.file_sha256), ("label_config", label_config),
                         ("dry_run", bool(args.dry_run))):
            if existing.get(key) != now:
                raise RunError("config", "run dir %s was created with %s=%r but this invocation has %r; "
                                         "use a new --out" % (run_dir, key, existing.get(key), now))
    snapshot = dict(existing or {})
    snapshot.update(_cost_fields(run_dir, args, config, prepared))
    snapshot.setdefault("created_at", utc_now())
    snapshot.update({
        "input_csv": str(Path(args.csv).resolve()), "input_file_sha256": prepared.file_sha256,
        "rows": len(prepared.texts), "limit": args.limit, "limited": prepared.limited,
        "label_config": label_config, "base_label_config": config.get("label_config"),
        "dry_run": bool(args.dry_run), "config_path": str(args.config), "config": config,
        "classification_input_fields": ["review_text"],
        "last_invocation_id": invocation_id, "updated_at": utc_now(),
    })
    if warm_from is not None:
        snapshot["warm_from"] = warm_from
    atomic_write_json(path, snapshot)
    return snapshot


CHAT_MAX_TOKENS_DEFAULT = {"verify": 600, "group": 1500, "memo": 2500}


def _cost_fields(run_dir: Path, args, config: dict, prepared) -> dict:
    """Top-level fields the cost calculator reads (cost/cost_calc.py)."""
    dry = bool(args.dry_run)
    client = config.get("client") or {}
    chat = config.get("chat") or {}
    lim = config.get("limits") or {}
    roles = {"enrich": {"provider": "mock" if dry else client.get("provider"),
                        "model": "mock" if dry else client.get("model"), "effort": "none", "max_tokens": None}}
    for role in CHAT_STAGES:
        block = config.get(role) or {}
        roles[role] = {"provider": "mock" if dry else (chat.get("provider") or "anthropic"),
                       "model": "mock" if dry else chat.get("model"),
                       "effort": chat.get("effort", "none"),
                       "max_tokens": int(block.get("max_tokens", CHAT_MAX_TOKENS_DEFAULT[role]))}
    return {
        "run_id": Path(run_dir).name,
        "input_sha256": prepared.file_sha256,
        "client": {"provider": roles["enrich"]["provider"], "model": roles["enrich"]["model"]},
        "roles": roles,
        "batching": {"max_reviews_per_request": int((config.get("batching") or {}).get("max_reviews_per_request", 50))},
        "limits": {"workers": int(args.workers or lim.get("workers", 1)), "spend_cap_usd": lim.get("spend_cap_usd")},
    }


def seed_warm_from(source_dir: Path, store: RecordStore, prepared, label_config: str) -> dict:
    """Copy the source run's completed records (same label_config, same source rows) into ``store``."""
    src_cfg_path = Path(source_dir) / "run_config.json"
    if not src_cfg_path.exists():
        raise RunError("config", "--warm-from %s has no run_config.json" % source_dir)
    src_cfg = json.loads(src_cfg_path.read_text(encoding="utf-8"))
    src_lc = src_cfg.get("label_config")
    if src_lc != label_config:
        raise RunError("config", "--warm-from label_config %r differs from this run's %r; cached results "
                                 "cannot be reused across configurations" % (src_lc, label_config))
    src = RecordStore(Path(source_dir) / "records.jsonl", repair=False)
    chosen = {}
    for rid in prepared.texts:
        m = src.meta(rid)
        if m is None or m[0] != "completed" or m[1] != label_config:
            continue
        rec = src.latest(rid)
        if rec.get("source_sha256") != prepared.source_sha[rid]:
            continue
        chosen[rid] = rec
    # Keep cache copies only when their direct original came along (no dangling or chained sources).
    for rid in [r for r, rec in chosen.items() if rec.get("cache_source_id")]:
        origin = chosen.get(chosen[rid]["cache_source_id"])
        if origin is None or origin.get("cache_source_id"):
            del chosen[rid]
    store.upsert(chosen.values())
    return {"path": str(Path(source_dir).resolve()), "records_copied": len(chosen),
            "source_label_config": src_lc, "seeded_at": utc_now()}


def _new_invocation_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def _log(args, msg: str) -> None:
    if not getattr(args, "quiet", False):
        print(msg, file=sys.stderr, flush=True)


def main(argv=None, hooks=None) -> int:
    """CLI entry. ``hooks`` (tests only): enrich_client, chat, sleep, rng, stop_event."""
    hooks = hooks or {}
    args = parse_args(argv)
    args.argv = list(argv) if argv is not None else sys.argv[1:]
    started_at, t_start = utc_now(), time.monotonic()
    if not hooks.get("skip_dotenv"):
        names = clients.load_dotenv(ROOT / ".env")
        if names:
            _log(args, ".env: found non-empty " + ", ".join(sorted(names)))
    try:
        config = load_config(args.config)
        stages = parse_stages(args.stages)
        if args.limit is not None and (config.get("full_run") or args.limit <= 0):
            raise RunError("config", "--limit is a development option and is refused for full-run configs "
                                     "(config.full_run=true) or non-positive values")
        if args.max_batches is not None and args.max_batches < 1:
            raise RunError("config", "--max-batches must be >= 1")
        # Resolve clients before any work: the mock guard aborts here.
        client = None
        if "enrich" in stages:
            if hooks.get("enrich_client") is not None:
                client = hooks["enrich_client"]
                label_config = clients.resolve_label_config(config, args.dry_run)
            else:
                client, label_config = clients.build_enrich_client(config, args.dry_run)
        else:
            label_config = clients.resolve_label_config(config, args.dry_run)
        chat = None
        if any(s in stages for s in CHAT_STAGES):
            chat = hooks.get("chat") or clients.build_chat(config, args.dry_run)
    except clients.ClientConfigError as e:
        print("error: " + str(e), file=sys.stderr)
        return EXIT["config"]
    except RunError as e:
        print("error: " + str(e), file=sys.stderr)
        return EXIT.get(e.kind, 1)

    run_dir = Path(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)
    invocation_id = _new_invocation_id()
    try:
        t0 = time.monotonic()
        prepared = prepare(args.csv, limit=args.limit)
        prepare_seconds = time.monotonic() - t0
        store = RecordStore(run_dir / "records.jsonl")
        call_log = CallLog(run_dir / "calls.jsonl")
        warm = None
        if args.warm_from is not None:
            prior = run_dir / "run_config.json"
            prior_cfg = json.loads(prior.read_text(encoding="utf-8")) if prior.exists() else {}
            same = (prior_cfg.get("warm_from") or {}).get("path") == str(Path(args.warm_from).resolve())
            if not same:
                if len(store):
                    raise RunError("config", "--warm-from needs a new, empty --out (found %d records in %s)"
                                             % (len(store), run_dir))
                warm = seed_warm_from(args.warm_from, store, prepared, label_config)
                _log(args, "warm-from: copied %d completed records from %s" % (warm["records_copied"], args.warm_from))
        _write_run_config(run_dir, args, config, prepared, label_config, invocation_id, warm)
    except (RunError, DuplicateReviewId, ValueError) as e:
        print("error: " + str(e), file=sys.stderr)
        return EXIT["config"]

    completed_start = store.completed_ids(label_config)
    phase = "resume" if completed_start else "initial"
    ckpt_dir = run_dir / "checkpoints"
    start_size = save_checkpoint(ckpt_dir / (invocation_id + "-start.json"), completed_start)
    _log(args, "invocation %s phase=%s rows=%d completed=%d label_config=%s"
         % (invocation_id, phase, len(prepared.texts), start_size, label_config))

    lim = config.get("limits") or {}
    ledger = SpendLedger(lim.get("spend_cap_usd"), run_dir / "ledger.json", rates=config.get("rates"))
    limiter = None
    if lim.get("requests_per_minute") or lim.get("tokens_per_minute"):
        limiter = RateLimiter(lim.get("requests_per_minute"), lim.get("tokens_per_minute"))

    stop_event = hooks.get("stop_event") or threading.Event()
    previous_handler = None

    def on_sigint(signum, frame):
        if stop_event.is_set():
            raise KeyboardInterrupt
        stop_event.set()
        print("\nSIGINT: finishing in-flight work and saving (press again to abort)", file=sys.stderr, flush=True)

    if threading.current_thread() is threading.main_thread():
        previous_handler = signal.signal(signal.SIGINT, on_sigint)

    stage_seconds = {s: None for s in STAGES}
    stage_summaries = {}
    stop_reason, stop_message, exit_kind = STOP_COMPLETED, "", STOP_COMPLETED
    ctx = None
    try:
        for stage in stages:
            if stop_event.is_set():
                stop_reason, exit_kind, stop_message = STOP_INTERRUPTED, STOP_INTERRUPTED, "stop requested"
                break
            t0 = time.monotonic()
            try:
                if stage == "ingest":
                    n = write_empty_quarantines(prepared, store)
                    summary = dict(prepared.stats, empty_quarantined_written=n, file_sha256=prepared.file_sha256,
                                   limited=prepared.limited, prepare_seconds=round(prepare_seconds, 3))
                    atomic_write_json(run_dir / "ingest" / "summary.json", summary)
                elif stage == "enrich":
                    settings = EnrichSettings.from_config(config, workers=args.workers, max_batches=args.max_batches)
                    progress_every = int(lim.get("progress_every_batches", 500))

                    def progress(c, _every=progress_every):
                        if _every and c["units"] % _every == 0:
                            _log(args, "  enrich: %d batches, %d calls, %d completed, %d cache copies, %d quarantined"
                                 % (c["units"], c["calls"], c["completed_new"], c["cache_copies"], c["quarantined_new"]))
                    enricher = Enricher(prepared=prepared, store=store, call_log=call_log, client=client,
                                        label_config=label_config, phase=phase, invocation_id=invocation_id,
                                        settings=settings, limiter=limiter, ledger=ledger, stop_event=stop_event,
                                        sleep=hooks.get("sleep", time.sleep), rng=hooks.get("rng", random.random),
                                        progress=progress)
                    summary = enricher.run()
                    if summary["stop_reason"] != STOP_COMPLETED:
                        stop_reason, stop_message = summary["stop_reason"], summary["stop_message"]
                        exit_kind = stop_reason
                else:
                    if ctx is None:
                        ctx = StageContext(run_dir=run_dir, config=config, label_config=label_config, phase=phase,
                                           invocation_id=invocation_id, dry_run=bool(args.dry_run),
                                           texts=prepared.texts, records=store.all_latest(prepared.texts),
                                           chat=chat, log_call=call_log.log, ledger=ledger,
                                           extras={"source_sha": prepared.source_sha, "stop_event": stop_event})
                    try:
                        module = importlib.import_module("pipeline." + stage)
                    except ModuleNotFoundError as e:
                        if e.name != "pipeline." + stage:
                            raise
                        raise RunError("stage_failed", "stage %r is not available (pipeline/%s.py missing)" % (stage, stage))
                    summary = module.run(ctx) or {}
                    ledger.save()
            finally:
                stage_seconds[stage] = round(time.monotonic() - t0, 3)
            stage_summaries[stage] = summary
            _log(args, "stage %s: %.2fs %s" % (stage, stage_seconds[stage],
                                                json.dumps({k: v for k, v in summary.items() if not isinstance(v, (dict, list))})[:400]))
            if stop_reason != STOP_COMPLETED:
                break
    except RunError as e:
        stop_reason, stop_message, exit_kind = e.kind, str(e), e.kind
    except BudgetExceeded as e:
        stop_reason, stop_message, exit_kind = STOP_BUDGET, str(e), STOP_BUDGET
    except KeyboardInterrupt:
        stop_reason, stop_message, exit_kind = STOP_INTERRUPTED, "aborted by second SIGINT", STOP_INTERRUPTED
    except Exception as e:  # noqa: BLE001 - classify client errors, re-raise everything else after saving
        from labelling.model_client import ModelClientError
        if isinstance(e, ModelClientError):
            stop_reason, stop_message, exit_kind = STOP_CLIENT_ERROR, str(e), STOP_CLIENT_ERROR
        else:
            stop_reason, stop_message, exit_kind = "error", "%s: %s" % (type(e).__name__, e), "stage_failed"
            _finish(run_dir, args, invocation_id, phase, started_at, t_start, stages, stage_seconds, stage_summaries,
                    stop_reason, stop_message, store, label_config, ledger, start_size, call_log)
            raise
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)

    _finish(run_dir, args, invocation_id, phase, started_at, t_start, stages, stage_seconds, stage_summaries,
            stop_reason, stop_message, store, label_config, ledger, start_size, call_log)
    code = EXIT.get(exit_kind, 1)
    if code:
        print("stopped: %s - %s" % (stop_reason, stop_message), file=sys.stderr)
    return code


def _finish(run_dir, args, invocation_id, phase, started_at, t_start, stages, stage_seconds, stage_summaries,
            stop_reason, stop_message, store, label_config, ledger, start_size, call_log):
    completed_end = store.completed_ids(label_config)
    end_size = save_checkpoint(run_dir / "checkpoints" / (invocation_id + "-end.json"), completed_end)
    ledger.save()
    by_status = store.count_by_status()
    entry = {
        "invocation_id": invocation_id, "phase": phase, "started_at": started_at, "ended_at": utc_now(),
        "wall_seconds": round(time.monotonic() - t_start, 3), "stop_reason": stop_reason, "stop_message": stop_message,
        "stages": stages, "stage_seconds": stage_seconds, "dry_run": bool(args.dry_run), "label_config": label_config,
        "argv": getattr(args, "argv", None),
        "max_batches": args.max_batches, "workers": args.workers, "limit": args.limit,
        "warm_from": str(args.warm_from) if args.warm_from else None,
        "checkpoint_start": "checkpoints/%s-start.json" % invocation_id,
        "checkpoint_end": "checkpoints/%s-end.json" % invocation_id,
        "counts": {"completed_start": start_size, "completed_end": end_size,
                   "records_completed": by_status.get("completed", 0),
                   "records_quarantined": by_status.get("quarantined", 0),
                   "enrich_calls": (stage_summaries.get("enrich") or {}).get("calls", 0),
                   "enrich_calls_failed": (stage_summaries.get("enrich") or {}).get("calls_failed", 0),
                   "cache_copies": (stage_summaries.get("enrich") or {}).get("cache_copies", 0),
                   "calls_log_total": len(call_log)},
        "stage_summaries": stage_summaries, "ledger": ledger.summary(),
    }
    append_invocation(run_dir, entry)
    store.close()
    _log(args, "done %s: stop_reason=%s wall=%.2fs completed %d -> %d"
         % (invocation_id, stop_reason, entry["wall_seconds"], start_size, end_size))
    return entry


if __name__ == "__main__":
    sys.exit(main())

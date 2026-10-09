"""Prepare and run the approved first-5000 Jev/DeepInfra checkpoint.

Default status and prepare are offline. Paid modes require explicit flags,
current route checks, configured credentials and a shared atomic cost ledger.
No request with unknown delivery is retried automatically.
"""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from spotify_pipeline.checkpoint5000_queue import CheckpointQueue
from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import file_sha256
from spotify_pipeline import deepinfra_batch
from spotify_pipeline import jev
from spotify_pipeline.jev_pilot import NANODOLLARS_PER_INPUT_TOKEN, RESERVATION_NANODOLLARS
from spotify_pipeline.project_budget import ProjectBudget
from tools import deepinfra_batch10_canary as canary
from tools import openrouter_extractor_benchmark as benchmark

HISTORICAL_BENCHMARK = str(Path.home() / "Documents/Codex/2026-10-06/task-3/spotify-extractor-benchmark/local/openrouter_extractor_benchmark.db")
HISTORICAL_JEV = str(Path.home() / "Documents/Codex/2026-10-06/task-2/spotify-v2-comparison/local/jev_checkpoint500_v2.db")
DATASET = str(Path.home() / "Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset")
MAX_WORKERS = 2
PROGRESS = (100, 1000, 2500, 5000)


def emit_progress(queue, field, reported):
    current = queue.summary()[field]
    for milestone in PROGRESS:
        if milestone <= current and milestone not in reported:
            reported.add(milestone)
            print(json.dumps({"checkpoint": milestone, field: current,
                "jev_exposure_nusd": queue.budget.exposure("jev"),
                "openrouter_exposure_nusd": queue.budget.exposure("openrouter")},
                sort_keys=True), flush=True)


def legacy_paths():
    return {"benchmark": HISTORICAL_BENCHMARK,
        "batch_v1": "local/deepinfra_batch10_canary.db",
        "batch_v2": "local/deepinfra_batch10_canary_v2.db",
        "jev_checkpoint": HISTORICAL_JEV}


def load_manifest(path):
    with open(path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest.get("schema_version") != "checkpoint5000-manifest-v1" or \
            manifest.get("selected_rows") != 5000 or len(manifest.get("rows", [])) != 5000 or \
            manifest.get("label_config_hash") != config_hash(jev.label_config()):
        raise ValueError("checkpoint manifest version, count or Jev configuration differs")
    if manifest.get("source_file") != "spotify_reviews_18months.csv":
        raise ValueError("checkpoint manifest source differs")
    with open(os.path.join(DATASET, "manifest.json"), encoding="utf-8") as stream:
        supplied = json.load(stream)
    if manifest["source_file_sha256"] != supplied["files"][manifest["source_file"]]["sha256"]:
        raise ValueError("checkpoint manifest source hash differs from supplied source")
    return manifest, file_sha256(path)


def seed_labels(manifest):
    """Resolve manifest cache candidates to direct, exact-text v2 Jev labels."""
    candidates = {row["saved500_label_source_id"]: row["text"] for row in manifest["rows"]
                  if row.get("saved500_label_source_id")}
    if not candidates:
        return {}
    path = HISTORICAL_JEV
    with sqlite3.connect("file:" + os.path.abspath(path) + "?mode=ro", uri=True) as db:
        saved = {rid: (text, cfg, value, direct) for rid, text, cfg, value, direct in db.execute(
            "SELECT review_id,review_text,config_hash,label_json,cache_source_id FROM results")}
    output = {}
    for rid, text in candidates.items():
        row = saved.get(rid)
        if row is None or row[0] != text or row[1] != manifest["label_config_hash"]:
            raise ValueError("saved500 cache candidate differs from source or label version")
        direct_id = row[3] or rid
        direct = saved.get(direct_id)
        if direct is None or direct[0] != text or direct[1] != row[1] or \
                direct[2] != row[2] or direct[3] is not None:
            raise ValueError("saved500 label cache origin is not a direct exact-text record")
        if text in output and output[text] != (direct[2], direct_id):
            raise ValueError("conflicting exact-text saved labels")
        output[text] = (direct[2], direct_id)
    return output


def open_checkpoint(args):
    manifest, manifest_sha = load_manifest(args.manifest)
    budget = ProjectBudget(args.budget, legacy_paths())
    try:
        queue = CheckpointQueue(budget, manifest["rows"], manifest["source_file_sha256"],
                                manifest_sha, seed_labels(manifest))
    except BaseException:
        budget.close()
        raise
    return budget, queue


def _metered_jev(payload):
    usage = payload.get("usage") if isinstance(payload, dict) else None
    value = usage.get("input_tokens") if isinstance(usage, dict) else None
    if type(value) is int and 0 <= value <= 64000:
        return value * NANODOLLARS_PER_INPUT_TOKEN
    return None


def _metered_deepinfra(payload):
    if not isinstance(payload, dict) or payload.get("provider") != "DeepInfra":
        return None
    usage = payload.get("usage") or {}
    inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if type(inp) is int and type(out) is int and 0 <= inp <= benchmark.ENDPOINT_BOUNDS["deepinfra"][0] \
            and 0 <= out <= benchmark.ENDPOINT_BOUNDS["deepinfra"][1]:
        return benchmark.money_nusd(Decimal(inp) * deepinfra_batch.INPUT_RATE +
                                     Decimal(out) * deepinfra_batch.OUTPUT_RATE)
    return None


def _jev_worker(text, key):
    started = time.monotonic()
    try:
        return jev.post_systemone(jev.build_request(text), key), time.monotonic() - started, None
    except Exception as error:
        return None, time.monotonic() - started, type(error).__name__


def _evidence_worker(payload, key):
    started = time.monotonic()
    try:
        return benchmark.request_json("https://openrouter.ai/api/v1/chat/completions", payload, key), \
            time.monotonic() - started, None
    except Exception as error:
        return None, time.monotonic() - started, type(error).__name__


def run_labels(queue, key, first_100=False, max_new_requests=None):
    queue.assert_resume_safe("jev")
    if not key:
        raise ValueError("Jev key unavailable; no paid call")
    jev.check_model_access(key)
    active = {}
    reported = set()
    admitted = failures = 0
    stop = False
    halt_reason = None
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        while active or not stop:
            while not stop and len(active) < MAX_WORKERS and (max_new_requests is None or
                    admitted < max_new_requests):
                row = queue.next_jev(first_100)
                if row is None:
                    break
                try:
                    request_key = queue.reserve("jev", [row], queue.label_config_sha,
                                                RESERVATION_NANODOLLARS)
                except Exception as error:
                    stop, halt_reason = True, type(error).__name__ + ": " + str(error)
                    break
                active[pool.submit(_jev_worker, row["review_text"], key)] = (request_key, row)
                admitted += 1
            if not active:
                break
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                request_key, row = active.pop(future)
                response, elapsed, error_class = future.result()
                if response is None:
                    queue.fail(request_key, error_class=error_class, elapsed_seconds=elapsed)
                    stop, halt_reason = True, "unknown Jev delivery"
                    continue
                try:
                    labels = jev.parse_response(response)
                except Exception as error:
                    charge = _metered_jev(response)
                    queue.fail(request_key, metered_charge=charge, error_class=type(error).__name__,
                               response=response, elapsed_seconds=elapsed)
                    failures += 1
                    if charge is None or response.get("model") != jev.MODEL or failures >= 5:
                        stop, halt_reason = True, "Jev invalid response or failure streak"
                    continue
                charge = labels.input_tokens * NANODOLLARS_PER_INPUT_TOKEN
                try:
                    queue.save_label(request_key, row, json.dumps(labels.__dict__, sort_keys=True),
                        charge, labels.input_tokens, labels.output_tokens, elapsed)
                except Exception as error:
                    queue.fail(request_key, metered_charge=charge, error_class=type(error).__name__,
                               response=response, elapsed_seconds=elapsed)
                    stop, halt_reason = True, "Jev result persistence failed"
                    continue
                failures = 0
                emit_progress(queue, "labels", reported)
            if stop:
                # Already admitted requests finish and are recorded; never cancel delivery blindly.
                continue
    return {"admitted": admitted, "paused": stop, "halt_reason": halt_reason,
            **queue.summary()}


def run_evidence(queue, key, batch_limit, first_100=False, max_new_requests=None,
                 defer_uncertain_evidence=False):
    queue.assert_resume_safe("evidence", defer_uncertain_evidence=defer_uncertain_evidence)
    if batch_limit not in (25, 50) or not key:
        raise ValueError("batch limit or OpenRouter key missing")
    benchmark.verify_route("deepinfra")
    canary.verify_project_key(key, deepinfra_batch.reservation_nusd())
    if first_100 and queue.db.execute("SELECT COUNT(*) FROM checkpoint_labels l JOIN "
            "checkpoint_rows r USING(review_id) WHERE r.position<=100").fetchone()[0] != 100:
        raise ValueError("first 100 Jev labels are incomplete")
    active = {}
    reported = set()
    admitted = failures = new_uncertain = 0
    stop = False
    halt_reason = None
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        while active or not stop:
            while not stop and len(active) < MAX_WORKERS and (max_new_requests is None or
                    admitted < max_new_requests):
                rows = queue.next_evidence(batch_limit, first_100)
                if not rows:
                    break
                try:
                    labels = queue.labels_for(rows)
                    request = deepinfra_batch.payload(rows, labels, batch_limit)
                    config = deepinfra_batch.config_sha(batch_limit, len(rows))
                    request_key = queue.reserve("evidence", rows, config,
                                                deepinfra_batch.reservation_nusd(), batch_limit)
                except Exception as error:
                    stop, halt_reason = True, type(error).__name__ + ": " + str(error)
                    break
                active[pool.submit(_evidence_worker, request, key)] = \
                    (request_key, rows, config)
                admitted += 1
            if not active:
                break
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                request_key, rows, config = active.pop(future)
                response, elapsed, error_class = future.result()
                if response is None:
                    queue.fail(request_key, error_class=error_class, elapsed_seconds=elapsed)
                    new_uncertain += 1
                    if not defer_uncertain_evidence or error_class == "HTTPError" or new_uncertain >= 2:
                        stop, halt_reason = True, "unknown DeepInfra delivery or repeated outage"
                    continue
                try:
                    accepted, invalid, inp, out, reasoning, charge = \
                        deepinfra_batch.inspect_response(response, rows, batch_limit)
                except Exception as error:
                    charge = _metered_deepinfra(response)
                    queue.fail(request_key, metered_charge=charge,
                               error_class=type(error).__name__, response=response,
                               elapsed_seconds=elapsed)
                    failures += 1
                    if charge is None:
                        new_uncertain += 1
                    if (failures >= 5 or not defer_uncertain_evidence and charge is None or
                            new_uncertain >= 2 or charge is None and (
                                not isinstance(response, dict) or response.get("provider") != "DeepInfra")):
                        stop, halt_reason = True, "DeepInfra invalid response or failure streak"
                    continue
                try:
                    queue.save_evidence(request_key, rows, accepted, config, charge,
                        inp, out, reasoning, response["id"], elapsed,
                        invalid=invalid, response=response)
                except Exception as error:
                    queue.fail(request_key, metered_charge=charge,
                               error_class=type(error).__name__, response=response,
                               elapsed_seconds=elapsed)
                    stop, halt_reason = True, "DeepInfra result persistence failed"
                    continue
                failures = failures + 1 if invalid else 0
                if failures >= 5 or not accepted:
                    stop, halt_reason = True, "DeepInfra row validation failure streak"
                emit_progress(queue, "complete", reported)
            if stop:
                continue
    return {"admitted": admitted, "paused": stop, "halt_reason": halt_reason,
            "new_uncertain_requests": new_uncertain,
            **queue.summary()}


def recover_metered_evidence(queue):
    """Accept valid rows and quarantine bad spans from one saved response."""
    saved = queue.db.execute("""SELECT request_key,batch_limit,config_sha,response_json
        FROM checkpoint_requests WHERE stage='evidence' AND status='quarantined_metered'
        ORDER BY rowid LIMIT 1""").fetchone()
    if saved is None:
        raise ValueError("no metered evidence response awaits recovery")
    key, batch_limit, config, raw = saved
    if not raw:
        raise ValueError("metered response body missing; no recovery")
    rows = []
    for rid, in queue.db.execute("SELECT review_id FROM checkpoint_request_members "
            "WHERE request_key=? ORDER BY rowid", (key,)):
        result = queue.db.execute("SELECT position,review_text,source_sha,text_sha "
            "FROM checkpoint_rows WHERE review_id=?", (rid,)).fetchone()
        rows.append({"source_position": result[0], "review_id": rid,
            "review_text": result[1], "source_sha256": result[2],
            "text_sha256": result[3]})
    response = json.loads(raw)
    try:
        accepted, invalid, inp, out, reasoning, charge = \
            deepinfra_batch.inspect_response(response, rows, batch_limit)
    except ValueError:
        accepted, invalid, inp, out, reasoning, charge = \
            deepinfra_batch.inspect_saved_response_for_recovery(response, rows, batch_limit)
    if not accepted or not invalid:
        raise ValueError("saved response is not an isolated partial-evidence failure")
    queue.recover_metered_evidence(key, rows, accepted, invalid, config, charge,
                                   inp, out, reasoning, response["id"])
    return {"status": "recovered_offline", "accepted_direct_rows": len(accepted),
            "quarantined_direct_rows": len(invalid), **queue.summary()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="local/checkpoint5000_manifest.json")
    parser.add_argument("--budget", default="local/project_budget.db")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--run-labels", action="store_true")
    mode.add_argument("--run-evidence", action="store_true")
    mode.add_argument("--recover-metered-evidence", action="store_true")
    parser.add_argument("--first-100", action="store_true")
    parser.add_argument("--batch-limit", type=int, choices=(25, 50))
    parser.add_argument("--max-new-requests", type=int)
    parser.add_argument("--jev-price-checked-on")
    args = parser.parse_args()
    if args.max_new_requests is not None and args.max_new_requests <= 0:
        parser.error("max-new-requests must be positive")
    if args.run_labels and (args.jev_price_checked_on != date.today().isoformat()):
        parser.error("Jev USD 0.042/M input price requires today's verified date")
    if args.run_evidence and args.batch_limit is None:
        parser.error("evidence mode requires --batch-limit 25 or 50")
    budget, queue = open_checkpoint(args)
    try:
        if args.run_labels:
            result = run_labels(queue, os.environ.get("TYPESAFE_API_KEY"), args.first_100,
                                args.max_new_requests)
        elif args.run_evidence:
            key = canary.keychain_secret(timeout_seconds=90)
            try:
                result = run_evidence(queue, key, args.batch_limit, args.first_100,
                                      args.max_new_requests)
            finally:
                key = None
        elif args.recover_metered_evidence:
            result = recover_metered_evidence(queue)
        else:
            result = {"status": "prepared_offline" if args.prepare else "offline_status",
                      **queue.summary()}
        print(json.dumps(result, sort_keys=True))
    finally:
        budget.close()


if __name__ == "__main__":
    main()

"""Foreground, restartable supervisor for the frozen 100k source scope.

Run from the repository root. The paid runner and project ledger remain the
authority for dispatch and money. This file only decides when to run a gate.
"""

import argparse
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3

from tools import scale100k_queue as scale
from tools.scale100k_manifest import load


SUPERVISOR_LOCK = Path("local/scale100k_supervisor.lock")
CHECKPOINT = Path("local/scale100k_supervisor.json")
MAX_QUALITY_STOPS = 2
MAX_SCALE_ROWS = 90000  # source positions 10,001 through 100,000


def call_runner(mode, manifest, manifest_sha, interrupted):
    args = argparse.Namespace(status=mode == "status", run_mixed=mode == "run-mixed",
        recover_metered=mode == "recover-metered",
        activate_next_gate=mode == "activate-next-gate", adopt25=False,
        run_jev=False, run_evidence=False, run25_trial=False,
        set_global_workers=None, global_workers=scale.WORKERS,
        jev_workers=scale.DEFAULT_JEV_WORKERS)
    return scale._main_locked(args, manifest, manifest_sha,
        stop_requested=interrupted)


def source_coverage(manifest, expected_count):
    """Check the already activated slice against the frozen source manifest."""
    if expected_count < 0 or expected_count > MAX_SCALE_ROWS or \
            expected_count % scale.GATE_ROWS:
        raise ValueError("activated source scope is not a frozen 10k gate")
    uri = Path(scale.BUDGET).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        rows = db.execute("SELECT position,review_id,source_sha FROM scale_rows ORDER BY position")
        seen = 0
        for index, (position, rid, source_sha) in enumerate(rows):
            if index >= expected_count:
                raise ValueError("activated source count exceeds reported count")
            source = manifest["rows"][index]
            if (position, rid, source_sha) != (source["source_position"],
                    source["review_id"], source["source_sha256"]):
                raise ValueError("activated source identity differs from frozen manifest")
            seen += 1
        if seen != expected_count:
            raise ValueError("activated source count differs from frozen manifest")


def checked_status(result, manifest):
    count = result["activated_source_rows"]
    source_coverage(manifest, count)
    states = result["source_states"]
    if sum(states.values()) != count:
        raise ValueError("source statuses do not reconcile")
    if states.get("in_flight", 0):
        raise ValueError("active source request; stop for manual reconciliation")
    if result["jev_eligible_unique"] < 0 or result["evidence_eligible_unique"] < 0:
        raise ValueError("negative eligible count")
    return count


def progress(result):
    return result["labels"] + result["evidence"]


def uncertain_count(result):
    return sum(v for k, v in result["requests"].items() if k.endswith(":uncertain"))


def save_checkpoint(state):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as out:
        json.dump(state, out, sort_keys=True)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    tmp.chmod(0o600)
    os.replace(tmp, CHECKPOINT)


def supervise(manifest, manifest_sha, interrupted, invoke=call_runner,
              resume_reviewed=False):
    """Advance only after each drained segment and checked source gate."""
    quality_stops = 0
    saved = None
    if CHECKPOINT.exists():
        saved = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if saved.get("manifest_sha") != manifest_sha:
            raise ValueError("supervisor checkpoint source identity differs")
        quality_stops = saved.get("quality_stops", 0)
        if type(quality_stops) is not int or not 0 <= quality_stops <= MAX_QUALITY_STOPS:
            raise ValueError("invalid supervisor quality-stop count")
        if type(saved.get("uncertain_baseline")) is not int or saved["uncertain_baseline"] < 0:
            raise ValueError("invalid supervisor uncertain baseline")

    allowed_uncertain = saved["uncertain_baseline"] if saved else None

    def record(reason, result):
        save_checkpoint({"manifest_sha": manifest_sha,
            "quality_stops": quality_stops, "stop_reason": reason,
            "uncertain_baseline": allowed_uncertain,
            "activated_source_rows": result["activated_source_rows"],
            "labels": result["labels"], "evidence": result["evidence"],
            "exposure_nusd": result["exposure_nusd"]})
        print(json.dumps({"supervisor": reason,
            "activated_source_rows": result["activated_source_rows"],
            "labels": result["labels"], "evidence": result["evidence"],
            "exposure_nusd": result["exposure_nusd"]}, sort_keys=True), flush=True)

    current = invoke("status", manifest, manifest_sha, interrupted)
    checked_status(current, manifest)
    observed_uncertain = uncertain_count(current)
    if saved is None:
        if resume_reviewed:
            raise ValueError("reviewed resume requires a saved supervisor stop")
        allowed_uncertain = observed_uncertain
        record("initial baseline", current)
    elif observed_uncertain != allowed_uncertain or quality_stops >= MAX_QUALITY_STOPS:
        if not resume_reviewed:
            print(json.dumps({"supervisor": "manual review required before resume",
                "saved_uncertain": allowed_uncertain,
                "observed_uncertain": observed_uncertain,
                "quality_stops": quality_stops}, sort_keys=True), flush=True)
            return 2
        quality_stops = 0
        allowed_uncertain = observed_uncertain
        record("reviewed resume acknowledged", current)
    elif resume_reviewed:
        raise ValueError("no reviewed stop requires acknowledgment")
    if current["requests"].get("evidence:quarantined_metered", 0):
        invoke("recover-metered", manifest, manifest_sha, interrupted)
        current = invoke("status", manifest, manifest_sha, interrupted)
        checked_status(current, manifest)
    while True:
        if interrupted():
            record("operator interrupt; drained", current)
            return 130
        count = checked_status(current, manifest)
        if count == MAX_SCALE_ROWS and not (current["jev_eligible_unique"] or
                current["evidence_eligible_unique"]):
            if current["source_states"].get("eligible_or_awaiting_label", 0):
                raise ValueError("source statuses show unfinished eligible rows")
            record("100k source scope complete or accounted for", current)
            return 0
        if quality_stops >= MAX_QUALITY_STOPS:
            record("repeated quality stops; manual review required", current)
            return 2
        if not (current["jev_eligible_unique"] or current["evidence_eligible_unique"]):
            if current["source_states"].get("eligible_or_awaiting_label", 0):
                raise ValueError("source statuses show unfinished eligible rows")
            if count == MAX_SCALE_ROWS:
                raise ValueError("scope complete but statuses do not reconcile")
            current = invoke("activate-next-gate", manifest, manifest_sha, interrupted)
            checked_status(current | {"jev_eligible_unique": 0,
                "evidence_eligible_unique": 0}, manifest)
            if current.get("activated_now") != scale.GATE_ROWS:
                raise ValueError("next frozen gate did not activate exactly 10k rows")
            current = invoke("status", manifest, manifest_sha, interrupted)
            checked_status(current, manifest)
            record("gate activated", current)
            continue

        before_uncertain = uncertain_count(current)
        before_progress = progress(current)
        outcome = invoke("run-mixed", manifest, manifest_sha, interrupted)
        current = invoke("status", manifest, manifest_sha, interrupted)
        checked_status(current, manifest)
        if current["activated_source_rows"] != count:
            raise ValueError("source gate changed during mixed segment")
        if uncertain_count(current) > before_uncertain or any(outcome.get("new_uncertain", {}).values()):
            record("new uncertain paid request; manual reconciliation required", current)
            return 2
        if interrupted():
            record("operator interrupt; drained", current)
            return 130
        halt = outcome.get("halt_reason")
        if outcome.get("paused") and halt != "structural quality gate":
            record("runner stopped: " + str(halt), current)
            return 2
        if halt == "structural quality gate":
            invoke("recover-metered", manifest, manifest_sha, interrupted)
            current = invoke("status", manifest, manifest_sha, interrupted)
            checked_status(current, manifest)
            if progress(current) <= before_progress:
                record("quality stop without accepted progress", current)
                return 2
            quality_stops += 1
            if quality_stops >= MAX_QUALITY_STOPS:
                record("repeated quality stops", current)
                return 2
            record("quality stop recovered from saved charged responses", current)
            continue
        if progress(current) <= before_progress:
            record("no accepted progress", current)
            return 2
        quality_stops = 0
        record("segment drained", current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-reviewed", action="store_true",
        help="acknowledge a reviewed quality stop or changed uncertain-request count")
    args = parser.parse_args()
    SUPERVISOR_LOCK.parent.mkdir(parents=True, exist_ok=True)
    stop = {"requested": False}
    def on_signal(signum, frame):
        stop["requested"] = True
    with SUPERVISOR_LOCK.open("a+b") as supervisor_lease:
        try:
            fcntl.flock(supervisor_lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another scale supervisor is active") from exc
        scale.LOCK.touch(mode=0o600, exist_ok=True)
        with scale.LOCK.open("r+") as paid_lease:
            try:
                fcntl.flock(paid_lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("manual paid runner or other supervisor is active") from exc
            old_int = signal.signal(signal.SIGINT, on_signal)
            old_term = signal.signal(signal.SIGTERM, on_signal)
            try:
                manifest, manifest_sha = load()
                try:
                    code = supervise(manifest, manifest_sha,
                        lambda: stop["requested"],
                        resume_reviewed=args.resume_reviewed)
                except Exception as exc:
                    print(json.dumps({"supervisor": "stopped; inspect runner and ledger",
                        "error_type": type(exc).__name__}, sort_keys=True), flush=True)
                    raise
            finally:
                signal.signal(signal.SIGINT, old_int)
                signal.signal(signal.SIGTERM, old_term)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

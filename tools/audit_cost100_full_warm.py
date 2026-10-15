"""Run all saved cost100 stages on an isolated copy, with paid/network calls denied."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import time
from unittest.mock import patch

from tools import cost100_harness as h


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(conn):
    result = {}
    for table, order in [("rows", "position"), ("outputs", "stage,key"), ("calls", "key")]:
        values = conn.execute("SELECT * FROM " + table + " ORDER BY " + order).fetchall()
        result[table] = {"count": len(values), "sha256": h.digest(values)}
    result["completed"] = conn.execute("SELECT COUNT(*) FROM outputs WHERE stage='enrich_evidence'").fetchone()[0]
    result["quarantined"] = conn.execute("SELECT COUNT(*) FROM outputs WHERE stage='quarantine_evidence'").fetchone()[0]
    return result


def audit(pilot, out):
    whole_start = time.monotonic()
    if out.exists():
        raise ValueError("Use a new output folder; existing evidence is never replaced")
    os.umask(0o077)
    out.mkdir(parents=True, mode=0o700)
    original = pilot / "pilot.db"
    original_sha = sha(original)
    copied = out / "pilot.db"
    shutil.copyfile(original, copied)
    os.chmod(copied, 0o600)
    conn = sqlite3.connect(str(copied))
    meta = dict(conn.execute("SELECT key,value FROM meta"))
    source_rows = h.rows(conn)
    source = out / "cost_100.csv"
    # Recover original bytes only if they match the immutable pilot source digest.
    matched = False
    for newline in ("\n", "\r\n"):
        for quoting in (csv.QUOTE_MINIMAL, csv.QUOTE_ALL):
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=h.SOURCE_FIELDS,
                                    lineterminator=newline, quoting=quoting)
            writer.writeheader(); writer.writerows(source_rows)
            for encoding in ("utf-8", "utf-8-sig"):
                content = stream.getvalue().encode(encoding)
                if hashlib.sha256(content).hexdigest() == meta["source_sha"]:
                    source.write_bytes(content); matched = True; break
            if matched: break
        if matched: break
    conn.close()
    if not matched:
        raise ValueError("Cannot reproduce exact source bytes; supply the original sample")
    conn = h.open_run(out, str(source), int(meta["cap_nusd"]))
    attempts = {"paid": 0, "transport": 0, "socket": 0}
    def deny(kind):
        def blocked(*args, **kwargs):
            attempts[kind] += 1
            raise AssertionError("Full warm orchestration attempted forbidden " + kind)
        return blocked
    before = snapshot(conn)
    event_start = conn.execute("SELECT COALESCE(MAX(n),0) FROM events").fetchone()[0]
    with patch.object(h, "paid", side_effect=deny("paid")), \
         patch.object(h, "post_systemone", side_effect=deny("transport")), \
         patch.object(h.openrouter, "request_json", side_effect=deny("transport")), \
         patch.object(socket.socket, "connect", side_effect=deny("socket")), \
         patch.object(socket, "create_connection", side_effect=deny("socket")):
        h.warm(conn, record=False)
        h.checkpoint(conn, out, "before")
        start = time.monotonic()
        h.execute(conn, str(source), int(meta["cap_nusd"]), None, None)
        elapsed = time.monotonic() - start
        h.warm(conn, record=False)
        h.checkpoint(conn, out, "after")
    after = snapshot(conn)
    stages = [{"stage": stage, "elapsed_seconds": seconds}
              for stage, seconds in conn.execute("SELECT stage,elapsed_seconds FROM events WHERE n>? ORDER BY n", (event_start,))]
    conn.close()
    if before != after or attempts != {"paid": 0, "transport": 0, "socket": 0}:
        raise AssertionError("Warm state or dispatch evidence differs")
    if [r["stage"] for r in stages] != ["label", "evidence", "verify", "group", "rank", "memo"]:
        raise AssertionError("Not all orchestration stages ran")
    if sha(original) != original_sha:
        raise AssertionError("Original pilot database changed")
    report = {"schema_version": "cost100-full-warm-audit-v1", "status": "passed",
              "scope": "new full execute() orchestration on a copy of the real unchanged 100-row pilot",
              "historical_main_run_recovery": False, "new_provider_inference": False,
              "source_bytes_match_pinned_pilot": True, "source_sha256": meta["source_sha"],
              "original_database_unchanged": True, "original_database_sha256": original_sha,
              "harness_sha256": sha(Path(h.__file__)), "audit_code_sha256": sha(Path(__file__)),
              "before": before, "after": after, "attempts": attempts,
              "orchestration_seconds": elapsed, "stages": stages,
              "whole_audit_seconds": time.monotonic() - whole_start,
              "notes": ["execute() emits literal cold phase labels; copied events are a new warm experiment, not a new cold benchmark.",
                        "All model stages reuse saved outputs; ranking is recomputed. Validation runs before and after.",
                        "Two original quarantines stay quarantined; no retry or relabel is attempted.",
                        "112 historical calls are retained unchanged; there are zero new calls for any role."]}
    (out / "aggregate_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pilot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    r = audit(args.pilot, args.out)
    print(json.dumps({"status": r["status"], "stages": len(r["stages"]), "attempts": r["attempts"],
                      "completed": r["after"]["completed"], "quarantined": r["after"]["quarantined"],
                      "orchestration_seconds": r["orchestration_seconds"], "original_database_unchanged": True}))


if __name__ == "__main__":
    main()

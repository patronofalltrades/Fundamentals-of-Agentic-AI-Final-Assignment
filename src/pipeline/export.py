"""Grading export: run dir -> grading folder (docs/INTERFACES.md §7, GRADING_CONTRACT.md).

Streaming and memory-conscious: records.jsonl is indexed by byte offset (one int per ID and
status), then the CSV is streamed in order and each chosen line is read back by seek.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from pipeline.io import atomic_write_text
from pipeline.rowhash import row_sha

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import check_submission as checker  # noqa: E402

COMPLETED_FIELDS = ("review_id", "source_sha256", "status", "topic", "intent", "sentiment", "severity",
                    "entities", "evidence_quote", "needs_review", "label_config")
VERSION = "a5-audit-v1"


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def index_records(path: Path):
    """review_id -> byte offset of its latest completed line / latest quarantined line."""
    completed: Dict[str, int] = {}
    quarantined: Dict[str, int] = {}
    if not path.exists():
        return completed, quarantined
    with path.open("rb") as f:
        offset = 0
        for raw in iter(f.readline, b""):
            here, offset = offset, offset + len(raw)
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                if not raw.endswith(b"\n"):
                    break  # torn final line from a crash
                raise
            rid, status = rec.get("review_id"), rec.get("status")
            if status == "completed":
                completed[rid] = here
            elif status == "quarantined":
                quarantined[rid] = here
    return completed, quarantined


class _Writer:
    """Plain or deterministic gzip (mtime=0) line writer; removes the other variant."""

    def __init__(self, out: Path, name: str, use_gzip: bool):
        plain, gz = out / name, out / (name + ".gz")
        (plain if use_gzip else gz).unlink(missing_ok=True)  # avoid the checker's ambiguous_file
        self.path = gz if use_gzip else plain
        self._raw = self.path.open("wb")
        self._f = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0) if use_gzip else self._raw

    def write(self, data: bytes):
        self._f.write(data)

    def close(self):
        if self._f is not self._raw:
            self._f.close()
        self._raw.close()


def export_records(run_dir: Path, csv_path: Path, out: Path, use_gzip: bool) -> dict:
    rec_path = run_dir / "records.jsonl"
    completed, quarantined = index_records(rec_path)
    counts = {"rows": 0, "completed": 0, "quarantined": 0, "not_processed": 0, "cache_reuses": 0,
              "run_source_sha_mismatch": 0}
    writer = _Writer(out, "records.jsonl", use_gzip)
    src = rec_path.open("rb") if rec_path.exists() else None
    try:
        for row in checker.csv_rows(csv_path):
            counts["rows"] += 1
            rid, digest = row["review_id"], row_sha(row)
            offset = completed.get(rid, quarantined.get(rid))
            rec = None
            if offset is not None:
                src.seek(offset)
                rec = json.loads(src.readline())
                if rec.get("source_sha256") not in (None, digest):
                    counts["run_source_sha_mismatch"] += 1
            if rec is not None and rid in completed:
                line = {k: rec.get(k) for k in COMPLETED_FIELDS}
                line["review_id"], line["source_sha256"], line["status"] = rid, digest, "completed"
                if rec.get("cache_source_id"):
                    line["cache_source_id"] = rec["cache_source_id"]
                    counts["cache_reuses"] += 1
                counts["completed"] += 1
            elif rec is not None:
                line = {"review_id": rid, "source_sha256": digest, "status": "quarantined",
                        "reason": rec.get("reason") or "unspecified"}
                counts["quarantined"] += 1
            else:
                reason = "empty_review_text" if not row["review_text"].strip() else "not_processed"
                line = {"review_id": rid, "source_sha256": digest, "status": "quarantined", "reason": reason}
                counts["not_processed" if reason == "not_processed" else "quarantined"] += 1
            writer.write((_dumps(line) + "\n").encode("utf-8"))
    finally:
        writer.close()
        if src:
            src.close()
    return counts


def export_calls(run_dir: Path, out: Path, use_gzip: bool) -> int:
    path, n = run_dir / "calls.jsonl", 0
    writer = _Writer(out, "calls.jsonl", use_gzip)
    try:
        if path.exists():
            with path.open("rb") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    if not raw.endswith(b"\n"):
                        try:
                            json.loads(raw)
                        except ValueError:
                            break  # torn final line
                        raw += b"\n"
                    writer.write(raw)
                    n += 1
    finally:
        writer.close()
    return n


def default_checkpoints(run_dir: Path):
    invocations = []
    path = run_dir / "invocations.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    invocations.append(json.loads(line))
                except ValueError:
                    pass
    if not invocations:
        return None, None
    ck = run_dir / "checkpoints"
    return (ck / ("%s-end.json" % invocations[0]["invocation_id"]),
            ck / ("%s-end.json" % invocations[-1]["invocation_id"]))


def _copy_checkpoint(src: Optional[Path], dest: Path) -> Optional[int]:
    if not src or not Path(src).exists():
        return None
    ids = json.loads(Path(src).read_text(encoding="utf-8")).get("completed_ids", [])
    atomic_write_text(dest, json.dumps({"completed_ids": ids}, ensure_ascii=False) + "\n")
    return len(ids)


def export(run_dir, csv_path, out, use_gzip: bool = False, checkpoint_before=None, checkpoint_after=None) -> dict:
    run_dir, csv_path, out = Path(run_dir), Path(csv_path), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    timings, summary = {}, {"out": str(out), "missing": []}

    t = time.monotonic()
    ingestion = checker.profile(csv_path)
    checker.write_json(out / "ingestion.json", ingestion)
    run = {"version": VERSION, "analysis_count": ingestion["counts"]["records"],
           "analysis_sha256": ingestion["file_sha256"], "classification_input_fields": ["review_text"],
           "allow_multi_issue": False}
    atomic_write_text(out / "run.json", json.dumps(run, indent=2) + "\n")
    timings["ingestion_profile"] = round(time.monotonic() - t, 2)

    t = time.monotonic()
    summary["records"] = export_records(run_dir, csv_path, out, use_gzip)
    timings["records"] = round(time.monotonic() - t, 2)

    t = time.monotonic()
    summary["calls"] = export_calls(run_dir, out, use_gzip)
    for name, src in (("membership.csv", run_dir / "group" / "membership.csv"),
                      ("ranking.csv", run_dir / "rank" / "ranking.csv"),
                      ("claims.csv", run_dir / "rank" / "claims.csv")):
        if src.exists():
            shutil.copyfile(src, out / name)
        else:
            (out / name).unlink(missing_ok=True)
            summary["missing"].append(name)
    d_before, d_after = default_checkpoints(run_dir)
    before = Path(checkpoint_before) if checkpoint_before else d_before
    after = Path(checkpoint_after) if checkpoint_after else d_after
    summary["checkpoint_before"] = {"source": str(before) if before else None,
                                    "ids": _copy_checkpoint(before, out / "checkpoint_before.json")}
    summary["checkpoint_after"] = {"source": str(after) if after else None,
                                   "ids": _copy_checkpoint(after, out / "checkpoint_after.json")}
    for key, name in (("checkpoint_before", "checkpoint_before.json"), ("checkpoint_after", "checkpoint_after.json")):
        if summary[key]["ids"] is None:
            summary["missing"].append(name)
    timings["calls_tables_checkpoints"] = round(time.monotonic() - t, 2)
    summary["timings_seconds"] = timings
    return summary


def load_or_build_reference(csv_path, ref_path) -> dict:
    """Reference for the full CSV vs itself; cached at ref_path and reused when the file hash matches."""
    csv_path, ref_path = Path(csv_path), Path(ref_path)
    digest = checker.sha(csv_path)
    if ref_path.exists():
        try:
            with ref_path.open(encoding="utf-8") as f:
                ref = json.load(f)
            if ref.get("version") == VERSION and ref.get("analysis_sha256") == digest \
                    and ref.get("ingestion", {}).get("file_sha256") == digest:
                return ref
        except ValueError:
            pass
    ref = checker.reference(csv_path, csv_path)
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(ref_path, json.dumps(ref, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return ref


def self_check(out, csv_path, ref_path, report_path) -> dict:
    timings = {}
    t = time.monotonic()
    ref = load_or_build_reference(csv_path, ref_path)
    timings["reference"] = round(time.monotonic() - t, 2)
    t = time.monotonic()
    result = checker.audit(Path(out), ref)
    timings["audit"] = round(time.monotonic() - t, 2)
    checker.write_json(report_path, result)
    return {"status": result["status"], "issue_counts": result["issue_counts"], "coverage": result["coverage"],
            "timings_seconds": timings, "report": str(report_path)}

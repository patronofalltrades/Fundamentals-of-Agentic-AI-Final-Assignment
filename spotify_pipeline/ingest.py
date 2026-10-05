"""Offline ingestion pipeline.

Builds a temporary SQLite database, validates every source row, computes the
contract profile, then publishes the database and report. The report is
written to a temporary file first so permission or directory errors are caught
before the database is replaced. A best-effort rollback restores the previous
database and report if the paired replace fails. This is not a claim of
multi-file atomicity; a crash between the two replaces is a documented window.
"""

import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from .contract import FULL_CORPUS_NAME, file_sha256, is_empty_text, row_sha256
from .csvio import (
    iter_source_rows,
    validate_likes,
    validate_rating,
    validate_timestamp,
)
from .db import Database, copy_state_from, read_source_identity
from .errors import PathCollisionError, PipelineError, StateError, ValidationError
from .jsonutil import load_strict
from .manifest import check_profile, declared_profile, validate_identity

CONTRACT_VERSION = 1
_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")


class _Profile:
    """Streaming profile accumulator. Holds counters only, not source rows."""

    def __init__(self) -> None:
        self.records = 0
        self.empty = 0
        self.nonempty = 0
        self.missing_version = 0
        self.months: Counter = Counter()
        self.ratings: Counter = Counter()
        self.rows_hasher = hashlib.sha256()
        self.first: Optional[Tuple[datetime, str]] = None
        self.last: Optional[Tuple[datetime, str]] = None

    def add(self, fields: Tuple[str, ...], timestamp: datetime, empty: bool, row_hash: str) -> None:
        self.records += 1
        self.rows_hasher.update(bytes.fromhex(row_hash))
        self.months[fields[5][:7]] += 1
        self.ratings[fields[2]] += 1
        if empty:
            self.empty += 1
        else:
            self.nonempty += 1
        if not fields[4].strip():
            self.missing_version += 1
        if self.first is None or timestamp < self.first[0]:
            self.first = (timestamp, fields[5])
        if self.last is None or timestamp > self.last[0]:
            self.last = (timestamp, fields[5])

    @property
    def parsed_rows_sha256(self) -> str:
        return self.rows_hasher.hexdigest()


def _real(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def check_path_collisions(paths: Dict[str, str]) -> None:
    primaries: Dict[str, str] = {}
    for label, path in paths.items():
        real = _real(path)
        if real in primaries:
            raise PathCollisionError(
                "paths for %r and %r resolve to the same file: %s"
                % (primaries[real], label, real)
            )
        primaries[real] = label

    for label, path in paths.items():
        for suffix in _SIDECAR_SUFFIXES:
            sidecar = _real(path + suffix)
            if sidecar in primaries:
                raise PathCollisionError(
                    "path for %r collides with SQLite sidecar %s of %r"
                    % (primaries[sidecar], sidecar, label)
                )


def _ensure_parent(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)


def _record_stream(input_path: str, profile: _Profile) -> Iterable[Dict[str, Any]]:
    for row_index, fields in iter_source_rows(input_path):
        if not fields[0].strip():
            raise ValidationError("blank review_id at data row %d" % row_index)
        validate_rating(fields[2])
        validate_likes(fields[3])
        timestamp = validate_timestamp(fields[5])
        empty = is_empty_text(fields[1])
        row_hash = row_sha256(fields)
        profile.add(fields, timestamp, empty, row_hash)
        yield {
            "row_index": row_index,
            "fields": fields,
            "row_sha256": row_hash,
            "is_empty": empty,
        }


def _build_report(
    basename: str,
    size: int,
    file_sha: str,
    profile: _Profile,
    distinct_texts: int,
    manifest_status: Dict[str, Any],
    preserved_completed: int,
    preserved_quarantined: int,
    configuration_counts: Dict[str, Any],
) -> Dict[str, Any]:
    core = {
        "file_sha256": file_sha,
        "parsed_rows_sha256": profile.parsed_rows_sha256,
        "counts": {
            "records": profile.records,
            "duplicate_review_ids": 0,
            "empty_review_text": profile.empty,
            "missing_app_version": profile.missing_version,
        },
        "reviews_by_month": dict(sorted(profile.months.items())),
        "reviews_by_rating": dict(sorted(profile.ratings.items())),
        "first_review": profile.first[1] if profile.first else None,
        "last_review": profile.last[1] if profile.last else None,
    }
    preserved = preserved_completed > 0 or preserved_quarantined > 0
    if preserved:
        note = (
            "Offline ingestion only. Prior completed/quarantined state for this "
            "same source was preserved."
        )
    else:
        note = "Offline ingestion only. No classification results are present."
    extended = {
        "contract_version": CONTRACT_VERSION,
        "source_basename": basename,
        "source_bytes": size,
        "nonempty_review_text": profile.nonempty,
        "distinct_nonempty_texts": distinct_texts,
        "duplicate_text_excess": profile.nonempty - distinct_texts,
        "preserved_state": preserved,
        "preserved_completed": preserved_completed,
        "preserved_quarantined": preserved_quarantined,
        "preserved_state_counts_scope": "record/configuration pairs, not unique source IDs",
        "configuration_status_counts": configuration_counts,
        "status_counts_scope": "unconfigured source; use configuration_status_counts for saved work",
        "status_counts": {
            "completed": 0,
            "quarantined": profile.empty,
            "pending": profile.nonempty,
        },
        "manifest_validation": manifest_status,
        "note": note,
    }
    report = dict(core)
    report["extended"] = extended
    return report


def extract_contract_profile(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return the exact contract-compatible core profile from a report."""
    keys = (
        "file_sha256",
        "parsed_rows_sha256",
        "counts",
        "reviews_by_month",
        "reviews_by_rating",
        "first_review",
        "last_review",
    )
    return {key: report[key] for key in keys}


def _write_report_temp(payload: Dict[str, Any], report_path: str) -> str:
    """Write the report to a temporary file next to its final path.

    Raises before any database publication if the report directory is missing
    or unwritable.
    """
    _ensure_parent(report_path)
    directory = os.path.dirname(os.path.abspath(report_path))
    fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return temp_path


def _publish(db_temp: str, report_temp: str, db_path: str, report_path: str) -> None:
    """Replace database then report with a best-effort rollback on failure."""
    pid = os.getpid()
    db_backup = "%s.bak-%d" % (db_path, pid)
    report_backup = "%s.bak-%d" % (report_path, pid)
    db_moved = False
    try:
        if os.path.exists(db_path):
            os.replace(db_path, db_backup)
        if os.path.exists(report_path):
            os.replace(report_path, report_backup)
        os.replace(db_temp, db_path)
        db_moved = True
        os.replace(report_temp, report_path)
    except Exception:
        if db_moved and os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(db_backup):
            os.replace(db_backup, db_path)
        if os.path.exists(report_backup):
            os.replace(report_backup, report_path)
        raise
    else:
        for backup in (db_backup, report_backup):
            if os.path.exists(backup):
                os.remove(backup)


def ingest(input_path: str, manifest_path: str, db_path: str, report_path: str) -> Dict[str, Any]:
    """Run the offline ingestion pipeline and return the report."""
    check_path_collisions(
        {
            "input": input_path,
            "manifest": manifest_path,
            "database": db_path,
            "report": report_path,
        }
    )

    if not os.path.isfile(input_path):
        raise PipelineError("input file not found: %s" % input_path)
    if not os.path.isfile(manifest_path):
        raise PipelineError("manifest file not found: %s" % manifest_path)
    if any(os.path.isdir(path) for path in (db_path, report_path)):
        raise PipelineError("database and report outputs must be files, not directories")

    manifest = load_strict(manifest_path)
    basename = os.path.basename(input_path)
    size = os.path.getsize(input_path)
    file_sha = file_sha256(input_path)
    manifest_status = validate_identity(manifest, basename, file_sha, size)

    existing_identity = read_source_identity(db_path) if os.path.exists(db_path) else None
    if os.path.exists(db_path):
        if not existing_identity or not existing_identity.get("file_sha256"):
            raise StateError("existing database is not a recognized pipeline database")
        if existing_identity["file_sha256"] != file_sha:
            raise StateError(
                "existing database was built from a different source; refusing to erase progress"
            )
        if existing_identity.get("source_basename") not in (None, basename):
            raise StateError("existing database source name does not match the input")
        if existing_identity.get("contract_version") not in (None, str(CONTRACT_VERSION)):
            raise StateError("existing database schema version does not match")

    declared = declared_profile(manifest, basename)

    _ensure_parent(db_path)
    db_dir = os.path.dirname(os.path.abspath(db_path))
    fd, temp_db_path = tempfile.mkstemp(dir=db_dir, prefix=".ingest-", suffix=".db-tmp")
    os.close(fd)
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    profile = _Profile()
    preserved_completed = 0
    preserved_quarantined = 0
    configuration_counts = {}
    try:
        with Database(temp_db_path) as db:
            db.initialize()
            db.set_meta("source_basename", basename)
            db.set_meta("file_sha256", file_sha)
            db.set_meta("source_bytes", str(size))
            db.set_meta("contract_version", str(CONTRACT_VERSION))
            db.insert_records(_record_stream(input_path, profile))
            db.set_meta("parsed_rows_sha256", profile.parsed_rows_sha256)
            distinct_texts = db.count_distinct_texts()
            if existing_identity:
                copy_state_from(db_path, db, file_sha)
                preserved_completed = db.conn.execute(
                    "SELECT COUNT(*) AS n FROM record_state WHERE status = 'completed'"
                ).fetchone()["n"]
                preserved_quarantined = db.conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM record_state rs
                    JOIN records r ON r.row_index = rs.row_index
                    WHERE rs.status = 'quarantined' AND r.is_empty = 0
                    """
                ).fetchone()["n"]
                for item in db.conn.execute("SELECT DISTINCT config_hash FROM record_state"):
                    configuration_counts[item["config_hash"]] = db.status_counts(item["config_hash"])
    except Exception:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        raise

    if declared is not None:
        computed = {
            "records": profile.records,
            "duplicate_review_ids": 0,
            "empty_review_text": profile.empty,
            "missing_app_version": profile.missing_version,
            "distinct_nonempty_texts": distinct_texts,
            "reviews_by_month": dict(profile.months),
            "reviews_by_rating": dict(profile.ratings),
            "first_review": profile.first[1] if profile.first else None,
            "last_review": profile.last[1] if profile.last else None,
        }
        try:
            check_profile(basename, declared, computed)
        except Exception:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            raise
        if basename == FULL_CORPUS_NAME:
            manifest_status["declared_profile_checked"] = True

    report = _build_report(
        basename,
        size,
        file_sha,
        profile,
        distinct_texts,
        manifest_status,
        preserved_completed,
        preserved_quarantined,
        configuration_counts,
    )

    try:
        report_temp = _write_report_temp(report, report_path)
    except Exception:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        raise

    try:
        _publish(temp_db_path, report_temp, db_path, report_path)
    except Exception:
        for leftover in (temp_db_path, report_temp):
            if os.path.exists(leftover):
                os.remove(leftover)
        raise
    return report

"""Import a canonical checkpoint and save accepted analysis without model calls."""

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dashboard_aggregate (
    dimension TEXT NOT NULL, value TEXT NOT NULL, count INTEGER NOT NULL,
    PRIMARY KEY (dimension, value)
);
CREATE TABLE IF NOT EXISTS analysis_run (
    run_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, config_hash TEXT NOT NULL,
    grouping_status TEXT NOT NULL, verifier_status TEXT NOT NULL,
    recommendation_status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS issue (
    run_id TEXT NOT NULL, issue_id TEXT NOT NULL, title TEXT NOT NULL,
    PRIMARY KEY (run_id, issue_id),
    FOREIGN KEY (run_id) REFERENCES analysis_run(run_id)
);
CREATE TABLE IF NOT EXISTS issue_membership (
    run_id TEXT NOT NULL, issue_id TEXT NOT NULL, row_index INTEGER NOT NULL,
    PRIMARY KEY (run_id, issue_id, row_index),
    FOREIGN KEY (run_id, issue_id) REFERENCES issue(run_id, issue_id),
    FOREIGN KEY (row_index) REFERENCES records(row_index)
);
CREATE TABLE IF NOT EXISTS recommendation (
    run_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, text TEXT NOT NULL,
    PRIMARY KEY (run_id, recommendation_id),
    FOREIGN KEY (run_id) REFERENCES analysis_run(run_id)
);
CREATE TABLE IF NOT EXISTS recommendation_issue (
    run_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, issue_id TEXT NOT NULL,
    PRIMARY KEY (run_id, recommendation_id, issue_id),
    FOREIGN KEY (run_id, recommendation_id) REFERENCES recommendation(run_id, recommendation_id),
    FOREIGN KEY (run_id, issue_id) REFERENCES issue(run_id, issue_id)
);
CREATE TABLE IF NOT EXISTS claim (
    run_id TEXT NOT NULL, claim_id TEXT NOT NULL, issue_id TEXT NOT NULL, metric TEXT NOT NULL, value TEXT NOT NULL,
    PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS memo (
    run_id TEXT PRIMARY KEY, text TEXT NOT NULL, sha256 TEXT NOT NULL, claim_check TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_membership_row ON issue_membership(row_index);
"""


def connect(path: str, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        if not os.path.isfile(path):
            raise ValueError("dashboard database not found")
        from urllib.parse import quote
        conn = sqlite3.connect("file:%s?mode=ro" % quote(os.path.abspath(path)), uri=True)
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _source_identity(conn: sqlite3.Connection) -> Dict[str, str]:
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    if not meta.get("file_sha256") or not meta.get("parsed_rows_sha256"):
        raise ValueError("not a canonical pipeline database")
    configs = conn.execute("SELECT DISTINCT config_hash FROM record_state").fetchall()
    if len(configs) != 1:
        raise ValueError("expected exactly one saved configuration")
    return {"source_sha256": meta["file_sha256"], "config_hash": configs[0][0]}


def _refresh_aggregates(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM dashboard_aggregate")
    queries = {
        "source_status": "SELECT CASE WHEN is_empty=1 THEN 'empty' ELSE 'nonempty' END, COUNT(*) FROM records GROUP BY 1",
        "processing_status": "SELECT status, COUNT(*) FROM record_state GROUP BY status",
        "topic": "SELECT topic, COUNT(*) FROM classifications GROUP BY topic",
        "intent": "SELECT intent, COUNT(*) FROM classifications GROUP BY intent",
        "severity": "SELECT CAST(severity AS TEXT), COUNT(*) FROM classifications GROUP BY severity",
        "coverage": "SELECT 'distinct_nonempty_texts', COUNT(*) FROM texts",
    }
    for dimension, query in queries.items():
        conn.executemany("INSERT INTO dashboard_aggregate VALUES (?, ?, ?)",
                         ((dimension, value, count) for value, count in conn.execute(query)))


def import_checkpoint(source: str, target: str) -> Dict[str, Any]:
    """Copy a complete canonical DB once. Repeating the same import changes nothing."""
    with connect(source, readonly=True) as src:
        identity = _source_identity(src)
        source_rows = src.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        completed = src.execute("SELECT COUNT(*) FROM record_state WHERE status='completed'").fetchone()[0]
        if source_rows != completed or source_rows != src.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]:
            raise ValueError("source is not a complete checkpoint")
        if os.path.exists(target):
            with connect(target, readonly=True) as dst:
                if _source_identity(dst) != identity or dst.execute("SELECT COUNT(*) FROM records").fetchone()[0] != source_rows:
                    raise ValueError("target already contains different source state")
                if dst.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='dashboard_aggregate'").fetchone()[0] != 1:
                    raise ValueError("target has not been initialized for dashboard")
            return {"result": "unchanged", "source_rows": source_rows, **identity}
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = str(target_path) + ".import-tmp"
        if os.path.exists(temporary):
            raise ValueError("temporary import file already exists")
        try:
            with connect(temporary) as dst:
                src.backup(dst)
                dst.executescript(EXTRA_SCHEMA)
                with dst:
                    dst.execute("INSERT INTO dashboard_meta VALUES (?, ?)", ("source_sha256", identity["source_sha256"]))
                    _refresh_aggregates(dst)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {"result": "imported", "source_rows": source_rows, **identity}


def initialize_existing(path: str) -> None:
    """Initialize a private copy that was made using SQLite backup."""
    with connect(path) as conn:
        identity = _source_identity(conn)
        conn.executescript(EXTRA_SCHEMA)
        with conn:
            conn.execute("INSERT OR IGNORE INTO dashboard_meta VALUES (?, ?)", ("source_sha256", identity["source_sha256"]))
            _refresh_aggregates(conn)


def import_analysis(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist accepted membership in a SQLite dashboard copy. See ``dashboard.analysis``."""
    from .analysis import load_analysis
    from .backend import SQLiteBackend
    with SQLiteBackend(path, readonly=False) as backend:
        return load_analysis(backend, payload)

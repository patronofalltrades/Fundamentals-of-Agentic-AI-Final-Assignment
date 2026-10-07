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
    """Persist accepted membership; derive ranking from saved classifications."""
    with connect(path) as conn:
        identity = _source_identity(conn)
        if payload.get("source_sha256") != identity["source_sha256"] or payload.get("config_hash") != identity["config_hash"]:
            raise ValueError("analysis source/configuration identity mismatch")
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise ValueError("run_id is required")
        issues = payload.get("issues")
        recommendations = payload.get("recommendations", [])
        if not isinstance(issues, list) or not issues or not isinstance(recommendations, list):
            raise ValueError("accepted issues and recommendation list are required")
        known_rows = {r[0]: r[1] for r in conn.execute("SELECT r.row_index,c.intent FROM records r JOIN classifications c USING(row_index) WHERE c.config_hash=?", (identity["config_hash"],))}
        issue_ids = set()
        memberships = []
        for item in issues:
            issue_id, title, rows = item.get("issue_id"), item.get("title"), item.get("row_indices")
            if not isinstance(issue_id, str) or not IDENTIFIER.fullmatch(issue_id) or issue_id in issue_ids or not isinstance(title, str) or not title.strip() or not isinstance(rows, list) or not rows:
                raise ValueError("issue needs unique ID, title, and nonempty membership")
            issue_ids.add(issue_id)
            if any(type(row) is not int for row in rows) or len(rows) != len(set(rows)) or any(known_rows.get(row) not in ("complaint", "cancellation") for row in rows):
                raise ValueError("membership must contain unique completed complaint/cancellation rows")
            memberships.extend((run_id, issue_id, row) for row in rows)
        recommendation_ids = set()
        for item in recommendations:
            rid, body, refs = item.get("recommendation_id"), item.get("text"), item.get("issue_ids")
            if not isinstance(rid, str) or not IDENTIFIER.fullmatch(rid) or rid in recommendation_ids or not isinstance(body, str) or not body.strip() or not isinstance(refs, list) or not refs or any(ref not in issue_ids for ref in refs) or len(refs) != len(set(refs)):
                raise ValueError("recommendation needs unique ID, text, and valid issue links")
            recommendation_ids.add(rid)
        with conn:
            existing = conn.execute("SELECT 1 FROM analysis_run WHERE run_id=?", (run_id,)).fetchone()
            if existing:
                raise ValueError("analysis run ID already exists; saved analysis is immutable")
            conn.execute("INSERT INTO analysis_run(run_id,source_sha256,config_hash,grouping_status,verifier_status,recommendation_status) VALUES(?,?,?,'accepted','pending',?)", (run_id, identity["source_sha256"], identity["config_hash"], "draft_unverified" if recommendations else "pending"))
            conn.executemany("INSERT INTO issue VALUES (?,?,?)", ((run_id, i["issue_id"], i["title"]) for i in issues))
            conn.executemany("INSERT INTO issue_membership VALUES (?,?,?)", memberships)
            for item in recommendations:
                conn.execute("INSERT INTO recommendation VALUES (?,?,?)", (run_id, item["recommendation_id"], item["text"]))
                conn.executemany("INSERT INTO recommendation_issue VALUES (?,?,?)", ((run_id, item["recommendation_id"], issue_id) for issue_id in item["issue_ids"]))
    return {"run_id": run_id, "issues": len(issues), "memberships": len(memberships), "recommendations": len(recommendations)}

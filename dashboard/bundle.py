"""Idempotent import contract between the review pipeline and the deployed dashboard database.

``export_bundle(dashboard_sqlite, out_dir)`` writes a bundle directory:

- ``rows.jsonl``: one line per source row, in ``row_index`` order. It keeps the original
  ``review_id``, the source ``row_sha256`` and ``text_sha256``, the processing status, the saved
  labels and the source-exact ``evidence_quote``. It does **not** contain the full review text,
  rating, likes, app version or timestamp: the dashboard does not need them.
- ``manifest.json``: bundle version, source and configuration identity, separate source-row and
  distinct-text counts, label aggregates, and the SHA-256 of ``rows.jsonl``.

``load_bundle(backend, bundle_dir)`` loads a bundle into SQLite or Postgres:

1. It checks the ``rows.jsonl`` hash and every count against the manifest before any write.
2. It refuses a database that holds a different source, configuration or bundle.
3. It records ``import_status=importing`` first, then inserts rows in chunks with
   ``ON CONFLICT DO NOTHING``. An interrupted load can run again and continue.
4. It recounts the rows in the database. Only when every count matches does it write the
   aggregates and set ``import_status=complete``.
5. A second load of the same complete bundle returns ``unchanged`` and writes nothing.

No model call happens here. Standard library only.
"""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .store import connect

BUNDLE_VERSION = "dashboard-bundle-v1"
ROW_FIELDS = ("row_index", "review_id", "row_sha256", "text_sha256", "is_empty", "status", "reason",
              "config_hash", "topic", "intent", "sentiment", "severity", "entities", "evidence_quote",
              "needs_review", "is_cached", "label_config", "model", "prompt_version", "schema_version")
CHUNK = 200

DDL = {
    "common": [
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS dashboard_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS records (row_index INTEGER PRIMARY KEY, review_id TEXT NOT NULL UNIQUE, "
        "row_sha256 TEXT NOT NULL, text_sha256 TEXT, is_empty INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS record_state (row_index INTEGER PRIMARY KEY REFERENCES records(row_index), "
        "config_hash TEXT NOT NULL, status TEXT NOT NULL, reason TEXT)",
        "CREATE TABLE IF NOT EXISTS classifications (row_index INTEGER NOT NULL REFERENCES records(row_index), "
        "config_hash TEXT NOT NULL, topic TEXT NOT NULL, intent TEXT NOT NULL, sentiment DOUBLE PRECISION, "
        "severity INTEGER NOT NULL, entities TEXT, evidence_quote TEXT NOT NULL, needs_review INTEGER NOT NULL, "
        "is_cached INTEGER NOT NULL, label_config TEXT, model TEXT, prompt_version TEXT, schema_version TEXT, "
        "PRIMARY KEY (row_index, config_hash))",
        "CREATE TABLE IF NOT EXISTS dashboard_aggregate (dimension TEXT NOT NULL, value TEXT NOT NULL, "
        "count INTEGER NOT NULL, PRIMARY KEY (dimension, value))",
        "CREATE TABLE IF NOT EXISTS issue (run_id TEXT NOT NULL, issue_id TEXT NOT NULL, title TEXT NOT NULL, "
        "PRIMARY KEY (run_id, issue_id))",
        "CREATE TABLE IF NOT EXISTS issue_membership (run_id TEXT NOT NULL, issue_id TEXT NOT NULL, "
        "row_index INTEGER NOT NULL, PRIMARY KEY (run_id, issue_id, row_index))",
        "CREATE TABLE IF NOT EXISTS recommendation (run_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, "
        "text TEXT NOT NULL, PRIMARY KEY (run_id, recommendation_id))",
        "CREATE TABLE IF NOT EXISTS recommendation_issue (run_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, "
        "issue_id TEXT NOT NULL, PRIMARY KEY (run_id, recommendation_id, issue_id))",
        "CREATE TABLE IF NOT EXISTS claim (run_id TEXT NOT NULL, claim_id TEXT NOT NULL, issue_id TEXT NOT NULL, "
        "metric TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (run_id, claim_id))",
        "CREATE TABLE IF NOT EXISTS memo (run_id TEXT PRIMARY KEY, text TEXT NOT NULL, sha256 TEXT NOT NULL, "
        "claim_check TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_classifications_topic ON classifications(topic)",
        "CREATE INDEX IF NOT EXISTS idx_membership_row ON issue_membership(row_index)",
    ],
    "sqlite": ["CREATE TABLE IF NOT EXISTS analysis_run (run_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, "
               "config_hash TEXT NOT NULL, grouping_status TEXT NOT NULL, verifier_status TEXT NOT NULL, "
               "recommendation_status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"],
    "postgres": ["CREATE TABLE IF NOT EXISTS analysis_run (run_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, "
                 "config_hash TEXT NOT NULL, grouping_status TEXT NOT NULL, verifier_status TEXT NOT NULL, "
                 "recommendation_status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (now()::text))"],
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def export_bundle(dashboard_db: str, out_dir: str) -> Dict[str, Any]:
    """Write ``rows.jsonl`` and ``manifest.json`` from a dashboard SQLite copy. Deterministic."""
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("bundle directory is not empty")
    out.mkdir(parents=True, exist_ok=True)
    with connect(dashboard_db, readonly=True) as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta"))
        configs = [r[0] for r in conn.execute("SELECT DISTINCT config_hash FROM record_state")]
        if len(configs) != 1:
            raise ValueError("expected exactly one saved configuration")
        distinct = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
        rows = conn.execute(
            "SELECT r.row_index, r.review_id, r.row_sha256, r.text_sha256, r.is_empty, s.status, s.reason, "
            "s.config_hash, c.topic, c.intent, c.sentiment, c.severity, c.entities, c.evidence_quote, "
            "c.needs_review, c.is_cached, c.label_config, c.model, c.prompt_version, c.schema_version "
            "FROM records r JOIN record_state s USING(row_index) "
            "LEFT JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=s.config_hash "
            "ORDER BY r.row_index").fetchall()
    counts = Counter()
    labels = {"topic": Counter(), "intent": Counter(), "severity": Counter()}
    rows_path = out / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            item = dict(zip(ROW_FIELDS, row))
            counts["source_rows"] += 1
            counts["empty_rows" if item["is_empty"] else "nonempty_rows"] += 1
            counts["%s_rows" % item["status"]] += 1
            if item["status"] == "completed":
                for dim in labels:
                    labels[dim][str(item[dim])] += 1
            f.write(_canonical(item) + "\n")
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "source": {"basename": meta.get("source_basename"), "file_sha256": meta.get("file_sha256"),
                   "parsed_rows_sha256": meta.get("parsed_rows_sha256")},
        "config_hash": configs[0],
        "counts": dict(sorted(counts.items()), distinct_nonempty_texts=distinct),
        "labels": {dim: dict(sorted(c.items())) for dim, c in labels.items()},
        "rows_sha256": _sha256(rows_path),
        "excluded_fields": ["review_text", "review_rating", "review_likes", "app_version", "review_timestamp"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _read_bundle(bundle_dir: str):
    root = Path(bundle_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("bundle_version") != BUNDLE_VERSION:
        raise ValueError("unsupported bundle version")
    if _sha256(root / "rows.jsonl") != manifest["rows_sha256"]:
        raise ValueError("rows.jsonl does not match the manifest hash")
    rows = [json.loads(line) for line in (root / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line]
    counts = Counter()
    for item in rows:
        if set(item) != set(ROW_FIELDS):
            raise ValueError("unexpected row fields")
        counts["source_rows"] += 1
        counts["empty_rows" if item["is_empty"] else "nonempty_rows"] += 1
        counts["%s_rows" % item["status"]] += 1
        if item["config_hash"] != manifest["config_hash"]:
            raise ValueError("row configuration differs from the manifest")
    expected = {k: v for k, v in manifest["counts"].items() if k != "distinct_nonempty_texts"}
    if dict(counts) != expected:
        raise ValueError("row counts do not match the manifest")
    if len({r["review_id"] for r in rows}) != len(rows) or [r["row_index"] for r in rows] != sorted({r["row_index"] for r in rows}):
        raise ValueError("review IDs and row indices must be unique")
    return manifest, rows


def _meta(backend, table: str) -> Dict[str, str]:
    if not backend.table_exists(table):
        return {}
    return {r[0]: r[1] for r in backend.execute("SELECT key, value FROM %s" % table)}


def _upsert_meta(table: str, key: str, value: str):
    return ("INSERT INTO %s (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value" % table,
            (key, value))


def _row_statements(chunk: List[Dict[str, Any]]) -> List[tuple]:
    statements = []
    for r in chunk:
        statements.append(("INSERT INTO records (row_index, review_id, row_sha256, text_sha256, is_empty) "
                           "VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                           (r["row_index"], r["review_id"], r["row_sha256"], r["text_sha256"], int(r["is_empty"]))))
        statements.append(("INSERT INTO record_state (row_index, config_hash, status, reason) VALUES (?, ?, ?, ?) "
                           "ON CONFLICT DO NOTHING", (r["row_index"], r["config_hash"], r["status"], r["reason"])))
        if r["status"] == "completed":
            statements.append((
                "INSERT INTO classifications (row_index, config_hash, topic, intent, sentiment, severity, entities, "
                "evidence_quote, needs_review, is_cached, label_config, model, prompt_version, schema_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (r["row_index"], r["config_hash"], r["topic"], r["intent"], r["sentiment"], r["severity"],
                 r["entities"], r["evidence_quote"], int(bool(r["needs_review"])), int(bool(r["is_cached"])),
                 r["label_config"], r["model"], r["prompt_version"], r["schema_version"])))
    return statements


def load_bundle(backend, bundle_dir: str, chunk_size: int = CHUNK) -> Dict[str, Any]:
    manifest, rows = _read_bundle(bundle_dir)
    identity = {"file_sha256": manifest["source"]["file_sha256"], "config_hash": manifest["config_hash"],
                "rows_sha256": manifest["rows_sha256"]}
    for sql in DDL["common"] + DDL[backend.dialect]:
        backend.execute(sql)
    state = _meta(backend, "dashboard_meta")
    if state.get("bundle_rows_sha256") and state["bundle_rows_sha256"] != identity["rows_sha256"]:
        raise ValueError("database already holds a different bundle")
    existing_source = _meta(backend, "meta").get("file_sha256")
    if existing_source and existing_source != identity["file_sha256"]:
        raise ValueError("database already holds a different source")
    if state.get("import_status") == "complete":
        return {"result": "unchanged", **_summary(manifest)}

    backend.run_batch([
        _upsert_meta("meta", "file_sha256", identity["file_sha256"]),
        _upsert_meta("meta", "parsed_rows_sha256", manifest["source"]["parsed_rows_sha256"] or ""),
        _upsert_meta("meta", "source_basename", manifest["source"]["basename"] or ""),
        _upsert_meta("dashboard_meta", "source_sha256", identity["file_sha256"]),
        _upsert_meta("dashboard_meta", "bundle_rows_sha256", identity["rows_sha256"]),
        _upsert_meta("dashboard_meta", "import_status", "importing"),
    ])
    for start in range(0, len(rows), chunk_size):
        backend.run_batch(_row_statements(rows[start:start + chunk_size]))

    loaded = {
        "source_rows": backend.execute("SELECT COUNT(*) FROM records").fetchone()[0],
        "state_rows": backend.execute("SELECT COUNT(*) FROM record_state").fetchone()[0],
        "classified_rows": backend.execute("SELECT COUNT(*) FROM classifications WHERE config_hash=?",
                                           (manifest["config_hash"],)).fetchone()[0],
    }
    counts = manifest["counts"]
    if loaded != {"source_rows": counts["source_rows"], "state_rows": counts["source_rows"],
                  "classified_rows": counts.get("completed_rows", 0)}:
        raise ValueError("loaded row counts differ from the manifest: %s" % loaded)

    aggregates = [("coverage", "distinct_nonempty_texts", counts["distinct_nonempty_texts"]),
                  ("source_status", "nonempty", counts.get("nonempty_rows", 0)),
                  ("source_status", "empty", counts.get("empty_rows", 0))]
    aggregates += [("processing_status", k[:-5], v) for k, v in counts.items()
                   if k.endswith("_rows") and k not in ("source_rows", "nonempty_rows", "empty_rows")]
    aggregates += [(dim, value, n) for dim, values in manifest["labels"].items() for value, n in values.items()]
    backend.run_batch([("DELETE FROM dashboard_aggregate", ())] +
                      [("INSERT INTO dashboard_aggregate (dimension, value, count) VALUES (?, ?, ?)", a)
                       for a in aggregates if a[2]] +
                      [_upsert_meta("dashboard_meta", "import_status", "complete")])
    return {"result": "imported", **_summary(manifest)}


def _summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {"source_rows": manifest["counts"]["source_rows"],
            "distinct_nonempty_texts": manifest["counts"]["distinct_nonempty_texts"],
            "config_hash": manifest["config_hash"], "rows_sha256": manifest["rows_sha256"]}


def default_bundle_dir() -> str:
    return os.path.join("local", "bundle")

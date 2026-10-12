"""Make a publishable copy of a private accepted-evidence database, and load it into Postgres or SQLite.

The accepted-evidence database is private: it keeps review IDs, source hashes, source text, exact quotes,
entities, raw model output and free-form reasons. ``export_public`` writes a new SQLite file that holds
only what the public API reads:

- Row keys are renumbered in a random order, so a key reveals no source position.
- ``records.review_id`` is the public reference for public examples and an opaque ``n…`` key otherwise.
  Source and text hashes are blank.
- ``classifications`` keep labels and model provenance. Exact quotes and entities are blank.
- ``record_state`` keeps the status only. Reasons, ``row_state``, ``source_text`` and ``raw_record`` are left out.
- ``semantic_flag`` keeps the blocked flag and counts, not the finding categories.
- ``dashboard_meta`` keeps the public manifest keys, the import status and saved evaluations.
- Issues, membership, claims, memo and recommendations are copied under the new keys.

Every public API response is then compared between the two databases. They must be identical, except the
evaluation check that says whether full texts are stored. ``load_public`` copies the file into an empty
Postgres or SQLite target in chunks and marks it complete only after every count matches.
Nothing here deploys anything or changes which database the site uses.
"""

import json
import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .analysis import multi_row_insert
from .bundle import DDL
from .server import PUBLIC_MANIFEST_KEYS, route

PUBLIC_TABLES = [
    "CREATE TABLE IF NOT EXISTS public_example (row_index INTEGER PRIMARY KEY, ref TEXT NOT NULL UNIQUE, "
    "excerpt TEXT NOT NULL, shortened INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS semantic_flag (row_index INTEGER PRIMARY KEY, blocked INTEGER NOT NULL, "
    "human_review_required INTEGER NOT NULL, finding_count INTEGER NOT NULL, categories TEXT NOT NULL)",
]
# Copy order matters for loading: the import status goes last.
TABLES = ("meta", "records", "record_state", "classifications", "public_example", "semantic_flag",
          "dashboard_aggregate", "analysis_run", "issue", "issue_membership", "claim", "memo", "recommendation",
          "recommendation_issue", "dashboard_meta")
ALLOWED = set(TABLES)


def _rows(conn, sql, args=()):
    return [tuple(r) for r in conn.execute(sql, args)]


def _has(conn, table):
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0] == 1


def export_public(private_db: str, out_db: str, rng=None) -> Dict[str, Any]:
    if Path(out_db).exists():
        raise ValueError("target file already exists; export into a new file")
    src = sqlite3.connect("file:%s?mode=ro" % private_db, uri=True)
    if not _has(src, "public_example"):
        raise ValueError("not an accepted-evidence database")
    status = dict(_rows(src, "SELECT key, value FROM dashboard_meta"))
    if status.get("import_status") != "complete":
        raise ValueError("the private import is not complete")
    rng = rng or random.SystemRandom()
    old = [r[0] for r in _rows(src, "SELECT row_index FROM records ORDER BY row_index")]
    new = list(range(1, len(old) + 1))
    rng.shuffle(new)
    key = dict(zip(old, new))
    refs = dict(_rows(src, "SELECT row_index, ref FROM public_example"))

    data = {
        "meta": _rows(src, "SELECT key, value FROM meta WHERE key IN ('file_sha256', 'source_basename')"),
        "records": [(key[i], "n%07d" % key[i], "", None, empty)
                    for i, empty in _rows(src, "SELECT row_index, is_empty FROM records")],
        "record_state": [(key[i], c, s, None) for i, c, s in _rows(src, "SELECT row_index, config_hash, status FROM record_state")],
        "classifications": [(key[r[0]],) + r[1:6] + ("[]", "") + r[6:] for r in _rows(
            src, "SELECT row_index, config_hash, topic, intent, sentiment, severity, needs_review, is_cached, "
                 "label_config, model, prompt_version, schema_version FROM classifications")],
        "public_example": [(key[i], ref, ex, sh) for i, ref, ex, sh in _rows(
            src, "SELECT row_index, ref, excerpt, shortened FROM public_example")],
        "semantic_flag": [(key[i], b, h, n, "[]") for i, b, h, n in _rows(
            src, "SELECT row_index, blocked, human_review_required, finding_count FROM semantic_flag")],
        "dashboard_aggregate": _rows(src, "SELECT dimension, value, count FROM dashboard_aggregate"),
    }
    for table in ("analysis_run", "issue", "claim", "memo", "recommendation", "recommendation_issue"):
        data[table] = _rows(src, "SELECT * FROM %s" % table) if _has(src, table) else []
    data["issue_membership"] = [(run, issue, key[i]) for run, issue, i in _rows(
        src, "SELECT run_id, issue_id, row_index FROM issue_membership")] if _has(src, "issue_membership") else []
    manifest = json.loads(status["import_manifest"])
    meta = [("source_sha256", status["source_sha256"]),
            ("import_manifest", json.dumps({k: manifest[k] for k in PUBLIC_MANIFEST_KEYS if k in manifest},
                                           sort_keys=True))]
    meta += [(k, v) for k, v in sorted(status.items()) if k.startswith("evaluation:")]
    data["dashboard_meta"] = meta + [("import_status", "complete")]

    out = sqlite3.connect(out_db)
    try:
        with out:
            for sql in DDL["common"] + DDL["sqlite"] + PUBLIC_TABLES:
                out.execute(sql)
            for table in TABLES:
                rows = data[table]
                if rows:
                    out.executemany("INSERT INTO %s VALUES (%s)" % (table, ", ".join("?" * len(rows[0]))), rows)
    finally:
        out.close()
        src.close()
    result = {"tables": {t: len(data[t]) for t in TABLES}}
    result.update(compare_api(private_db, out_db))
    result["leaks"] = audit_public(private_db, out_db)
    if result["differences"] or any(result["leaks"].values()):
        raise ValueError("the public copy differs from the private API or holds private data: %s" % result)
    return result


def _get(db, path, query=""):
    from .backend import SQLiteBackend
    return route(lambda: SQLiteBackend(db), "GET", path, query)


def _paths(db) -> List[tuple]:
    """Every public route the page can reach, with the query strings it uses."""
    paths = [(p, "") for p in ("/api/summary", "/api/issues", "/api/claims", "/api/memo", "/api/recommendations")]
    paths += [("/api/reviews", q) for q in ("limit=50", "limit=50&offset=50", "q=crash", "q=ads", "topic=playback",
                                            "topic=billing&limit=50")]
    for item in json.loads(_get(db, "/api/issues")[2])["items"]:
        paths.append(("/api/issues/" + item["issue_id"], ""))
        paths.append(("/api/reviews", "issue_id=%s&limit=50" % item["issue_id"]))
    paths += [("/api/reviews/" + i["ref"], "") for i in json.loads(_get(db, "/api/reviews", "limit=50")[2])["items"]]
    return paths


def compare_api(private_db: str, public_db: str) -> Dict[str, Any]:
    paths = _paths(private_db)
    differences = [path + ("?" + query if query else "") for path, query in paths
                   if _get(private_db, path, query) != _get(public_db, path, query)]
    # The evaluation page says whether full texts are stored: the private file does, the public copy does not.
    a, b = (json.loads(_get(db, "/api/evals")[2]) for db in (private_db, public_db))
    other = lambda r: [c for c in r["checks"] if not c["name"].startswith("Full review texts")]
    if other(a) != other(b) or [c["status"] for c in b["checks"] if c["name"].startswith("Full review texts")] != ["passed"]:
        differences.append("/api/evals")
    return {"compared_routes": len(paths) + 1, "differences": differences}


def _values(conn):
    """Every text value stored in the file, with the longer free-text fields joined for substring checks."""
    values, long_text = set(), []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        for row in conn.execute("SELECT * FROM %s" % table):
            for v in row:
                if isinstance(v, str):
                    values.add(v)
                    if table in ("memo", "claim", "recommendation", "dashboard_meta", "issue"):
                        long_text.append(v)
    return values, "\n".join(long_text)


def audit_public(private_db: str, public_db: str) -> Dict[str, int]:
    """Counts of private values found in the public copy. All must be zero."""
    src = sqlite3.connect("file:%s?mode=ro" % private_db, uri=True)
    pub = sqlite3.connect("file:%s?mode=ro" % public_db, uri=True)
    try:
        tables = {r[0] for r in pub.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        values, text = _values(pub)
        ids = {r[0] for r in src.execute("SELECT review_id FROM records")}
        hashes = {r[0] for r in src.execute("SELECT row_sha256 FROM records")} | \
            {r[0] for r in src.execute("SELECT text_sha256 FROM records") if r[0]}
        long_quotes = {r[0] for r in src.execute("SELECT evidence_quote FROM classifications") if len(r[0].split()) > 30}
        old = dict(src.execute("SELECT ref, row_index FROM public_example"))
        same_key = sum(old.get(ref) == i for i, ref in pub.execute("SELECT row_index, ref FROM public_example"))
        return {"unexpected_tables": len(tables - ALLOWED),
                "review_ids": len(ids & values) + sum(i in text for i in ids),
                "source_hashes": len(hashes & values) + sum(h in text for h in hashes),
                "exact_quotes": audit_tables(pub),
                "long_quotes": len(long_quotes & values),
                "keys_kept": same_key if same_key > 5 else 0}  # a random renumbering keeps about one by chance
    finally:
        src.close()
        pub.close()


def load_public(backend, public_db: str, rows_per_batch: int = 2000) -> Dict[str, Any]:
    """Copy a public file into an empty target. Interrupted loads must restart on a fresh database."""
    src = sqlite3.connect("file:%s?mode=ro" % public_db, uri=True)
    try:
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables - ALLOWED or audit_tables(src):
            raise ValueError("not a public export")
        for sql in DDL["common"] + DDL[backend.dialect] + PUBLIC_TABLES:
            backend.execute(sql)
        if backend.execute("SELECT COUNT(*) FROM records").fetchone()[0]:
            raise ValueError("the target database is not empty")
        counts = {}
        for table in TABLES:
            rows = [tuple(r) for r in src.execute("SELECT * FROM %s" % table)]
            if table == "dashboard_meta":
                rows = [r for r in rows if r[0] != "import_status"] + [("import_status", "loading")]
            counts[table] = len(rows)
            if not rows:
                continue
            columns = [c[1] for c in src.execute("PRAGMA table_info(%s)" % table)]
            for start in range(0, len(rows), rows_per_batch):
                backend.run_batch(multi_row_insert(table, columns, rows[start:start + rows_per_batch]))
        for table, n in counts.items():
            if backend.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0] != n:
                raise ValueError("loaded %s count differs; load into a fresh database again" % table)
        backend.run_batch([("UPDATE dashboard_meta SET value='complete' WHERE key='import_status'", ())])
        return {"result": "loaded", "tables": counts}
    finally:
        src.close()


def audit_tables(conn) -> int:
    """Nonzero when a public file still carries private columns' content."""
    return conn.execute("SELECT COUNT(*) FROM classifications WHERE evidence_quote<>'' OR entities<>'[]'").fetchone()[0] + \
        conn.execute("SELECT COUNT(*) FROM records WHERE row_sha256<>'' OR text_sha256 IS NOT NULL").fetchone()[0] + \
        conn.execute("SELECT COUNT(*) FROM record_state WHERE reason IS NOT NULL").fetchone()[0]

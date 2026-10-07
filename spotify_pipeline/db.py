"""SQLite-backed bounded-memory dedup and state.

Source rows, exact-text identity, per-configuration status and completed
classifications live here. No model results are seeded from real data.

Concurrency note: this is a single-writer local store. Close all writers
before re-ingesting so the atomic replace is not racing an open connection.
"""

import json
import os
import re
import sqlite3
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import cache_key, config_hash
from .contract import text_sha256
from .errors import PipelineError, StateError, ValidationError
from .schema import (
    EMPTY_REASON,
    raise_for_errors,
    validate_cache_reuse,
    validate_completed,
    validate_direct,
    validate_is_cached,
    validate_quarantine,
)

SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE records (
    row_index INTEGER PRIMARY KEY,
    review_id TEXT NOT NULL UNIQUE,
    review_text TEXT NOT NULL,
    review_rating TEXT NOT NULL,
    review_likes TEXT NOT NULL,
    app_version TEXT NOT NULL,
    review_timestamp TEXT NOT NULL,
    row_sha256 TEXT NOT NULL,
    text_sha256 TEXT,
    text_identity INTEGER,
    is_empty INTEGER NOT NULL
);

CREATE TABLE texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL UNIQUE,
    text_sha256 TEXT NOT NULL
);

CREATE TABLE record_state (
    row_index INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    cache_source_id TEXT,
    request_id TEXT,
    provenance TEXT,
    PRIMARY KEY (row_index, config_hash)
);

CREATE TABLE classifications (
    row_index INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    topic TEXT,
    intent TEXT,
    sentiment REAL,
    severity INTEGER,
    entities TEXT,
    evidence_quote TEXT,
    needs_review INTEGER,
    label_config TEXT,
    model TEXT,
    effort TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    cache_key TEXT,
    is_cached INTEGER NOT NULL DEFAULT 0,
    cache_source_id TEXT,
    request_id TEXT,
    provenance TEXT,
    PRIMARY KEY (row_index, config_hash)
);

CREATE INDEX idx_state_status ON record_state(config_hash, status);
CREATE INDEX idx_class_cachekey ON classifications(cache_key);
CREATE INDEX idx_records_text_identity ON records(text_identity);
"""

MAX_BATCH = 50
SOURCE_IDENTITY_KEYS = ("review_id", "source_sha256", "review_text", "config_hash")

_CLASSIFICATION_COLUMNS = (
    "topic",
    "intent",
    "sentiment",
    "severity",
    "entities",
    "evidence_quote",
    "needs_review",
    "label_config",
    "model",
    "effort",
    "prompt_version",
    "schema_version",
    "cache_key",
    "is_cached",
    "cache_source_id",
    "request_id",
    "provenance",
)

META_KEYS = (
    "source_basename",
    "file_sha256",
    "parsed_rows_sha256",
    "source_bytes",
    "contract_version",
)


def _readonly_uri(path: str) -> str:
    return "file:%s?mode=ro" % urllib.parse.quote(os.path.abspath(path))


_CONFIG_HASH_RE = re.compile(r"[0-9a-fA-F]{64}")


def _require_config_hash(value: Any) -> str:
    if not isinstance(value, str) or not _CONFIG_HASH_RE.fullmatch(value):
        raise ValidationError("configuration hash must be a 64-character hex string")
    return value


class Database:
    """A thin wrapper around one SQLite file."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def open_existing(cls, path: str) -> "Database":
        """Open a recognized database read-only without creating a file."""
        if not os.path.exists(path):
            raise PipelineError("database not found: %s" % path)
        try:
            conn = sqlite3.connect(_readonly_uri(path), uri=True)
        except sqlite3.Error as exc:
            raise StateError("cannot open database: %s" % exc) from exc
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("SELECT value FROM meta WHERE key = 'file_sha256'").fetchone()
        except sqlite3.Error as exc:
            conn.close()
            raise StateError("not a recognized pipeline database: %s" % path) from exc
        instance = cls.__new__(cls)
        instance.path = path
        instance.conn = conn
        return instance

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def initialize(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- meta -------------------------------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value)
        )
        self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else row["value"]

    def identity(self) -> Dict[str, Optional[str]]:
        return {key: self.get_meta(key) for key in META_KEYS}

    # -- source rows ------------------------------------------------------

    def insert_records(self, records: Iterable[Dict[str, Any]], batch_size: int = 1000) -> int:
        """Insert source records in batches. Duplicate IDs fail the whole call."""
        cursor = self.conn.cursor()
        count = 0
        try:
            for record in records:
                fields = record["fields"]
                text = fields[1]
                empty = 1 if record["is_empty"] else 0
                text_id = None
                t_hash = None
                if not empty:
                    t_hash = text_sha256(text)
                    found = cursor.execute(
                        "SELECT id FROM texts WHERE text = ?", (text,)
                    ).fetchone()
                    if found is None:
                        cursor.execute(
                            "INSERT INTO texts(text, text_sha256) VALUES(?, ?)",
                            (text, t_hash),
                        )
                        text_id = cursor.lastrowid
                    else:
                        text_id = found["id"]
                try:
                    cursor.execute(
                        """
                        INSERT INTO records(
                            row_index, review_id, review_text, review_rating,
                            review_likes, app_version, review_timestamp,
                            row_sha256, text_sha256, text_identity, is_empty
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record["row_index"],
                            fields[0],
                            fields[1],
                            fields[2],
                            fields[3],
                            fields[4],
                            fields[5],
                            record["row_sha256"],
                            t_hash,
                            text_id,
                            empty,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValidationError(
                        "duplicate review_id at data row %d: %r"
                        % (record["row_index"], fields[0])
                    ) from exc
                count += 1
                if count % batch_size == 0:
                    self.conn.commit()
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return count

    def count_records(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"]

    def count_distinct_texts(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM texts").fetchone()["n"]

    def get_record(self, row_index: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM records WHERE row_index = ?", (row_index,)
        ).fetchone()
        return None if row is None else dict(row)

    def get_record_by_review_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM records WHERE review_id = ?", (review_id,)
        ).fetchone()
        return None if row is None else dict(row)

    def all_records(self) -> Iterable[Dict[str, Any]]:
        for row in self.conn.execute("SELECT * FROM records ORDER BY row_index"):
            yield dict(row)

    # -- state ------------------------------------------------------------

    def get_state(self, row_index: int, config_hash_value: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM record_state WHERE row_index = ? AND config_hash = ?",
            (row_index, config_hash_value),
        ).fetchone()
        return None if row is None else dict(row)

    def effective_status(self, row_index: int, config_hash_value: str) -> str:
        record = self.get_record(row_index)
        if record is None:
            raise StateError("unknown row_index %d" % row_index)
        if record["is_empty"]:
            return "quarantined"
        state = self.get_state(row_index, config_hash_value)
        if state is None:
            return "pending"
        return state["status"]

    def effective_reason(self, row_index: int, config_hash_value: str) -> Optional[str]:
        """Return the explicit quarantine reason, including intrinsic empties."""
        record = self.get_record(row_index)
        if record is None:
            raise StateError("unknown row_index %d" % row_index)
        if record["is_empty"]:
            return EMPTY_REASON
        state = self.get_state(row_index, config_hash_value)
        if state is None or state["status"] != "quarantined":
            return None
        return state["reason"]

    def status_counts(self, config_hash_value: Optional[str] = None) -> Dict[str, int]:
        """Counts for one configuration.

        Without a configuration this returns unconfigured-source counts: the
        empty/nonempty split only, with no completed work and no cross-config
        total.
        """
        total = self.count_records()
        empty = self.conn.execute(
            "SELECT COUNT(*) AS n FROM records WHERE is_empty = 1"
        ).fetchone()["n"]
        completed = 0
        extra_quarantine = 0
        if config_hash_value is not None:
            completed = self.conn.execute(
                "SELECT COUNT(*) AS n FROM record_state WHERE config_hash = ? AND status = 'completed'",
                (config_hash_value,),
            ).fetchone()["n"]
            extra_quarantine = self.conn.execute(
                """
                SELECT COUNT(*) AS n FROM record_state rs
                JOIN records r ON r.row_index = rs.row_index
                WHERE rs.config_hash = ? AND rs.status = 'quarantined' AND r.is_empty = 0
                """,
                (config_hash_value,),
            ).fetchone()["n"]
        quarantined = empty + extra_quarantine
        pending = total - completed - quarantined
        return {
            "records": total,
            "completed": completed,
            "quarantined": quarantined,
            "pending": pending,
            "empty_review_text": empty,
            "configured": config_hash_value is not None,
        }

    def quarantine(self, row_index: int, config_hash_value: str, reason: str) -> None:
        """Quarantine one nonempty row. Completed state is immutable."""
        config_hash_value = _require_config_hash(config_hash_value)
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("quarantine reason is required")
        record = self.get_record(row_index)
        if record is None:
            raise StateError("unknown row_index %d" % row_index)

        if record["is_empty"]:
            if reason != EMPTY_REASON:
                raise ValidationError(
                    "empty source text may only be quarantined as %r" % EMPTY_REASON
                )
            return

        if reason == EMPTY_REASON:
            raise ValidationError("empty_review_text requires empty source text")

        existing = self.get_state(row_index, config_hash_value)
        if existing is not None and existing["status"] == "completed":
            raise StateError("completed state is immutable for the same configuration")

        view = {
            "status": "quarantined",
            "review_id": record["review_id"],
            "source_sha256": record["row_sha256"],
            "review_text": record["review_text"],
            "reason": reason,
        }
        raise_for_errors(validate_quarantine(view, source=record))
        self.conn.execute(
            """
            INSERT OR REPLACE INTO record_state(
                row_index, config_hash, status, reason,
                cache_source_id, request_id, provenance
            ) VALUES(?, ?, 'quarantined', ?, NULL, NULL, NULL)
            """,
            (row_index, config_hash_value, reason),
        )
        self.conn.commit()

    # -- classifications --------------------------------------------------

    def get_classification(self, row_index: int, config_hash_value: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM classifications WHERE row_index = ? AND config_hash = ?",
            (row_index, config_hash_value),
        ).fetchone()
        return None if row is None else dict(row)

    def _record_completed_view(
        self, record: Dict[str, Any], item: Dict[str, Any], config_hash_value: str
    ) -> Dict[str, Any]:
        authoritative = {
            "status": "completed",
            "review_id": record["review_id"],
            "source_sha256": record["row_sha256"],
            "review_text": record["review_text"],
            "config_hash": config_hash_value,
        }
        for key in SOURCE_IDENTITY_KEYS:
            if key in item and item[key] != authoritative[key]:
                raise ValidationError(
                    "%s must match the stored source/configuration" % key
                )
        view = dict(authoritative)
        for key, value in item.items():
            if key in SOURCE_IDENTITY_KEYS:
                continue
            view[key] = value
        supplied = view.get("label_config")
        if supplied is None or supplied == "":
            view["label_config"] = config_hash_value
        elif supplied != config_hash_value:
            raise ValidationError(
                "label_config must equal the computed configuration hash"
            )
        return view

    def _original_view(self, original: Dict[str, Any], original_class: Dict[str, Any], cfg_hash: str) -> Dict[str, Any]:
        return {
            "status": "completed",
            "review_id": original["review_id"],
            "review_text": original["review_text"],
            "config_hash": cfg_hash,
            "topic": original_class.get("topic"),
            "intent": original_class.get("intent"),
            "sentiment": original_class.get("sentiment"),
            "severity": original_class.get("severity"),
            "entities": decode_entities(original_class.get("entities")),
            "evidence_quote": original_class.get("evidence_quote"),
            "needs_review": bool(original_class.get("needs_review")),
            "label_config": original_class.get("label_config"),
            "request_id": original_class.get("request_id"),
            "provenance": original_class.get("provenance"),
            "is_cached": bool(original_class.get("is_cached")),
            "cache_source_id": original_class.get("cache_source_id"),
        }

    def _validate_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(item, dict) or type(item.get("row_index")) is not int or item["row_index"] < 0:
            raise ValidationError("completed item requires a nonnegative integer row_index")
        record = self.get_record(item["row_index"])
        if record is None:
            raise StateError("unknown row_index %r" % item.get("row_index"))
        cfg = {
            "model": item.get("model"),
            "effort": item.get("effort"),
            "prompt_version": item.get("prompt_version"),
            "schema_version": item.get("schema_version"),
        }
        cfg_hash = config_hash(cfg)
        view = self._record_completed_view(record, item, cfg_hash)

        cached_value = item.get("is_cached", False)
        is_cached = cached_value is True or (
            isinstance(cached_value, int) and not isinstance(cached_value, bool) and cached_value == 1
        )

        errors = validate_completed(view, source=record)
        errors.extend(validate_is_cached(cached_value))

        if is_cached:
            original = self.get_record_by_review_id(item.get("cache_source_id") or "")
            if original is None:
                raise ValidationError(
                    "cache_source_id %r does not reference a known review"
                    % item.get("cache_source_id")
                )
            original_state = self.get_state(original["row_index"], cfg_hash)
            if original_state is None or original_state["status"] != "completed":
                raise ValidationError(
                    "cache original %r is not currently completed for this configuration"
                    % item.get("cache_source_id")
                )
            original_class = self.get_classification(original["row_index"], cfg_hash)
            if original_class is None:
                raise ValidationError(
                    "cache original %r has no completed result for this configuration"
                    % item.get("cache_source_id")
                )
            original_view = self._original_view(original, original_class, cfg_hash)
            errors.extend(
                validate_cache_reuse(view, original_view, not original_view["is_cached"])
            )
        else:
            errors.extend(validate_direct(view))

        raise_for_errors(errors)
        return {"config_hash": cfg_hash, "view": view, "record": record, "is_cached": is_cached}

    def _classification_row(self, item: Dict[str, Any], cfg_hash: str, text: str) -> tuple:
        return (
            item["row_index"],
            cfg_hash,
            item.get("topic"),
            item.get("intent"),
            float(item["sentiment"]),
            int(item["severity"]),
            _encode_entities(item.get("entities")),
            item.get("evidence_quote"),
            1 if item.get("needs_review") else 0,
            item.get("label_config") or cfg_hash,
            item.get("model"),
            item.get("effort"),
            item.get("prompt_version"),
            item.get("schema_version"),
            cache_key(
                {
                    "model": item.get("model"),
                    "effort": item.get("effort"),
                    "prompt_version": item.get("prompt_version"),
                    "schema_version": item.get("schema_version"),
                },
                text,
            ),
            1 if item.get("is_cached") else 0,
            item.get("cache_source_id"),
            item.get("request_id"),
            item.get("provenance"),
        )

    def _rows_equal(self, existing: Dict[str, Any], item: Dict[str, Any], cfg_hash: str, text: str) -> bool:
        expected = self._classification_row(item, cfg_hash, text)
        columns = ("row_index", "config_hash") + _CLASSIFICATION_COLUMNS
        for column, value in zip(columns, expected):
            if existing.get(column) != value:
                return False
        return True

    def save_completed_batch(
        self, items: List[Dict[str, Any]], max_batch: int = MAX_BATCH
    ) -> Dict[str, int]:
        """Validate and save up to ``max_batch`` completed records atomically.

        All items are validated before any write. Duplicate ``(row_index,
        config)`` pairs inside one batch are rejected. Existing identical
        results are idempotent; conflicting writes fail explicitly.
        """
        if not isinstance(items, list):
            raise ValidationError("batch must be a list")
        if isinstance(max_batch, bool) or not isinstance(max_batch, int) or not (1 <= max_batch <= MAX_BATCH):
            raise ValidationError(
                "max_batch must be an integer between 1 and %d" % MAX_BATCH
            )
        if len(items) > max_batch:
            raise ValidationError(
                "batch size %d exceeds maximum %d" % (len(items), max_batch)
            )

        validated = [self._validate_item(item) for item in items]

        seen: Dict[Tuple[int, str], int] = {}
        for position, (item, checked) in enumerate(zip(items, validated)):
            key = (item["row_index"], checked["config_hash"])
            if key in seen:
                raise ValidationError(
                    "duplicate (row_index, config) in batch: row_index %d at positions %d and %d"
                    % (key[0], seen[key], position)
                )
            seen[key] = position

        skipped = 0
        for item, checked in zip(items, validated):
            cfg_hash = checked["config_hash"]
            text = checked["record"]["review_text"]
            existing = self.get_classification(item["row_index"], cfg_hash)
            if existing is not None:
                if self._rows_equal(existing, item, cfg_hash, text):
                    skipped += 1
                    continue
                raise StateError(
                    "conflicting completed write for row_index %d and configuration"
                    % item["row_index"]
                )

        cursor = self.conn.cursor()
        try:
            inserted = 0
            for item, checked in zip(items, validated):
                cfg_hash = checked["config_hash"]
                if self.get_classification(item["row_index"], cfg_hash) is not None:
                    continue
                text = checked["record"]["review_text"]
                cursor.execute(
                    """
                    INSERT INTO classifications(
                        row_index, config_hash, topic, intent, sentiment,
                        severity, entities, evidence_quote, needs_review,
                        label_config, model, effort, prompt_version,
                        schema_version, cache_key, is_cached, cache_source_id,
                        request_id, provenance
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._classification_row(item, cfg_hash, text),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO record_state(
                        row_index, config_hash, status, reason,
                        cache_source_id, request_id, provenance
                    ) VALUES(?, ?, 'completed', NULL, ?, ?, ?)
                    """,
                    (
                        item["row_index"],
                        cfg_hash,
                        item.get("cache_source_id"),
                        item.get("request_id"),
                        item.get("provenance"),
                    ),
                )
                inserted += 1
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {"inserted": inserted, "skipped": skipped}

    def completed_ids(self, config_hash_value: str) -> List[str]:
        rows = self.conn.execute(
            """
            SELECT r.review_id AS review_id
            FROM record_state rs
            JOIN records r ON r.row_index = rs.row_index
            WHERE rs.config_hash = ? AND rs.status = 'completed'
            ORDER BY r.review_id
            """,
            (config_hash_value,),
        ).fetchall()
        return [row["review_id"] for row in rows]

    def completed_row_indices(self, config_hash_value: str) -> List[int]:
        rows = self.conn.execute(
            """
            SELECT row_index FROM record_state
            WHERE config_hash = ? AND status = 'completed'
            ORDER BY row_index
            """,
            (config_hash_value,),
        ).fetchall()
        return [row["row_index"] for row in rows]

    def pending_row_indices(self, config_hash_value: str) -> List[int]:
        rows = self.conn.execute(
            """
            SELECT r.row_index AS row_index
            FROM records r
            LEFT JOIN record_state rs
              ON rs.row_index = r.row_index AND rs.config_hash = ?
            WHERE r.is_empty = 0
              AND (rs.status IS NULL OR rs.status = 'pending')
            ORDER BY r.row_index
            """,
            (config_hash_value,),
        ).fetchall()
        return [row["row_index"] for row in rows]


def _encode_entities(entities: Any) -> str:
    return json.dumps(entities if entities is not None else [], ensure_ascii=False)


def decode_entities(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return json.loads(value)


def read_source_identity(path: str) -> Optional[Dict[str, str]]:
    """Read source identity from an existing DB without modifying it."""
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(_readonly_uri(path), uri=True)
    except sqlite3.Error as exc:
        raise StateError("cannot open existing database: %s" % exc) from exc
    try:
        try:
            rows = conn.execute(
                "SELECT key, value FROM meta WHERE key IN (%s)"
                % ", ".join("'%s'" % key for key in META_KEYS)
            ).fetchall()
        except sqlite3.Error as exc:
            raise StateError("existing database is not a pipeline database") from exc
        return {key: value for key, value in rows}
    finally:
        conn.close()


def copy_state_from(
    old_path: str, new_db: "Database", expected_file_sha: str, chunk: int = 1000
) -> Dict[str, int]:
    """Copy per-configuration state from an old database.

    Uses a read-only old connection and bounded ``fetchmany`` chunks. The old
    source identity is validated before any copy.
    """
    old = sqlite3.connect(_readonly_uri(old_path), uri=True)
    try:
        old_sha = old.execute(
            "SELECT value FROM meta WHERE key = 'file_sha256'"
        ).fetchone()
        if old_sha is None or old_sha[0] != expected_file_sha:
            raise StateError("old database source identity does not match; refusing to copy state")
        old_version = old.execute(
            "SELECT value FROM meta WHERE key = 'contract_version'"
        ).fetchone()
        new_version = new_db.get_meta("contract_version")
        if old_version is not None and new_version is not None and old_version[0] != new_version:
            raise StateError("old database schema version does not match; refusing to copy state")

        new_cursor = new_db.conn.cursor()
        state_columns = (
            "row_index, config_hash, status, reason, cache_source_id, request_id, provenance"
        )
        class_columns = ", ".join(("row_index", "config_hash") + _CLASSIFICATION_COLUMNS)
        copied_state = 0
        copied_class = 0
        try:
            source_cursor = old.execute("SELECT %s FROM record_state" % state_columns)
            while True:
                rows = source_cursor.fetchmany(chunk)
                if not rows:
                    break
                new_cursor.executemany(
                    """
                    INSERT OR REPLACE INTO record_state(
                        row_index, config_hash, status, reason,
                        cache_source_id, request_id, provenance
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                copied_state += len(rows)

            source_cursor = old.execute("SELECT %s FROM classifications" % class_columns)
            placeholders = ", ".join(["?"] * (2 + len(_CLASSIFICATION_COLUMNS)))
            while True:
                rows = source_cursor.fetchmany(chunk)
                if not rows:
                    break
                new_cursor.executemany(
                    """
                    INSERT OR REPLACE INTO classifications(
                        row_index, config_hash, %s
                    ) VALUES(%s)
                    """
                    % (", ".join(_CLASSIFICATION_COLUMNS), placeholders),
                    rows,
                )
                copied_class += len(rows)
            new_db.conn.commit()
        except Exception:
            new_db.conn.rollback()
            raise
        return {"state_rows": copied_state, "classification_rows": copied_class}
    finally:
        old.close()

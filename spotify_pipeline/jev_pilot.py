"""Persistent, bounded Jev cost-sample runner. Importing this sends no requests."""

import json
import os
import sqlite3
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable

from .config import config_hash
from .contract import text_sha256
from .errors import StateError, ValidationError
from .jev import MAX_ATTEMPTS, MODEL, JevHTTPError, build_request, label_config, parse_response, post_systemone

NANODOLLARS_PER_INPUT_TOKEN = 42  # USD 0.042 / 1,000,000; reverify before use.
MAX_INPUT_TOKENS = 64000  # published context maximum; includes state and questions.
RESERVATION_NANODOLLARS = MAX_INPUT_TOKENS * NANODOLLARS_PER_INPUT_TOKEN
MAX_APPROVABLE_CAP = Decimal("0.60")

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE attempts (
  id INTEGER PRIMARY KEY, review_id TEXT NOT NULL, number INTEGER NOT NULL,
  status TEXT NOT NULL, reserved_nusd INTEGER NOT NULL, charged_nusd INTEGER,
  input_tokens INTEGER, output_tokens INTEGER, elapsed_seconds REAL,
  model TEXT, error_class TEXT
);
CREATE TABLE results (
  review_id TEXT PRIMARY KEY, review_text TEXT NOT NULL, text_sha256 TEXT NOT NULL,
  source_sha256 TEXT NOT NULL, config_hash TEXT NOT NULL, label_json TEXT NOT NULL,
  cache_source_id TEXT, provenance TEXT NOT NULL, attempt_id INTEGER,
  FOREIGN KEY(attempt_id) REFERENCES attempts(id)
);
CREATE INDEX idx_results_text ON results(text_sha256, config_hash);
CREATE TABLE evidence (
  review_id TEXT PRIMARY KEY, entities_json TEXT NOT NULL, evidence_quote TEXT NOT NULL,
  model TEXT NOT NULL, prompt_version TEXT NOT NULL, elapsed_seconds REAL NOT NULL,
  cache_source_id TEXT, FOREIGN KEY(review_id) REFERENCES results(review_id)
);
"""


def cap_to_nusd(cap_usd: Decimal) -> int:
    if not cap_usd.is_finite() or cap_usd <= 0 or cap_usd > MAX_APPROVABLE_CAP:
        raise ValidationError("pilot cap must be positive and at most USD 0.60")
    nanos = cap_usd * Decimal(1000000000)
    if nanos != nanos.to_integral_value():
        raise ValidationError("pilot cap has sub-nanodollar precision")
    return int(nanos)


class PilotLedger:
    """Local SQLite journal. A crashed reservation remains fully charged."""

    def __init__(self, path: str, source_sha256: str, cap_usd: Decimal):
        self.path = path
        self.cap_nusd = cap_to_nusd(cap_usd)
        self.config_hash = config_hash(label_config())
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            raise ValidationError("source SHA-256 is required")
        if os.path.exists(path):
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            expected = {"source_sha256": source_sha256, "config_hash": self.config_hash,
                        "cap_nusd": str(self.cap_nusd), "model": MODEL}
            actual = dict(self.conn.execute("SELECT key, value FROM meta"))
            if actual != expected:
                self.conn.close()
                raise StateError("pilot ledger source, configuration, model or cap differs")
        else:
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            try:
                self.conn.executescript(SCHEMA)
                self.conn.executemany("INSERT INTO meta(key,value) VALUES (?,?)", (
                    ("source_sha256", source_sha256), ("config_hash", self.config_hash),
                    ("cap_nusd", str(self.cap_nusd)), ("model", MODEL)))
                self.conn.commit()
            except Exception:
                self.conn.close()
                raise

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "PilotLedger":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def charged_or_reserved_nusd(self) -> int:
        return int(self.conn.execute(
            "SELECT COALESCE(SUM(COALESCE(charged_nusd,reserved_nusd)),0) FROM attempts"
        ).fetchone()[0])

    def reserve(self, review_id: str, number: int) -> int:
        """Commit worst-case spend before network I/O. One writer only."""
        if not review_id or number not in range(1, MAX_ATTEMPTS + 1):
            raise ValidationError("invalid review ID or retry number")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            spent = self.charged_or_reserved_nusd()
            if spent + RESERVATION_NANODOLLARS > self.cap_nusd:
                raise StateError("pilot spending cap would be exceeded")
            cursor = self.conn.execute(
                "INSERT INTO attempts(review_id,number,status,reserved_nusd) VALUES (?,?,'reserved',?)",
                (review_id, number, RESERVATION_NANODOLLARS))
            self.conn.commit()
            return cursor.lastrowid
        except Exception:
            self.conn.rollback()
            raise

    def settle(self, attempt_id: int, input_tokens: int, output_tokens: int,
               elapsed_seconds: float, model: str) -> None:
        if (type(input_tokens) is not int or input_tokens < 0 or input_tokens > MAX_INPUT_TOKENS
                or type(output_tokens) is not int or output_tokens < 0 or model != MODEL):
            raise ValidationError("invalid measured Jev usage or model")
        cursor = self.conn.execute(
            "UPDATE attempts SET status='settled',charged_nusd=?,input_tokens=?,"
            "output_tokens=?,elapsed_seconds=?,model=? WHERE id=? AND status='reserved'",
            (input_tokens * NANODOLLARS_PER_INPUT_TOKEN, input_tokens, output_tokens,
             elapsed_seconds, model, attempt_id))
        if cursor.rowcount != 1:
            self.conn.rollback()
            raise StateError("attempt is not reserved")
        self.conn.commit()

    def uncertain(self, attempt_id: int, elapsed_seconds: float, error_class: str) -> None:
        cursor = self.conn.execute(
            "UPDATE attempts SET status='uncertain',charged_nusd=reserved_nusd,"
            "elapsed_seconds=?,error_class=? WHERE id=? AND status='reserved'",
            (elapsed_seconds, error_class, attempt_id))
        if cursor.rowcount != 1:
            self.conn.rollback()
            raise StateError("attempt is not reserved")
        self.conn.commit()

    def existing(self, review_id: str, review_text: str, source_sha256: str) -> bool:
        row = self.conn.execute("SELECT review_text,source_sha256,config_hash FROM results WHERE review_id=?",
                                (review_id,)).fetchone()
        if row is None:
            return False
        if (row["review_text"], row["source_sha256"], row["config_hash"]) != (
                review_text, source_sha256, self.config_hash):
            raise StateError("saved review identity differs from current source")
        return True

    def cached_original(self, review_text: str):
        """Hash narrows lookup; exact text and direct provenance prove reuse."""
        return self.conn.execute(
            "SELECT * FROM results WHERE text_sha256=? AND config_hash=? "
            "AND review_text=? AND provenance='jev_direct' ORDER BY rowid LIMIT 1",
            (text_sha256(review_text), self.config_hash, review_text)).fetchone()

    def save_result(self, review_id: str, review_text: str, source_sha256: str,
                    label_json: str, provenance: str, cache_source_id=None, attempt_id=None) -> None:
        if provenance not in ("jev_direct", "jev_exact_text_cache"):
            raise ValidationError("invalid pilot provenance")
        if provenance == "jev_direct" and (attempt_id is None or cache_source_id is not None):
            raise ValidationError("direct result requires an attempt and no cache source")
        if provenance == "jev_exact_text_cache" and (not cache_source_id or attempt_id is not None):
            raise ValidationError("cache result requires a direct original")
        self.conn.execute(
            "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
            (review_id, review_text, text_sha256(review_text), source_sha256,
             self.config_hash, label_json, cache_source_id, provenance, attempt_id))
        self.conn.commit()

    def summary(self) -> Dict[str, Any]:
        attempts = dict(self.conn.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status"))
        results = dict(self.conn.execute("SELECT provenance,COUNT(*) FROM results GROUP BY provenance"))
        usage = self.conn.execute("SELECT SUM(input_tokens),SUM(output_tokens),SUM(elapsed_seconds) "
                                  "FROM attempts WHERE status='settled'").fetchone()
        evidence_count = self.conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        return {"status": "offline_replay", "model": MODEL, "source_sha256":
                dict(self.conn.execute("SELECT key,value FROM meta"))["source_sha256"],
                "cap_usd": str(Decimal(self.cap_nusd) / Decimal(1000000000)),
                "charged_or_reserved_usd": str(Decimal(self.charged_or_reserved_nusd()) / Decimal(1000000000)),
                "attempts": attempts, "results": results,
                "evidence_records": evidence_count,
                "measured_input_tokens": usage[0], "measured_output_tokens": usage[1],
                "measured_attempt_seconds": usage[2]}

    def missing_evidence(self):
        return self.conn.execute(
            "SELECT r.review_id,r.review_text,r.label_json,r.cache_source_id "
            "FROM results r LEFT JOIN evidence e ON e.review_id=r.review_id "
            "WHERE e.review_id IS NULL ORDER BY r.rowid"
        )

    def get_evidence(self, review_id: str):
        return self.conn.execute("SELECT * FROM evidence WHERE review_id=?", (review_id,)).fetchone()

    def save_evidence(self, review_id: str, evidence: Dict[str, Any], model: str,
                      prompt_version: str, elapsed_seconds: float, cache_source_id=None) -> None:
        from .codex_evidence import validate_evidence
        row = self.conn.execute("SELECT review_text,cache_source_id FROM results WHERE review_id=?",
                                (review_id,)).fetchone()
        if row is None:
            raise StateError("evidence review has no Jev labels")
        checked = validate_evidence(row["review_text"], evidence)
        if cache_source_id is not None:
            if row["cache_source_id"] != cache_source_id or self.get_evidence(cache_source_id) is None:
                raise StateError("evidence cache must reference saved direct evidence")
        self.conn.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?)",
                          (review_id, json.dumps(checked["entities"]), checked["evidence_quote"],
                           model, prompt_version, elapsed_seconds, cache_source_id))
        self.conn.commit()


def run_reviews(rows: Iterable[Dict[str, str]], ledger: PilotLedger, api_key: str,
                transport: Callable = post_systemone, sleep: Callable = time.sleep) -> Dict[str, Any]:
    """Live core. Caller must validate the pinned cost file and approve paid use."""
    if not api_key:
        raise ValidationError("TypeSafe API key is missing")
    processed = 0
    for row in rows:
        review_id, review_text, source_sha = row["review_id"], row["review_text"], row["source_sha256"]
        if ledger.existing(review_id, review_text, source_sha):
            continue
        original = ledger.cached_original(review_text)
        if original is not None:
            ledger.save_result(review_id, review_text, source_sha, original["label_json"],
                               "jev_exact_text_cache", cache_source_id=original["review_id"])
            processed += 1
            continue
        request = build_request(review_text)
        for number in range(1, MAX_ATTEMPTS + 1):
            attempt_id = ledger.reserve(review_id, number)
            started = time.monotonic()
            try:
                payload = transport(request, api_key)
                labels = parse_response(payload)
                elapsed = time.monotonic() - started
                ledger.settle(attempt_id, labels.input_tokens, labels.output_tokens, elapsed, labels.model)
                ledger.save_result(review_id, review_text, source_sha,
                                   json.dumps(labels.__dict__, sort_keys=True),
                                   "jev_direct", attempt_id=attempt_id)
                processed += 1
                break
            except Exception as error:
                elapsed = time.monotonic() - started
                # If usage is unavailable or persistence failed, keep the full
                # pre-call reservation. Never turn unknown billing into zero.
                status = ledger.conn.execute("SELECT status FROM attempts WHERE id=?", (attempt_id,)).fetchone()[0]
                if status == "reserved":
                    ledger.uncertain(attempt_id, elapsed, type(error).__name__)
                if (isinstance(error, JevHTTPError) and number < MAX_ATTEMPTS
                        and error.status in (429, 500, 502, 503, 504)):
                    sleep(error.retry_after if error.retry_after is not None else 1.0)
                    continue
                raise
    report = ledger.summary()
    report["processed_this_run"] = processed
    return report

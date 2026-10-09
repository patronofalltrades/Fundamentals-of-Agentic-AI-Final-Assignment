"""One atomic project cost ledger for future OpenRouter and Jev requests.

Historical ledgers are read only and frozen by state digest. Every new paid
worker must reserve here before network I/O. An interrupted reservation holds
its full amount until a separate, evidence-backed reconciliation.
"""

import hashlib
import fcntl
import json
import os
import sqlite3
from contextlib import closing

CAPS = {"openrouter": 5_000_000_000, "jev": 5_000_000_000}
PREVIOUS_CAPS = {"openrouter": 5_000_000_000, "jev": 600_000_000}
MAX_GLOBAL_INFLIGHT = 8
MAX_CONFIGURED_GLOBAL_INFLIGHT = 12
SOURCES = ("benchmark", "batch_v1", "batch_v2", "jev_checkpoint")


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def _exposure(rows):
    total = 0
    for _, status, reserved, charged in rows:
        if type(reserved) is not int or reserved < 0 or charged is not None and (
                type(charged) is not int or charged < 0):
            raise ValueError("historical cost row is invalid")
        total += charged if status == "succeeded" and charged is not None else max(
            reserved, charged or 0)
    return total


def snapshot(name, path):
    """Return budget, amount and digest without reading text or credentials."""
    if name not in SOURCES or not os.path.isfile(path):
        raise ValueError("required historical cost ledger is missing")
    with closing(sqlite3.connect("file:" + os.path.abspath(path) + "?mode=ro", uri=True)) as db:
        if name == "benchmark":
            rows = list(db.execute("SELECT id,status,reserved_nusd,charged_nusd FROM calls ORDER BY id"))
            return "openrouter", _exposure(rows), _digest(rows)
        if name.startswith("batch_"):
            rows = list(db.execute("SELECT id,status,reserved_nusd,charged_nusd FROM batches ORDER BY id"))
            if len(rows) != 1 or rows[0][1] != "succeeded":
                raise ValueError("completed canary ledger required")
            return "openrouter", _exposure(rows), _digest(rows)
        rows = list(db.execute("SELECT id,status,reserved_nusd,charged_nusd FROM attempts ORDER BY id"))
        seed = list(db.execute("SELECT v1_charge_nusd FROM checkpoint_seed"))
        if len(seed) != 1 or type(seed[0][0]) is not int or seed[0][0] < 0:
            raise ValueError("Jev checkpoint seed charge missing")
        if any(type(reserved) is not int or reserved < 0 or charged is not None and (
                type(charged) is not int or charged < 0) for _, _, reserved, charged in rows):
            raise ValueError("historical Jev cost row is invalid")
        amount = sum(charged if status == "settled" and charged is not None else max(
            reserved, charged or 0) for _, status, reserved, charged in rows)
        return "jev", amount + seed[0][0], _digest([rows, seed])


class ProjectBudget:
    def __init__(self, path, legacy_paths, max_global_inflight=MAX_GLOBAL_INFLIGHT):
        if max_global_inflight is not None and (type(max_global_inflight) is not int or
                not 1 <= max_global_inflight <= MAX_CONFIGURED_GLOBAL_INFLIGHT):
            raise ValueError("global in-flight limit must be an integer from 1 through 12")
        if set(legacy_paths) != set(SOURCES):
            raise ValueError("all four historical cost ledgers are required")
        self.legacy_paths = dict(legacy_paths)
        self.snapshots = {name: snapshot(name, self.legacy_paths[name]) for name in SOURCES}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # All current budget users hold a shared lease for their full lifetime.
        # Reconfiguration needs its exclusive form, so another dispatcher
        # cannot start between the zero-reservation check and the update.
        self.lease = open(path + "-admission.lock", "a+b")
        fcntl.flock(self.lease.fileno(), fcntl.LOCK_SH)
        self.db = sqlite3.connect(path, timeout=30, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("CREATE TABLE IF NOT EXISTS caps(budget TEXT PRIMARY KEY, cap_nusd INTEGER NOT NULL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS legacy_sources(
            name TEXT PRIMARY KEY, budget TEXT NOT NULL, exposure_nusd INTEGER NOT NULL,
            state_sha TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS reservations(
            request_key TEXT PRIMARY KEY, budget TEXT NOT NULL, status TEXT NOT NULL,
            reserved_nusd INTEGER NOT NULL, charged_nusd INTEGER,
            created_utc TEXT NOT NULL DEFAULT (datetime('now')),
            settled_utc TEXT)""")
        self.db.execute("CREATE TABLE IF NOT EXISTS coordination(key TEXT PRIMARY KEY,value INTEGER NOT NULL)")
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            saved_limit = self.db.execute("SELECT value FROM coordination WHERE key='global_inflight_limit'").fetchone()
            if saved_limit is None:
                # Existing ledgers migrate to the conservative eight-slot
                # ceiling, even if this caller asked for more.
                self.db.execute("INSERT INTO coordination VALUES ('global_inflight_limit',?)",
                    (MAX_GLOBAL_INFLIGHT,))
                saved_limit = (MAX_GLOBAL_INFLIGHT,)
            if type(saved_limit[0]) is not int or not 1 <= saved_limit[0] <= MAX_CONFIGURED_GLOBAL_INFLIGHT:
                raise ValueError("saved global paid-request limit is invalid")
            if max_global_inflight is not None and saved_limit[0] != max_global_inflight:
                raise ValueError("global paid-request limit differs from shared ledger")
            self.max_global_inflight = saved_limit[0]
            current_caps = dict(self.db.execute("SELECT budget,cap_nusd FROM caps"))
            if current_caps and current_caps not in (CAPS, PREVIOUS_CAPS):
                raise ValueError("project budget caps changed")
            if not current_caps:
                self.db.executemany("INSERT INTO caps VALUES (?,?)", CAPS.items())
            saved = {row[0]: tuple(row[1:]) for row in self.db.execute(
                "SELECT name,budget,exposure_nusd,state_sha FROM legacy_sources")}
            if saved and saved != self.snapshots:
                raise ValueError("historical cost ledger changed or omitted")
            if not saved:
                self.db.executemany("INSERT INTO legacy_sources VALUES (?,?,?,?)",
                    ((name,) + self.snapshots[name] for name in SOURCES))
            if current_caps == PREVIOUS_CAPS:
                # User-approved cumulative Jev increase. Preserve every charge,
                # hold, source digest, and the unchanged OpenRouter cap.
                changed = self.db.execute("UPDATE caps SET cap_nusd=? WHERE budget='jev' AND cap_nusd=?",
                    (CAPS["jev"], PREVIOUS_CAPS["jev"])).rowcount
                if changed != 1:
                    raise ValueError("approved Jev cap migration did not update one row")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            self.lease.close()
            raise

    def close(self):
        self.db.close()
        self.lease.close()

    def configure_global_inflight(self, new_limit):
        """Change the shared ceiling only with no active work or other users."""
        if type(new_limit) is not int or not 1 <= new_limit <= MAX_CONFIGURED_GLOBAL_INFLIGHT:
            raise ValueError("global in-flight limit must be an integer from 1 through 12")
        try:
            fcntl.flock(self.lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another budget user is connected; cannot change global limit") from exc
        try:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                if self.db.execute("SELECT 1 FROM reservations WHERE status='reserved' LIMIT 1").fetchone():
                    raise ValueError("active reservations prevent global limit change")
                saved = self.db.execute("SELECT value FROM coordination WHERE key='global_inflight_limit'").fetchone()
                if saved != (self.max_global_inflight,):
                    raise ValueError("shared global limit changed unexpectedly")
                self.db.execute("UPDATE coordination SET value=? WHERE key='global_inflight_limit'",
                    (new_limit,))
                self.db.commit()
                self.max_global_inflight = new_limit
            except BaseException:
                self.db.rollback()
                raise
        finally:
            fcntl.flock(self.lease.fileno(), fcntl.LOCK_SH)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _check_sources(self):
        if {name: snapshot(name, self.legacy_paths[name]) for name in SOURCES} != self.snapshots:
            raise ValueError("historical cost ledger changed; no new call")

    def exposure(self, budget):
        if budget not in CAPS:
            raise ValueError("unknown budget")
        legacy = self.db.execute("SELECT COALESCE(SUM(exposure_nusd),0) FROM legacy_sources WHERE budget=?",
                                 (budget,)).fetchone()[0]
        future = self.db.execute("""SELECT COALESCE(SUM(CASE
            WHEN status IN ('succeeded','quarantined_metered') AND charged_nusd IS NOT NULL
            THEN charged_nusd
            ELSE MAX(reserved_nusd,COALESCE(charged_nusd,0)) END),0)
            FROM reservations WHERE budget=?""", (budget,)).fetchone()[0]
        return legacy + future

    def reserve(self, request_key, budget, amount_nusd, record=None):
        if not request_key or budget not in CAPS or type(amount_nusd) is not int or amount_nusd <= 0:
            raise ValueError("invalid cost reservation")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self._check_sources()
            if self.db.execute("SELECT 1 FROM reservations WHERE request_key=?", (request_key,)).fetchone():
                raise ValueError("request already reserved or settled; no duplicate call")
            if self.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0] >= self.max_global_inflight:
                raise ValueError("configured global paid-request limit is already in flight")
            if self.exposure(budget) + amount_nusd >= CAPS[budget]:
                raise ValueError("cumulative project cap would be reached")
            self.db.execute("INSERT INTO reservations(request_key,budget,status,reserved_nusd)"
                            " VALUES (?,?,'reserved',?)", (request_key, budget, amount_nusd))
            if record is not None:
                record(self.db)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def settle(self, request_key, status, charged_nusd, record=None):
        if status not in ("succeeded", "quarantined_metered") or type(charged_nusd) is not int or charged_nusd < 0:
            raise ValueError("settlement requires measured nonnegative charge")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT reserved_nusd,status FROM reservations WHERE request_key=?",
                                  (request_key,)).fetchone()
            if row is None or row[1] != "reserved" or charged_nusd > row[0]:
                raise ValueError("request not reserved or charge exceeds bound")
            self.db.execute("UPDATE reservations SET status=?,charged_nusd=?,settled_utc=datetime('now')"
                            " WHERE request_key=?", (status, charged_nusd, request_key))
            if record is not None:
                record(self.db)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def uncertain(self, request_key, record=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            changed = self.db.execute("UPDATE reservations SET status='uncertain'"
                " WHERE request_key=? AND status='reserved'", (request_key,)).rowcount
            if changed != 1:
                raise ValueError("only a reserved request can become uncertain")
            if record is not None:
                record(self.db)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

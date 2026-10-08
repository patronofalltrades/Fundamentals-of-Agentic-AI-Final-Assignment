"""Durable per-source-row label/evidence queue in the shared project ledger.

The cost reservation and request membership are committed in one SQLite
transaction. Saved results for all members of a batch commit with settlement.
"""

import hashlib
import json

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.config import config_hash
from spotify_pipeline.contract import SOURCE_FIELDS, row_sha256, text_sha256
from spotify_pipeline.jev import label_config


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


class CheckpointQueue:
    def __init__(self, budget, rows, source_sha, prefix_sha, seed_labels=None):
        self.budget = budget
        self.db = budget.db
        self.label_config_sha = config_hash(label_config())
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_meta(
            key TEXT PRIMARY KEY,value TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_rows(
            position INTEGER PRIMARY KEY,review_id TEXT NOT NULL UNIQUE,
            review_text TEXT NOT NULL,source_sha TEXT NOT NULL,text_sha TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_labels(
            review_id TEXT PRIMARY KEY,label_json TEXT NOT NULL,config_sha TEXT NOT NULL,
            provenance TEXT NOT NULL,cache_source_id TEXT,request_key TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_evidence(
            review_id TEXT PRIMARY KEY,entities_json TEXT NOT NULL,evidence_quote TEXT NOT NULL,
            config_sha TEXT NOT NULL,provenance TEXT NOT NULL,cache_source_id TEXT,
            request_key TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_quarantines(
            review_id TEXT PRIMARY KEY,source_sha TEXT NOT NULL,
            reason TEXT NOT NULL,request_key TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_requests(
            request_key TEXT PRIMARY KEY,stage TEXT NOT NULL,status TEXT NOT NULL,
            batch_limit INTEGER,config_sha TEXT NOT NULL,response_id TEXT,
            input_tokens INTEGER,output_tokens INTEGER,reasoning_tokens INTEGER,
            elapsed_seconds REAL,error_class TEXT,response_json TEXT)""")
        columns = {item[1] for item in self.db.execute("PRAGMA table_info(checkpoint_requests)")}
        if "response_json" not in columns:
            self.db.execute("ALTER TABLE checkpoint_requests ADD COLUMN response_json TEXT")
        self.db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_request_members(
            request_key TEXT NOT NULL,review_id TEXT NOT NULL,
            PRIMARY KEY(request_key,review_id))""")
        self.db.commit()
        identity = {"source_sha": source_sha, "prefix_sha": prefix_sha,
                    "rows": "5000", "label_config_sha": self.label_config_sha}
        normalized = []
        for position, row in enumerate(rows, 1):
            if row.get("source_position", position) != position:
                raise ValueError("checkpoint source order changed")
            text = row.get("review_text", row.get("text"))
            if not isinstance(text, str) or not text.strip():
                raise ValueError("checkpoint has empty review text")
            source_hash = row.get("source_sha256", row.get("source_sha"))
            if all(field in row for field in SOURCE_FIELDS):
                if row_sha256([row[field] for field in SOURCE_FIELDS]) != source_hash:
                    raise ValueError("checkpoint source row hash differs")
            if text_sha256(text) != row.get("text_sha256", row.get("text_sha")):
                raise ValueError("checkpoint text hash differs")
            normalized.append((position, row["review_id"], text, source_hash,
                               text_sha256(text)))
        if len(normalized) != 5000 or len({r[1] for r in normalized}) != 5000:
            raise ValueError("checkpoint requires 5000 distinct source IDs")
        saved_identity = dict(self.db.execute("SELECT key,value FROM checkpoint_meta"))
        saved_rows = list(self.db.execute("SELECT * FROM checkpoint_rows ORDER BY position"))
        if saved_identity and (saved_identity != identity or saved_rows != normalized):
            raise ValueError("checkpoint identity or source rows changed")
        if not saved_identity:
            with self.db:
                self.db.executemany("INSERT INTO checkpoint_meta VALUES (?,?)", identity.items())
                self.db.executemany("INSERT INTO checkpoint_rows VALUES (?,?,?,?,?)", normalized)
        self._materialize_seed(seed_labels or {})
        self._materialize_label_aliases()

    def _materialize_seed(self, seed_labels):
        """seed_labels maps exact text to (label_json, direct_original_id)."""
        with self.db:
            for text, (label_json, origin_id) in seed_labels.items():
                if not origin_id or not isinstance(text, str):
                    raise ValueError("cache original must be direct and named")
                for rid, saved_text in self.db.execute(
                        "SELECT review_id,review_text FROM checkpoint_rows WHERE text_sha=?",
                        (text_sha256(text),)).fetchall():
                    if saved_text != text:
                        continue
                    existing = self.db.execute("SELECT label_json,config_sha,cache_source_id "
                        "FROM checkpoint_labels WHERE review_id=?", (rid,)).fetchone()
                    expected = (label_json, self.label_config_sha, origin_id)
                    if existing is not None and existing != expected:
                        raise ValueError("seed label cache changed")
                    if existing is None:
                        self.db.execute("INSERT INTO checkpoint_labels VALUES (?,?,?,?,?,NULL)",
                            (rid, label_json, self.label_config_sha, "jev_exact_text_cache", origin_id))

    def _materialize_label_aliases(self):
        with self.db:
            originals = list(self.db.execute("""SELECT r.review_text,l.label_json,l.review_id
                FROM checkpoint_rows r JOIN checkpoint_labels l USING(review_id)
                WHERE l.provenance='jev_direct' ORDER BY r.position"""))
            for text, label_json, origin_id in originals:
                for rid, in self.db.execute("SELECT review_id FROM checkpoint_rows WHERE review_text=?",
                                            (text,)).fetchall():
                    if self.db.execute("SELECT 1 FROM checkpoint_labels WHERE review_id=?", (rid,)).fetchone():
                        continue
                    self.db.execute("INSERT INTO checkpoint_labels VALUES (?,?,?,?,?,NULL)",
                        (rid, label_json, self.label_config_sha, "jev_exact_text_cache", origin_id))

    def _pending(self, stage, first_100=False):
        result_table = "checkpoint_labels" if stage == "jev" else "checkpoint_evidence"
        rows = self.db.execute("""SELECT r.position,r.review_id,r.review_text,r.source_sha,r.text_sha
            FROM checkpoint_rows r WHERE (?=0 OR r.position<=100) AND NOT EXISTS(
            SELECT 1 FROM """ + result_table + """ x WHERE x.review_id=r.review_id)
            AND NOT EXISTS(SELECT 1 FROM checkpoint_request_members m
            WHERE m.review_id=r.review_id AND EXISTS(SELECT 1 FROM checkpoint_requests q
            WHERE q.request_key=m.request_key AND q.stage=?)) ORDER BY r.position""",
            (int(first_100), stage)).fetchall()
        attempted_texts = {text for text, in self.db.execute("""SELECT DISTINCT r.review_text
            FROM checkpoint_rows r JOIN checkpoint_request_members m USING(review_id)
            JOIN checkpoint_requests q USING(request_key) WHERE q.stage=?""", (stage,))}
        seen = set()
        selected = []
        for position, rid, text, source_sha, text_sha in rows:
            if text in seen or text in attempted_texts:
                continue
            if stage == "evidence" and not self.db.execute(
                    "SELECT 1 FROM checkpoint_labels WHERE review_id=?", (rid,)).fetchone():
                continue
            seen.add(text)
            selected.append({"source_position": position, "review_id": rid,
                "review_text": text, "source_sha256": source_sha,
                "text_sha256": text_sha})
        return selected

    def next_jev(self, first_100=False):
        pending = self._pending("jev", first_100)
        return pending[0] if pending else None

    def next_evidence(self, batch_limit, first_100=False):
        if batch_limit not in (25, 50):
            raise ValueError("batch limit must be 25 or 50")
        return self._pending("evidence", first_100)[:batch_limit]

    def labels_for(self, rows):
        result = {}
        for row in rows:
            saved = self.db.execute("SELECT label_json FROM checkpoint_labels WHERE review_id=?",
                                    (row["review_id"],)).fetchone()
            if saved is None:
                raise ValueError("evidence request has no saved labels")
            result[row["review_id"]] = json.loads(saved[0])
        return result

    def request_key(self, stage, rows, config_sha):
        return _sha({"prefix": dict(self.db.execute("SELECT key,value FROM checkpoint_meta"))["prefix_sha"],
            "stage": stage, "ids": [r["review_id"] for r in rows], "config": config_sha})

    def reserve(self, stage, rows, config_sha, amount_nusd, batch_limit=None):
        if stage not in ("jev", "evidence") or not rows:
            raise ValueError("invalid request stage or empty batch")
        key = self.request_key(stage, rows, config_sha)
        def record(db):
            db.execute("INSERT INTO checkpoint_requests(request_key,stage,status,batch_limit,config_sha)"
                " VALUES (?,?,'reserved',?,?)", (key, stage, batch_limit, config_sha))
            db.executemany("INSERT INTO checkpoint_request_members VALUES (?,?)",
                ((key, row["review_id"]) for row in rows))
        self.budget.reserve(key, "jev" if stage == "jev" else "openrouter",
                            amount_nusd, record=record)
        return key

    def save_label(self, request_key, row, label_json, charge_nusd, input_tokens,
                   output_tokens, elapsed_seconds):
        text = row["review_text"]
        rid = row["review_id"]
        def record(db):
            for alias_id, in db.execute("SELECT review_id FROM checkpoint_rows WHERE review_text=?",
                                        (text,)).fetchall():
                if db.execute("SELECT 1 FROM checkpoint_labels WHERE review_id=?", (alias_id,)).fetchone():
                    raise ValueError("label already saved for exact text")
                db.execute("INSERT INTO checkpoint_labels VALUES (?,?,?,?,?,?)",
                    (alias_id, label_json, self.label_config_sha,
                     "jev_direct" if alias_id == rid else "jev_exact_text_cache",
                     None if alias_id == rid else rid, request_key if alias_id == rid else None))
            db.execute("UPDATE checkpoint_requests SET status='succeeded',input_tokens=?,"
                "output_tokens=?,elapsed_seconds=? WHERE request_key=? AND status='reserved'",
                (input_tokens, output_tokens, elapsed_seconds, request_key))
        self.budget.settle(request_key, "succeeded", charge_nusd, record=record)

    def _write_evidence_rows(self, db, request_key, rows, accepted, invalid, config_sha):
        if set(accepted) & set(invalid) or set(accepted) | set(invalid) != \
                {r["review_id"] for r in rows}:
            raise ValueError("batch result coverage differs")
        by_id = {row["review_id"]: row for row in rows}
        for rid, value in accepted.items():
            text = by_id[rid]["review_text"]
            evidence = validate_evidence(text, value)
            for alias_id, in db.execute("SELECT review_id FROM checkpoint_rows WHERE review_text=?",
                                        (text,)).fetchall():
                if db.execute("SELECT 1 FROM checkpoint_evidence WHERE review_id=?", (alias_id,)).fetchone():
                    raise ValueError("evidence already saved for exact text")
                db.execute("INSERT INTO checkpoint_evidence VALUES (?,?,?,?,?,?,?)",
                    (alias_id, json.dumps(evidence["entities"], ensure_ascii=False),
                     evidence["evidence_quote"], config_sha,
                     "deepinfra_direct" if alias_id == rid else "deepinfra_exact_text_cache",
                     None if alias_id == rid else rid, request_key if alias_id == rid else None))
        for rid, reason in invalid.items():
            text = by_id[rid]["review_text"]
            for alias_id, source_sha in db.execute("SELECT review_id,source_sha FROM checkpoint_rows "
                    "WHERE review_text=?", (text,)).fetchall():
                db.execute("INSERT INTO checkpoint_quarantines VALUES (?,?,?,?)",
                    (alias_id, source_sha, reason, request_key))

    def save_evidence(self, request_key, rows, accepted, config_sha, charge_nusd,
                      input_tokens, output_tokens, reasoning_tokens, response_id,
                      elapsed_seconds, invalid=None, response=None):
        invalid = invalid or {}
        saved_response = json.dumps(response, ensure_ascii=False) if response is not None else None
        def record(db):
            self._write_evidence_rows(db, request_key, rows, accepted, invalid, config_sha)
            changed = db.execute("UPDATE checkpoint_requests SET status=?,response_id=?,"
                "input_tokens=?,output_tokens=?,reasoning_tokens=?,elapsed_seconds=?,"
                "response_json=?"
                " WHERE request_key=? AND status='reserved'",
                ("partial_succeeded" if invalid else "succeeded", response_id,
                 input_tokens, output_tokens, reasoning_tokens, elapsed_seconds,
                 saved_response, request_key)).rowcount
            if changed != 1:
                raise ValueError("evidence request is not reserved")
        self.budget.settle(request_key, "succeeded", charge_nusd, record=record)

    def recover_metered_evidence(self, request_key, rows, accepted, invalid,
                                 config_sha, charge_nusd, input_tokens, output_tokens,
                                 reasoning_tokens, response_id):
        """Offline salvage of a fully identified metered response; no POST."""
        if not accepted or not invalid:
            raise ValueError("partial recovery needs both accepted and invalid rows")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            saved = self.db.execute("""SELECT q.stage,q.status,q.config_sha,b.status,b.charged_nusd,
                q.response_json FROM checkpoint_requests q JOIN reservations b USING(request_key)
                WHERE q.request_key=?""", (request_key,)).fetchone()
            if saved is None or saved[:5] != ("evidence", "quarantined_metered",
                    config_sha, "quarantined_metered", charge_nusd) or not saved[5]:
                raise ValueError("metered response is not eligible for offline recovery")
            self._write_evidence_rows(self.db, request_key, rows, accepted, invalid, config_sha)
            self.db.execute("UPDATE checkpoint_requests SET status='partial_succeeded',"
                "response_id=?,input_tokens=?,output_tokens=?,reasoning_tokens=?"
                " WHERE request_key=?", (response_id, input_tokens, output_tokens,
                 reasoning_tokens, request_key))
            self.db.execute("UPDATE reservations SET status='succeeded' WHERE request_key=?",
                            (request_key,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def fail(self, request_key, metered_charge=None, error_class=None,
             response=None, elapsed_seconds=None):
        saved_response = json.dumps(response, ensure_ascii=False) if response is not None else None
        if metered_charge is None:
            self.budget.uncertain(request_key, record=lambda db: db.execute(
                "UPDATE checkpoint_requests SET status='uncertain',error_class=?,"
                "elapsed_seconds=?,response_json=? WHERE request_key=?",
                (error_class, elapsed_seconds, saved_response, request_key)))
        else:
            self.budget.settle(request_key, "quarantined_metered", metered_charge,
                record=lambda db: db.execute("UPDATE checkpoint_requests SET "
                    "status='quarantined_metered',error_class=?,elapsed_seconds=?,"
                    "response_json=? WHERE request_key=?",
                    (error_class, elapsed_seconds, saved_response, request_key)))

    def summary(self):
        total = self.db.execute("SELECT COUNT(*) FROM checkpoint_rows").fetchone()[0]
        labels = self.db.execute("SELECT COUNT(*) FROM checkpoint_labels").fetchone()[0]
        evidence = self.db.execute("SELECT COUNT(*) FROM checkpoint_evidence").fetchone()[0]
        quarantined = self.db.execute("SELECT COUNT(*) FROM checkpoint_quarantines").fetchone()[0]
        attempts = dict(self.db.execute("SELECT status,COUNT(*) FROM checkpoint_requests GROUP BY status"))
        usage = {}
        for stage in ("jev", "evidence"):
            observed = self.db.execute("""SELECT COUNT(*),COALESCE(SUM(input_tokens),0),
                COALESCE(SUM(output_tokens),0),COALESCE(SUM(reasoning_tokens),0),
                COALESCE(SUM(elapsed_seconds),0) FROM checkpoint_requests
                WHERE stage=? AND status IN ('succeeded','partial_succeeded')""",
                (stage,)).fetchone()
            charged = self.db.execute("""SELECT COALESCE(SUM(b.charged_nusd),0)
                FROM checkpoint_requests q JOIN reservations b USING(request_key)
                WHERE q.stage=? AND b.charged_nusd IS NOT NULL""", (stage,)).fetchone()[0]
            usage[stage] = {"successful_requests": observed[0], "input_tokens": observed[1],
                "output_tokens": observed[2], "reasoning_tokens": observed[3],
                "summed_request_seconds": observed[4], "measured_charge_nusd": charged}
        return {"source_rows": total, "labels": labels, "evidence": evidence,
                "quarantined_rows": quarantined,
                "complete": self.db.execute("""SELECT COUNT(*) FROM checkpoint_rows r
                    JOIN checkpoint_labels l USING(review_id)
                    JOIN checkpoint_evidence e USING(review_id)""").fetchone()[0],
                "requests": attempts, "usage": usage,
                "openrouter_exposure_nusd": self.budget.exposure("openrouter"),
                "jev_exposure_nusd": self.budget.exposure("jev")}

    def assert_resume_safe(self, stage, defer_uncertain_evidence=False):
        if self.db.execute("SELECT 1 FROM checkpoint_requests WHERE status='reserved' LIMIT 1").fetchone():
            raise ValueError("checkpoint has an active reservation; no duplicate worker")
        uncertain = list(self.db.execute("""SELECT q.request_key,q.stage,q.batch_limit,
            b.budget,b.status,b.reserved_nusd,b.charged_nusd
            FROM checkpoint_requests q LEFT JOIN reservations b USING(request_key)
            WHERE q.status='uncertain'"""))
        if uncertain and not defer_uncertain_evidence:
            raise ValueError("checkpoint has unresolved delivery; inspect and reconcile before more calls")
        if defer_uncertain_evidence:
            if stage != "evidence":
                raise ValueError("uncertain delivery deferral applies only to evidence")
            from spotify_pipeline.deepinfra_batch import reservation_nusd
            for key, request_stage, batch_limit, budget, status, reserved, charged in uncertain:
                if (request_stage != "evidence" or batch_limit not in (25, 50) or
                        budget != "openrouter" or status != "uncertain" or
                        reserved != reservation_nusd() or charged is not None or
                        self.db.execute("SELECT COUNT(*) FROM checkpoint_request_members "
                            "WHERE request_key=?", (key,)).fetchone()[0] == 0):
                    raise ValueError("uncertain evidence reservation is not fully held")
                if self.db.execute("""SELECT 1 FROM checkpoint_request_members m
                    LEFT JOIN checkpoint_evidence e USING(review_id)
                    LEFT JOIN checkpoint_quarantines q USING(review_id)
                    WHERE m.request_key=? AND (e.review_id IS NOT NULL OR q.review_id IS NOT NULL)
                    LIMIT 1""", (key,)).fetchone():
                    raise ValueError("uncertain evidence member was already settled")
        streak = 0
        for status, in self.db.execute("SELECT status FROM checkpoint_requests "
                                       "WHERE stage=? ORDER BY rowid DESC", (stage,)):
            if status in ("succeeded", "partial_succeeded"):
                break
            if status == "quarantined_metered":
                streak += 1
        if streak >= 5:
            raise ValueError("five consecutive metered validation failures paused this route")

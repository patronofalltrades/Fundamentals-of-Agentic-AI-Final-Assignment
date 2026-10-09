"""Import the private accepted-evidence handoff into a local, private dashboard database.

Contract: ``docs/accepted-evidence-dashboard-import.md`` in the pipeline worktree. Input is the private,
ignored ``spotify-accepted100k-dashboard-handoff-v1`` JSON plus the source CSV it names. Both are read
by this code only; nothing here prints review text, IDs or model output.

Gates, all before anything is written:

1. The handoff digest and schema version match. No ID repeats. Accepted and excluded IDs partition the
   selected IDs, and the coverage counts agree with the rows.
2. The source CSV hash matches. Every selected ID is a CSV row; its six-field source hash matches, and its
   position matches when the handoff gives one. Every accepted quote and entity is rechecked against the
   record's own source text.
3. Each row gets one state: ``accepted``, ``quarantined``, ``unresolved``, ``empty`` or ``pending``.
   Unknown states stop the import. Only accepted rows enter label and trend aggregates.
4. Records with ``representative_evidence_blocked_by_known_flags`` are marked blocked and never appear as
   representative examples. The count must equal the coverage figure (47).
5. An import manifest is saved: counts, hashes, state counts and the import time. It holds no path.

The database keeps source text (``source_text``) and raw model output (``raw_record``) in local tables.
The API never reads them. This file does not publish or deploy anything.
"""

import csv
import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.errors import ValidationError
from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256

from .bundle import DDL
from .store import connect

SCHEMA_VERSION = "spotify-accepted100k-dashboard-handoff-v1"
IMPORT_VERSION = "accepted-evidence-import-v1"

# Dashboard state for each saved source state. Pending rows await a label; they are not failures.
STATE_GROUPS = {
    "eligible_or_awaiting_label": "pending",
    "empty_text": "empty",
    "quarantined": "quarantined",
    "uncertain": "unresolved",
    "uncertain_direct": "unresolved",
    "uncertain_exact_text_alias": "unresolved",
    "uncertain_prior_exact_text_alias": "unresolved",
    "prior_uncertain_exact_text": "unresolved",
    "attempted_exact_text_alias": "unresolved",
}
STATES = ("accepted", "quarantined", "unresolved", "empty", "pending")
# The dashboard API keeps its historical name for accepted rows.
STATUS_FOR = {"accepted": "completed"}

PRIVATE_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS source_text (row_index INTEGER PRIMARY KEY REFERENCES records(row_index), "
    "review_text TEXT NOT NULL, review_rating TEXT, review_likes TEXT, app_version TEXT, review_timestamp TEXT)",
    "CREATE TABLE IF NOT EXISTS raw_record (row_index INTEGER PRIMARY KEY REFERENCES records(row_index), "
    "labels_json TEXT NOT NULL, provenance_json TEXT NOT NULL, semantic_json TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS row_state (row_index INTEGER PRIMARY KEY REFERENCES records(row_index), "
    "state TEXT NOT NULL, source_state TEXT NOT NULL, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS semantic_flag (row_index INTEGER PRIMARY KEY REFERENCES records(row_index), "
    "blocked INTEGER NOT NULL, human_review_required INTEGER NOT NULL, finding_count INTEGER NOT NULL, "
    "categories TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_row_state ON row_state(state)",
]


def _month_day(timestamp: str):
    return timestamp[:7], timestamp[:10]


def _check_handoff(handoff: Dict[str, Any]) -> Dict[str, Any]:
    if handoff.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported handoff schema")
    cov, accepted, excluded = handoff["coverage"], handoff["records"], handoff["excluded"]
    ids = [r["review_id"] for r in accepted] + [r["review_id"] for r in excluded]
    if len(ids) != len(set(ids)):
        raise ValueError("a review ID repeats")
    if (len(ids) != cov["selected_source_rows"] or len(accepted) != cov["accepted_rows"]
            or len(excluded) != cov["excluded_rows"] or cov.get("in_flight_rows", 0) != 0):
        raise ValueError("coverage counts differ from the rows")
    unknown = {r["status"] for r in excluded} - set(STATE_GROUPS)
    if unknown:
        raise ValueError("unknown source state: %s" % ", ".join(sorted(unknown)))
    pending = sum(STATE_GROUPS[r["status"]] == "pending" for r in excluded)
    if pending != cov["pending_rows"]:
        raise ValueError("pending count differs from coverage")
    blocked = sum(bool(r["semantic_review"]["representative_evidence_blocked_by_known_flags"]) for r in accepted)
    if blocked != cov["known_semantic_flags_excluded_from_representative_evidence"]:
        raise ValueError("representative-evidence exclusions differ from coverage")
    for r in accepted:
        sem = r["semantic_review"]
        if sem["representative_evidence_blocked_by_known_flags"] and not (sem["human_review_required"] and sem["findings"]):
            raise ValueError("a representative exclusion lacks its finding")
    configs = {r["provenance"]["label"]["config_sha256"] for r in accepted}
    if len(configs) != 1:
        raise ValueError("accepted rows must share one label configuration")
    return {"config_hash": configs.pop(), "blocked": blocked}


def _source_rows(source_csv: str, wanted: set) -> Dict[str, Dict[str, Any]]:
    found = {}
    with open(source_csv, encoding="utf-8", newline="") as f:
        for position, row in enumerate(csv.DictReader(f), 1):
            if row["review_id"] in wanted:
                found[row["review_id"]] = dict(row, _position=position)
                if len(found) == len(wanted):
                    break
    if len(found) != len(wanted):
        raise ValueError("source CSV is missing %d selected rows" % (len(wanted) - len(found)))
    return found


def _chunks(items: List[tuple], size: int = 2000) -> Iterable[List[tuple]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def import_accepted(handoff_path: str, source_csv: str, db_path: str, expected_sha256: str,
                    now: Optional[str] = None) -> Dict[str, Any]:
    digest = file_sha256(handoff_path)
    if digest != expected_sha256:
        raise ValueError("handoff digest differs from the expected digest")
    handoff = json.loads(Path(handoff_path).read_text(encoding="utf-8"))
    checked = _check_handoff(handoff)
    if file_sha256(source_csv) != handoff["source_file_sha256"]:
        raise ValueError("source CSV hash differs from the handoff")
    accepted, excluded = handoff["records"], handoff["excluded"]
    selected = {r["review_id"]: r for r in accepted + excluded}
    source = _source_rows(source_csv, set(selected))

    for rid, item in selected.items():
        row = source[rid]
        if row_sha256([row[k] for k in SOURCE_FIELDS]) != item["source_sha256"]:
            raise ValueError("a source row hash differs")
        if "source_position" in item and item["source_position"] != row["_position"]:
            raise ValueError("a source position differs")
    for rec in accepted:
        if [rec["source"][k] for k in SOURCE_FIELDS] != [source[rec["review_id"]][k] for k in SOURCE_FIELDS]:
            raise ValueError("a record's source fields differ from the CSV")
        try:
            validate_evidence(rec["source"]["review_text"], rec["evidence"])
        except ValidationError as error:
            raise ValueError("an accepted evidence span fails the source check: %s" % error) from None

    if Path(db_path).exists():
        raise ValueError("target database already exists; import into a new file")
    config = checked["config_hash"]
    records, states, rowstate, classes, texts, raws, flags = [], [], [], [], [], [], []
    groups, details, labels = Counter(), Counter(), {"topic": Counter(), "intent": Counter(), "severity": Counter()}
    months, days, distinct = {}, {}, set()
    for rid, item in sorted(selected.items(), key=lambda kv: source[kv[0]]["_position"]):
        src = source[rid]
        idx = src["_position"] - 1
        text = src["review_text"]
        is_empty = int(not text.strip())
        if not is_empty:
            distinct.add(text)
        records.append((idx, rid, item["source_sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest(), is_empty))
        texts.append((idx, text, src["review_rating"], src["review_likes"], src["app_version"], src["review_timestamp"]))
        if "labels" in item:
            state, source_state, reason = "accepted", "accepted", None
            lab, ev, sem = item["labels"], item["evidence"], item["semantic_review"]
            classes.append((idx, config, lab["topic"], lab["intent"], lab["sentiment"], int(lab["severity"]),
                            json.dumps(ev["entities"], ensure_ascii=False), ev["evidence_quote"],
                            int(bool(lab["needs_review"])), int(item["provenance"]["label"]["kind"] != "jev_direct"),
                            config, lab["model"], "jev-rubric-v2", "jev-labels-v1"))
            raws.append((idx, json.dumps(lab, ensure_ascii=False), json.dumps(item["provenance"], ensure_ascii=False),
                         json.dumps(sem, ensure_ascii=False)))
            categories = sorted({f.get("category", "") for f in sem["findings"]} - {""})
            flags.append((idx, int(bool(sem["representative_evidence_blocked_by_known_flags"])),
                          int(bool(sem["human_review_required"])), len(sem["findings"]), json.dumps(categories)))
            for dim in labels:
                labels[dim][str(lab[dim])] += 1
            month, day = _month_day(src["review_timestamp"])
            for bucket, key in ((months, month), (days, day)):
                b = bucket.setdefault(key, {"reviews": 0, "complaints": 0, "severity_sum": 0})
                b["reviews"] += 1
                if lab["intent"] in ("complaint", "cancellation"):
                    b["complaints"] += 1
                    b["severity_sum"] += int(lab["severity"])
        else:
            source_state, reason = item["status"], item.get("reason")
            state = STATE_GROUPS[source_state]
        groups[state] += 1
        details[source_state] += 1
        states.append((idx, config, STATUS_FOR.get(state, state), reason if state != "accepted" else None))
        rowstate.append((idx, state, source_state, reason))

    if groups["accepted"] != len(accepted) or sum(groups.values()) != len(selected):
        raise ValueError("state counts do not add up")
    blocked = sum(f[1] for f in flags)
    if blocked != checked["blocked"]:
        raise ValueError("blocked count changed during import")

    requests = Counter((m["stage"], m["status"]) for m in handoff.get("request_metadata", []))
    manifest = {
        "import_version": IMPORT_VERSION,
        "handoff_schema": handoff["schema_version"],
        "handoff_sha256": digest,
        "source_file_sha256": handoff["source_file_sha256"],
        "frozen_manifest_sha256": handoff.get("frozen_manifest_sha256", {}),
        "label_config_hash": config,
        "scope": handoff.get("scope"),
        "selected_rows": len(selected),
        "accepted_rows": groups["accepted"],
        "state_counts": {s: groups[s] for s in STATES},
        "source_state_counts": dict(sorted(details.items())),
        "representative_evidence_exclusions": blocked,
        "distinct_nonempty_texts": len(distinct),
        "request_counts": {"%s:%s" % k: v for k, v in sorted(requests.items())},
        "cost_nusd": handoff.get("cost_nusd", {}),
        "semantic_overlay": handoff.get("semantic_overlay", {}),
        "imported_at": now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "not_human_accuracy": True,
    }

    aggregates = [("coverage", "distinct_nonempty_texts", len(distinct)),
                  ("source_status", "nonempty", len(selected) - groups["empty"]),
                  ("source_status", "empty", groups["empty"])]
    aggregates += [("processing_status", STATUS_FOR.get(s, s), n) for s, n in groups.items()]
    aggregates += [("row_state", s, n) for s, n in groups.items()]
    aggregates += [("source_state", s, n) for s, n in details.items()]
    aggregates += [(dim, value, n) for dim, values in labels.items() for value, n in values.items()]
    aggregates += [("month_" + k, m, v[k]) for m, v in months.items() for k in ("reviews", "complaints") if v[k]]
    aggregates += [("month_severity_sum", m, v["severity_sum"]) for m, v in months.items() if v["severity_sum"]]
    aggregates += [("day_" + k, d, v[k]) for d, v in days.items() for k in ("reviews", "complaints") if v[k]]
    aggregates += [("day_severity_sum", d, v["severity_sum"]) for d, v in days.items() if v["severity_sum"]]

    conn = connect(db_path)
    try:
        with conn:
            for sql in DDL["common"] + DDL["sqlite"] + PRIVATE_SCHEMA:
                conn.execute(sql)
            meta = {"file_sha256": handoff["source_file_sha256"], "parsed_rows_sha256": digest,
                    "source_basename": "spotify_reviews_18months.csv (first %d rows)" % len(selected)}
            conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())
            for sql, rows in (
                    ("INSERT INTO records VALUES (?, ?, ?, ?, ?)", records),
                    ("INSERT INTO record_state VALUES (?, ?, ?, ?)", states),
                    ("INSERT INTO row_state VALUES (?, ?, ?, ?)", rowstate),
                    ("INSERT INTO classifications (row_index, config_hash, topic, intent, sentiment, severity, entities, "
                     "evidence_quote, needs_review, is_cached, label_config, model, prompt_version, schema_version) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", classes),
                    ("INSERT INTO source_text VALUES (?, ?, ?, ?, ?, ?)", texts),
                    ("INSERT INTO raw_record VALUES (?, ?, ?, ?)", raws),
                    ("INSERT INTO semantic_flag VALUES (?, ?, ?, ?, ?)", flags)):
                for chunk in _chunks(rows):
                    conn.executemany(sql, chunk)
            conn.executemany("INSERT INTO dashboard_aggregate VALUES (?, ?, ?)", aggregates)
            conn.executemany("INSERT INTO dashboard_meta VALUES (?, ?)", [
                ("source_sha256", handoff["source_file_sha256"]),
                ("import_manifest", json.dumps(manifest, sort_keys=True)),
                ("import_status", "complete")])
        recount = dict(conn.execute("SELECT state, COUNT(*) FROM row_state GROUP BY state").fetchall())
        if recount != {k: v for k, v in groups.items() if v}:
            raise ValueError("saved state counts differ after import")
    finally:
        conn.close()
    return manifest

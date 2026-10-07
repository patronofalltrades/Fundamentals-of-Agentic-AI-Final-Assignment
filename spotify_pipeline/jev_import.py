"""Validate a complete Jev pilot ledger against the canonical source database."""

import json
from typing import Any, Dict, List

from .config import config_hash
from .contract import text_sha256
from .errors import StateError
from .jev import label_config
from .jev_pilot import PilotLedger


def completed_items(ledger: PilotLedger, source_db: Any, expected_count: int = 100) -> List[Dict[str, Any]]:
    """Produce complete records in direct-then-cache order; never calls models."""
    saved = list(ledger.conn.execute(
        "SELECT r.*,e.entities_json,e.evidence_quote FROM results r "
        "LEFT JOIN evidence e ON e.review_id=r.review_id ORDER BY r.rowid"))
    if len(saved) != expected_count or any(row["evidence_quote"] is None for row in saved):
        raise StateError("pilot labels and exact evidence are not complete")
    cfg = label_config()
    expected_config_hash = config_hash(cfg)
    direct: List[Dict[str, Any]] = []
    cached: List[Dict[str, Any]] = []
    for saved_row in saved:
        if saved_row["config_hash"] != expected_config_hash:
            raise StateError("pilot label configuration differs from current rubric")
        source = source_db.get_record_by_review_id(saved_row["review_id"])
        if (source is None or source["review_text"] != saved_row["review_text"] or
                source["row_sha256"] != saved_row["source_sha256"] or
                text_sha256(source["review_text"]) != saved_row["text_sha256"]):
            raise StateError("pilot review differs from canonical source")
        labels = json.loads(saved_row["label_json"])
        attempt_id = saved_row["attempt_id"]
        is_cached = saved_row["provenance"] == "jev_exact_text_cache"
        if not is_cached:
            attempt = ledger.conn.execute("SELECT status FROM attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None or attempt["status"] != "settled":
                raise StateError("direct result lacks a settled paid attempt")
        item = {
            "row_index": source["row_index"], "topic": labels["topic"],
            "intent": labels["intent"], "severity": labels["severity"],
            "sentiment": labels["sentiment"], "needs_review": labels["needs_review"],
            "entities": json.loads(saved_row["entities_json"]),
            "evidence_quote": saved_row["evidence_quote"],
            **cfg,
            "is_cached": is_cached,
            "cache_source_id": saved_row["cache_source_id"],
            # TypeSafe does not supply a response request ID. This is the
            # local, persisted attempt correlation ID, not a provider claim.
            "request_id": None if is_cached else "local-jev-attempt-%s" % attempt_id,
            "provenance": "jev_exact_text_cache" if is_cached else "typesafe_jev_direct",
        }
        (cached if is_cached else direct).append(item)
    return direct + cached


def import_completed_pilot(ledger: PilotLedger, target_db: Any) -> Dict[str, int]:
    """Explicit write step after source/evidence validation; never calls models."""
    items = completed_items(ledger, target_db)
    counts = {"inserted": 0, "skipped": 0}
    for index in range(0, len(items), 50):
        result = target_db.save_completed_batch(items[index:index + 50])
        counts["inserted"] += result["inserted"]
        counts["skipped"] += result["skipped"]
    return counts

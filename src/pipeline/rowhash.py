"""Hashing and label constants, byte-identical to check_submission.py.

tests/test_rowhash.py asserts equality with the vendored checker, so any drift fails loudly.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")
TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("complaint", "request", "praise", "cancellation", "unclear")
RANKED_INTENTS = ("complaint", "cancellation")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row) -> str:
    # Strings are preserved exactly; no trimming, translating, or Unicode normalization.
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

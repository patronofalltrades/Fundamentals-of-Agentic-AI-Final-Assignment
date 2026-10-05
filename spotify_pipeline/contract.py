"""Frozen data contract helpers.

The six source fields and the row hash are contract-compatible with the
supplied grading contract. Do not change the order or the hashing recipe.
"""

import hashlib
import json
import os
from typing import Iterable, Sequence

SOURCE_FIELDS = (
    "review_id",
    "review_text",
    "review_rating",
    "review_likes",
    "app_version",
    "review_timestamp",
)

TOPICS = (
    "access",
    "usability",
    "playback",
    "downloads",
    "catalog",
    "billing",
    "support",
    "other",
)

INTENTS = (
    "cancellation",
    "complaint",
    "request",
    "praise",
    "unclear",
)

FULL_CORPUS_NAME = "spotify_reviews_18months.csv"

_READ_CHUNK = 1024 * 1024


def row_sha256(fields: Sequence[str]) -> str:
    """Hash the six original source strings exactly as the contract requires.

    The payload is compact UTF-8 JSON with sorted keys, no ASCII escaping and
    no NaN/Infinity. Values are never normalized.
    """
    if len(fields) != len(SOURCE_FIELDS):
        raise ValueError(
            "row_sha256 expects %d fields, got %d" % (len(SOURCE_FIELDS), len(fields))
        )
    for value in fields:
        if not isinstance(value, str):
            raise ValueError("row_sha256 fields must be strings")
    payload = json.dumps(
        list(fields),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_row_payload(fields: Sequence[str]) -> str:
    """Return the exact canonical JSON payload used by :func:`row_sha256`."""
    if len(fields) != len(SOURCE_FIELDS):
        raise ValueError("canonical_row_payload expects six fields")
    return json.dumps(
        list(fields),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def parsed_rows_sha256(row_hashes: Iterable[str]) -> str:
    """SHA-256 of the concatenated raw bytes of each row hash, in CSV order."""
    digest = hashlib.sha256()
    for row_hash in row_hashes:
        digest.update(bytes.fromhex(row_hash))
    return digest.hexdigest()


def file_sha256(path: str) -> str:
    """Stream a file and return its SHA-256 without loading it fully."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: str) -> int:
    """Return the byte size of a file."""
    return os.path.getsize(path)


def text_sha256(text: str) -> str:
    """SHA-256 of the exact UTF-8 bytes of a text value."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_empty_text(text: str) -> bool:
    """Empty means the stripped text has no content. Missing version is separate."""
    return not text.strip()

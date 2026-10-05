"""Validation for completed and quarantined classification output.

Validation returns a list of human-readable errors. Callers decide whether to
raise. Standalone helpers accept an optional authoritative ``source`` mapping
(``review_id``, ``source_sha256``/``row_sha256``, ``review_text``). The database
always supplies the stored source so a caller cannot override identity.
"""

import math
import re
from typing import Any, Dict, List, Optional

from .contract import INTENTS, TOPICS
from .errors import ValidationError

PROVENANCE_DIRECT = ("model_call_placeholder", "synthetic_fixture")

COMPLETED_CLASSIFICATION_FIELDS = (
    "topic",
    "intent",
    "sentiment",
    "severity",
    "entities",
    "evidence_quote",
    "needs_review",
    "label_config",
)

EMPTY_REASON = "empty_review_text"

_SHA_RE = re.compile(r"[0-9a-fA-F]{64}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value))


def _source_sha(source: Dict[str, Any]) -> Any:
    if "source_sha256" in source:
        return source.get("source_sha256")
    return source.get("row_sha256")


def validate_is_cached(value: Any) -> List[str]:
    """Accept bool or explicit int 0/1. Reject truthy strings and other types."""
    if isinstance(value, bool):
        return []
    if isinstance(value, int) and value in (0, 1):
        return []
    return ["is_cached must be a boolean or integer 0/1"]


def validate_completed(
    record: Dict[str, Any], source: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Validate one completed record. Empty text can never complete.

    When ``source`` is supplied it is authoritative for ID, hash and text.
    """
    errors: List[str] = []

    if record.get("status") != "completed":
        errors.append("status must be 'completed'")

    text = record.get("review_text")
    expected_sha = record.get("source_sha256")
    expected_id = record.get("review_id")
    if source is not None:
        stored_id = source.get("review_id")
        stored_sha = _source_sha(source)
        stored_text = source.get("review_text")
        if "review_id" in record and record.get("review_id") != stored_id:
            errors.append("review_id must match the stored source")
        if "source_sha256" in record and record.get("source_sha256") != stored_sha:
            errors.append("source_sha256 must match the stored source")
        if "review_text" in record and record.get("review_text") != stored_text:
            errors.append("review_text must match the stored source")
        expected_id = stored_id
        expected_sha = stored_sha
        text = stored_text

    if not isinstance(expected_id, str) or not expected_id.strip():
        errors.append("review_id must be a nonempty string")

    if not _is_hex64(expected_sha):
        errors.append("source_sha256 must be a 64-character hex string")

    if not isinstance(text, str) or not text.strip():
        errors.append("empty review_text cannot complete")

    if record.get("topic") not in TOPICS:
        errors.append("topic must be one of %r" % (TOPICS,))

    if record.get("intent") not in INTENTS:
        errors.append("intent must be one of %r" % (INTENTS,))

    sentiment = record.get("sentiment")
    if not _is_number(sentiment):
        errors.append("sentiment must be a finite number")
    else:
        try:
            numeric = float(sentiment)
        except (OverflowError, ValueError):
            errors.append("sentiment must be a finite number")
        else:
            if not math.isfinite(numeric) or not (-1.0 <= numeric <= 1.0):
                errors.append("sentiment must be within [-1, 1]")

    severity = record.get("severity")
    if not _is_int(severity) or not (1 <= severity <= 5):
        errors.append("severity must be an integer in 1..5")

    entities = record.get("entities")
    if not isinstance(entities, list) or not all(
        isinstance(item, str) and item.strip() for item in entities
    ):
        errors.append("entities must be a list of nonblank strings")

    quote = record.get("evidence_quote")
    if not isinstance(quote, str) or not quote.strip():
        errors.append("evidence_quote must be a nonblank string")
    elif isinstance(text, str) and quote not in text:
        errors.append("evidence_quote must be an exact substring of review_text")

    if not isinstance(record.get("needs_review"), bool):
        errors.append("needs_review must be a boolean")

    label_config = record.get("label_config")
    if not isinstance(label_config, str) or not label_config.strip():
        errors.append("label_config must be a nonempty string")

    return errors


def validate_direct(record: Dict[str, Any]) -> List[str]:
    """A direct result requires a nonempty request id and known provenance."""
    errors: List[str] = []
    request_id = record.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        errors.append("direct result requires a nonempty request_id")
    provenance = record.get("provenance")
    if provenance not in PROVENANCE_DIRECT:
        errors.append(
            "provenance must be one of %r for a direct result" % (PROVENANCE_DIRECT,)
        )
    cache_source_id = record.get("cache_source_id")
    if isinstance(cache_source_id, str) and cache_source_id.strip():
        errors.append("direct result cannot carry a cache_source_id")
    return errors


def validate_cache_reuse(
    target: Dict[str, Any], original: Dict[str, Any], original_is_direct: bool
) -> List[str]:
    """Validate that a cached result points at one direct completed original.

    The same exact text, configuration and every classification field must
    match. Alias chains, self references and non-direct origins are rejected.
    """
    errors: List[str] = []

    if not target.get("is_cached"):
        errors.append("target is not marked as cached")

    cache_source_id = target.get("cache_source_id")
    if not isinstance(cache_source_id, str) or not cache_source_id.strip():
        errors.append("cached result requires cache_source_id")
    elif cache_source_id != original.get("review_id"):
        errors.append("cache_source_id does not match the original review_id")

    if target.get("review_id") == original.get("review_id"):
        errors.append("cached result cannot point at itself")

    if not original_is_direct:
        errors.append("cached result must point at a direct original, not another cache")

    if original.get("status") != "completed":
        errors.append("cache original must be currently completed")

    if not original.get("request_id") or not str(original.get("request_id")).strip():
        errors.append("cache original must retain a nonempty request_id")

    if original.get("provenance") not in PROVENANCE_DIRECT:
        errors.append("cache original must retain known provenance")

    if target.get("review_text") != original.get("review_text"):
        errors.append("cached result text must exactly equal the original text")

    if target.get("config_hash") != original.get("config_hash"):
        errors.append("cached result configuration must equal the original configuration")

    for field in COMPLETED_CLASSIFICATION_FIELDS:
        if target.get(field) != original.get(field):
            errors.append("cached field %r must equal the original" % field)

    return errors


def validate_quarantine(
    record: Dict[str, Any], source: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Validate a quarantine. The contract key is ``reason``."""
    errors: List[str] = []
    if record.get("status") != "quarantined":
        errors.append("status must be 'quarantined'")

    reason = record.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append("quarantine reason is required")
    elif reason != reason.strip():
        errors.append("quarantine reason must not contain surrounding whitespace")

    expected_id = record.get("review_id")
    expected_sha = record.get("source_sha256")
    text = record.get("review_text")
    if source is not None:
        stored_id = source.get("review_id")
        stored_sha = _source_sha(source)
        stored_text = source.get("review_text")
        if "review_id" in record and record.get("review_id") != stored_id:
            errors.append("review_id must match the stored source")
        if "source_sha256" in record and record.get("source_sha256") != stored_sha:
            errors.append("source_sha256 must match the stored source")
        expected_id = stored_id
        expected_sha = stored_sha
        text = stored_text

    if not isinstance(expected_id, str) or not expected_id.strip():
        errors.append("review_id must be a nonempty string")
    if not _is_hex64(expected_sha):
        errors.append("source_sha256 must be a 64-character hex string")

    if reason == EMPTY_REASON and isinstance(text, str) and text.strip():
        errors.append("empty_review_text requires empty source text")

    return errors


def raise_for_errors(errors: List[str]) -> None:
    if errors:
        raise ValidationError("; ".join(errors))

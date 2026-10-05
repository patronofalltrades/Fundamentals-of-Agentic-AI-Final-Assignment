"""Manifest lookup and input identity validation.

The real supplied manifest carries file identity under ``files[name]`` and the
full-corpus facts at the manifest root::

    {
      "files": {
        "spotify_reviews_18months.csv": {"sha256": "<64 hex>", "bytes": 97400616}
      },
      "profile": {
        "records": 660622,
        "duplicate_review_ids": 0,
        "empty_review_text": 13,
        "missing_app_version": 159701
      },
      "reviews_by_month": {"2022-05": 123, ...},
      "reviews_by_rating": {"1": 1, ...},
      "window": {
        "start_inclusive": "2022-05-17",
        "end_exclusive": "2023-11-17",
        "first_review": "2022-05-17 00:01:07",
        "last_review": "2023-11-15 23:16:10"
      }
    }

Every file entry must carry both a 64-hex ``sha256`` and a nonnegative integer
``bytes``. Bare strings and alias keys are rejected so identity can never be
silently skipped. Only the full corpus is checked against declared facts.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional

from .contract import FULL_CORPUS_NAME
from .errors import ManifestError

_SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_COUNT_KEYS = (
    "records",
    "duplicate_review_ids",
    "empty_review_text",
    "missing_app_version",
)
_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _files_map(manifest: Any) -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    files = manifest.get("files")
    if isinstance(files, dict):
        return files
    return manifest


def lookup_entry(manifest: Any, basename: str) -> Any:
    files = _files_map(manifest)
    if basename not in files:
        raise ManifestError("input %r is not listed in the manifest" % basename)
    return files[basename]


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.match(value))


def _parse_dt(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ManifestError("%s must be a date/time string, got %r" % (label, value))
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ManifestError("%s is not a valid date/time: %r" % (label, value))


def validate_identity(manifest: Any, basename: str, sha256: str, size: int) -> Dict[str, Any]:
    """Validate file identity. Both sha256 and bytes are required."""
    entry = lookup_entry(manifest, basename)
    if not isinstance(entry, dict):
        raise ManifestError(
            "manifest entry for %r must be an object with sha256 and bytes" % basename
        )
    expected_sha = entry.get("sha256")
    if not _is_hex64(expected_sha):
        raise ManifestError(
            "manifest entry for %r has no valid 64-hex sha256" % basename
        )
    if expected_sha.lower() != sha256.lower():
        raise ManifestError(
            "sha256 mismatch for %r: manifest=%s actual=%s"
            % (basename, expected_sha, sha256)
        )
    expected_bytes = entry.get("bytes")
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise ManifestError(
            "manifest bytes for %r must be a nonnegative integer" % basename
        )
    if expected_bytes != size:
        raise ManifestError(
            "byte size mismatch for %r: manifest=%d actual=%d"
            % (basename, expected_bytes, size)
        )
    return {
        "validated": True,
        "sha256_matched": True,
        "bytes_matched": True,
        "declared_profile_checked": False,
    }


def declared_profile(manifest: Any, basename: str) -> Optional[Dict[str, Any]]:
    """Return normalized full-file facts from the manifest.

    Combines the real root layout with an optional legacy per-entry ``profile``.
    Returns ``None`` when no facts are declared for this file.
    """
    if basename != FULL_CORPUS_NAME:
        return None
    normalized: Dict[str, Any] = {
        "counts": {},
        "reviews_by_month": {},
        "reviews_by_rating": {},
        "window": {},
    }
    found = False

    entry = lookup_entry(manifest, basename)
    if isinstance(entry, dict):
        legacy = entry.get("profile")
        if isinstance(legacy, dict):
            for key in _COUNT_KEYS:
                if key in legacy:
                    normalized["counts"][key] = legacy[key]
                    found = True
            for key in ("reviews_by_month", "reviews_by_rating"):
                if isinstance(legacy.get(key), dict):
                    normalized[key] = legacy[key]
                    found = True
            for key in ("first_review", "last_review"):
                if key in legacy:
                    normalized["window"][key] = legacy[key]
                    found = True

    if basename == FULL_CORPUS_NAME and isinstance(manifest, dict):
        root_profile = manifest.get("profile")
        if isinstance(root_profile, dict):
            missing = [key for key in _COUNT_KEYS if key not in root_profile]
            if missing:
                raise ManifestError(
                    "root profile is missing required counts: %r" % missing
                )
            for key in _COUNT_KEYS:
                normalized["counts"][key] = root_profile[key]
                found = True
        for key in ("reviews_by_month", "reviews_by_rating"):
            if isinstance(manifest.get(key), dict):
                normalized[key] = manifest[key]
                found = True
        root_window = manifest.get("window")
        if isinstance(root_window, dict):
            for key in ("start_inclusive", "end_exclusive", "first_review", "last_review"):
                if key in root_window:
                    normalized["window"][key] = root_window[key]
                    found = True

    return normalized if found else None


def _check_counts(basename: str, declared: Dict[str, Any], computed: Dict[str, Any]) -> None:
    for key, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ManifestError(
                "profile count %s.%s must be a nonnegative integer" % (basename, key)
            )
        actual = computed.get(key)
        if actual != value:
            raise ManifestError(
                "profile mismatch for %s.%s: declared=%r actual=%r"
                % (basename, key, value, actual)
            )


def _check_distribution(basename: str, label: str, declared: Dict[str, Any], computed: Dict[str, Any]) -> None:
    if not isinstance(declared, dict):
        raise ManifestError("profile %s must be an object" % label)
    declared_norm = {}
    for key, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ManifestError(
                "profile %s[%r] must be a nonnegative integer" % (label, key)
            )
        declared_norm[str(key)] = value
    computed_norm = {str(k): v for k, v in computed.items()}
    if declared_norm != computed_norm:
        missing = sorted(set(computed_norm) - set(declared_norm))
        extra = sorted(set(declared_norm) - set(computed_norm))
        detail = []
        if missing:
            detail.append("computed keys absent from manifest: %r" % missing)
        if extra:
            detail.append("manifest keys absent from computed: %r" % extra)
        for key in sorted(set(declared_norm) & set(computed_norm)):
            if declared_norm[key] != computed_norm[key]:
                detail.append("%s declared=%r actual=%r" % (key, declared_norm[key], computed_norm[key]))
        raise ManifestError("profile %s mismatch: %s" % (label, "; ".join(detail)))


def _check_window(basename: str, declared: Dict[str, Any], computed: Dict[str, Any]) -> None:
    first = computed.get("first_review")
    last = computed.get("last_review")
    first_dt = _parse_dt(first, "computed first_review") if first else None
    last_dt = _parse_dt(last, "computed last_review") if last else None

    if "start_inclusive" in declared:
        start = _parse_dt(declared["start_inclusive"], "window.start_inclusive")
        if first_dt is not None and first_dt < start:
            raise ManifestError(
                "window mismatch for %s: first_review %s is before start_inclusive %s"
                % (basename, first, declared["start_inclusive"])
            )
    if "end_exclusive" in declared:
        end = _parse_dt(declared["end_exclusive"], "window.end_exclusive")
        if last_dt is not None and last_dt >= end:
            raise ManifestError(
                "window mismatch for %s: last_review %s is at or after end_exclusive %s"
                % (basename, last, declared["end_exclusive"])
            )
    for key in ("first_review", "last_review"):
        if key in declared:
            expected = declared[key]
            actual = computed.get(key)
            if expected != actual:
                raise ManifestError(
                    "window mismatch for %s.%s: declared=%r actual=%r"
                    % (basename, key, expected, actual)
                )


def check_profile(basename: str, declared: Dict[str, Any], computed: Dict[str, Any]) -> None:
    """Compare declared full-file facts against computed facts.

    Only the full corpus is checked. Declared distributions must match exactly,
    so an extra computed month or rating fails.
    """
    if basename != FULL_CORPUS_NAME:
        return

    _check_counts(basename, declared.get("counts") or {}, computed)

    if declared.get("reviews_by_month"):
        _check_distribution(
            basename,
            "reviews_by_month",
            declared["reviews_by_month"],
            computed.get("reviews_by_month") or {},
        )
    if declared.get("reviews_by_rating"):
        _check_distribution(
            basename,
            "reviews_by_rating",
            declared["reviews_by_rating"],
            computed.get("reviews_by_rating") or {},
        )
    if declared.get("window"):
        _check_window(basename, declared["window"], computed)

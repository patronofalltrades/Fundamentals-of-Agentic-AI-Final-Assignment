"""Strict JSON helpers.

Reject NaN, Infinity and duplicate object keys. Malformed JSON, invalid UTF-8
and file errors become :class:`ValidationError` so the CLI exits cleanly.
"""

import json
from typing import Any

from .errors import ValidationError


def _reject_constant(name: str) -> Any:
    raise ValidationError("JSON constant not allowed: %s" % name)


def _no_duplicate_keys(pairs: Any) -> Any:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key: %r" % key)
        result[key] = value
    return result


def loads_strict(text: str) -> Any:
    """Parse JSON, rejecting NaN/Infinity and duplicate keys."""
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicate_keys,
        )
    except ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise ValidationError("invalid JSON: %s" % exc) from exc


def load_strict(path: str) -> Any:
    """Read and strictly parse a UTF-8 JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ValidationError("cannot read JSON file: %s" % exc) from exc
    except UnicodeDecodeError as exc:
        raise ValidationError("JSON file is not valid UTF-8: %s" % exc) from exc
    return loads_strict(text)

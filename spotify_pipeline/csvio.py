"""Strict CSV parsing and per-field validation.

The parser is UTF-8-sig, comma-delimited, streaming and uses ``csv`` strict
mode. It preserves quoted multiline and whitespace text exactly. CSV errors
and Unicode decoding failures are converted into :class:`ValidationError` so
the CLI exits cleanly. No pandas-style coercion is used.
"""

import csv
import re
from datetime import datetime
from typing import Iterator, List, Tuple

from .contract import SOURCE_FIELDS
from .errors import ValidationError

_RATING_RE = re.compile(r"[1-5]")
_LIKES_RE = re.compile(r"[0-9]+")
_TIMESTAMP_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def validate_header(header: List[str]) -> None:
    """Require exactly the six source fields, in order and unique.

    Golden files that add label columns are rejected here.
    """
    if header != list(SOURCE_FIELDS):
        raise ValidationError(
            "unexpected header; expected exactly %r in order, got %r"
            % (list(SOURCE_FIELDS), header)
        )


def validate_rating(value: str) -> None:
    if not _RATING_RE.fullmatch(value):
        raise ValidationError("invalid review_rating: %r" % value)


def validate_likes(value: str) -> None:
    if not _LIKES_RE.fullmatch(value):
        raise ValidationError("invalid review_likes: %r" % value)


def validate_timestamp(value: str) -> datetime:
    """Accept only the canonical ``YYYY-MM-DD HH:MM:SS`` shape."""
    if not _TIMESTAMP_RE.fullmatch(value):
        raise ValidationError("invalid review_timestamp: %r" % value)
    try:
        return datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ValidationError("invalid review_timestamp: %r" % value) from exc


def iter_source_rows(path: str) -> Iterator[Tuple[int, List[str]]]:
    """Yield ``(row_index, fields)`` for each data row.

    Row width must be exactly six. The header is validated once. Malformed CSV
    quoting and invalid UTF-8 raise :class:`ValidationError`.
    """
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ValidationError("cannot read input: %s" % exc) from exc

    with handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader)
        except StopIteration:
            raise ValidationError("empty CSV: missing header")
        except (csv.Error, UnicodeDecodeError) as exc:
            raise ValidationError("CSV parse error: %s" % exc) from exc
        validate_header(header)

        index = 0
        while True:
            try:
                row = next(reader)
            except StopIteration:
                break
            except (csv.Error, UnicodeDecodeError) as exc:
                raise ValidationError(
                    "CSV parse error at data row %d: %s" % (index, exc)
                ) from exc
            if len(row) != len(SOURCE_FIELDS):
                raise ValidationError(
                    "malformed row width at data row %d: expected %d fields, got %d"
                    % (index, len(SOURCE_FIELDS), len(row))
                )
            yield index, row
            index += 1

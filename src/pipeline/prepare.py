"""Stream the input CSV once and build the in-memory indexes the harness needs.

Parsing matches ``check_submission.csv_rows`` exactly (``utf-8-sig``, ``newline=""``,
``csv.DictReader(strict=True)``, missing/duplicate headers and short/long rows rejected), so every
``source_sha256`` we write equals the checker's ``row_sha``. No model calls; standard library only.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .rowhash import FIELDS, file_sha256, row_sha


class DuplicateReviewId(ValueError):
    """The input repeats a review_id; IDs are the unit of accounting, so we refuse to guess."""


def iter_rows(path) -> Iterator[dict]:
    """Yield CSV rows as dicts, rejecting the same malformed input the checker rejects."""
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate CSV headers")
        missing = [k for k in FIELDS if k not in reader.fieldnames]
        if missing:
            raise ValueError("CSV lacks required columns: " + ", ".join(missing))
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row near line %d" % reader.line_num)
            yield row


@dataclass
class Prepared:
    path: str
    file_sha256: Optional[str]
    texts: Dict[str, str]                 # review_id -> exact review_text, CSV order
    source_sha: Dict[str, str]            # review_id -> row_sha (checker-identical)
    text_first: Dict[str, str]            # exact nonempty text -> first review_id in file order
    empty_ids: List[str]                  # ids whose text is blank (`not text.strip()`)
    limited: bool = False                 # True when --limit truncated the input
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def ids(self):
        return self.texts.keys()

    def is_empty(self, review_id: str) -> bool:
        return not self.texts[review_id].strip()


def prepare(path, limit: Optional[int] = None, with_file_sha: bool = True) -> Prepared:
    """Read the CSV in one streaming pass. ``limit`` keeps only the first N rows (dev only)."""
    texts: Dict[str, str] = {}
    source_sha: Dict[str, str] = {}
    text_first: Dict[str, str] = {}
    empty_ids: List[str] = []
    intern = sys.intern
    limited = False
    for row in iter_rows(path):
        if limit is not None and len(texts) >= limit:
            limited = True
            break
        rid = intern(row["review_id"])
        if rid in texts:
            raise DuplicateReviewId("Duplicate review_id in input: " + rid)
        text = row["review_text"]
        texts[rid] = text
        source_sha[rid] = row_sha(row)
        if not text.strip():
            empty_ids.append(rid)
        elif text not in text_first:
            text_first[text] = rid
    nonempty = len(texts) - len(empty_ids)
    stats = {
        "rows": len(texts),
        "empty_review_text": len(empty_ids),
        "nonempty": nonempty,
        "distinct_nonempty_texts": len(text_first),
        "repeated_nonempty_texts": nonempty - len(text_first),
    }
    return Prepared(
        path=str(path),
        file_sha256=file_sha256(path) if with_file_sha else None,
        texts=texts, source_sha=source_sha, text_first=text_first, empty_ids=empty_ids,
        limited=limited, stats=stats,
    )

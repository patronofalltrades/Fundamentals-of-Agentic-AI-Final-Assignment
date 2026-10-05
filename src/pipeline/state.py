"""Durable run state: the record store, the call log, checkpoints and the invocation log.

``records.jsonl`` and ``calls.jsonl`` are append-only. A crash mid-append can leave a torn final
line; on open we truncate that fragment so the next append starts on a fresh line (otherwise the
fragment and the next record would merge into one unparseable line).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .io import append_jsonl, atomic_write_json, dumps_line, read_jsonl


def repair_torn_tail(path) -> int:
    """Drop a trailing partial line (no final newline). Returns the number of bytes removed."""
    path = Path(path)
    if not path.exists():
        return 0
    size = path.stat().st_size
    if size == 0:
        return 0
    with path.open("rb+") as f:
        f.seek(size - 1)
        if f.read(1) == b"\n":
            return 0
        # Walk back to the previous newline in chunks.
        pos = size
        keep = 0
        while pos > 0:
            step = min(65536, pos)
            pos -= step
            f.seek(pos)
            chunk = f.read(step)
            idx = chunk.rfind(b"\n")
            if idx >= 0:
                keep = pos + idx + 1
                break
        tail = size - keep
        f.truncate(keep)
        f.flush()
        os.fsync(f.fileno())
    return tail


class RecordStore:
    """Append-only ``records.jsonl``; the last line per review_id wins.

    Memory: per review_id we keep only the latest line's byte position (one packed int) and a
    small metadata tuple (status, label_config, has cache_source_id). ``latest(id)`` seeks and
    parses on demand, so the 660k-record store does not hold every line in memory.
    """

    _SHIFT = 32  # packed position = offset << 32 | length

    def __init__(self, path, repair: bool = True):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._pos: Dict[str, int] = {}
        self._meta: Dict[str, Tuple[str, Optional[str], bool]] = {}
        self._interned: Dict[str, str] = {}
        self._reader = None
        self._size = 0
        self.torn_bytes_repaired = repair_torn_tail(self.path) if repair else 0
        self._load()

    def _intern(self, value):
        if value is None:
            return None
        return self._interned.setdefault(value, value)

    def _index(self, record: dict, offset: int, length: int) -> None:
        rid = sys.intern(record["review_id"])
        self._pos[rid] = (offset << self._SHIFT) | length
        self._meta[rid] = (self._intern(record.get("status")), self._intern(record.get("label_config")),
                           bool(record.get("cache_source_id")))

    def _load(self) -> None:
        if not self.path.exists():
            return
        offset = 0
        with self.path.open("rb") as f:
            for number, raw in enumerate(f, 1):
                length = len(raw)
                if raw.strip():
                    torn = not raw.endswith(b"\n")
                    try:
                        record = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        if torn:  # torn final line (only reachable with repair=False): never index it
                            break
                        raise ValueError("%s:%d: malformed JSON line" % (self.path, number))
                    if torn:
                        break
                    if not isinstance(record, dict) or not isinstance(record.get("review_id"), str):
                        raise ValueError("%s:%d: not a record line" % (self.path, number))
                    self._index(record, offset, length)
                offset += length
        self._size = offset

    def upsert(self, records: Iterable[dict]) -> int:
        records = list(records)
        if not records:
            return 0
        encoded = [(dumps_line(r) + "\n").encode("utf-8") for r in records]
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as f:
                offset = f.tell()
                f.write(b"".join(encoded))
                f.flush()
                os.fsync(f.fileno())
            for record, data in zip(records, encoded):
                self._index(record, offset, len(data))
                offset += len(data)
            self._size = offset
        return len(records)

    def __len__(self) -> int:
        return len(self._pos)

    def __contains__(self, review_id) -> bool:
        return review_id in self._pos

    def _read(self, packed: int) -> dict:
        offset, length = packed >> self._SHIFT, packed & ((1 << self._SHIFT) - 1)
        with self._lock:
            if self._reader is None:
                self._reader = self.path.open("rb")
            self._reader.seek(offset)
            data = self._reader.read(length)
        return json.loads(data.decode("utf-8"))

    def latest(self, review_id: str) -> Optional[dict]:
        packed = self._pos.get(review_id)
        return self._read(packed) if packed is not None else None

    def meta(self, review_id: str) -> Optional[Tuple[str, Optional[str], bool]]:
        """(status, label_config, is_cache_copy) of the latest line, or None."""
        return self._meta.get(review_id)

    def completed_ids(self, label_config: Optional[str] = None) -> Set[str]:
        return {rid for rid, (status, lc, _) in self._meta.items()
                if status == "completed" and (label_config is None or lc == label_config)}

    def count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for status, _, _ in self._meta.values():
            counts[status] = counts.get(status, 0) + 1
        return counts

    def all_latest(self, ids: Optional[Iterable[str]] = None) -> Dict[str, dict]:
        """Parse latest records (in ``ids`` order if given, else store order)."""
        keys = list(self._pos.keys()) if ids is None else [i for i in ids if i in self._pos]
        return {rid: self._read(self._pos[rid]) for rid in keys}

    def close(self) -> None:
        with self._lock:
            if self._reader is not None:
                self._reader.close()
                self._reader = None

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter shutdown
            pass


class CallLog:
    """Append-only ``calls.jsonl`` that keeps ``request_id`` unique across the whole file."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.torn_bytes_repaired = repair_torn_tail(self.path)
        self._seen: Set[str] = set()
        for event in read_jsonl(self.path):
            rid = event.get("request_id")
            if isinstance(rid, str):
                self._seen.add(rid)

    def _unique(self, request_id: Optional[str], attempt) -> str:
        rid = request_id if isinstance(request_id, str) and request_id else "local-" + uuid.uuid4().hex
        if rid not in self._seen:
            return rid
        candidate = "%s#%s" % (rid, attempt)
        n = 2
        while candidate in self._seen:
            candidate = "%s#%s.%d" % (rid, attempt, n)
            n += 1
        return candidate

    def log_many(self, events: List[dict]) -> List[dict]:
        if not events:
            return []
        with self._lock:
            for event in events:
                event["request_id"] = self._unique(event.get("request_id"), event.get("attempt", 1))
                self._seen.add(event["request_id"])
            append_jsonl(self.path, events)
        return events

    def log(self, event: dict) -> dict:
        return self.log_many([event])[0]

    def __len__(self) -> int:
        return len(self._seen)


def save_checkpoint(path, completed_ids: Iterable[str]) -> int:
    ids = sorted(set(completed_ids))
    atomic_write_json(path, {"completed_ids": ids}, indent=None)
    return len(ids)


def load_checkpoint(path) -> List[str]:
    with Path(path).open(encoding="utf-8") as f:
        value = json.load(f)
    ids = value.get("completed_ids")
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        raise ValueError("bad checkpoint: " + str(path))
    return ids


def append_invocation(run_dir, entry: dict) -> None:
    path = Path(run_dir) / "invocations.jsonl"
    repair_torn_tail(path)
    append_jsonl(path, entry)


def read_invocations(run_dir) -> List[dict]:
    return list(read_jsonl(Path(run_dir) / "invocations.jsonl"))

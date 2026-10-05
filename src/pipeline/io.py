"""Durable file helpers: atomic replace for snapshots, fsync'd appends for logs."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterator


def dumps_line(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def atomic_write_text(path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(path, value, indent: int | None = 2) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=indent, allow_nan=False) + "\n")


def append_jsonl(path, values) -> None:
    """Append one or more JSON objects, then flush and fsync before returning."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(values, dict):
        values = [values]
    with path.open("a", encoding="utf-8", newline="") as f:
        for value in values:
            f.write(dumps_line(value) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path) -> Iterator[dict]:
    """Yield objects; a torn final line (crash mid-write) is skipped, any other bad line raises."""
    path = Path(path)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            if number == len(lines) and not line.endswith("\n"):
                return
            raise

"""Stable checkpoint snapshots for resume.

Checkpoints list original completed IDs under one configuration plus the
source and configuration identity. Pending rows never count as completed.
"""

import json
import os
import tempfile
from typing import Any, Dict

from .config import CONFIG_FIELDS, config_hash
from .db import Database
from .errors import ValidationError


def build_checkpoint(db: Database, config: Dict[str, str]) -> Dict[str, Any]:
    """Build a JSON-safe checkpoint for one configuration."""
    for field in CONFIG_FIELDS:
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValidationError("config field %r must be a nonempty string" % field)

    cfg_hash = config_hash(config)
    completed_ids = sorted(db.completed_ids(cfg_hash))
    pending = db.pending_row_indices(cfg_hash)
    counts = db.status_counts(cfg_hash)

    source = {
        "basename": db.get_meta("source_basename"),
        "file_sha256": db.get_meta("file_sha256"),
        "parsed_rows_sha256": db.get_meta("parsed_rows_sha256"),
    }

    return {
        "checkpoint_version": 1,
        "config": {field: config[field] for field in CONFIG_FIELDS},
        "config_hash": cfg_hash,
        "source": source,
        "completed_ids": completed_ids,
        "completed_count": len(completed_ids),
        "pending_count": len(pending),
        "status_counts": counts,
        "note": "Pending rows are not completed. Offline checkpoint only.",
    }


def write_checkpoint(checkpoint: Dict[str, Any], out_path: str) -> None:
    """Atomically write a checkpoint JSON file."""
    directory = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".checkpoint-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(checkpoint, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, out_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

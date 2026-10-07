"""Label configuration and cache key helpers.

A cache key includes the complete model, effort, prompt and schema versions
plus the exact review text. Star ratings and golden answers are never inputs.
"""

import hashlib
import json
from typing import Any, Dict

from .errors import ValidationError
from .jsonutil import load_strict

CONFIG_FIELDS = ("model", "effort", "prompt_version", "schema_version")


def canonical_config_payload(config: Dict[str, Any]) -> str:
    if not isinstance(config, dict) or set(config) != set(CONFIG_FIELDS):
        raise ValidationError("configuration must contain exactly the four supported fields")
    payload = {}
    for field in CONFIG_FIELDS:
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("label_config field %r must be a nonempty string" % field)
        payload[field] = value
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def config_hash(config: Dict[str, Any]) -> str:
    """Return the canonical configuration hash accepted as ``label_config``."""
    payload = canonical_config_payload(config)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_key(config: Dict[str, Any], text: str) -> str:
    """Return the exact-text cache key for a configuration."""
    payload = json.loads(canonical_config_payload(config))
    for field in CONFIG_FIELDS:
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("cache key field %r must be a nonempty string" % field)
        payload[field] = value
    payload["text"] = text
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_config(path: str) -> Dict[str, str]:
    """Load a label configuration JSON file and validate its fields."""
    data = load_strict(path)
    if not isinstance(data, dict):
        raise ValidationError("config file must contain a JSON object")
    canonical_config_payload(data)
    config = {}
    for field in CONFIG_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("config field %r must be a nonempty string" % field)
        config[field] = value
    return config

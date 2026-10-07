"""SYNTHETIC fixtures for tests.

Every value here is invented. These helpers never touch the real dataset.
"""

import csv
import json
import os
from typing import Any, Dict, Iterable, List, Optional

from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256

SYNTHETIC_ROWS: List[List[str]] = [
    ["1", "Great app", "5", "0", "1.0.0", "2022-05-17 00:01:07"],
    ["2", "  spaced text  ", "4", "3", "", "2022-06-01 12:00:00"],
    ["3", "", "3", "0", "1.2.0", "2022-06-15 09:30:00"],
    ["4", "line one\nline two", "2", "1", "1.3.0", "2023-01-01 00:00:00"],
    ["5", "caf\u00e9 \u2615", "1", "0", "", "2023-11-15 23:16:10"],
]


def write_csv(path: str, rows: Iterable[Iterable[str]], header: Optional[List[str]] = None) -> None:
    header = list(SOURCE_FIELDS) if header is None else list(header)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def write_manifest(path: str, entries: Dict[str, Any], wrapper: bool = True, root: Optional[Dict[str, Any]] = None) -> None:
    data: Any = {"files": entries} if wrapper else entries
    if root:
        data.update(root)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def manifest_entry(path: str, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "sha256": file_sha256(path),
        "bytes": os.path.getsize(path),
    }
    if profile is not None:
        entry["profile"] = profile
    return entry


def make_input(tmpdir: str, rows: Optional[List[List[str]]] = None, name: str = "sample.csv") -> str:
    path = os.path.join(tmpdir, name)
    write_csv(path, SYNTHETIC_ROWS if rows is None else rows)
    return path


def make_db(tmpdir: str, rows: Optional[List[List[str]]] = None, name: str = "sample.csv") -> str:
    from spotify_pipeline.ingest import ingest

    input_path = make_input(tmpdir, rows, name=name)
    manifest_path = os.path.join(tmpdir, "manifest.json")
    write_manifest(manifest_path, {name: manifest_entry(input_path)})
    db_path = os.path.join(tmpdir, "state.db")
    report_path = os.path.join(tmpdir, "report.json")
    ingest(input_path, manifest_path, db_path, report_path)
    return db_path


def config_a() -> Dict[str, str]:
    return {
        "model": "synthetic-model",
        "effort": "low",
        "prompt_version": "p1",
        "schema_version": "s1",
    }


def config_b() -> Dict[str, str]:
    return {
        "model": "synthetic-model",
        "effort": "high",
        "prompt_version": "p2",
        "schema_version": "s2",
    }


def completed_item(row_index: int, text: str, **overrides: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "row_index": row_index,
        "topic": "usability",
        "intent": "complaint",
        "sentiment": -0.5,
        "severity": 3,
        "entities": ["app"],
        "evidence_quote": text,
        "needs_review": False,
        "model": "synthetic-model",
        "effort": "low",
        "prompt_version": "p1",
        "schema_version": "s1",
        "request_id": "req-1",
        "provenance": "synthetic_fixture",
        "is_cached": False,
        "cache_source_id": None,
    }
    item.update(overrides)
    return item


def measured_measurements() -> Dict[str, Any]:
    return {
        "status": "measured",
        "provenance": "synthetic_fixture",
        "runs": {
            "cold": {
                "wall_seconds": 100,
                "enrichment_calls": 10,
                "api_units": {
                    "uncached_input_tokens": "1000",
                    "cached_input_tokens": "0",
                    "output_tokens": "500",
                },
                "fixed_api_units": {"request_count": "1"},
                "local": {"compute_seconds": "50"},
            },
            "warm": {
                "wall_seconds": 60,
                "enrichment_calls": 0,
                "api_units": {
                    "uncached_input_tokens": "0",
                    "cached_input_tokens": "0",
                    "output_tokens": "0",
                },
                "fixed_api_units": {},
                "local": {"compute_seconds": "50"},
            },
        },
    }


def measured_rates() -> Dict[str, Any]:
    return {
        "currency": "USD",
        "as_of": "2026-10-01",
        "source": "https://example.invalid/rates",
        "api": {
            "uncached_input_tokens": {"price": "0.001", "unit": "per_1k_tokens"},
            "cached_input_tokens": {"price": "0.0005", "unit": "per_1k_tokens"},
            "output_tokens": {"price": "0.002", "unit": "per_1k_tokens"},
            "request_count": {"price": "0.01", "unit": "per_call"},
        },
        "local": {"compute_seconds": {"price": "0.0001", "unit": "per_second"}},
    }


def scenario() -> Dict[str, Any]:
    return {
        "currency": "USD",
        "budget_ceiling_usd": "49.99",
        "concurrency": 1,
        "target_records": 660622,
        "nonempty_records": 660609,
        "distinct_texts": 484189,
        "limits": {"max_workers": 1, "output_token_cap": 100, "fallback_cap": 2},
        "assumptions": None,
    }

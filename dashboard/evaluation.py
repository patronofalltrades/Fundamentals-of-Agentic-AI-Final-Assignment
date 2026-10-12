"""Save a golden-set evaluation report (the course checker's ``score_gold`` JSON) for the dashboard.

The report scores one classifier against a human-labelled benchmark. The dashboard shows its
agreement next to the saved labels, so the report must name the same classifier:

- The report must carry ``label_configs``. Every entry must equal the single ``label_config`` that
  the dashboard database holds for its loaded configuration. Otherwise the import stops.
- Agreement values are numbers from 0 to 1, or null. ``approved_cases`` is an integer of 1 or more.

Only summary fields are saved, in ``dashboard_meta`` under ``evaluation:<label-set>``. Per-case
results and review IDs are not saved. An identical report gives ``unchanged``. A different report
for the same label set replaces the saved one (``replaced``): evaluations are diagnostics and can
be refreshed. No model call happens here. The report file is only read.
"""

import json
import re
from typing import Any, Dict

from .analysis import _identity
from .bundle import _upsert_meta

LABEL_SET = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
AGREEMENT_KEYS = ("topic", "intent", "severity", "joint")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
KEY_PREFIX = "evaluation:"


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _count(value: Any, minimum: int) -> bool:
    return type(value) is int and value >= minimum


def _label_config(backend) -> str:
    config_hash = _identity(backend)["config_hash"]
    values = [r[0] for r in backend.execute(
        "SELECT DISTINCT label_config FROM classifications WHERE config_hash=?", (config_hash,))]
    if len(values) != 1 or not isinstance(values[0], str) or not values[0]:
        raise ValueError("database has no single label_config for its loaded configuration")
    return values[0]


def evaluation_record(report: Dict[str, Any], label_set: str, label_config: str) -> Dict[str, Any]:
    """Check ``report`` and return only the fields the dashboard saves."""
    if not isinstance(label_set, str) or not LABEL_SET.fullmatch(label_set):
        raise ValueError("label set must be a short lowercase identifier, such as original or adjudicated")
    if not isinstance(report, dict):
        raise ValueError("evaluation report must be a JSON object")
    configs = report.get("label_configs")
    if not isinstance(configs, list) or not configs:
        raise ValueError("evaluation report has no label_configs; it cannot be matched to these labels")
    if any(config != label_config for config in configs):
        raise ValueError("evaluation report scores a different classifier (label_config differs from the dashboard)")
    agreement = report.get("agreement")
    if not isinstance(agreement, dict) or set(agreement) != set(AGREEMENT_KEYS):
        raise ValueError("agreement must have exactly topic, intent, severity and joint")
    if any(v is not None and not (_number(v) and 0 <= v <= 1) for v in agreement.values()):
        raise ValueError("agreement values must be numbers from 0 to 1, or null")
    if not _count(report.get("approved_cases"), 1):
        raise ValueError("approved_cases must be an integer of 1 or more")
    if not _count(report.get("total_cases"), report["approved_cases"]):
        raise ValueError("total_cases must be an integer not below approved_cases")
    if not _count(report.get("missing_or_invalid_predictions"), 0) \
            or report["missing_or_invalid_predictions"] > report["approved_cases"]:
        raise ValueError("missing_or_invalid_predictions must be an integer from 0 to approved_cases")
    mae = report.get("severity_mae_on_valid_predictions")
    if mae is not None and not (_number(mae) and mae >= 0):
        raise ValueError("severity_mae_on_valid_predictions must be a number of 0 or more, or null")
    version, digest = report.get("benchmark_version"), report.get("benchmark_sha256")
    if not isinstance(version, str) or not version.strip() or not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("benchmark_version and a lowercase hex benchmark_sha256 are required")
    if not isinstance(report.get("official"), bool):
        raise ValueError("official must be true or false")
    return {"label_set": label_set, "benchmark_version": version, "benchmark_sha256": digest,
            "approved_cases": report["approved_cases"], "total_cases": report["total_cases"],
            "missing_or_invalid_predictions": report["missing_or_invalid_predictions"],
            "agreement": {key: agreement[key] for key in AGREEMENT_KEYS},
            "severity_mae_on_valid_predictions": mae, "official": report["official"], "label_config": label_config}


def load_evaluation(backend, report: Dict[str, Any], label_set: str) -> Dict[str, Any]:
    """Check and save one evaluation report. Returns ``saved``, ``replaced`` or ``unchanged``."""
    for table in ("meta", "record_state", "classifications", "dashboard_meta"):
        if not backend.table_exists(table):
            raise ValueError("database is not a loaded dashboard database")
    record = evaluation_record(report, label_set, _label_config(backend))
    value = json.dumps(record, separators=(",", ":"), sort_keys=True, allow_nan=False)
    key = KEY_PREFIX + label_set
    row = backend.execute("SELECT value FROM dashboard_meta WHERE key=?", (key,)).fetchone()
    if row and row[0] == value:
        result = "unchanged"
    else:
        backend.run_batch([_upsert_meta("dashboard_meta", key, value)])
        result = "replaced" if row else "saved"
    return {"result": result, "label_set": label_set, "approved_cases": record["approved_cases"],
            "agreement": record["agreement"]}

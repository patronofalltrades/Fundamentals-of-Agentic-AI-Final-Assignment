"""Offline cost scaffold.

No paid execution exists here. This module replays saved measurements with
editable dated rates. Missing measurements, stages, wall time or rates stay
unresolved and never grant approval to scale. All money arithmetic uses
Decimal. Projections are not implemented; this is a scaffold.

Billing items are nonoverlapping: ``uncached_input_tokens``,
``cached_input_tokens`` and ``output_tokens`` for variable API work, plus a
single fixed call item. A legacy ``input_tokens`` total is rejected as
ambiguous.
"""

import json
import math
import os
import tempfile
import urllib.parse
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from .errors import CostError
from .jsonutil import load_strict

BUDGET_HARD_CEILING = Decimal("50")
SYNTHETIC_PROVENANCE = "synthetic_fixture"
MEASUREMENT_STATUSES = ("not_measured", "synthetic_fixture", "measured")

VARIABLE_API_KEYS = ("uncached_input_tokens", "cached_input_tokens", "output_tokens")
FIXED_API_KEYS = ("request_count", "call_count")
LOCAL_KEYS = ("compute_seconds",)
AMBIGUOUS_API_KEYS = ("input_tokens", "total_input_tokens", "total_tokens")

_UNIT_DIVISORS = {
    "per_token": Decimal(1),
    "per_1k_tokens": Decimal(1000),
    "per_1m_tokens": Decimal(1000000),
    "per_call": Decimal(1),
    "per_request": Decimal(1),
    "per_second": Decimal(1),
    "per_minute": Decimal(60),
    "per_hour": Decimal(3600),
}


def _to_decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise CostError("%s must be a number, got %r" % (label, value))
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise CostError("%s is not a valid decimal: %r" % (label, value)) from exc
    if not decimal_value.is_finite():
        raise CostError("%s must be finite, got %r" % (label, value))
    return decimal_value


def _require_nonnegative(value: Any, label: str) -> Decimal:
    decimal_value = _to_decimal(value, label)
    if decimal_value < 0:
        raise CostError("%s must not be negative" % label)
    return decimal_value


def _validate_currency(currency: Any) -> str:
    if not isinstance(currency, str) or currency.upper() != "USD":
        raise CostError("currency must be USD, got %r" % (currency,))
    return "USD"


def _validate_source_url(source: Any) -> None:
    if not isinstance(source, str) or not source.strip():
        raise CostError("rates.source must be a nonempty URL when a price is set")
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise CostError("rates.source must be a real http(s) URL, got %r" % source)


def _validate_rates(rates: Dict[str, Any]) -> str:
    currency = _validate_currency(rates.get("currency"))
    api_rates = rates.get("api")
    local_rates = rates.get("local")
    if api_rates is None:
        api_rates = {}
    if local_rates is None:
        local_rates = {}
    if not isinstance(api_rates, dict):
        raise CostError("rates.api must be an object")
    if not isinstance(local_rates, dict):
        raise CostError("rates.local must be an object")

    allowed_api = set(VARIABLE_API_KEYS) | set(FIXED_API_KEYS)
    for key in api_rates:
        if key not in allowed_api:
            raise CostError("rates.api has an unsupported item %r" % key)
    for key in local_rates:
        if key not in LOCAL_KEYS:
            raise CostError("rates.local has an unsupported item %r" % key)

    has_price = False
    for group in (api_rates, local_rates):
        for item, entry in group.items():
            if entry is None:
                continue
            if not isinstance(entry, dict):
                raise CostError("rate entries must be objects or null")
            price = entry.get("price")
            if price is None:
                continue
            has_price = True
            unit = entry.get("unit")
            if unit not in _UNIT_DIVISORS:
                raise CostError("rate unit is unknown: %r" % (unit,))
            allowed_units = (
                {"per_token", "per_1k_tokens", "per_1m_tokens"}
                if item in VARIABLE_API_KEYS
                else {"per_call", "per_request"}
                if item in FIXED_API_KEYS
                else {"per_second", "per_minute", "per_hour"}
            )
            if unit not in allowed_units:
                raise CostError("rate unit does not match billing item %r" % item)
            if _require_nonnegative(price, "rate price") < 0:
                raise CostError("rate price must not be negative")
    if has_price:
        _validate_source_url(rates.get("source"))
        as_of = rates.get("as_of")
        if not isinstance(as_of, str) or not as_of.strip():
            raise CostError("rates.as_of is required when any price is set")
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise CostError("rates.as_of must be an ISO date") from exc
    return currency


def _validate_measurements(measurements: Dict[str, Any]) -> None:
    status = measurements.get("status")
    if status not in MEASUREMENT_STATUSES:
        raise CostError(
            "measurements.status must be one of %r" % (MEASUREMENT_STATUSES,)
        )
    provenance = measurements.get("provenance")
    if provenance is not None and not isinstance(provenance, str):
        raise CostError("measurements.provenance must be a string or null")
    runs = measurements.get("runs")
    if runs is None:
        runs = {}
    if not isinstance(runs, dict):
        raise CostError("measurements.runs must be an object")
    for name in ("cold", "warm"):
        run = runs.get(name)
        if run is None:
            continue
        if not isinstance(run, dict):
            raise CostError("measurements.runs.%s must be an object" % name)
        if not run:
            raise CostError(
                "empty %s measurement fixture cannot be marked measured" % name
            )
        if "enrichment_calls" not in run:
            raise CostError("measurements.runs.%s requires enrichment_calls" % name)
        calls = run["enrichment_calls"]
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise CostError("enrichment_calls must be a non-negative integer")


def _validate_cap(value: Any, label: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CostError("%s must be a nonnegative integer or null" % label)
    return value


def _validate_scenario(scenario: Dict[str, Any]) -> Decimal:
    budget = _require_nonnegative(scenario.get("budget_ceiling_usd"), "budget_ceiling_usd")
    if budget <= 0:
        raise CostError("budget_ceiling_usd must be positive")
    if budget >= BUDGET_HARD_CEILING:
        raise CostError("budget_ceiling_usd must be strictly under 50")
    concurrency = scenario.get("concurrency")
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise CostError("concurrency must be a positive integer")
    limits = scenario.get("limits")
    if limits is not None and not isinstance(limits, dict):
        raise CostError("scenario.limits must be an object")
    if isinstance(limits, dict):
        _validate_cap(limits.get("max_workers"), "limits.max_workers")
        _validate_cap(limits.get("output_token_cap"), "limits.output_token_cap")
        _validate_cap(limits.get("fallback_cap"), "limits.fallback_cap")
    _validate_cap(scenario.get("output_token_cap"), "output_token_cap")
    _validate_cap(scenario.get("fallback_cap"), "fallback_cap")
    return budget


def _units_field(run: Dict[str, Any], key: str, name: str) -> Optional[Dict[str, Any]]:
    if key not in run or run[key] is None:
        return None
    value = run[key]
    if not isinstance(value, dict):
        raise CostError("measurements.runs.%s.%s must be an object or null" % (name, key))
    return value


def _reject_ambiguous(api_units: Optional[Dict[str, Any]], fixed_units: Optional[Dict[str, Any]], name: str) -> None:
    if api_units:
        for key in AMBIGUOUS_API_KEYS:
            if key in api_units:
                raise CostError(
                    "%s.api_units uses ambiguous %r; use uncached/cached/output tokens"
                    % (name, key)
                )
    if api_units and fixed_units:
        overlap = set(api_units) & set(fixed_units)
        if overlap:
            raise CostError("%s has duplicate billed items: %r" % (name, sorted(overlap)))
    if fixed_units and "request_count" in fixed_units and "call_count" in fixed_units:
        raise CostError("%s.fixed_api_units has duplicate call items" % name)


def _valid_wall(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(numeric) and numeric >= 0


def _unit_cost(quantity: Any, entry: Any, label: str) -> Optional[Decimal]:
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise CostError("%s rate entry must be an object" % label)
    price = entry.get("price")
    if price is None:
        return None
    unit = entry.get("unit")
    if unit not in _UNIT_DIVISORS:
        raise CostError("%s rate unit is unknown: %r" % (label, unit))
    qty = _require_nonnegative(quantity, "%s quantity" % label)
    price_dec = _require_nonnegative(price, "%s price" % label)
    return qty / _UNIT_DIVISORS[unit] * price_dec


def _sum_costs(units: Optional[Dict[str, Any]], rates: Dict[str, Any], label: str) -> Tuple[Optional[Decimal], bool]:
    if units is None:
        return None, False
    total = Decimal(0)
    known = True
    for key, quantity in units.items():
        cost = _unit_cost(quantity, rates.get(key), "%s.%s" % (label, key))
        if cost is None:
            known = False
        else:
            total += cost
    return (total if known else None), known


def _evaluate_run(run: Dict[str, Any], rates: Dict[str, Any], name: str) -> Dict[str, Any]:
    api_units = _units_field(run, "api_units", name)
    fixed_units = _units_field(run, "fixed_api_units", name)
    local_units = _units_field(run, "local", name)
    _reject_ambiguous(api_units, fixed_units, name)

    api, api_known = _sum_costs(api_units, rates.get("api") or {}, name)
    fixed, fixed_known = _sum_costs(fixed_units, rates.get("api") or {}, "%s.fixed" % name)
    local, local_known = _sum_costs(local_units, rates.get("local") or {}, "%s.local" % name)
    wall_valid = _valid_wall(run.get("wall_seconds"))

    subtotal = None
    if api_known and fixed_known and local_known and wall_valid:
        subtotal = api + fixed + local

    return {
        "wall_seconds": run.get("wall_seconds"),
        "wall_valid": wall_valid,
        "enrichment_calls": run.get("enrichment_calls"),
        "api_subtotal": _decimal_str(api),
        "fixed_api_subtotal": _decimal_str(fixed),
        "local_subtotal": _decimal_str(local),
        "total": _decimal_str(subtotal),
        "api_resolved": api_known,
        "local_resolved": local_known,
    }


def _decimal_str(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.000001")), "f")


def _run_resolved(run: Optional[Dict[str, Any]]) -> bool:
    return bool(
        run
        and run["total"] is not None
        and run["api_resolved"]
        and run["local_resolved"]
        and run["wall_valid"]
    )


def evaluate(
    measurements: Dict[str, Any], rates: Dict[str, Any], scenario: Dict[str, Any]
) -> Dict[str, Any]:
    """Replay saved measurements. Missing data stays unresolved/null."""
    _validate_measurements(measurements)
    currency = _validate_rates(rates)
    budget = _validate_scenario(scenario)

    notes: List[str] = []
    status = measurements.get("status")
    provenance = measurements.get("provenance")
    runs = measurements.get("runs") or {}

    pilot: Dict[str, Any] = {"cold": None, "warm": None}
    warm_calls = None
    for name in ("cold", "warm"):
        run = runs.get(name)
        if run is None:
            notes.append("%s measurements missing; totals unresolved" % name)
            continue
        if name == "warm" and run.get("enrichment_calls") != 0:
            raise CostError("verified warm data must have zero enrichment calls")
        evaluated = _evaluate_run(run, rates, name)
        pilot[name] = evaluated
        if name == "warm":
            warm_calls = run.get("enrichment_calls")
        if not _run_resolved(evaluated):
            notes.append("%s run is incomplete; totals unresolved" % name)

    if status == "not_measured":
        report_status = "not_measured"
    elif status == "synthetic_fixture" or provenance == SYNTHETIC_PROVENANCE:
        report_status = "synthetic_fixture"
    else:
        report_status = "measured"

    resolved_real = (
        report_status == "measured"
        and _run_resolved(pilot["cold"])
        and _run_resolved(pilot["warm"])
    )
    if report_status == "measured" and not resolved_real:
        report_status = "unresolved"
    if not resolved_real:
        notes.append("no genuine measured pilot; no approval to scale")

    return {
        "status": report_status,
        "currency": currency,
        "budget_ceiling_usd": _decimal_str(budget),
        "pilot": pilot,
        "warm_enrichment_calls": warm_calls,
        "projection": {
            "status": "not_implemented",
            "base": None,
            "conservative": None,
            "note": "Projections are not implemented in this offline scaffold.",
        },
        "approved_to_scale": False,
        "notes": notes,
        "disclaimer": (
            "Offline scaffold only. No paid execution command exists, no human "
            "approval is recorded, and this is not proven live spend control."
        ),
    }


def admit(
    spent: Any,
    reserved: Any,
    next_cost: Any,
    scenario: Dict[str, Any],
    workers: Optional[int] = None,
    output_tokens: Optional[int] = None,
    fallback_calls: Optional[int] = None,
) -> Dict[str, Any]:
    """Offline spend-control admission check. Not proven live control."""
    budget = _validate_scenario(scenario)
    spent_d = _require_nonnegative(spent, "spent")
    reserved_d = _require_nonnegative(reserved, "reserved")
    next_d = _require_nonnegative(next_cost, "next_cost")

    limits = scenario.get("limits") or {}
    reasons: List[str] = []
    if workers is not None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise CostError("workers must be a positive integer")
        cap = limits.get("max_workers", scenario.get("concurrency"))
        if not isinstance(cap, int) or isinstance(cap, bool):
            reasons.append("max_workers cap is unset; admission blocked")
        elif workers > cap:
            reasons.append("workers %d exceeds cap %d" % (workers, cap))
    if output_tokens is not None:
        if isinstance(output_tokens, bool) or not isinstance(output_tokens, int) or output_tokens < 0:
            raise CostError("output_tokens must be a nonnegative integer")
        cap = limits.get("output_token_cap")
        if not isinstance(cap, int) or isinstance(cap, bool):
            reasons.append("output_token_cap is unset; admission blocked")
        elif output_tokens > cap:
            reasons.append("output tokens %d exceeds cap %d" % (output_tokens, cap))
    if fallback_calls is not None:
        if isinstance(fallback_calls, bool) or not isinstance(fallback_calls, int) or fallback_calls < 0:
            raise CostError("fallback_calls must be a nonnegative integer")
        cap = limits.get("fallback_cap")
        if not isinstance(cap, int) or isinstance(cap, bool):
            reasons.append("fallback_cap is unset; admission blocked")
        elif fallback_calls > cap:
            reasons.append("fallback calls %d exceeds cap %d" % (fallback_calls, cap))

    projected = spent_d + reserved_d + next_d
    if projected > budget:
        reasons.append(
            "projected spend %s exceeds budget %s"
            % (_decimal_str(projected), _decimal_str(budget))
        )

    return {
        "admitted": not reasons,
        "human_approval": False,
        "projected_spend_usd": _decimal_str(projected),
        "budget_ceiling_usd": _decimal_str(budget),
        "reasons": reasons,
    }


def load_measurements(path: str) -> Dict[str, Any]:
    return _as_object(load_strict(path), "measurements")


def load_rates(path: str) -> Dict[str, Any]:
    return _as_object(load_strict(path), "rates")


def load_scenario(path: str) -> Dict[str, Any]:
    return _as_object(load_strict(path), "scenario")


def _as_object(data: Any, label: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise CostError("%s file must contain a JSON object" % label)
    return data


def write_report(payload: Dict[str, Any], path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=directory or ".", prefix=".cost-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

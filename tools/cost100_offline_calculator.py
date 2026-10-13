"""Recalculate the saved cost-100 pilot and estimate a full run, without credentials or network calls.

Measured part: every pilot call is billed again from its saved usage and the editable dated rates.
Estimated part: each stage is scaled by its own work count, using that stage's measured tokens and seconds
per unit of work. The memo is one-time work and is not scaled. Assumptions are in an editable scenario file
(``cost/scenario_full.json``). Changing the scenario never changes the measured results.
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
import json
from pathlib import Path

NUSD = Decimal(1000)              # nanodollars per (token x US$ per million tokens)
STAGES = ("label", "evidence", "verify", "group", "memo")
ONE_TIME = ("memo",)


def nanodollars(input_tokens, output_tokens, input_rate, output_rate):
    amount = (Decimal(input_tokens) * Decimal(input_rate) +
              Decimal(output_tokens) * Decimal(output_rate)) * NUSD
    return int(amount.to_integral_value(rounding=ROUND_UP))


def _provider(call):
    if call["provider"] == "TypeSafe":
        return "jev"
    if call["provider"] == "deepinfra/bf16":
        return "deepinfra"
    raise ValueError("unrecognized route")


def _stage(call):
    return ("label" if call["request_id"].startswith("jev:") else
            "evidence" if call["request_id"].startswith("evidence:") else call["role"])


def _units(call):
    if isinstance(call.get("review_ids"), list):
        return len(call["review_ids"])
    if type(call.get("review_count")) is int:
        return call["review_count"]
    raise ValueError("call has neither review_ids nor review_count")


def _usd(nusd):
    return str((Decimal(nusd) / Decimal(10) ** 9).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _load(folder, rates_file):
    folder = Path(folder)
    rates = json.loads(Path(rates_file or folder / "rates.json").read_text())
    saved = json.loads((folder / "report.json").read_text())
    calls = [json.loads(line) for line in (folder / "pilot_calls.jsonl").read_text().splitlines()]
    if rates.get("currency") != "USD" or not rates.get("as_of") or len(calls) != saved["calls"]:
        raise ValueError("rates or saved call count invalid")
    return rates, saved, calls


def stage_profile(calls, rates):
    """Per stage: provider, model, settings, calls, outcomes, work units, tokens, seconds and billed cost."""
    stages = {}
    for call in calls:
        if any(type(call.get(k)) is not int or call[k] < 0 for k in ("input_tokens", "output_tokens")):
            raise ValueError("missing real usage")
        provider = _provider(call)
        s = stages.setdefault(_stage(call), {
            "provider": call["provider"], "model": call["model"], "label_config": call.get("label_config"),
            "rate_key": provider, "calls": 0, "outcomes": {}, "units": 0, "max_batch": 0,
            "input_tokens": 0, "output_tokens": 0, "seconds": 0.0, "nusd": 0})
        n = _units(call)
        s["calls"] += 1
        s["outcomes"][call["outcome"]] = s["outcomes"].get(call["outcome"], 0) + 1
        s["units"] += n
        s["max_batch"] = max(s["max_batch"], n)
        s["input_tokens"] += call["input_tokens"]
        s["output_tokens"] += call["output_tokens"]
        s["seconds"] += call.get("elapsed_seconds") or 0.0
        s["nusd"] += nanodollars(call["input_tokens"], call["output_tokens"],
                                 rates[provider + "_input_usd_per_million"], rates[provider + "_output_usd_per_million"])
    return stages


def _work(scenario, case, records):
    """Work units for each stage in one case. ``records`` is the projected source-row count."""
    empty = scenario["empty_texts"]
    if records == scenario["projected_records"]:
        nonempty, distinct = records - empty, scenario["distinct_nonempty_texts"]
    else:  # keep the full corpus's distinct-text share
        nonempty = max(records - empty, 0)
        share = Decimal(scenario["distinct_nonempty_texts"]) / Decimal(scenario["projected_records"] - empty)
        distinct = int((Decimal(nonempty) * share).to_integral_value(rounding=ROUND_UP))
    texts = distinct if case["exact_text_reuse"] else nonempty
    retry = Decimal(case["retry_fraction"])
    return {"label": Decimal(texts) * (1 + retry),
            "evidence": Decimal(texts) * (1 + retry + Decimal(case["fallback_fraction"]) * Decimal(case["fallback_cost_multiplier"])),
            "verify": Decimal(texts) * Decimal(case["verify_fraction"]),
            "group": Decimal(nonempty) * Decimal(case["complaint_fraction"]),
            "memo": Decimal(case["memo_calls"])}, {"nonempty": nonempty, "texts_sent": texts, "quarantined_empty": empty}


def estimate(stages, rates, scenario, records):
    """Base and conservative estimates, each with and without exact-text reuse."""
    budget = Decimal(scenario["budget_usd"]) * Decimal(10) ** 9
    out = []
    for name, case in scenario["cases"].items():
        for reuse in (True, False):
            case_r = dict(case, exact_text_reuse=reuse)
            work, counts = _work(scenario, case_r, records)
            growth = Decimal(case["output_token_growth"])
            nusd, seconds, by_stage = Decimal(0), Decimal(0), {}
            for stage in STAGES:
                s = stages[stage]
                per = Decimal(1) / (Decimal(s["calls"]) if stage in ONE_TIME else Decimal(s["units"]))
                in_tok = Decimal(s["input_tokens"]) * per * work[stage]
                out_tok = Decimal(s["output_tokens"]) * per * work[stage] * growth
                cap = scenario.get("output_token_cap_per_unit")
                if cap is not None and stage not in ONE_TIME:
                    out_tok = min(out_tok, Decimal(cap) * work[stage])
                cost = (in_tok * Decimal(rates[s["rate_key"] + "_input_usd_per_million"]) +
                        out_tok * Decimal(rates[s["rate_key"] + "_output_usd_per_million"])) * NUSD
                secs = Decimal(str(s["seconds"])) * per * work[stage]
                if stage not in ONE_TIME:
                    secs /= Decimal(case["max_concurrency"])
                nusd += cost; seconds += secs
                by_stage[stage] = _usd(cost)
            total = int(nusd.to_integral_value(rounding=ROUND_UP))
            out.append({"case": name, "exact_text_reuse": reuse, **counts,
                        "api_usd": _usd(total), "api_usd_by_stage": by_stage,
                        "elapsed_hours_modeled": str((seconds / 3600).quantize(Decimal("0.1"))),
                        "max_concurrency": case["max_concurrency"],
                        "over_budget": total > budget,
                        "warning": ("exceeds the declared budget of US$%s" % scenario["budget_usd"]) if total > budget else None})
    return out


def calculate(folder, rates_file=None, projected_records=100, scenario_file=None):
    if type(projected_records) is not int or projected_records < 0:
        raise ValueError("projected record count must be a nonnegative integer")
    rates, saved, calls = _load(folder, rates_file)
    if saved["rows"] != 100 or saved["completed"] + saved["failed_records"] != 100:
        raise ValueError("pilot row accounting invalid")
    stages = stage_profile(calls, rates)
    counted = sum(s["nusd"] for s in stages.values())
    measured = {"rows": 100, "completed": saved["completed"], "failed": saved["failed_records"],
        "calls": len(calls), "worker_limit": 1,
        "api_nusd_at_editable_rates": counted,
        "by_role_nusd": {k: s["nusd"] for k, s in stages.items()},
        "recorded_api_nusd": saved["actual_charged_nusd"],
        "usd_per_1000_input_rows": _usd(counted * 10),
        "usd_per_completed_record": _usd(counted // saved["completed"]),
        "stages": {k: {"provider": s["provider"], "model": s["model"], "label_config": s["label_config"],
                       "calls": s["calls"], "outcomes": s["outcomes"], "work_units": s["units"],
                       "max_batch": s["max_batch"], "input_tokens": s["input_tokens"],
                       "output_tokens": s["output_tokens"], "request_seconds": round(s["seconds"], 3)}
                   for k, s in stages.items()},
        "cold_active_stage_seconds": saved["cold_active_stage_seconds"],
        "cold_wall_including_interruptions_seconds": saved["cold_end_to_end_wall_seconds"],
        "warm_seconds": saved["warm_seconds"]}
    result = {"measured": measured, "rates_as_of": rates["as_of"], "currency": "USD", "local_compute_cost": None}
    if scenario_file is None:
        result["scenario"] = {"projected_records": projected_records,
            "projection_status": "pass --scenario cost/scenario_full.json for full-run estimates"}
        return result
    scenario = json.loads(Path(scenario_file).read_text())
    records = projected_records if projected_records != 100 else scenario["projected_records"]
    result["scenario"] = {"projected_records": records, "budget_usd": scenario["budget_usd"],
        "projection_status": "estimate", "estimates": estimate(stages, rates, scenario, records),
        "notes": scenario.get("notes", [])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pilot", default="cost/pilot")
    parser.add_argument("--rates")
    parser.add_argument("--scenario", help="editable full-run assumptions, e.g. cost/scenario_full.json")
    parser.add_argument("--projected-records", type=int, default=100,
                        help="source rows to project; with --scenario the default is the scenario's count")
    args = parser.parse_args()
    print(json.dumps(calculate(args.pilot, args.rates, args.projected_records, args.scenario), sort_keys=True, indent=1))


if __name__ == "__main__":
    main()

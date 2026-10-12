"""Recalculate the saved cost-100 pilot without credentials or network calls."""

import argparse
from decimal import Decimal, ROUND_UP
import json
from pathlib import Path


def nanodollars(input_tokens, output_tokens, input_rate, output_rate):
    amount = (Decimal(input_tokens) * Decimal(input_rate) +
              Decimal(output_tokens) * Decimal(output_rate)) * Decimal(1000)
    return int(amount.to_integral_value(rounding=ROUND_UP))


def calculate(folder, rates_file=None, projected_records=100):
    folder = Path(folder)
    if type(projected_records) is not int or projected_records < 0:
        raise ValueError("projected record count must be a nonnegative integer")
    rates = json.loads(Path(rates_file or folder / "rates.json").read_text())
    saved = json.loads((folder / "report.json").read_text())
    calls = [json.loads(line) for line in (folder / "pilot_calls.jsonl").read_text().splitlines()]
    if rates.get("currency") != "USD" or not rates.get("as_of") or len(calls) != saved["calls"]:
        raise ValueError("rates or saved call count invalid")
    totals = {}; counted = 0
    for call in calls:
        provider = "jev" if call["provider"] == "TypeSafe" else "deepinfra"
        if provider == "deepinfra" and call["provider"] != "deepinfra/bf16":
            raise ValueError("unrecognized route")
        if any(type(call.get(k)) is not int or call[k] < 0 for k in ("input_tokens", "output_tokens")):
            raise ValueError("missing real usage")
        bill = nanodollars(call["input_tokens"], call["output_tokens"],
            rates[provider + "_input_usd_per_million"], rates[provider + "_output_usd_per_million"])
        stage = ("label" if call["request_id"].startswith("jev:") else
                 "evidence" if call["request_id"].startswith("evidence:") else call["role"])
        totals[stage] = totals.get(stage, 0) + bill
        counted += bill
    if saved["rows"] != 100 or saved["completed"] + saved["failed_records"] != 100:
        raise ValueError("pilot row accounting invalid")
    return {"measured": {"rows": 100, "completed": saved["completed"],
        "failed": saved["failed_records"], "calls": len(calls),
        "api_nusd_at_editable_rates": counted, "by_role_nusd": totals,
        "recorded_api_nusd": saved["actual_charged_nusd"],
        "cold_active_stage_seconds": saved["cold_active_stage_seconds"],
        "cold_wall_including_interruptions_seconds": saved["cold_end_to_end_wall_seconds"],
        "warm_seconds": saved["warm_seconds"]},
        "scenario": {"projected_records": projected_records,
            "projection_status": "unavailable_until_stage_specific_scaling_assumptions"},
        "rates_as_of": rates["as_of"], "currency": "USD",
        "local_compute_cost": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", default="cost/pilot")
    parser.add_argument("--rates")
    parser.add_argument("--projected-records", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(calculate(args.pilot, args.rates, args.projected_records), sort_keys=True))


if __name__ == "__main__":
    main()

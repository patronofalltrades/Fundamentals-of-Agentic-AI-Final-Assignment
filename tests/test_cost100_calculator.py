"""Offline cost-100 calculator on the committed pilot copy (cost/pilot). No credentials or network."""

import json
from decimal import Decimal
import tempfile
import unittest
from pathlib import Path

from tools.cost100_offline_calculator import calculate

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "cost" / "pilot"
SCENARIO = ROOT / "cost" / "scenario_full.json"


def _estimates(result):
    return {(e["case"], e["exact_text_reuse"]): e for e in result["scenario"]["estimates"]}


class Cost100CalculatorTests(unittest.TestCase):
    def test_recomputes_the_recorded_charge(self):
        result = calculate(PILOT)["measured"]
        self.assertEqual(result["api_nusd_at_editable_rates"], result["recorded_api_nusd"])
        self.assertEqual((result["rows"], result["completed"], result["failed"], result["calls"]), (100, 98, 2, 112))
        self.assertEqual(sum(result["by_role_nusd"].values()), result["api_nusd_at_editable_rates"])

    def test_doubling_rates_doubles_measured_and_estimated_api_cost(self):
        rates = json.loads((PILOT / "rates.json").read_text())
        doubled = {k: (str(Decimal(v) * 2) if k.endswith("_per_million") else v) for k, v in rates.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rates.json"
            path.write_text(json.dumps(doubled))
            base, high = calculate(PILOT, scenario_file=SCENARIO), calculate(PILOT, path, scenario_file=SCENARIO)
        self.assertEqual(high["measured"]["api_nusd_at_editable_rates"], 2 * base["measured"]["api_nusd_at_editable_rates"])
        self.assertEqual(high["measured"]["warm_seconds"], base["measured"]["warm_seconds"])
        for key, low in _estimates(base).items():
            high_usd = Decimal(_estimates(high)[key]["api_usd"])
            self.assertLessEqual(abs(high_usd - 2 * Decimal(low["api_usd"])), Decimal("0.000002"))
            self.assertEqual(_estimates(high)[key]["elapsed_hours_modeled"], low["elapsed_hours_modeled"])

    def test_projected_count_never_changes_the_measured_pilot(self):
        small = calculate(PILOT, projected_records=1000, scenario_file=SCENARIO)
        full = calculate(PILOT, scenario_file=SCENARIO)
        self.assertEqual(small["measured"], full["measured"])
        self.assertEqual(full["scenario"]["projected_records"], 660622)
        self.assertLess(Decimal(_estimates(small)[("base", True)]["api_usd"]),
                        Decimal(_estimates(full)[("base", True)]["api_usd"]))

    def test_full_run_accounting_reuse_and_one_time_memo(self):
        estimates = _estimates(calculate(PILOT, scenario_file=SCENARIO))
        reuse, no_reuse = estimates[("base", True)], estimates[("base", False)]
        self.assertEqual((reuse["texts_sent"], no_reuse["texts_sent"]), (484189, 660609))
        self.assertEqual((reuse["nonempty"], reuse["quarantined_empty"]), (660609, 13))
        self.assertLess(Decimal(reuse["api_usd"]), Decimal(no_reuse["api_usd"]))
        small = _estimates(calculate(PILOT, projected_records=1000, scenario_file=SCENARIO))
        self.assertEqual(small[("base", True)]["api_usd_by_stage"]["memo"], reuse["api_usd_by_stage"]["memo"])

    def test_budget_warning(self):
        scenario = json.loads(SCENARIO.read_text())
        scenario["budget_usd"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario.json"
            path.write_text(json.dumps(scenario))
            estimates = calculate(PILOT, scenario_file=path)["scenario"]["estimates"]
        self.assertTrue(all(e["over_budget"] and "US$1" in e["warning"] for e in estimates))

    def test_pilot_ids_when_present_match_the_checkpoints(self):
        records_file = PILOT / "pilot_records.jsonl"
        if not records_file.exists():
            self.skipTest("pilot_records.jsonl not committed")
        records = [json.loads(line) for line in records_file.read_text().splitlines()]
        ids = [r["review_id"] for r in records]
        self.assertEqual((len(ids), len(set(ids))), (100, 100))
        completed = {r["review_id"] for r in records if r["status"] == "completed"}
        after = json.loads((PILOT / "checkpoint_after.json").read_text())["completed_ids"]
        self.assertEqual(set(after), completed)
        self.assertEqual(json.loads((PILOT / "checkpoint_before.json").read_text())["completed_ids"], [])


if __name__ == "__main__":
    unittest.main()

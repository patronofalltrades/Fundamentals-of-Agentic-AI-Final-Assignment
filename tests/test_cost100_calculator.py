"""Offline cost-100 calculator on the committed pilot copy (cost/pilot). No credentials or network."""

import json
from decimal import Decimal
import tempfile
import unittest
from pathlib import Path

from tools.cost100_offline_calculator import calculate

PILOT = Path(__file__).resolve().parents[1] / "cost" / "pilot"


class Cost100CalculatorTests(unittest.TestCase):
    def test_recomputes_the_recorded_charge(self):
        result = calculate(PILOT)["measured"]
        self.assertEqual(result["api_nusd_at_editable_rates"], result["recorded_api_nusd"])
        self.assertEqual((result["rows"], result["completed"], result["failed"], result["calls"]), (100, 98, 2, 112))
        self.assertEqual(sum(result["by_role_nusd"].values()), result["api_nusd_at_editable_rates"])

    def test_doubling_rates_doubles_the_charge_and_keeps_measurements(self):
        rates = json.loads((PILOT / "rates.json").read_text())
        doubled = {k: (str(Decimal(v) * 2) if k.endswith("_per_million") else v) for k, v in rates.items()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rates.json"
            path.write_text(json.dumps(doubled))
            base, high = calculate(PILOT)["measured"], calculate(PILOT, path, 100000)
        self.assertEqual(high["measured"]["api_nusd_at_editable_rates"], 2 * base["api_nusd_at_editable_rates"])
        self.assertEqual(high["measured"]["warm_seconds"], base["warm_seconds"])
        self.assertEqual(high["scenario"]["projected_records"], 100000)

    def test_committed_copy_holds_no_review_ids(self):
        for path in PILOT.iterdir():
            text = path.read_text()
            self.assertNotIn("review_ids", text)
            self.assertNotIn("completed_ids", text)


if __name__ == "__main__":
    unittest.main()

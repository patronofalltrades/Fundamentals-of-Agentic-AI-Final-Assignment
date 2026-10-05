"""SYNTHETIC tests for the offline cost scaffold."""

import copy
import unittest
from decimal import Decimal

from spotify_pipeline.cost import admit, evaluate
from spotify_pipeline.errors import CostError

from tests.helpers import measured_measurements, measured_rates, scenario


class MissingCostTests(unittest.TestCase):
    def test_not_measured_is_unresolved(self):
        measurements = {"status": "not_measured", "runs": {"cold": None, "warm": None}}
        rates = measured_rates()
        for group in ("api", "local"):
            for entry in rates[group].values():
                entry["price"] = None
        rates["source"] = None
        rates["as_of"] = None
        report = evaluate(measurements, rates, scenario())
        self.assertEqual(report["status"], "not_measured")
        self.assertIsNone(report["pilot"]["cold"])
        self.assertFalse(report["approved_to_scale"])
        self.assertEqual(report["projection"]["status"], "not_implemented")
        self.assertIsNone(report["projection"]["base"])

    def test_missing_rate_is_null_not_zero(self):
        rates = measured_rates()
        rates["local"]["compute_seconds"]["price"] = None
        report = evaluate(measured_measurements(), rates, scenario())
        self.assertIsNone(report["pilot"]["cold"]["local_subtotal"])
        self.assertIsNone(report["pilot"]["cold"]["total"])
        self.assertEqual(report["status"], "synthetic_fixture")
        self.assertFalse(report["approved_to_scale"])

    def test_omitted_units_are_unknown(self):
        measurements = measured_measurements()
        del measurements["runs"]["cold"]["api_units"]
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertIsNone(report["pilot"]["cold"]["api_subtotal"])
        self.assertIsNone(report["pilot"]["cold"]["total"])
        self.assertFalse(report["pilot"]["cold"]["api_resolved"])

    def test_explicit_empty_units_are_zero(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["enrichment_calls"] = 0
        measurements["runs"]["cold"]["api_units"] = {}
        measurements["runs"]["cold"]["fixed_api_units"] = {}
        measurements["runs"]["cold"]["local"] = {}
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertEqual(report["pilot"]["cold"]["total"], "0.000000")

    def test_positive_calls_need_all_token_usage_components(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["api_units"] = {}
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertIsNone(report["pilot"]["cold"]["api_subtotal"])
        self.assertIsNone(report["pilot"]["cold"]["total"])

        measurements["runs"]["cold"]["api_units"] = {"output_tokens": 50}
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertIsNone(report["pilot"]["cold"]["api_subtotal"])

    def test_empty_fixture_cannot_be_measured(self):
        measurements = {
            "status": "measured",
            "provenance": "synthetic_fixture",
            "runs": {"cold": {}, "warm": {"enrichment_calls": 0}},
        }
        with self.assertRaises(CostError):
            evaluate(measurements, measured_rates(), scenario())


class ValidationTests(unittest.TestCase):
    def test_ambiguous_total_input_rejected(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["api_units"]["input_tokens"] = "5"
        with self.assertRaises(CostError):
            evaluate(measurements, measured_rates(), scenario())

    def test_duplicate_billed_item_rejected(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["fixed_api_units"]["uncached_input_tokens"] = "5"
        with self.assertRaises(CostError):
            evaluate(measurements, measured_rates(), scenario())

    def test_nonfinite_rate_rejected(self):
        rates = measured_rates()
        rates["local"]["compute_seconds"]["price"] = "nan"
        with self.assertRaises(CostError):
            evaluate(measured_measurements(), rates, scenario())

    def test_negative_quantity_rejected(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["local"]["compute_seconds"] = "-5"
        with self.assertRaises(CostError):
            evaluate(measurements, measured_rates(), scenario())

    def test_priced_rate_requires_http_source(self):
        rates = measured_rates()
        rates["source"] = "synthetic-fixture"
        with self.assertRaises(CostError):
            evaluate(measured_measurements(), rates, scenario())

    def test_currency_must_be_usd(self):
        rates = measured_rates()
        rates["currency"] = "EUR"
        with self.assertRaises(CostError):
            evaluate(measured_measurements(), rates, scenario())

    def test_wall_time_must_be_nonnegative_finite(self):
        measurements = measured_measurements()
        measurements["runs"]["cold"]["wall_seconds"] = "-1"
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertIsNone(report["pilot"]["cold"]["total"])
        self.assertFalse(report["pilot"]["cold"]["wall_valid"])

    def test_warm_enrichment_calls_must_be_zero(self):
        measurements = measured_measurements()
        measurements["runs"]["warm"]["enrichment_calls"] = 5
        with self.assertRaises(CostError):
            evaluate(measurements, measured_rates(), scenario())


class CostArithmeticTests(unittest.TestCase):
    def test_measured_arithmetic(self):
        report = evaluate(measured_measurements(), measured_rates(), scenario())
        cold = report["pilot"]["cold"]
        self.assertEqual(cold["api_subtotal"], "0.002000")
        self.assertEqual(cold["fixed_api_subtotal"], "0.010000")
        self.assertEqual(cold["local_subtotal"], "0.005000")
        self.assertEqual(cold["total"], "0.017000")
        self.assertEqual(report["pilot"]["warm"]["total"], "0.005000")
        self.assertEqual(report["status"], "synthetic_fixture")
        self.assertFalse(report["approved_to_scale"])

    def test_doubled_api_rates_double_api_only(self):
        base_rates = measured_rates()
        doubled = copy.deepcopy(base_rates)
        for entry in doubled["api"].values():
            entry["price"] = str(float(entry["price"]) * 2)
        base = evaluate(measured_measurements(), base_rates, scenario())
        doubled_report = evaluate(measured_measurements(), doubled, scenario())
        self.assertEqual(doubled_report["pilot"]["cold"]["api_subtotal"], "0.004000")
        self.assertEqual(
            Decimal(doubled_report["pilot"]["cold"]["api_subtotal"]),
            Decimal(base["pilot"]["cold"]["api_subtotal"]) * 2,
        )
        self.assertEqual(
            base["pilot"]["cold"]["local_subtotal"],
            doubled_report["pilot"]["cold"]["local_subtotal"],
        )
        self.assertEqual(
            base["pilot"]["cold"]["wall_seconds"],
            doubled_report["pilot"]["cold"]["wall_seconds"],
        )

    def test_real_measurement_still_not_approved(self):
        measurements = measured_measurements()
        measurements["provenance"] = "real-provider"
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertEqual(report["status"], "measured")
        self.assertFalse(report["approved_to_scale"])

    def test_projection_is_not_implemented(self):
        measurements = measured_measurements()
        measurements["provenance"] = "real-provider"
        report = evaluate(measurements, measured_rates(), scenario())
        self.assertEqual(report["projection"]["status"], "not_implemented")
        self.assertIsNone(report["projection"]["base"])
        self.assertIsNone(report["projection"]["conservative"])


class SpendControlTests(unittest.TestCase):
    def test_admit_within_budget(self):
        self.assertTrue(admit("40", "5", "4.99", scenario())["admitted"])

    def test_admit_over_budget(self):
        result = admit("40", "5", "5.01", scenario())
        self.assertFalse(result["admitted"])
        self.assertFalse(result["human_approval"])

    def test_budget_must_be_under_50(self):
        bad = scenario()
        bad["budget_ceiling_usd"] = "50.00"
        with self.assertRaises(CostError):
            admit("0", "0", "0", bad)

    def test_worker_and_output_caps(self):
        self.assertFalse(admit("0", "0", "1", scenario(), workers=2)["admitted"])
        self.assertFalse(admit("0", "0", "1", scenario(), output_tokens=101)["admitted"])
        self.assertFalse(admit("0", "0", "1", scenario(), fallback_calls=3)["admitted"])

    def test_unset_caps_block_admission(self):
        unset = scenario()
        unset["limits"] = {"max_workers": 1, "output_token_cap": None, "fallback_cap": None}
        self.assertFalse(admit("0", "0", "1", unset, output_tokens=1)["admitted"])
        self.assertFalse(admit("0", "0", "1", unset, fallback_calls=1)["admitted"])
        no_worker_cap = scenario()
        no_worker_cap["limits"] = {"max_workers": None, "output_token_cap": 100, "fallback_cap": 2}
        self.assertFalse(admit("0", "0", "1", no_worker_cap, workers=1)["admitted"])
        self.assertFalse(admit("0", "0", "1", unset)["admitted"])
        self.assertFalse(admit("0", "0", "1", no_worker_cap)["admitted"])

    def test_bool_and_negative_values_rejected(self):
        with self.assertRaises(CostError):
            admit(True, "0", "0", scenario())
        with self.assertRaises(CostError):
            admit("0", "0", "0", scenario(), workers=True)
        with self.assertRaises(CostError):
            admit("0", "0", "0", scenario(), workers=0)


if __name__ == "__main__":
    unittest.main()

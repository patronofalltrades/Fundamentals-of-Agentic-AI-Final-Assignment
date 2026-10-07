"""Synthetic checks for the saved-pilot comparison boundary."""

import unittest

from tools.compare_jev_pilots import compare


class CompareJevPilotsTests(unittest.TestCase):
    def runs(self):
        label = {"topic": "other", "intent": "praise", "severity": 1,
                 "sentiment": 1.0, "needs_review": True}
        common = {"labels": {"synthetic-id": label}, "results": 1, "attempts": 1,
                  "input_tokens": 1, "output_tokens": 0, "summed_attempt_seconds": 0.5,
                  "usage_derived_cost_usd": "0.003691254", "evidence": {},
                  "meta": {"config_hash": "synthetic"}}
        v1 = {**common, "evidence": {"synthetic-id": {
            "model": "synthetic", "prompt_version": "evidence-extract-v1"}}}
        v2 = {**common, "meta": {"config_hash": "synthetic-2", "cap_nusd": "596308746"},
              "usage_derived_cost_usd": "0.004262454"}
        return v1, v2

    def test_negative_wall_value_is_not_claimed_as_measured(self):
        v1, v2 = self.runs()
        report = compare(v1, v2, "synthetic-hash", {
            "runner_exit_code": 0, "wall_seconds": -0.04})
        self.assertIsNone(report["v2_runner_wall_seconds"])
        self.assertEqual(report["v2_timing_status"], "invalid_negative_or_missing_value")
        self.assertEqual(report["changes"]["v1_evidence_label_compatible_rows"], 1)

    def test_cumulative_cap_is_enforced(self):
        v1, v2 = self.runs()
        v2["meta"]["cap_nusd"] = "600000000"
        with self.assertRaisesRegex(ValueError, "cumulative authorized cap"):
            compare(v1, v2, "synthetic-hash", {"runner_exit_code": 0, "wall_seconds": 1.0})


if __name__ == "__main__":
    unittest.main()

"""Synthetic 25-review payload and metering checks; no provider calls."""

import unittest

from tools import deepinfra_recheck100 as base
from tools import scale100k_batch25 as trial


class Batch25Test(unittest.TestCase):
    def rows(self):
        return [{"review_id": "id" + str(i), "review_text": "review text " + str(i),
            "source_sha256": "sha" + str(i), "labels": {
                "topic": "other", "intent": "praise", "severity": 1,
                "sentiment": 0.5}} for i in range(25)]

    def test_full_bound_strict_schema_and_cache_version_differ_from_ten(self):
        body = trial.payload(self.rows())
        self.assertEqual(body["max_tokens"], 12288)
        self.assertEqual(body["response_format"]["json_schema"]["schema"]
            ["properties"]["results"]["minItems"], 25)
        self.assertEqual(body["provider"], {"only": [base.PROVIDER],
            "allow_fallbacks": False, "require_parameters": True,
            "data_collection": "deny", "zdr": True})
        self.assertNotEqual(trial.config_sha(), base.config_sha())
        self.assertGreater(trial.reservation_nusd(), base.reservation_nusd())
        tail = trial.payload(self.rows()[:24])
        self.assertEqual(tail["response_format"]["json_schema"]["schema"]
            ["properties"]["results"]["maxItems"], 24)
        self.assertNotEqual(trial.config_for_size(24), trial.config_sha())
        self.assertRaises(ValueError, trial.payload, [])

    def test_exact_ids_spans_and_usage_including_reasoning(self):
        rows = self.rows()
        items = [{"review_id": r["review_id"], "entities": [],
            "evidence_quote": r["review_text"]} for r in rows]
        response = {"id": "synthetic-generation", "model": base.MODEL,
            "provider": "DeepInfra", "usage": {"prompt_tokens": 1000,
            "completion_tokens": 5000,
            "completion_tokens_details": {"reasoning_tokens": 3500}},
            "choices": [{"finish_reason": "stop", "message": {
                "content": base.canonical({"results": items})}}]}
        self.assertEqual(len(trial.inspect(response, rows)[0]), 25)
        self.assertEqual(trial.measured_usage(response)[2], 3500)
        items[0]["review_id"] = "id1"
        response["choices"][0]["message"]["content"] = base.canonical({"results": items})
        self.assertRaises(ValueError, trial.inspect, response, rows)
        response["usage"]["completion_tokens"] = 12289
        self.assertRaises(ValueError, trial.measured_usage, response)


if __name__ == "__main__":
    unittest.main()

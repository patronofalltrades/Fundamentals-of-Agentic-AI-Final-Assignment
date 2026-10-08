"""Offline synthetic checks for the separately versioned repair pilot."""

import json
import unittest

from spotify_pipeline.contract import text_sha256
from tools import deepinfra_recheck100 as pilot


def rows():
    return [{"review_id": "synthetic-%02d" % i,
        "review_text": "Playback stops on phone %d." % i,
        "source_sha256": "a" * 64,
        "text_sha256": text_sha256("Playback stops on phone %d." % i),
        "labels": {"topic": "playback", "intent": "complaint",
            "severity": 3, "sentiment": -0.5}} for i in range(10)]


def response(items):
    return {"id": "synthetic-generation", "provider": "DeepInfra",
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500,
            "completion_tokens_details": {"reasoning_tokens": 100}},
        "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"results": items})}}]}


class Recheck100Test(unittest.TestCase):
    def test_pinned_payload_and_full_reservation(self):
        body = pilot.payload(rows())
        self.assertEqual(body["model"], "openai/gpt-oss-120b")
        self.assertEqual(body["provider"], {"only": ["deepinfra/bf16"],
            "allow_fallbacks": False, "require_parameters": True,
            "data_collection": "deny", "zdr": True})
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["response_format"]["json_schema"]["schema"]["properties"]
            ["results"]["minItems"], 10)
        self.assertEqual(pilot.reservation_nusd(), 5_545_984)
        self.assertNotEqual(pilot.config_sha(), "")

    def test_strict_id_and_exact_spans_with_per_row_quarantine(self):
        items = [{"review_id": r["review_id"], "entities": ["Playback"],
            "evidence_quote": "Playback stops"} for r in rows()]
        saved = response(items)
        inp, out, reasoning, charge = pilot.measured_usage(saved)
        self.assertEqual((inp, out, reasoning), (1000, 500, 100))
        self.assertLess(charge, pilot.reservation_nusd())
        accepted, invalid = pilot.inspect(saved, rows())
        self.assertEqual((len(accepted), len(invalid)), (10, 0))
        items[0]["evidence_quote"] = "paraphrased complaint"
        accepted, invalid = pilot.inspect(response(items), rows())
        self.assertEqual((len(accepted), len(invalid)), (9, 1))
        self.assertIn("evidence quote", invalid["synthetic-00"])
        items[0]["review_id"] = "unknown-id"
        with self.assertRaisesRegex(ValueError, "unknown or repeated source ID"):
            pilot.inspect(response(items), rows())

    def test_missing_usage_or_route_fails_before_settlement(self):
        saved = response([])
        del saved["usage"]
        with self.assertRaisesRegex(ValueError, "usage missing"):
            pilot.measured_usage(saved)
        saved = response([])
        saved["provider"] = "OtherProvider"
        with self.assertRaisesRegex(ValueError, "route"):
            pilot.measured_usage(saved)


if __name__ == "__main__":
    unittest.main()

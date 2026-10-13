import json
import unittest

from spotify_pipeline import deepinfra_batch as batch


def fixture(count):
    rows = [{"review_id": "synthetic-" + str(i),
        "review_text": "Complaint about premium access number " + str(i),
        "review_rating": "2", "review_likes": "0", "app_version": "",
        "review_timestamp": "2023-01-01 00:00:00"} for i in range(count)]
    labels = {r["review_id"]: {"topic": "billing", "intent": "complaint",
        "severity": 3, "sentiment": -0.5} for r in rows}
    return rows, labels


class DeepInfraBatchTest(unittest.TestCase):
    def test_25_and_50_strict_source_and_output(self):
        for count in (25, 50):
            rows, labels = fixture(count)
            payload = batch.payload(rows, labels, count)
            self.assertEqual(payload["provider"], {"only": ["deepinfra/bf16"],
                "allow_fallbacks": False, "require_parameters": True,
                "data_collection": "deny", "zdr": True})
            self.assertEqual(payload["response_format"]["json_schema"]["schema"]
                ["properties"]["results"]["minItems"], count)
            self.assertIn("empty entity list", payload["messages"][0]["content"])
            response = {"id": "synthetic-generation", "provider": "DeepInfra",
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                    "results": [{"review_id": r["review_id"], "entities": ["premium access"],
                        "evidence_quote": "premium access"} for r in rows]})}}],
                "usage": {"prompt_tokens": 2000, "completion_tokens": 1000,
                          "completion_tokens_details": {"reasoning_tokens": 400}}}
            accepted, inp, out, reasoning, cost = batch.validate_response(response, rows, count)
            self.assertEqual((len(accepted), inp, out, reasoning), (count, 2000, 1000, 400))
            self.assertEqual(cost, 244000)
            broken = json.loads(response["choices"][0]["message"]["content"])
            broken["results"][-1]["review_id"] = rows[0]["review_id"]
            response["choices"][0]["message"]["content"] = json.dumps(broken)
            with self.assertRaisesRegex(ValueError, "repeated"):
                batch.validate_response(response, rows, count)

    def test_batch_size_changes_cache_identity_and_bound(self):
        self.assertNotEqual(batch.config_sha(25), batch.config_sha(50))
        self.assertNotEqual(batch.config_sha(50, 49), batch.config_sha(50, 50))
        self.assertEqual(batch.reservation_nusd(), 24_903_544)


if __name__ == "__main__":
    unittest.main()

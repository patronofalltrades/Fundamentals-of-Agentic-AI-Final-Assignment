import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "benchmark", Path(__file__).resolve().parents[1] / "tools/openrouter_extractor_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkTest(unittest.TestCase):
    def test_pinned_privacy_schema_and_usage(self):
        row = {"review_id": "synthetic", "review_text": "Spotify playback fails."}
        payload = benchmark.make_payload("deepinfra", row, {
            "topic": "playback", "intent": "complaint", "severity": 4, "sentiment": -0.5})
        self.assertEqual(payload["provider"], {
            "only": ["deepinfra/bf16"], "allow_fallbacks": False,
            "require_parameters": True, "data_collection": "deny", "zdr": True})
        self.assertEqual(payload["response_format"]["json_schema"]["strict"], True)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        response = {"provider": "DeepInfra", "choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"entities": ["Spotify"], "evidence_quote": "playback fails"})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "completion_tokens_details": {"reasoning_tokens": 30}}}
        evidence, inp, out, reasoning, _, _, charge = benchmark.parse_response(response, row, "deepinfra")
        self.assertEqual(evidence["entities"], ["Spotify"])
        self.assertEqual((inp, out, reasoning, charge), (100, 50, 30, 12200))
        response["choices"][0]["message"]["content"] = json.dumps({
            "entities": ["pot"], "evidence_quote": "playback fails"})
        with self.assertRaises(Exception):
            benchmark.parse_response(response, row, "deepinfra")

    def test_reservation_survives_uncertain_and_blocks_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            db = benchmark.connect(str(Path(folder) / "ledger.db"), "synthetic-source")
            row = {"review_id": "synthetic", "review_text": "Spotify playback fails."}
            payload = benchmark.make_payload("groq", row, {
                "topic": "playback", "intent": "complaint", "severity": 4, "sentiment": -0.5})
            benchmark.reserve(db, "groq", row, payload, "synthetic-row")
            self.assertEqual(benchmark.budget_used(db), 29_491_200)
            with self.assertRaises(Exception):
                benchmark.reserve(db, "groq", row, payload, "synthetic-row")
            with self.assertRaises(ValueError):
                benchmark.connect(str(Path(folder) / "ledger.db"), "different-source")

    def test_published_limit_is_required_before_paid_work(self):
        original = benchmark.request_json
        model, tag, input_rate, output_rate = benchmark.ROUTES["deepinfra"]
        listing = {"data": {"endpoints": [{
            "tag": tag, "model_id": model, "status": 0,
            "context_length": 131072, "max_completion_tokens": 117964,
            "pricing": {"prompt": str(input_rate), "completion": str(output_rate)},
            "supported_parameters": ["response_format", "structured_outputs", "reasoning_effort", "max_tokens"]}]}}
        try:
            benchmark.request_json = lambda url: listing
            benchmark.verify_route("deepinfra")
            listing["data"]["endpoints"][0]["max_completion_tokens"] += 1
            with self.assertRaises(ValueError):
                benchmark.verify_route("deepinfra")
        finally:
            benchmark.request_json = original


if __name__ == "__main__":
    unittest.main()

"""Synthetic Jev request and response checks; never call a provider."""

import unittest
import io
from unittest.mock import patch

from spotify_pipeline.config import config_hash
from spotify_pipeline.errors import ValidationError
from spotify_pipeline.jev import (
    JevHTTPError, build_request, check_model_access, combine_with_evidence, enrich_labels,
    label_config, parse_response,
)


def fixture_response():
    return {
        "model": "jev-1.13.0",
        "answers": {
            "topic": {"type": "choice", "choice": "playback", "confidence": 0.9},
            "intent": {"type": "choice", "choice": "complaint", "confidence": 0.8},
            "severity": {"type": "choice", "choice": "3", "confidence": 0.7},
            "sentiment": {"type": "score", "score": 1.5, "confidence": 0.55},
        },
        "usage": {"input_tokens": 410, "output_tokens": 40},
    }


class JevTests(unittest.TestCase):
    def test_request_has_text_only_and_contract_options(self):
        body = build_request("Playback pauses")
        self.assertEqual(body["state"], "Playback pauses")
        self.assertEqual(body["model"], "jev-1.13.0")
        self.assertEqual(set(body["questions"]), {"topic", "intent", "severity", "sentiment"})
        self.assertEqual(set(body["questions"]["severity"]["criteria"]), {"1", "2", "3", "4", "5"})
        self.assertEqual(len(config_hash(label_config())), 64)
        with self.assertRaises(ValidationError):
            build_request(" ")

    def test_response_maps_score_and_flags_low_confidence(self):
        result = parse_response(fixture_response())
        self.assertEqual(result.severity, 3)
        self.assertEqual(result.sentiment, -0.25)
        self.assertTrue(result.needs_review)
        self.assertEqual(result.input_tokens, 410)

    def test_response_rejects_drift_and_bad_usage(self):
        payload = fixture_response()
        payload["model"] = "jev-latest"
        with self.assertRaises(ValidationError):
            parse_response(payload)
        payload = fixture_response()
        payload["usage"]["input_tokens"] = None
        with self.assertRaises(ValidationError):
            parse_response(payload)
        payload = fixture_response()
        payload["answers"]["severity"]["choice"] = "6"
        with self.assertRaises(ValidationError):
            parse_response(payload)

    def test_retry_only_transient_http_once(self):
        calls = []
        def transport(request, key):
            calls.append(request)
            if len(calls) == 1:
                raise JevHTTPError(429, 0)
            return fixture_response()
        result = enrich_labels("Playback pauses", "synthetic-key", transport=transport, sleep=lambda _: None)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_evidence_must_be_exact(self):
        labels = parse_response(fixture_response())
        with self.assertRaises(ValidationError):
            combine_with_evidence(labels, "Playback pauses", [], "playback")
        result = combine_with_evidence(labels, "Playback pauses", [], "Playback")
        self.assertEqual(result["evidence_quote"], "Playback")

    def test_read_only_model_access_gate(self):
        with patch("spotify_pipeline.jev.urllib.request.urlopen", return_value=io.BytesIO(b'{"models":[{"name":"jev-latest"}]}')):
            check_model_access("synthetic-key")
        with patch("spotify_pipeline.jev.urllib.request.urlopen", return_value=io.BytesIO(b'{"models":[]}')):
            with self.assertRaises(ValidationError):
                check_model_access("synthetic-key")


if __name__ == "__main__":
    unittest.main()

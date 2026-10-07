"""Synthetic Jev request and response checks; never call a provider."""

import unittest
import io
from unittest.mock import patch

from spotify_pipeline.config import cache_key, config_hash
from spotify_pipeline.contract import TOPICS
from spotify_pipeline.errors import ValidationError
from spotify_pipeline.jev import (
    JevHTTPError, PROMPT_VERSION, TOPIC_CRITERIA, build_request, check_model_access,
    combine_with_evidence, enrich_labels, label_config, parse_response,
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

    def test_topic_rubric_v2_contains_contract_guidance_in_choice_payload(self):
        topic = build_request("Synthetic review text")["questions"]["topic"]
        self.assertEqual(topic["type"], "choice")
        self.assertEqual(tuple(topic["criteria"]), TOPICS)
        self.assertEqual(topic["criteria"], TOPIC_CRITERIA)
        for phrase in ("highest supported severity", "first specific problem",
                       "first specific praised feature", "Premium mention alone",
                       "Ad interruptions", "loading failures", "missing offline lyrics"):
            self.assertIn(phrase, topic["instructions"])
        for name, phrase in (("usability", "ad interruptions"),
                             ("playback", "crashes"),
                             ("catalog", "recommendations"),
                             ("catalog", "lyrics availability"),
                             ("billing", "premium-only controls"),
                             ("support", "customer service"),
                             ("other", "General praise")):
            self.assertIn(phrase, topic["criteria"][name])

    def test_new_prompt_has_distinct_config_and_exact_text_cache_key(self):
        current = label_config()
        old = {**current, "prompt_version": "jev-rubric-v1"}
        self.assertEqual(PROMPT_VERSION, "jev-rubric-v2")
        self.assertNotEqual(config_hash(current), config_hash(old))
        self.assertNotEqual(cache_key(current, "Synthetic review text"),
                            cache_key(old, "Synthetic review text"))

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

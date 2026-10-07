"""SYNTHETIC tests for the completed/quarantined schema validator."""

import unittest

from spotify_pipeline.schema import (
    validate_cache_reuse,
    validate_completed,
    validate_direct,
    validate_is_cached,
    validate_quarantine,
)


def _record(**overrides):
    record = {
        "status": "completed",
        "review_id": "1",
        "source_sha256": "a" * 64,
        "review_text": "the app keeps crashing",
        "topic": "playback",
        "intent": "complaint",
        "sentiment": -0.4,
        "severity": 4,
        "entities": ["app"],
        "evidence_quote": "keeps crashing",
        "needs_review": False,
        "label_config": "cfg-hash",
    }
    record.update(overrides)
    return record


def _source():
    return {
        "review_id": "1",
        "row_sha256": "a" * 64,
        "review_text": "the app keeps crashing",
    }


class CompletedSchemaTests(unittest.TestCase):
    def test_valid_record_passes(self):
        self.assertEqual(validate_completed(_record()), [])

    def test_valid_record_with_source_passes(self):
        self.assertEqual(validate_completed(_record(), source=_source()), [])

    def test_source_override_rejected(self):
        self.assertTrue(validate_completed(_record(review_id="2"), source=_source()))
        self.assertTrue(validate_completed(_record(source_sha256="b" * 64), source=_source()))
        self.assertTrue(validate_completed(_record(review_text="other"), source=_source()))

    def test_quote_checked_against_source_text(self):
        self.assertEqual(validate_completed(_record(), source=_source()), [])
        bad = _record(evidence_quote="not in source")
        self.assertTrue(validate_completed(bad, source=_source()))

    def test_bool_severity_rejected(self):
        self.assertTrue(validate_completed(_record(severity=True)))

    def test_nan_sentiment_rejected(self):
        self.assertTrue(validate_completed(_record(sentiment=float("nan"))))

    def test_huge_int_sentiment_rejected(self):
        self.assertTrue(validate_completed(_record(sentiment=10 ** 1000)))

    def test_out_of_range_sentiment_rejected(self):
        self.assertTrue(validate_completed(_record(sentiment=1.5)))

    def test_quote_not_substring_rejected(self):
        self.assertTrue(validate_completed(_record(evidence_quote="not in text")))

    def test_bad_source_hash_rejected(self):
        self.assertTrue(validate_completed(_record(source_sha256="xyz")))
        self.assertTrue(validate_completed(_record(source_sha256="+" + "a" * 63)))

    def test_empty_text_cannot_complete(self):
        self.assertTrue(validate_completed(_record(review_text="   ")))

    def test_needs_review_must_be_bool(self):
        self.assertTrue(validate_completed(_record(needs_review=0)))

    def test_bad_topic_and_intent_rejected(self):
        self.assertTrue(validate_completed(_record(topic="nope")))
        self.assertTrue(validate_completed(_record(intent="nope")))

    def test_blank_label_config_rejected(self):
        self.assertTrue(validate_completed(_record(label_config="  ")))


class DirectAndCacheTests(unittest.TestCase):
    def test_direct_requires_request_id_and_provenance(self):
        self.assertEqual(
            validate_direct({"request_id": "req-1", "provenance": "synthetic_fixture"}), []
        )
        self.assertTrue(validate_direct({"request_id": "", "provenance": "synthetic_fixture"}))
        self.assertTrue(validate_direct({"request_id": "req-1", "provenance": "unknown"}))

    def test_direct_rejects_cache_source_id(self):
        self.assertTrue(
            validate_direct(
                {
                    "request_id": "req-1",
                    "provenance": "synthetic_fixture",
                    "cache_source_id": "1",
                }
            )
        )

    def test_is_cached_types(self):
        self.assertEqual(validate_is_cached(True), [])
        self.assertEqual(validate_is_cached(False), [])
        self.assertEqual(validate_is_cached(1), [])
        self.assertEqual(validate_is_cached(0), [])
        self.assertTrue(validate_is_cached("yes"))
        self.assertTrue(validate_is_cached(2))

    def _original(self):
        original = _record()
        original.update(
            {
                "config_hash": "cfg",
                "request_id": "req-1",
                "provenance": "synthetic_fixture",
                "is_cached": False,
                "cache_source_id": None,
            }
        )
        return original

    def test_cache_reuse_valid(self):
        original = self._original()
        target = dict(original)
        target["review_id"] = "2"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertEqual(validate_cache_reuse(target, original, True), [])

    def test_cache_label_config_mismatch_rejected(self):
        original = self._original()
        target = dict(original)
        target["review_id"] = "2"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        target["label_config"] = "different"
        self.assertTrue(validate_cache_reuse(target, original, True))

    def test_cache_self_reference_rejected(self):
        original = self._original()
        target = dict(original)
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, True))

    def test_cache_chain_rejected(self):
        original = self._original()
        target = dict(original)
        target["review_id"] = "2"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, False))

    def test_cache_origin_provenance_required(self):
        original = self._original()
        original["provenance"] = "unknown"
        target = dict(original)
        target["review_id"] = "2"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, True))

    def test_cache_origin_request_id_required(self):
        original = self._original()
        original["request_id"] = ""
        target = dict(original)
        target["review_id"] = "2"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, True))

    def test_cache_different_text_rejected(self):
        original = self._original()
        target = dict(original)
        target["review_id"] = "2"
        target["review_text"] = "different text"
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, True))

    def test_cache_different_field_rejected(self):
        original = self._original()
        target = dict(original)
        target["review_id"] = "2"
        target["severity"] = 1
        target["is_cached"] = True
        target["cache_source_id"] = "1"
        self.assertTrue(validate_cache_reuse(target, original, True))


class QuarantineTests(unittest.TestCase):
    def test_reason_required(self):
        self.assertEqual(
            validate_quarantine(
                {
                    "status": "quarantined",
                    "reason": "empty_review_text",
                    "review_id": "1",
                    "source_sha256": "b" * 64,
                    "review_text": "",
                }
            ),
            [],
        )
        self.assertTrue(
            validate_quarantine(
                {"status": "quarantined", "reason": "", "review_id": "1", "source_sha256": "b" * 64}
            )
        )

    def test_legacy_key_rejected(self):
        self.assertTrue(
            validate_quarantine(
                {
                    "status": "quarantined",
                    "quarantine_reason": "empty_review_text",
                    "review_id": "1",
                    "source_sha256": "b" * 64,
                }
            )
        )

    def test_empty_reason_requires_empty_text(self):
        self.assertTrue(
            validate_quarantine(
                {
                    "status": "quarantined",
                    "reason": "empty_review_text",
                    "review_id": "1",
                    "source_sha256": "b" * 64,
                    "review_text": "not empty",
                }
            )
        )

    def test_source_override_rejected(self):
        self.assertTrue(
            validate_quarantine(
                {
                    "status": "quarantined",
                    "reason": "other",
                    "review_id": "2",
                    "source_sha256": "b" * 64,
                    "review_text": "",
                },
                source={"review_id": "1", "row_sha256": "b" * 64, "review_text": ""},
            )
        )


if __name__ == "__main__":
    unittest.main()

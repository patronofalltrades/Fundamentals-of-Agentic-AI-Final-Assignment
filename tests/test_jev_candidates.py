"""Synthetic tests only; no model calls or assignment review text."""

import unittest

from spotify_pipeline.errors import ValidationError
from spotify_pipeline.jev_candidates import build_request, generate, select_evidence


class CandidateTests(unittest.TestCase):
    def test_exact_offsets_and_unicode_boundaries(self):
        text = "C++17 stalls; café plays. 版本2.1 loads."
        found = generate(text)
        for span in found.entities + found.quotes:
            self.assertEqual(text[span.start:span.end], span.text)
        self.assertTrue(any(span.text == "C++17" for span in found.entities))
        self.assertTrue(any("café" in span.text for span in found.entities))
        self.assertTrue(any("2.1" in span.text for span in found.entities))
        self.assertFalse(any(span.text == "afé" for span in found.entities))

    def test_request_is_bounded_and_has_abstain(self):
        text = "Playback pauses on device X12."
        request, found = build_request(text, {"topic": "playback", "intent": "complaint",
                                              "severity": 3, "sentiment": -0.5})
        self.assertEqual(request["questions"]["quote"]["criteria"]["none"],
                         "No candidate supports the predicted labels")
        self.assertLessEqual(len(found.entities), 96)
        self.assertLessEqual(len(found.quotes), 16)
        self.assertEqual(len(request["questions"]), len(found.entities) + 2)
        self.assertNotIn("review_id", str(request))

    def test_cap_loss_abstains_instead_of_completing(self):
        text = " ".join("word%d" % index for index in range(90))
        found = generate(text)
        self.assertTrue(found.entity_truncated)
        self.assertGreater(found.entity_total, len(found.entities))
        with self.assertRaisesRegex(ValidationError, "candidate cap exceeded"):
            build_request(text, {"topic": "playback", "intent": "complaint",
                                 "severity": 3, "sentiment": -0.5})
        answers = {"quote": {"type": "choice", "choice": "q00"},
                   "support_exists": {"type": "noul", "noul": 1.0}}
        answers.update({"e%02d" % i: {"type": "noul", "noul": 0.0}
                        for i in range(len(found.entities))})
        result = select_evidence(text, found, {"model": "jev-1.13.0", "answers": answers})
        self.assertEqual(result["status"], "abstained")
        self.assertIn("entity_candidates_truncated", result["flags"])

    def test_invalid_choice_and_noul_rejected(self):
        text = "Playback stops."
        found = generate(text)
        answers = {"quote": {"type": "choice", "choice": "q99"},
                   "support_exists": {"type": "noul", "noul": 1.0}}
        answers.update({"e%02d" % i: {"type": "noul", "noul": 0.0}
                        for i in range(len(found.entities))})
        with self.assertRaises(ValidationError):
            select_evidence(text, found, {"model": "jev-1.13.0", "answers": answers})
        answers["quote"]["choice"] = "q00"
        answers["support_exists"]["noul"] = float("nan")
        with self.assertRaises(ValidationError):
            select_evidence(text, found, {"model": "jev-1.13.0", "answers": answers})

    def test_selected_evidence_and_no_entity_case(self):
        text = "Playback stops."
        found = generate(text)
        answers = {"quote": {"type": "choice", "choice": "q00"},
                   "support_exists": {"type": "noul", "noul": 1.0}}
        answers.update({"e%02d" % i: {"type": "noul", "noul": 0.0}
                        for i in range(len(found.entities))})
        result = select_evidence(text, found, {"model": "jev-1.13.0", "answers": answers})
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["evidence"]["entities"], [])
        self.assertEqual(result["evidence"]["evidence_quote"], text)


if __name__ == "__main__":
    unittest.main()

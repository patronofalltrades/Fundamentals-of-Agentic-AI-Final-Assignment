"""Whole-word entity matching for src/labelling/extract.py (extract-v2)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from labelling.extract import EXTRACT_VERSION, extract_entities, extract_evidence_quote  # noqa: E402


class EntityBoundaries(unittest.TestCase):
    def assertEntities(self, text, expected):
        self.assertEqual(extract_entities(text), expected, text)

    def test_ad_inside_words_is_not_an_ad(self):
        # v1 bugs: "ad " matched inside bad / read / dead / Brkdn-style gibberish.
        for text in ("This is a bad app", "Very bad app", "Vary bad experience.i am uninstalling",
                     "I read the lyrics", "Most fun i have had recently", "Nbjmmjnmjvkjnzudbdnidbdnad Brkdn.",
                     "my phone is dead", "loads of downloads"):
            self.assertNotIn("ads", extract_entities(text), text)

    def test_real_ads(self):
        for text in ("Too many ads", "The ads are so loud :'(", "without an ad bro", "AD after every song",
                     "so many advertisements", "advert every song", "the commercials are long", "ads, ads, ads!",
                     "plays adds instead of songs", "So much adds", "Irritating adds. Continuous podcast",
                     "Adds are still plenty"):
            self.assertIn("ads", extract_entities(text), text)

    def test_adds_as_a_verb_is_not_an_ad(self):
        for text in ("It adds songs whether you want it to", "this adds a new feature",
                     "Spotify adds more podcasts", "the update adds to the problem"):
            self.assertNotIn("ads", extract_entities(text), text)

    def test_suggestions(self):
        self.assertEqual(extract_entities("always fire suggestions!"), ["recommendation"])

    def test_other_substring_false_positives(self):
        cases = {"lag": "red flag", "search": "I did my research", "support": "unsupported device",
                 "charge": "I need to recharge my phone", "repeat": "it crashed repeatedly",
                 "connection": "the database is fine", "price": "priceless", "update": "outdated"}
        for term, text in cases.items():
            self.assertNotIn(term, extract_entities(text), text)

    def test_inflections_and_phrases_still_match(self):
        self.assertEntities("It keeps crashing", ["crash"])
        self.assertEntities("crashed twice, crashes daily", ["crash"])
        self.assertEntities("after updating it broke", ["update"])
        self.assertEntities("the new updates", ["update"])
        self.assertEntities("shuffling is random", ["shuffle"])
        self.assertEntities("I was charged twice", ["charge"])
        self.assertEntities("I can't log  in", ["login"])
        self.assertEntities("Sign-in fails", ["login"])
        self.assertEntities("Lyrics are missing", ["lyrics"])
        self.assertEntities("so laggy and buffering", ["lag"])
        self.assertEntities("it costs too much", ["price"])
        self.assertEntities("skipped and skipping", ["skip"])

    def test_order_and_dedup_follow_lexicon(self):
        self.assertEqual(extract_entities("ads ads premium subscription crash"), ["ads", "premium", "crash"])

    def test_version(self):
        self.assertEqual(EXTRACT_VERSION, "extract-v2")


class QuoteAnchors(unittest.TestCase):
    def test_anchor_uses_patterns_not_entity_names(self):
        filler = "The app is fine overall and I listen every day on my commute to work. " * 4
        text = filler + "Downloads vanish overnight. Too many ads after every song."
        entities = extract_entities(text)
        self.assertIn("ads", entities)
        # v1 picked the "Downloads" sentence because "ads" is a substring of "downloads".
        quote = extract_evidence_quote(text, ["ads"])
        self.assertEqual(quote, "Too many ads after every song.")
        self.assertIn(quote, text)

    def test_multiword_anchor(self):
        filler = "I have used this for years and mostly enjoy it a lot every single day. " * 4
        text = filler + "Lately the sound quality is awful."
        self.assertEqual(extract_evidence_quote(text, ["audio_quality"]), "Lately the sound quality is awful.")

    def test_short_review_is_whole_text(self):
        self.assertEqual(extract_evidence_quote("  Very bad app ", []), "Very bad app")


if __name__ == "__main__":
    unittest.main()

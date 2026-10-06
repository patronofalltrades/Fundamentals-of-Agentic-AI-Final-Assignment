"""Rubric v2 (topic) prompt structure for src/labelling/prompts.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from labelling import prompts  # noqa: E402

TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")


class RubricV2(unittest.TestCase):
    def test_version(self):
        self.assertEqual(prompts.RUBRIC_VERSION, "v2")

    def test_topic_criteria_cover_exactly_the_contract_topics(self):
        self.assertEqual(tuple(prompts.TOPIC_GLOSS), TOPICS)

    def test_boundary_rules_reach_the_model(self):
        q = prompts.build_questions("r1")["topic_r1"]
        self.assertIn("`r1`", q["instructions"])  # packed batches still target one review
        for phrase in ("general praise is other", "Ad interruptions are usability",
                       "loading failures are playback", "missing offline lyrics are catalog"):
            self.assertIn(phrase, q["instructions"])
        self.assertIn("Generic 'great music app' praise is other", q["criteria"]["other"])
        self.assertIn("not support meaning endorsement", q["criteria"]["support"])
        for rule in ("Ad interruptions are 'usability'", "loading failures are 'playback'"):
            self.assertIn(rule, prompts.RUBRIC)

    def test_other_questions_unchanged_in_shape(self):
        q = prompts.build_questions("r1")
        self.assertEqual(sorted(q), sorted(f"{n}_r1" for n in ("topic", "intent", "severity", "sentiment", "needs_review")))


if __name__ == "__main__":
    unittest.main()

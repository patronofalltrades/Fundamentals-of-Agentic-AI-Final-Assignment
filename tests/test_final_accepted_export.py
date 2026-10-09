"""Synthetic checks for final handoff identity and semantic exclusions."""

import unittest

from tools.final_accepted_export import pulse_flags


class FinalAcceptedExportTests(unittest.TestCase):
    def setUp(self):
        self.row = {"review_id": "synthetic-1", "source_position": 10001,
            "source_sha256": "a" * 64, "text_sha256": "b" * 64}
        self.finding = {"review_id": "synthetic-1", "source_position": 10001,
            "source_sha256": "a" * 64, "text_sha256": "b" * 64,
            "human_review_required": True,
            "representative_evidence_blocked_by_known_flag": True}
        self.overlay = {"schema": "scale100k-semantic-findings-overlay-v1",
            "saved_model_outputs_preserved": True,
            "findings": [dict(self.finding, review_id="synthetic-" + str(n))
                for n in range(1, 9)]}
        self.source = {"synthetic-" + str(n): dict(self.row,
            review_id="synthetic-" + str(n)) for n in range(1, 9)}
        self.accepted = set(self.source)

    def test_eight_accepted_flags_remain_representative_exclusions(self):
        flags = pulse_flags(self.overlay, self.source, self.accepted)
        self.assertEqual(len(flags), 8)
        self.assertTrue(all(len(items) == 1 for items in flags.values()))

    def test_rejects_flag_for_nonaccepted_or_changed_source(self):
        self.accepted.remove("synthetic-1")
        with self.assertRaises(ValueError):
            pulse_flags(self.overlay, self.source, self.accepted)
        self.accepted.add("synthetic-1")
        self.overlay["findings"][0]["text_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            pulse_flags(self.overlay, self.source, self.accepted)


if __name__ == "__main__":
    unittest.main()

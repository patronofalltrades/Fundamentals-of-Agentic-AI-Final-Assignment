"""Synthetic checks for pilot-v2 provenance, abstention and source protection."""

import unittest

from tools.reconcile_grouping_pilot_v2 import PRIORITY_SHA256, RULE_VERSION, reconcile


PRIORITY = [6, 8, 18, 29, 35, 37, 46, 50, 54, 56, 59, 61, 64, 80,
            82, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]


class ReconcileGroupingPilotV2Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"status": "pilot_authorized", "mapping_rule_version": RULE_VERSION,
            "pilot_revision": {"production_approved": False,
                "priority_decisions_sha256": PRIORITY_SHA256},
            "issues": [{"issue_id": "APP-LAUNCH"}, {"issue_id": "ACC-LOGIN"}] +
                [{"issue_id": "SYN-%02d" % i} for i in range(39)]}
        self.pilot = {"rows": [{"pilot_index": i, "review_id": "synthetic-%03d" % i,
            "source_sha256": "a" * 64, "source_text": "Synthetic %d" % i,
            "evidence": {"evidence_quote": "Synthetic", "entities": []},
            "known_semantic_flag": i >= 91} for i in range(1, 101)]}
        self.assignments = {"rows": [{"pilot_index": i,
            "provisional_issue_id": "ACC-LOGIN"} for i in range(1, 101)]}
        review_ids = set(PRIORITY) | set([i for i in range(1, 101)
                                          if i not in PRIORITY][:28])
        self.full_review = {"review_cases": [{"pilot_index": i}
            for i in sorted(review_ids)]}
        kinds = (["revise_catalog"] * 9 + ["correct_saved_label"] * 4 +
                 ["accept_provisional"] * 7 + ["choose_alternative"] * 2)
        self.priority = []
        nonblank = [i for i in PRIORITY if i not in (29, 92, 97)]
        for i in PRIORITY:
            source = self.pilot["rows"][i - 1]
            kind = kinds[nonblank.index(i)] if i in nonblank else ""
            choice = ("" if not kind or i == 80 else
                      "APP-LAUNCH" if kind == "revise_catalog" else "ACC-LOGIN")
            self.priority.append({"pilot_index": str(i), "review_id": source["review_id"],
                "source_sha256": source["source_sha256"],
                "source_text": source["source_text"],
                "evidence_quote": "Synthetic", "provisional_issue_id": "ACC-LOGIN",
                "reviewer_decision": kind, "chosen_issue_id": choice,
                "decision_notes": ("Claude proposal, confirmed by Hanif 2026-10-10: Synthetic"
                                   if kind else "")})
        self.assertEqual(len(self.full_review["review_cases"]), 53)

    def test_overlay_keeps_label_corrections_out_of_membership(self):
        overlay, remaining = reconcile(self.catalog, self.pilot, self.assignments,
                                       self.full_review, self.priority)
        self.assertEqual(overlay["counts"]["recorded_priority_decisions"], 22)
        self.assertEqual(overlay["counts"]["production_memberships"], 0)
        self.assertEqual(overlay["unresolved_priority_indices"], [29, 92, 97])
        self.assertEqual(overlay["rule_propagations"][0]["pilot_index"], 1)
        self.assertEqual(overlay["rule_propagations"][0]["v2_pilot_suggested_issue_id"],
                         "APP-LAUNCH")
        self.assertEqual(len(remaining["review_cases"]), 28)
        self.assertTrue(all(x["reviewer_decision"] is None for x in remaining["review_cases"]))
        self.assertTrue(all(x["production_membership_issue_id"] is None
                            for x in overlay["decisions"]))
        self.assertTrue(all(x["pilot_suggested_issue_id"] is None
                            for x in overlay["decisions"] if x["label_correction_pending"]))

    def test_changed_source_or_decision_is_rejected(self):
        self.priority[0]["source_text"] = "changed"
        with self.assertRaisesRegex(ValueError, "source or frozen proposal"):
            reconcile(self.catalog, self.pilot, self.assignments,
                      self.full_review, self.priority)
        self.priority[0]["source_text"] = self.pilot["rows"][5]["source_text"]
        self.priority[0]["reviewer_decision"] = ""
        with self.assertRaisesRegex(ValueError, "blank decision"):
            reconcile(self.catalog, self.pilot, self.assignments,
                      self.full_review, self.priority)


if __name__ == "__main__":
    unittest.main()

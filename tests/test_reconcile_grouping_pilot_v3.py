"""Synthetic checks for v3 decision audit and blind human-check selection."""

import unittest

from tools.grouping_independent40 import freeze
from tools.reconcile_grouping_pilot_v3 import PRIORITY_SHA256, REMAINING_SHA256, reconcile


PRIORITY = [6, 8, 18, 29, 35, 37, 46, 50, 54, 56, 59, 61, 64, 80,
            82, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
CORRECTIONS = {18, 43, 61, 80, 89, 94}
OPEN = {22, 29, 31, 81, 97}


class PilotV3Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"status": "pilot_authorized",
            "mapping_rule_version": "pilot-primary-problem-v3-20261010",
            "v3_revision": {"production_approved": False,
                "priority_decisions_sha256": PRIORITY_SHA256,
                "remaining28_decisions_sha256": REMAINING_SHA256},
            "issues": [{"issue_id": name} for name in
                ("ACC-LOGIN", "APP-LAUNCH", "PLY-QUALITY") +
                tuple("SYN-%02d" % i for i in range(38))]}
        self.pilot = {"rows": [{"pilot_index": i, "review_id": "synthetic-%03d" % i,
            "source_sha256": "a" * 64, "source_text": "Synthetic text %d" % i,
            "evidence": {"evidence_quote": "Synthetic", "entities": []},
            "known_semantic_flag": False} for i in range(1, 101)]}
        self.assignments = {"rows": [{"pilot_index": i,
            "provisional_issue_id": "PLY-QUALITY" if i == 92 else "ACC-LOGIN"}
            for i in range(1, 101)]}
        mandatory = {1, 22, 31, 43, 55, 81, 89}
        additional = mandatory | set([i for i in range(1, 101)
                                      if i not in PRIORITY and i not in mandatory][:21])
        self.assertEqual(len(additional), 28)
        review_ids = set(PRIORITY) | additional
        self.full_review = {"review_cases": [{"pilot_index": i}
            for i in sorted(review_ids)]}
        self.v2_remaining = {"review_cases": [{"pilot_index": i,
            "v2_pilot_suggested_issue_id": "APP-LAUNCH" if i == 1 else "ACC-LOGIN"}
            for i in sorted(additional)]}
        self.v2_overlay = {"mapping_rule_version": "pilot-primary-problem-v2-20261010"}
        priority_kinds = ({i: "revise_catalog" for i in
            (6, 8, 35, 37, 46, 50, 54, 56, 82)} |
            {i: "correct_saved_label" for i in (18, 61, 80, 94)} |
            {i: "accept_provisional" for i in
             (59, 64, 92, 95, 96, 98, 99, 100)} |
            {i: "choose_alternative" for i in (91, 93)})
        remaining_kinds = {i: "" for i in (22, 31, 81)}
        remaining_kinds.update({43: "correct_saved_label", 89: "correct_saved_label",
                                1: "accept_provisional", 55: "choose_alternative"})
        for i in sorted(additional):
            if i not in remaining_kinds:
                remaining_kinds[i] = "revise_catalog" if not any(
                    x == "revise_catalog" for x in remaining_kinds.values()) else \
                    ("choose_alternative" if sum(x == "choose_alternative"
                     for x in remaining_kinds.values()) < 4 else "accept_provisional")
        self.priority_rows = [self._sheet_row(i, priority_kinds.get(i, ""), True)
                              for i in PRIORITY]
        self.remaining_rows = [self._sheet_row(i, remaining_kinds[i], False)
                               for i in sorted(additional)]
        self.assertEqual({k: list(remaining_kinds.values()).count(k) for k in
            set(remaining_kinds.values())}, {"": 3, "correct_saved_label": 2,
            "accept_provisional": 18, "choose_alternative": 4, "revise_catalog": 1})

    def _sheet_row(self, idx, kind, priority):
        source = self.pilot["rows"][idx - 1]
        original = self.assignments["rows"][idx - 1]["provisional_issue_id"]
        v2 = "APP-LAUNCH" if idx == 1 else original
        chosen = ("" if not kind or idx == 80 else
                  v2 if kind == "accept_provisional" else
                  "PLY-QUALITY" if idx == 55 else "ACC-LOGIN")
        row = {"pilot_index": str(idx), "review_id": source["review_id"],
            "source_sha256": source["source_sha256"],
            "source_text": source["source_text"],
            "evidence_quote": "Synthetic", "reviewer_decision": kind,
            "chosen_issue_id": chosen,
            "decision_notes": ("Claude proposal, confirmed by Hanif 2026-10-10: Synthetic"
                               if kind else "")}
        if priority:
            row["provisional_issue_id"] = original
        else:
            row["v1_provisional_issue_id"] = original
            row["v2_pilot_suggested_issue_id"] = v2
        return row

    def test_v3_keeps_open_and_label_cases_out_of_membership(self):
        result = reconcile(self.catalog, self.pilot, self.assignments,
            self.full_review, self.v2_remaining, self.v2_overlay,
            self.priority_rows, self.remaining_rows)
        self.assertEqual(result["counts"]["recorded_decisions"], 48)
        self.assertEqual(result["counts"]["pilot_issue_suggestions"], 42)
        self.assertEqual(result["open_indices"], sorted(OPEN))
        self.assertEqual(result["label_correction_indices"], sorted(CORRECTIONS))
        self.assertTrue(all(x["production_membership_issue_id"] is None
                            for x in result["entries"]))
        self.assertEqual(next(x for x in result["entries"] if x["pilot_index"] == 1)
                         ["v3_pilot_suggested_issue_id"], "APP-LAUNCH")

    def test_source_or_open_case_tamper_fails(self):
        self.remaining_rows[0]["source_text"] = "changed"
        with self.assertRaisesRegex(ValueError, "source or exact evidence"):
            reconcile(self.catalog, self.pilot, self.assignments,
                self.full_review, self.v2_remaining, self.v2_overlay,
                self.priority_rows, self.remaining_rows)

    def test_independent_sample_excludes_prior_ids_and_texts(self):
        topics = ("access", "billing", "catalog", "downloads", "other",
                  "playback", "support", "usability")
        rows = [{"review_id": "synthetic-%05d" % i,
            "source_text": "Synthetic distinct text %d" % i,
            "topic": topics[i % 8]} for i in range(30403)]
        selected = freeze({"schema_version": "spotify-issue-grouping-frame-v1",
                           "rows": rows},
                          {"rows": rows[:64]}, {"rows": rows[64:164]})
        self.assertEqual(len(selected), 40)
        self.assertEqual(len({x["review_id"] for x in selected}), 40)
        self.assertFalse({x["source_text"] for x in selected} &
                         {x["source_text"] for x in rows[:164]})


if __name__ == "__main__":
    unittest.main()

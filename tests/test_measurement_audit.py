"""Synthetic edge cases and aggregate-only regression checks; no human answers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dashboard import server
from dashboard.backend import SQLiteBackend
from tests.test_dashboard_vercel import build_dashboard_copy
from tools import build_eval_registry as registry
from tools import build_measurement_audit as audit


class CoverageTests(unittest.TestCase):
    def test_missing_prediction_is_neither_agreement_nor_disagreement(self):
        claims = [{"review_ref": "a" * 64, "claim": "x"}, {"review_ref": "b" * 64, "claim": "y"}]
        result = audit.blind_join(claims, {"a" * 64: {"output": "z"}}, lambda r: "claim", lambda r: "output")
        self.assertEqual((result["paired_outputs"], result["missing_outputs"], result["disagreed"], result["agreed"]), (1, 1, 1, 0))
        empty = audit.blind_join(claims, {}, lambda r: "claim", lambda r: "output")
        self.assertIsNone(empty["disagreement_on_paired_outputs"])

    def test_duplicates_and_raw_ids_rejected(self):
        for rows in ([{"review_ref": "synthetic-raw-id"}], [{"review_ref": "a" * 64}] * 2):
            with self.assertRaises(ValueError):
                audit.index_cases(rows)

    def test_saved_aggregate_and_coverage_arithmetic(self):
        result = audit.build()
        self.assertEqual(result, json.loads((audit.ROOT / audit.OUT).read_text()))
        self.assertEqual((result["verifier"]["observed"], result["verifier"]["missing"]), (980, 20))
        self.assertEqual((result["grouping"]["observed"], result["grouping"]["missing"]), (580, 20))
        for key, n, paired, missing in (("planted_labels", 40, 41, 2), ("planted_issues", 46, 46, 4)):
            self.assertEqual(tuple(result[key][k] for k in ("disagreed", "paired_outputs", "missing_outputs")), (n, paired, missing))
        self.assertEqual(result["cost"]["known_plus_held_nusd"], 413438403)
        self.assertEqual(result["cost"]["unknown_charge_attempts"], 125)
        self.assertEqual(result["recovery"]["settled_logical_requests"], 212)
        self.assertEqual(result["recovery"]["logical_requests_without_settled_result"], 1)
        self.assertEqual(result["recovery"]["resumed_attempts_for_initial_settled_requests"], 0)
        encoded = json.dumps(result)
        for forbidden in ('review_ref', 'review_id', 'claimed_topic', 'verifier_topic', 'review_text'):
            self.assertNotIn(forbidden, encoded)

    def test_registry_preserves_partial_coverage_and_time_scopes(self):
        items = {i["id"]: i for i in registry.build()["items"]}
        # Observed results are measured; completion gaps must remain separate and visible.
        for key in ("labelling-runs", "extractor-benchmark", "blind-verifier-batch10", "grouping-stage", "projection-100k", "gap-operations", "planted-and-injection"):
            self.assertEqual(items[key]["status"], "measured")
            if key not in ("blind-verifier-batch10", "grouping-stage", "planted-and-injection"):
                self.assertTrue(items[key]["gaps"], key)
            for gap in items[key]["gaps"]:
                self.assertTrue(gap["label"] and gap["detail"], key)
        metrics = {m["label"]: m for m in items["cost100-cold-full-warm"]["metrics"]}
        self.assertGreater(metrics["Full warm orchestration"]["value"], 0)
        self.assertEqual(metrics["New paid / transport / socket attempts"]["value"], 0)
        self.assertNotIn("all stages", json.dumps(items["projection-100k"]).lower())

    def test_measured_badge_does_not_fill_missing_evidence(self):
        items = {i["id"]: i for i in registry.build()["items"]}
        for key, observed, selected in (("blind-verifier-batch10", 1000, 1000), ("grouping-stage", 600, 600)):
            self.assertEqual((items[key]["metrics"][0]["value"], items[key]["metrics"][0]["of"]), (observed, selected))
            self.assertEqual(items[key]["gaps"], [])
            self.assertIn("0 missing", items[key]["metrics"][0]["note"])
        errors = next(r for r in items["labelling-runs"]["compare"]["rows"] if r["label"] == "Schema or identity errors")
        self.assertIsNone(errors["values"][1])
        self.assertIn("46 calls", items["projection-100k"]["gaps"][0]["detail"])
        self.assertIn("125 attempts", items["gap-operations"]["gaps"][0]["detail"])
        self.assertEqual(items["planted-and-injection"]["gaps"], [])
        self.assertIn("100 of 100 label-auditor", items["planted-and-injection"]["sample"])

    def test_warm_card_rejects_wrong_source_or_network_attempt(self):
        measured = audit.build()
        pilot = json.loads((registry.ROOT / registry.COST_PILOT).read_text())
        warm = json.loads((registry.ROOT / registry.FULL_WARM).read_text())
        for change in ({"source_sha256": "wrong"}, {"attempts": {"paid": 0, "transport": 1, "socket": 0}}):
            with self.assertRaises(ValueError):
                registry.operational_measurements(pilot, {**warm, **change}, measured)


class VerificationScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "registry.json"
        self.saved = registry.build()["verification"]
        self.patch = patch.object(server, "EVALS", self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, saved):
        self.path.write_text(json.dumps({"verification": saved}))

    def test_scope_mismatch_or_missing_registry_never_reports_saved_sample(self):
        self.assertIsNone(server._saved_verification("source", "config"))
        self.write(self.saved)
        self.assertIsNone(server._saved_verification("wrong", self.saved["config_hash"]))
        self.assertIsNone(server._saved_verification(self.saved["source_sha256"], "wrong"))
        self.path.write_text("{bad")
        self.assertIsNone(server._saved_verification("source", "config"))

    def test_invalid_counts_or_truth_claim_fail_closed(self):
        for changes in ({"missing": 1}, {"observed": True}, {"not_human_accuracy": False},
                        {"agreement_counts": {"topic": 1, "intent": 1, "severity": 1, "joint": 2}}):
            self.write({**self.saved, **changes})
            self.assertIsNone(server._saved_verification(self.saved["source_sha256"], self.saved["config_hash"]))

    def test_summary_attaches_only_matching_sample_and_leaves_accuracy_unknown(self):
        db = build_dashboard_copy(self.temp.name)
        with SQLiteBackend(db) as conn:
            source = conn.execute("SELECT value FROM meta WHERE key='file_sha256'").fetchone()[0]
            config = conn.execute("SELECT DISTINCT config_hash FROM record_state LIMIT 1").fetchone()[0]
            self.write(self.saved)
            self.assertEqual(server.summary(conn)["quality"]["blind_verifier"], "pending")
            self.write({**self.saved, "source_sha256": source, "config_hash": config})
            quality = server.summary(conn)["quality"]
            self.assertEqual(quality["blind_verifier"], "sample_measured")
            self.assertEqual(quality["verification"]["missing"], 0)
            self.assertIsNone(quality["classifier_agreement"])
            self.assertEqual(quality["human_evaluation"], "pending")


if __name__ == "__main__":
    unittest.main()

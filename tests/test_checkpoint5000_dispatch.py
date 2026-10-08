import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from spotify_pipeline.checkpoint5000_queue import CheckpointQueue
from spotify_pipeline.project_budget import ProjectBudget
from tests.test_checkpoint5000_queue import rows5000
from tests.test_project_budget import fixtures
from tests.test_jev import fixture_response
from tools.checkpoint5000_dispatch import recover_metered_evidence, run_evidence, run_labels


class DispatcherTest(unittest.TestCase):
    def test_two_bounded_jev_calls_save_distinct_text_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix")
                with mock.patch("tools.checkpoint5000_dispatch.jev.check_model_access"), \
                     mock.patch("tools.checkpoint5000_dispatch.jev.post_systemone",
                                return_value=fixture_response()) as post:
                    result = run_labels(queue, "synthetic-key", first_100=True,
                                        max_new_requests=2)
                self.assertEqual(result["admitted"], 2)
                self.assertEqual(result["labels"], 4)
                self.assertEqual(post.call_count, 2)
                self.assertEqual(result["requests"], {"succeeded": 2})
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix")
                self.assertEqual(queue.next_jev(first_100=True)["review_id"], rows[4]["review_id"])

    def test_one_twenty_five_review_request_saves_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:100])}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix", seed)
                chosen = queue.next_evidence(25, first_100=True)
                response = {"id": "synthetic-generation", "provider": "DeepInfra",
                    "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                        "results": [{"review_id": row["review_id"], "entities": ["premium"],
                            "evidence_quote": "premium problem"} for row in chosen]})}}],
                    "usage": {"prompt_tokens": 2000, "completion_tokens": 1000,
                              "completion_tokens_details": {"reasoning_tokens": 400}}}
                with mock.patch("tools.checkpoint5000_dispatch.benchmark.verify_route"), \
                     mock.patch("tools.checkpoint5000_dispatch.canary.verify_project_key"), \
                     mock.patch("tools.checkpoint5000_dispatch.benchmark.request_json",
                                return_value=response) as post:
                    result = run_evidence(queue, "synthetic-key", 25, first_100=True,
                                          max_new_requests=1)
                self.assertEqual(post.call_count, 1)
                self.assertEqual(result["admitted"], 1)
                self.assertEqual(result["evidence"], 50)
                self.assertEqual(result["complete"], 50)

    def test_unknown_delivery_holds_reservation_and_blocks_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix")
                with mock.patch("tools.checkpoint5000_dispatch.jev.check_model_access"), \
                     mock.patch("tools.checkpoint5000_dispatch.jev.post_systemone",
                                side_effect=TimeoutError("synthetic timeout")):
                    result = run_labels(queue, "synthetic-key", first_100=True,
                                        max_new_requests=1)
                self.assertTrue(result["paused"])
                self.assertEqual(result["requests"], {"uncertain": 1})
                self.assertEqual(result["jev_exposure_nusd"], 23_691_254 + 2_688_000)
                with mock.patch("tools.checkpoint5000_dispatch.jev.check_model_access") as access:
                    with self.assertRaisesRegex(ValueError, "unresolved delivery"):
                        run_labels(queue, "synthetic-key", first_100=True,
                                   max_new_requests=1)
                    access.assert_not_called()

    def test_offline_partial_recovery_keeps_charge_and_quarantines_one_row(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:100])}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix", seed)
                chosen = queue.next_evidence(25, first_100=True)
                key = queue.reserve("evidence", chosen, "config", 24_903_544, 25)
                response = {"id": "synthetic-generation", "provider": "DeepInfra",
                    "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                        "results": [{"review_id": r["review_id"], "entities": ["premium"],
                            "evidence_quote": "invented quote" if i == 20 else "premium problem"}
                            for i, r in enumerate(chosen)]})}}],
                    "usage": {"prompt_tokens": 2000, "completion_tokens": 1000,
                              "completion_tokens_details": {"reasoning_tokens": 50}}}
                queue.fail(key, metered_charge=244_000, error_class="ValidationError",
                           response=response, elapsed_seconds=1.2)
                exposure_before = budget.exposure("openrouter")
                outcome = recover_metered_evidence(queue)
                self.assertEqual(outcome["accepted_direct_rows"], 24)
                self.assertEqual(outcome["quarantined_direct_rows"], 1)
                self.assertEqual(outcome["evidence"], 48)
                self.assertEqual(outcome["quarantined_rows"], 2)
                self.assertEqual(budget.exposure("openrouter"), exposure_before)
                with self.assertRaisesRegex(ValueError, "no metered"):
                    recover_metered_evidence(queue)

    def test_offline_repeated_id_recovery_quarantines_repeated_and_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:100])}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix", seed)
                chosen = queue.next_evidence(25, first_100=True)
                key = queue.reserve("evidence", chosen, "config", 24_903_544, 25)
                results = [{"review_id": r["review_id"], "entities": ["premium"],
                    "evidence_quote": "premium problem"} for r in chosen]
                results[-1]["review_id"] = chosen[0]["review_id"]
                response = {"id": "synthetic-generation", "provider": "DeepInfra",
                    "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                        "results": results})}}],
                    "usage": {"prompt_tokens": 2000, "completion_tokens": 1000,
                              "completion_tokens_details": {"reasoning_tokens": 50}}}
                queue.fail(key, metered_charge=244_000, error_class="ValueError",
                           response=response, elapsed_seconds=1.2)
                exposure_before = budget.exposure("openrouter")
                outcome = recover_metered_evidence(queue)
                self.assertEqual(outcome["accepted_direct_rows"], 23)
                self.assertEqual(outcome["quarantined_direct_rows"], 2)
                self.assertEqual(outcome["evidence"], 46)
                self.assertEqual(outcome["quarantined_rows"], 4)
                self.assertEqual(budget.exposure("openrouter"), exposure_before)
                self.assertEqual(queue.db.execute("SELECT COUNT(*) FROM checkpoint_requests "
                    "WHERE status='partial_succeeded'").fetchone()[0], 1)

    def test_deferred_uncertain_batches_keep_holds_and_stop_repeated_outage(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            path = str(Path(folder) / "project.db")
            rows = rows5000()
            label = json.dumps({"topic": "billing", "intent": "complaint",
                "severity": 3, "sentiment": -0.5, "needs_review": False})
            seed = {r["review_text"]: (label, "external-" + str(i))
                    for i, r in enumerate(rows[:100])}
            with ProjectBudget(path, paths) as budget:
                queue = CheckpointQueue(budget, rows, "source", "prefix", seed)
                before = budget.exposure("openrouter")
                incomplete = {"provider": "DeepInfra", "id": "synthetic-generation"}
                with mock.patch("tools.checkpoint5000_dispatch.benchmark.verify_route"), \
                     mock.patch("tools.checkpoint5000_dispatch.canary.verify_project_key"), \
                     mock.patch("tools.checkpoint5000_dispatch.benchmark.request_json",
                                return_value=incomplete) as post:
                    result = run_evidence(queue, "synthetic-key", 25, first_100=True,
                        max_new_requests=2, defer_uncertain_evidence=True)
                self.assertEqual(post.call_count, 2)
                self.assertEqual(result["new_uncertain_requests"], 2)
                self.assertTrue(result["paused"])
                self.assertEqual(result["requests"], {"uncertain": 2})
                self.assertEqual(budget.exposure("openrouter"), before + 2 * 24_903_544)
                self.assertEqual(len(queue.next_evidence(25, first_100=True)), 0)


if __name__ == "__main__":
    unittest.main()

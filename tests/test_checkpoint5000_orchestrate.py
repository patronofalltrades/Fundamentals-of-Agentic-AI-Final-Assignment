"""Offline checks for the foreground checkpoint runner."""

import argparse
import io
import unittest
from unittest import mock

from tools import checkpoint5000_orchestrate as runner


class FakeQueue:
    def __init__(self, labels=True, evidence=True):
        self.labels = labels
        self.evidence = evidence
        self.db = mock.Mock()
        self.db.execute.return_value.fetchone.return_value = (100, 100, 96, 4)

    def next_jev(self):
        return {"review_id": "synthetic"} if self.labels else None

    def next_evidence(self, _limit):
        return [{"review_id": "synthetic"}] if self.evidence else []

    def summary(self):
        return {"labels": 100, "complete": 96}

    def assert_resume_safe(self, _stage, defer_uncertain_evidence=False):
        return None


class OrchestrateTest(unittest.TestCase):
    def test_pinned_jev_price(self):
        page = b"<p>Current models Jev 1.13 jev-1.13.0 Price (per Btok / per Mtok) $42 / $0.042</p>"
        self.assertEqual(runner.verify_jev_price(lambda *_args, **_kwargs: io.BytesIO(page))[
            "input_usd_per_million"], "0.042")
        with self.assertRaisesRegex(ValueError, "price or model changed"):
            runner.verify_jev_price(lambda *_args, **_kwargs: io.BytesIO(
                page.replace(b"$0.042", b"$0.043")))

    def test_sequential_stages_and_key_services(self):
        budget, queue = mock.Mock(), FakeQueue()
        events = []

        def secret(**kwargs):
            events.append("key:" + kwargs.get("service", "openrouter"))
            return "synthetic-key"

        def labels(_queue, _key):
            events.append("labels")
            return {"admitted": 1, "paused": False, "halt_reason": None}

        def evidence(_queue, _key, limit, defer_uncertain_evidence=False):
            events.append("evidence:" + str(limit))
            return {"admitted": 1, "paused": False, "halt_reason": None}

        with mock.patch.object(runner, "open_checkpoint", return_value=(budget, queue)), \
                mock.patch.object(runner, "qa_status", return_value={
                    "accepted_rows": 4996, "quarantined_rows": 4, "pending_rows": 0,
                    "uncertain_rows": 0, "in_flight_rows": 0}), \
                mock.patch.object(runner, "verify_jev_price", return_value={"model": "jev-1.13.0"}), \
                mock.patch.object(runner.canary, "keychain_secret", side_effect=secret), \
                mock.patch.object(runner, "run_labels", side_effect=labels), \
                mock.patch.object(runner, "run_evidence", side_effect=evidence):
            result = runner.run(argparse.Namespace(manifest="synthetic", budget="synthetic",
                defer_uncertain_evidence=False))
        self.assertEqual(events, ["key:spotify-review-jev", "labels", "key:openrouter",
                                  "evidence:50"])
        self.assertEqual(result["status"], "checkpoint_accounted_with_quarantines")
        budget.close.assert_called_once()

    def test_jev_pause_does_not_read_openrouter_key(self):
        budget, queue = mock.Mock(), FakeQueue()
        with mock.patch.object(runner, "open_checkpoint", return_value=(budget, queue)), \
                mock.patch.object(runner, "qa_status", return_value={
                    "accepted_rows": 96, "quarantined_rows": 4, "pending_rows": 4900,
                    "uncertain_rows": 0, "in_flight_rows": 0}), \
                mock.patch.object(runner, "verify_jev_price", return_value={}), \
                mock.patch.object(runner.canary, "keychain_secret", return_value="synthetic-key") as secret, \
                mock.patch.object(runner, "run_labels", return_value={
                    "admitted": 1, "paused": True, "halt_reason": "synthetic pause"}), \
                mock.patch.object(runner, "run_evidence") as evidence:
            result = runner.run(argparse.Namespace(manifest="synthetic", budget="synthetic",
                defer_uncertain_evidence=False))
        self.assertEqual(result["status"], "paused_after_jev")
        secret.assert_called_once()
        evidence.assert_not_called()

    def test_unsettled_jev_request_stops_before_key_lookup(self):
        budget, queue = mock.Mock(), FakeQueue()
        queue.assert_resume_safe = mock.Mock(side_effect=ValueError("reserved request"))
        with mock.patch.object(runner, "open_checkpoint", return_value=(budget, queue)), \
                mock.patch.object(runner, "qa_status", return_value={
                    "accepted_rows": 96, "quarantined_rows": 4, "pending_rows": 4900,
                    "uncertain_rows": 0, "in_flight_rows": 0}), \
                mock.patch.object(runner, "verify_jev_price") as price, \
                mock.patch.object(runner.canary, "keychain_secret") as secret:
            with self.assertRaisesRegex(ValueError, "reserved request"):
                runner.run(argparse.Namespace(manifest="synthetic", budget="synthetic",
                    defer_uncertain_evidence=False))
        price.assert_not_called()
        secret.assert_not_called()
        budget.close.assert_called_once()

    def test_uncertain_request_stops_even_when_no_new_row_is_selectable(self):
        budget, queue = mock.Mock(), FakeQueue(labels=False, evidence=False)
        queue.assert_resume_safe = mock.Mock(side_effect=ValueError("unresolved delivery"))
        with mock.patch.object(runner, "open_checkpoint", return_value=(budget, queue)), \
                mock.patch.object(runner, "qa_status", return_value={
                    "accepted_rows": 4950, "quarantined_rows": 0, "pending_rows": 0,
                    "uncertain_rows": 50, "in_flight_rows": 0}), \
                mock.patch.object(runner.canary, "keychain_secret") as secret:
            with self.assertRaisesRegex(ValueError, "unresolved delivery"):
                runner.run(argparse.Namespace(manifest="synthetic", budget="synthetic",
                    defer_uncertain_evidence=False))
        secret.assert_not_called()
        budget.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

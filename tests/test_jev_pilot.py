"""Synthetic persistent budget, retry, cache, and replay checks."""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.errors import StateError
from spotify_pipeline.codex_evidence import validate_evidence
from spotify_pipeline.jev import JevHTTPError
from spotify_pipeline.jev_pilot import PilotLedger, run_reviews
from spotify_pipeline.jev_import import completed_items
from spotify_pipeline.db import Database
from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import label_config
from tests.test_jev import fixture_response
from tests.helpers import make_db

SOURCE = "a" * 64


def row(review_id, text):
    return {"review_id": review_id, "review_text": text, "source_sha256": "b" * 64}


class PilotTests(unittest.TestCase):
    def test_persisted_reservation_survives_reopen_and_caps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "pilot.db")
            with PilotLedger(path, SOURCE, Decimal("0.002688")) as ledger:
                ledger.reserve("one", 1)
            with PilotLedger(path, SOURCE, Decimal("0.002688")) as ledger:
                self.assertEqual(ledger.summary()["attempts"], {"reserved": 1})
                with self.assertRaises(StateError):
                    ledger.reserve("two", 1)

    def test_usage_settlement_releases_unused_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            with PilotLedger(str(Path(folder) / "pilot.db"), SOURCE, Decimal("0.003")) as ledger:
                attempt = ledger.reserve("one", 1)
                ledger.settle(attempt, 100, 20, 0.1, "jev-1.13.0")
                self.assertEqual(ledger.summary()["charged_or_reserved_usd"], "0.0000042")
                ledger.reserve("two", 1)

    def test_failure_keeps_full_reserve_and_no_result(self):
        with tempfile.TemporaryDirectory() as folder:
            with PilotLedger(str(Path(folder) / "pilot.db"), SOURCE, Decimal("0.60")) as ledger:
                def fail(*_):
                    raise TimeoutError("synthetic timeout")
                with self.assertRaises(TimeoutError):
                    run_reviews([row("one", "Synthetic playback failure")], ledger, "synthetic-key", transport=fail)
                self.assertEqual(ledger.summary()["attempts"], {"uncertain": 1})
                self.assertEqual(ledger.summary()["results"], {})
                self.assertEqual(ledger.summary()["charged_or_reserved_usd"], "0.002688")

    def test_transient_retry_and_exact_text_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "pilot.db")
            calls = []
            def transport(*_):
                calls.append(1)
                if len(calls) == 1:
                    raise JevHTTPError(429, 0)
                return fixture_response()
            rows = [row("one", "Synthetic playback failure"), row("two", "Synthetic playback failure")]
            with PilotLedger(path, SOURCE, Decimal("0.60")) as ledger:
                report = run_reviews(rows, ledger, "synthetic-key", transport=transport, sleep=lambda _: None)
                self.assertEqual(report["attempts"], {"uncertain": 1, "settled": 1})
                self.assertEqual(report["results"], {"jev_direct": 1, "jev_exact_text_cache": 1})
                self.assertEqual(len(calls), 2)
                self.assertEqual(ledger.conn.execute("SELECT cache_source_id FROM results WHERE review_id='two'").fetchone()[0], "one")
            with PilotLedger(path, SOURCE, Decimal("0.60")) as ledger:
                replay = run_reviews(rows, ledger, "synthetic-key", transport=transport)
                self.assertEqual(replay["processed_this_run"], 0)
                self.assertEqual(len(calls), 2)

    def test_missing_usage_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with PilotLedger(str(Path(folder) / "pilot.db"), SOURCE, Decimal("0.60")) as ledger:
                response = fixture_response()
                del response["usage"]
                with self.assertRaises(Exception):
                    run_reviews([row("one", "Synthetic text")], ledger, "synthetic-key", transport=lambda *_: response)
                self.assertEqual(ledger.summary()["attempts"], {"uncertain": 1})

    def test_evidence_is_separate_and_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            with PilotLedger(str(Path(folder) / "pilot.db"), SOURCE, Decimal("0.60")) as ledger:
                rows = [row("one", "Synthetic playback failure"), row("two", "Synthetic playback failure")]
                run_reviews(rows, ledger, "synthetic-key", transport=lambda *_: fixture_response())
                with self.assertRaises(Exception):
                    ledger.save_evidence("one", {"entities": ["playback"], "evidence_quote": "Playback"},
                                         "synthetic", "v1", 0.1)
                evidence = validate_evidence("Synthetic playback failure",
                                             {"entities": ["playback"], "evidence_quote": "playback failure"})
                ledger.save_evidence("one", evidence, "synthetic", "v1", 0.1)
                ledger.save_evidence("two", evidence, "synthetic", "v1", 0.0, cache_source_id="one")
                self.assertEqual(ledger.summary()["evidence_records"], 2)

    def test_completed_import_into_foundation_is_offline_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [["one", "Synthetic playback failure", "1", "0", "", "2023-01-01 00:00:00"],
                    ["two", "Synthetic playback failure", "2", "0", "", "2023-01-02 00:00:00"]]
            db_path = make_db(folder, rows)
            with Database(db_path) as db:
                pilot_rows = [{"review_id": r["review_id"], "review_text": r["review_text"],
                               "source_sha256": r["row_sha256"]} for r in db.all_records()]
                with PilotLedger(str(Path(folder) / "pilot.db"), SOURCE, Decimal("0.60")) as ledger:
                    run_reviews(pilot_rows, ledger, "synthetic-key", transport=lambda *_: fixture_response())
                    evidence = {"entities": ["playback"], "evidence_quote": "playback failure"}
                    ledger.save_evidence("one", evidence, "synthetic", "v1", 0.1)
                    ledger.save_evidence("two", evidence, "synthetic", "v1", 0.0, cache_source_id="one")
                    self.assertEqual(len(completed_items(ledger, db, expected_count=2)), 2)
                    with self.assertRaises(StateError):
                        completed_items(ledger, db)
                    # The import gate normally demands 100 rows; exercise the
                    # identical persistence path on this two-row fixture.
                    for item in completed_items(ledger, db, expected_count=2):
                        db.save_completed_batch([item])
                    self.assertEqual(db.status_counts(config_hash(label_config()))["completed"], 2)


if __name__ == "__main__":
    unittest.main()

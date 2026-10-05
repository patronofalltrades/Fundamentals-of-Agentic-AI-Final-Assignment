"""Synthetic persistent budget, retry, cache, and replay checks."""

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from spotify_pipeline.errors import StateError, ValidationError
from spotify_pipeline.codex_evidence import align_unique_source_span, validate_evidence
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
    def test_v1_ledger_cannot_reopen_as_v2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "pilot.db")
            with PilotLedger(path, SOURCE, Decimal("0.60")):
                pass
            old = {**label_config(), "prompt_version": "jev-rubric-v1"}
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE meta SET value=? WHERE key='config_hash'",
                                   (config_hash(old),))
            with self.assertRaises(StateError):
                PilotLedger(path, SOURCE, Decimal("0.60"))

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

    def test_quote_alignment_copies_only_unique_source_span(self):
        text = "The Player\nStops, but resumes."
        self.assertEqual(align_unique_source_span(text, "the player stops"), "The Player\nStops")
        with self.assertRaises(Exception):
            align_unique_source_span("play play", "PLAY")
        with self.assertRaises(Exception):
            align_unique_source_span(text, "a different claim")

    def test_entity_validation_requires_clean_edges_and_whole_source_words(self):
        for entity in ("ad", "ad ", " ad", "ads"):
            with self.subTest(entity=entity), self.assertRaises(ValidationError):
                validate_evidence("bad experience", {"entities": [entity],
                                                     "evidence_quote": "bad"})
        with self.assertRaises(ValidationError):
            validate_evidence("ads play", {"entities": ["ad"], "evidence_quote": "ads"})
        with self.assertRaises(ValidationError):
            validate_evidence("cafe\u0301 tastes", {"entities": ["cafe"],
                                               "evidence_quote": "tastes"})
        with self.assertRaises(ValidationError):
            validate_evidence("C++17", {"entities": ["C++"], "evidence_quote": "C++17"})
        text = "A bad ad plays after the ads. C++ and café work. 広告 is shown."
        valid = {"entities": ["ad", "ads", "C++", "café", "広告"],
                 "evidence_quote": "bad ad plays"}
        self.assertEqual(validate_evidence(text, valid), valid)
        for entity in ("fé", "C++17"):
            with self.subTest(entity=entity), self.assertRaises(ValidationError):
                validate_evidence(text, {"entities": [entity], "evidence_quote": "bad"})
        # Quotes remain exact substrings; they are not entity names.
        self.assertEqual(validate_evidence("bad experience", {"entities": [],
                          "evidence_quote": "ad"})["evidence_quote"], "ad")

    def test_entity_alignment_rejects_partial_words_but_preserves_source_spans(self):
        with self.assertRaises(ValidationError):
            align_unique_source_span("bad experience", "ad", entity=True)
        with self.assertRaises(ValidationError):
            align_unique_source_span("an ad plays", "ad ", entity=True)
        with self.assertRaises(ValidationError):
            align_unique_source_span("ad ad", "AD", entity=True)
        self.assertEqual(align_unique_source_span("bad AD plays", "ad", entity=True), "AD")
        self.assertEqual(align_unique_source_span("The Player\nStops", "the player stops",
                                                  entity=True), "The Player\nStops")
        self.assertEqual(align_unique_source_span("Learn C++ today", "c++", entity=True),
                         "C++")

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
                    old = {**label_config(), "prompt_version": "jev-rubric-v1"}
                    ledger.conn.execute("UPDATE results SET config_hash=?", (config_hash(old),))
                    ledger.conn.commit()
                    with self.assertRaises(StateError):
                        completed_items(ledger, db, expected_count=2)


if __name__ == "__main__":
    unittest.main()

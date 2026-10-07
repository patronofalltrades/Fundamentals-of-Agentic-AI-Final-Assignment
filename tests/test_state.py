"""SYNTHETIC tests for SQLite state, caching, quarantine and checkpoints."""

import tempfile
import unittest

from spotify_pipeline.checkpoint import build_checkpoint
from spotify_pipeline.config import config_hash
from spotify_pipeline.db import Database
from spotify_pipeline.errors import StateError, ValidationError

from tests.helpers import completed_item, config_a, config_b, make_db

SAME_ROWS = [
    ["1", "same text", "5", "0", "", "2022-05-17 00:01:07"],
    ["2", "same text", "4", "0", "", "2022-05-18 00:01:07"],
    ["3", "same text", "3", "0", "", "2022-05-19 00:01:07"],
]


class StateTests(unittest.TestCase):
    def test_config_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            b = config_hash(config_b())
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
                counts_a = db.status_counts(a)
                counts_b = db.status_counts(b)
            self.assertEqual(counts_a["completed"], 1)
            self.assertEqual(counts_a["pending"], 3)
            self.assertEqual(counts_b["completed"], 0)
            self.assertEqual(counts_b["pending"], 4)

    def test_unconfigured_counts_are_source_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
                counts = db.status_counts()
            self.assertEqual(counts["completed"], 0)
            self.assertFalse(counts["configured"])
            self.assertEqual(counts["records"], 5)

    def test_direct_requires_request_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([completed_item(0, "Great app", request_id="")])

    def test_direct_rejects_cache_source_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(
                        [completed_item(0, "Great app", cache_source_id="2")]
                    )

    def test_is_cached_truthy_string_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(
                        [completed_item(0, "Great app", is_cached="yes")]
                    )

    def test_source_identity_override_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(
                        [completed_item(0, "Great app", review_id="999")]
                    )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(
                        [completed_item(0, "Great app", source_sha256="b" * 64)]
                    )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(
                        [completed_item(0, "Great app", label_config="different")]
                    )

    def test_cache_valid_direct_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            a = config_hash(config_a())
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "same text")])
                cached = completed_item(
                    1, "same text", is_cached=True, cache_source_id="1", request_id=None
                )
                result = db.save_completed_batch([cached])
            self.assertEqual(result["inserted"], 1)
            with Database(db_path) as db:
                self.assertEqual(db.status_counts(a)["completed"], 2)

    def test_cache_invalidation_on_field_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "same text")])
                cached = completed_item(
                    1, "same text", is_cached=True, cache_source_id="1", severity=1, request_id=None
                )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([cached])

    def test_cache_config_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "same text")])
                cached = completed_item(
                    1,
                    "same text",
                    is_cached=True,
                    cache_source_id="1",
                    request_id=None,
                    **config_b()
                )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([cached])

    def test_cache_chain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "same text")])
                db.save_completed_batch(
                    [completed_item(1, "same text", is_cached=True, cache_source_id="1", request_id=None)]
                )
                chain = completed_item(
                    2, "same text", is_cached=True, cache_source_id="2", request_id=None
                )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([chain])

    def test_cache_origin_must_be_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            with Database(db_path) as db:
                cached = completed_item(
                    1, "same text", is_cached=True, cache_source_id="1", request_id=None
                )
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([cached])

    def test_duplicate_completion_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
                with self.assertRaises(StateError):
                    db.save_completed_batch([completed_item(0, "Great app", topic="access")])

    def test_idempotent_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                first = db.save_completed_batch([completed_item(0, "Great app")])
                second = db.save_completed_batch([completed_item(0, "Great app")])
            self.assertEqual(first["inserted"], 1)
            self.assertEqual(second["inserted"], 0)
            self.assertEqual(second["skipped"], 1)

    def test_batch_rollback_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                good = completed_item(0, "Great app")
                bad = completed_item(1, "  spaced text  ", evidence_quote="not present")
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([good, bad])
                self.assertEqual(db.status_counts()["completed"], 0)

    def test_batch_max_50(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                items = [completed_item(0, "Great app") for _ in range(51)]
                with self.assertRaises(ValidationError):
                    db.save_completed_batch(items)

    def test_max_batch_cannot_be_bypassed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([completed_item(0, "Great app")], max_batch=100)

    def test_duplicate_pair_in_batch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                item = completed_item(0, "Great app")
                with self.assertRaises(ValidationError):
                    db.save_completed_batch([item, dict(item)])

    def test_restart_preserves_pending_and_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
            with Database(db_path) as db:
                self.assertEqual(db.status_counts(a)["completed"], 1)
                self.assertEqual(db.pending_row_indices(a), [1, 3, 4])

    def test_checkpoint_sorted_and_pending_not_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp, SAME_ROWS)
            with Database(db_path) as db:
                db.save_completed_batch(
                    [completed_item(0, "same text"), completed_item(1, "same text")]
                )
                checkpoint = build_checkpoint(db, config_a())
            self.assertEqual(checkpoint["completed_ids"], ["1", "2"])
            self.assertEqual(checkpoint["completed_count"], 2)
            self.assertEqual(checkpoint["pending_count"], 1)
            self.assertNotIn("3", checkpoint["completed_ids"])


class QuarantineTests(unittest.TestCase):
    def test_empty_reason_is_intrinsic_and_retrievable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                db.quarantine(2, a, "empty_review_text")
                self.assertEqual(db.effective_status(2, a), "quarantined")
                self.assertEqual(db.effective_reason(2, a), "empty_review_text")

    def test_empty_row_only_accepts_empty_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.quarantine(2, a, "other")

    def test_nonempty_row_rejects_empty_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.quarantine(0, a, "empty_review_text")

    def test_blank_reason_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.quarantine(0, a, "   ")

    def test_invalid_config_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            with Database(db_path) as db:
                with self.assertRaises(ValidationError):
                    db.quarantine(0, "nothex", "other")

    def test_completed_state_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = make_db(tmp)
            a = config_hash(config_a())
            with Database(db_path) as db:
                db.save_completed_batch([completed_item(0, "Great app")])
                with self.assertRaises(StateError):
                    db.quarantine(0, a, "other")


if __name__ == "__main__":
    unittest.main()

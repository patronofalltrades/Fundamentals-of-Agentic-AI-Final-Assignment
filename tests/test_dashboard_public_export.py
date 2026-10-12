"""SYNTHETIC tests: the publishable copy of an accepted-evidence database, and loading it."""

import random
import sqlite3
import unittest

from dashboard.backend import SQLiteBackend
from dashboard.public_export import audit_public, compare_api, export_public, load_public

from tests import test_dashboard_accepted as base
from tests import test_dashboard_accepted_grading as grading


class PublicExportTests(unittest.TestCase):
    setUp = base.AcceptedImportTests.setUp
    run_import = base.AcceptedImportTests.run_import
    get = base.AcceptedImportTests.get
    records = grading.AcceptedGradingTests.records
    folder = grading.AcceptedGradingTests.folder
    catalog = grading.AcceptedGradingTests.catalog
    load = grading.AcceptedGradingTests.load

    def private(self):
        _, db = self.run_import()
        self.load(db, self.folder())
        return db

    def test_public_copy_serves_identical_responses_without_private_data(self):
        db = self.private()
        out = str(self.tmp / "public.db")
        result = export_public(db, out, rng=random.Random(7))
        self.assertEqual(result["differences"], [])
        self.assertGreater(result["compared_routes"], 15)
        self.assertEqual(set(result["leaks"].values()), {0})
        pub = sqlite3.connect(out)
        tables = {r[0] for r in pub.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse(tables & {"source_text", "raw_record", "row_state"})
        dump = "\n".join(pub.iterdump())
        for rid, text, *_ in base.SOURCE:
            self.assertNotIn(rid + "'", dump)
            if text.strip():
                self.assertNotIn(text, dump)
        self.assertEqual(pub.execute("SELECT COUNT(*) FROM classifications WHERE evidence_quote<>''").fetchone()[0], 0)
        self.assertEqual(self.get(out, "/api/issues")[1]["items"][0]["issue_id"], "PLY-FAIL")

    def test_export_refuses_existing_file_and_private_leaks_are_detected(self):
        db = self.private()
        out = self.tmp / "public.db"
        out.write_text("")
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_public(db, str(out))
        out.unlink()
        export_public(db, str(out), rng=random.Random(1))
        conn = sqlite3.connect(str(out))
        with conn:  # simulate a broken export: one exact quote and one review ID put back
            conn.execute("UPDATE classifications SET evidence_quote='crashes every time I open my playlist' "
                         "WHERE rowid=(SELECT MIN(rowid) FROM classifications)")
            conn.execute("UPDATE records SET review_id='synthetic-2' WHERE rowid=(SELECT MIN(rowid) FROM records)")
        leaks = audit_public(db, str(out))
        self.assertGreater(leaks["exact_quotes"], 0)
        self.assertGreater(leaks["review_ids"], 0)

    def test_load_into_empty_target_and_refuse_a_second_load(self):
        db = self.private()
        out = str(self.tmp / "public.db")
        export_public(db, out, rng=random.Random(3))
        target = str(self.tmp / "target.db")
        with SQLiteBackend(target, readonly=False) as backend:
            result = load_public(backend, out, rows_per_batch=3)
        self.assertEqual(result["tables"]["records"], len(base.SOURCE))
        self.assertEqual(compare_api(db, target)["differences"], [])
        with SQLiteBackend(target, readonly=False) as backend:
            with self.assertRaisesRegex(ValueError, "not empty"):
                load_public(backend, out)
        with SQLiteBackend(str(self.tmp / "other.db"), readonly=False) as backend:
            with self.assertRaisesRegex(ValueError, "not a public export"):
                load_public(backend, db)


if __name__ == "__main__":
    unittest.main()

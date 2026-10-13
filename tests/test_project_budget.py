"""Synthetic accounting checks; no provider or credential access."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from spotify_pipeline.project_budget import ProjectBudget


def fixtures(folder):
    paths = {name: str(Path(folder) / (name + ".db")) for name in
             ("benchmark", "batch_v1", "batch_v2", "jev_checkpoint")}
    with sqlite3.connect(paths["benchmark"]) as db:
        db.execute("CREATE TABLE calls(id INTEGER,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
        db.executemany("INSERT INTO calls VALUES (?,?,?,?)", [
            (1, "succeeded", 1_000_000, 100_000),
            (2, "uncertain", 25_000_000, None)])
    for name, charge in (("batch_v1", 200_000), ("batch_v2", 240_000)):
        with sqlite3.connect(paths[name]) as db:
            db.execute("CREATE TABLE batches(id INTEGER,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
            db.execute("INSERT INTO batches VALUES (1,'succeeded',24903544,?)", (charge,))
    with sqlite3.connect(paths["jev_checkpoint"]) as db:
        db.execute("CREATE TABLE attempts(id INTEGER,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
        db.execute("INSERT INTO attempts VALUES (1,'settled',2688000,20000000)")
        db.execute("CREATE TABLE checkpoint_seed(v1_charge_nusd INTEGER)")
        db.execute("INSERT INTO checkpoint_seed VALUES (3691254)")
    return paths


class ProjectBudgetTest(unittest.TestCase):
    def test_all_legacy_sources_required_and_restart_preserves_unknown_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with self.assertRaisesRegex(ValueError, "all four"):
                ProjectBudget(budget_path, {k: v for k, v in paths.items() if k != "batch_v1"})
            with ProjectBudget(budget_path, paths) as budget:
                self.assertEqual(budget.exposure("openrouter"), 25_540_000)
                self.assertEqual(budget.exposure("jev"), 23_691_254)
                with self.assertRaises(sqlite3.OperationalError):
                    budget.reserve("rolled-back", "openrouter", 1000,
                        record=lambda db: db.execute("INSERT INTO absent VALUES (1)"))
                self.assertIsNone(budget.db.execute("SELECT 1 FROM reservations WHERE request_key='rolled-back'").fetchone())
                budget.reserve("batch-1", "openrouter", 24_903_544)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    budget.reserve("batch-1", "openrouter", 24_903_544)
                budget.uncertain("batch-1")
                self.assertEqual(budget.exposure("openrouter"), 50_443_544)
            with ProjectBudget(budget_path, paths) as restarted:
                self.assertEqual(restarted.exposure("openrouter"), 50_443_544)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    restarted.reserve("batch-1", "openrouter", 24_903_544)
            with sqlite3.connect(paths["batch_v1"]) as db:
                db.execute("UPDATE batches SET charged_nusd=0")
            with self.assertRaisesRegex(ValueError, "historical cost ledger changed"):
                ProjectBudget(budget_path, paths)

    def test_two_workers_share_one_atomic_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with ProjectBudget(budget_path, paths):
                pass

            def try_reserve(number):
                with ProjectBudget(budget_path, paths) as budget:
                    try:
                        budget.reserve("worker-" + str(number), "openrouter", 2_500_000_000)
                        return True
                    except ValueError as error:
                        self.assertIn("cap", str(error))
                        return False

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sum(pool.map(try_reserve, range(2))), 1)
            with ProjectBudget(budget_path, paths) as budget:
                self.assertEqual(budget.exposure("openrouter"), 2_525_540_000)
                with self.assertRaisesRegex(ValueError, "cap"):
                    budget.reserve("jev-too-much", "jev", 4_990_000_000)
                budget.reserve("jev-one", "jev", 100_000_000)
                budget.settle("jev-one", "quarantined_metered", 30_000)
                self.assertEqual(budget.exposure("jev"), 23_721_254)

    def test_approved_jev_cap_migration_preserves_holds_and_eight_global_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with ProjectBudget(budget_path, paths) as budget:
                budget.reserve("old-hold", "openrouter", 10_000_000)
                budget.uncertain("old-hold")
                budget.db.execute("UPDATE caps SET cap_nusd=600000000 WHERE budget='jev'")
                budget.db.commit()
            with ProjectBudget(budget_path, paths) as budget:
                self.assertEqual(dict(budget.db.execute("SELECT budget,cap_nusd FROM caps")),
                    {"jev": 5_000_000_000, "openrouter": 5_000_000_000})
                self.assertEqual(budget.exposure("openrouter"), 35_540_000)
                for number in range(8):
                    budget.reserve("active-" + str(number), "jev", 2_688_000)
                with self.assertRaisesRegex(ValueError, "global paid-request limit"):
                    budget.reserve("ninth", "openrouter", 5_545_984)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    budget.reserve("active-0", "jev", 2_688_000)
                budget.uncertain("active-0")
                budget.reserve("after-hold", "openrouter", 5_545_984)
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 8)

    def test_twelve_process_connections_admit_only_eight_unique_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with ProjectBudget(budget_path, paths):
                pass

            def try_reserve(number):
                with ProjectBudget(budget_path, paths) as budget:
                    try:
                        budget.reserve("parallel-" + str(number), "jev", 2_688_000)
                        return True
                    except ValueError as error:
                        self.assertIn("global paid-request limit", str(error))
                        return False

            with ThreadPoolExecutor(max_workers=12) as pool:
                self.assertEqual(sum(pool.map(try_reserve, range(12))), 8)
            with ProjectBudget(budget_path, paths) as budget:
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0], 8)
                self.assertEqual(budget.exposure("jev"), 23_691_254 + 8 * 2_688_000)

    def test_concurrent_identical_request_key_is_admitted_once(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with ProjectBudget(budget_path, paths):
                pass

            def try_same_key(_):
                with ProjectBudget(budget_path, paths) as budget:
                    try:
                        budget.reserve("same-source-request", "openrouter", 5_545_984)
                        return True
                    except ValueError as error:
                        self.assertIn("duplicate", str(error))
                        return False

            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(try_same_key, range(4))), 1)

    def test_shared_ceiling_rejects_conflicting_instances_and_safe_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            # A fresh or older ledger always starts at eight, including when
            # the first caller requests twelve.
            with self.assertRaisesRegex(ValueError, "differs from shared ledger"):
                ProjectBudget(budget_path, paths, max_global_inflight=12)
            with ProjectBudget(budget_path, paths) as first:
                self.assertEqual(first.max_global_inflight, 8)
                with self.assertRaisesRegex(ValueError, "differs from shared ledger"):
                    ProjectBudget(budget_path, paths, max_global_inflight=12)
                with ProjectBudget(budget_path, paths, max_global_inflight=None) as admin:
                    with self.assertRaisesRegex(ValueError, "another budget user"):
                        admin.configure_global_inflight(12)
                for i in range(8):
                    first.reserve("held-" + str(i), "jev", 2_688_000)
                with self.assertRaisesRegex(ValueError, "global paid-request limit"):
                    first.reserve("ninth", "jev", 2_688_000)
            with ProjectBudget(budget_path, paths, max_global_inflight=None) as admin:
                with self.assertRaisesRegex(ValueError, "active reservations"):
                    admin.configure_global_inflight(12)
                for i in range(8):
                    admin.uncertain("held-" + str(i))
                admin.configure_global_inflight(12)
                self.assertEqual(admin.max_global_inflight, 12)
            with self.assertRaisesRegex(ValueError, "differs from shared ledger"):
                ProjectBudget(budget_path, paths)  # stale default-eight user
            with ProjectBudget(budget_path, paths, max_global_inflight=12) as raised:
                for i in range(12):
                    raised.reserve("raised-" + str(i), "jev", 2_688_000)
                with self.assertRaisesRegex(ValueError, "global paid-request limit"):
                    raised.reserve("thirteenth", "jev", 2_688_000)
                self.assertEqual(raised.db.execute("SELECT value FROM coordination "
                    "WHERE key='global_inflight_limit'").fetchone()[0], 12)

    def test_conflicting_eight_and_twelve_callers_cannot_race_to_ninth(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = fixtures(folder)
            budget_path = str(Path(folder) / "project.db")
            with ProjectBudget(budget_path, paths):
                pass

            def attempt(i):
                try:
                    with ProjectBudget(budget_path, paths,
                                       max_global_inflight=12 if i % 2 else 8) as budget:
                        budget.reserve("mixed-" + str(i), "jev", 2_688_000)
                        return "admitted"
                except ValueError as exc:
                    return str(exc)

            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(attempt, range(20)))
            self.assertEqual(results.count("admitted"), 8)
            self.assertTrue(all("differs from shared ledger" in value
                for i, value in enumerate(results) if i % 2))
            with ProjectBudget(budget_path, paths) as budget:
                self.assertEqual(budget.db.execute("SELECT COUNT(*) FROM reservations "
                    "WHERE status='reserved'").fetchone()[0], 8)


if __name__ == "__main__":
    unittest.main()

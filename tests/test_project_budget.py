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
                    budget.reserve("jev-too-much", "jev", 590_000_000)
                budget.reserve("jev-one", "jev", 100_000_000)
                budget.settle("jev-one", "quarantined_metered", 30_000)
                self.assertEqual(budget.exposure("jev"), 23_721_254)


if __name__ == "__main__":
    unittest.main()

"""No-network synthetic cold and warm handoff regression."""

import unittest

from tools.offline_pipeline_harness import run_harness


class OfflineHarnessTests(unittest.TestCase):
    def test_synthetic_cold_and_warm_handoffs(self):
        result = run_harness()
        self.assertEqual(result["provenance"], "synthetic_fixture")
        self.assertEqual(result["network_calls"], 0)
        cold, warm = result["phases"]["cold"], result["phases"]["warm"]
        self.assertEqual(cold["classifications"], 2)
        self.assertEqual(warm["classifications"], 2)
        self.assertEqual(cold["stub_calls"]["classify"], 1)
        self.assertEqual(cold["stub_calls"]["evidence"], 1)
        self.assertTrue(all(count == 0 for count in warm["stub_calls"].values()))
        self.assertGreaterEqual(cold["wall_seconds"], cold["stage_seconds"]["ingest"])
        self.assertGreaterEqual(warm["wall_seconds"], 0)


if __name__ == "__main__":
    unittest.main()

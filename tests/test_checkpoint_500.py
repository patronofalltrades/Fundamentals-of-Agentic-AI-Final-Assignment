"""Synthetic checkpoint identity and bounded-scope preflight."""

import os
import tempfile
import unittest
from unittest.mock import patch

from tests.helpers import manifest_entry, write_csv, write_manifest
from tools.checkpoint_500 import plan, source_rows


class CheckpointTests(unittest.TestCase):
    def test_exact_500_and_new_text_count(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "checkpoint_500.csv")
            manifest = os.path.join(folder, "manifest.json")
            rows = [["synthetic-%d" % i, "Synthetic issue %d" % (i if i != 100 else 0),
                     "2", "0", "1.0", "2022-05-17 00:01:07"] for i in range(500)]
            write_csv(source, rows)
            write_manifest(manifest, {"checkpoint_500.csv": manifest_entry(source)})
            with patch("tools.checkpoint_500.inspect_seed", return_value=(
                    {"config_hash": "synthetic-hash"}, 4262454)):
                report = plan(source, manifest, "synthetic-seed")
            self.assertEqual(report["remaining_source_rows"], 400)
            self.assertEqual(report["new_distinct_texts_at_most"], 399)
            self.assertEqual(report["exact_text_cache_candidates"], 1)
            self.assertEqual(report["new_jev_headroom_usd"], "0.592046292")

    def test_duplicate_id_and_changed_manifest_block_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "checkpoint_500.csv")
            manifest = os.path.join(folder, "manifest.json")
            rows = [["synthetic-%d" % i, "Synthetic issue %d" % i,
                     "2", "0", "1.0", "2022-05-17 00:01:07"] for i in range(500)]
            write_csv(source, rows)
            write_manifest(manifest, {"checkpoint_500.csv": manifest_entry(source)})
            rows[499][0] = rows[0][0]
            write_csv(source, rows)
            with self.assertRaisesRegex(ValueError, "manifest"):
                source_rows(source, manifest)
            write_manifest(manifest, {"checkpoint_500.csv": manifest_entry(source)})
            with self.assertRaisesRegex(ValueError, "distinct"):
                source_rows(source, manifest)


if __name__ == "__main__":
    unittest.main()

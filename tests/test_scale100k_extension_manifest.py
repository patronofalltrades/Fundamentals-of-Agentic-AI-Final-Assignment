"""Synthetic source identity tests for optional accepted-target gates."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spotify_pipeline.contract import SOURCE_FIELDS, file_sha256, row_sha256, text_sha256
from tools import scale100k_manifest as manifest


class ExtensionManifestTest(unittest.TestCase):
    def test_freeze_and_load_exact_extension_without_reusing_prior_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.csv"
            supplied = root / "supplied.json"
            extension_path = root / "extension.json"
            rows = [{"review_id": "id" + str(i), "review_text": "review " + str(i),
                "review_rating": "3", "review_likes": "0", "app_version": "",
                "review_timestamp": "2023-01-01 00:00:00"} for i in range(1, 5)]
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            source_sha = file_sha256(str(source))
            supplied.write_text(json.dumps({"files": {source.name: {
                "bytes": source.stat().st_size, "sha256": source_sha}}}))
            base = {"source_file_sha256": source_sha, "rows": [{"review_id": "id2"}]}
            with patch.object(manifest, "EXTENSION_FIRST", 3), \
                    patch.object(manifest, "EXTENSION_LAST", 4), \
                    patch.object(manifest, "EXTENSION_OUT", extension_path):
                frozen = manifest.build_extension(source, supplied, base, "base-sha", {"id1"})
                extension_path.write_text(manifest.canonical(frozen))
                loaded, digest = manifest.load_extension(base, "base-sha", {"id1"})
                self.assertEqual(loaded, frozen)
                self.assertEqual(digest, file_sha256(str(extension_path)))
                self.assertEqual([r["source_position"] for r in loaded["rows"]], [3, 4])
                frozen["rows"][0]["review_id"] = "id1"
                frozen["rows"][0]["source_sha256"] = row_sha256([
                    frozen["rows"][0][field] for field in SOURCE_FIELDS])
                frozen["rows"][0]["text_sha256"] = text_sha256(
                    frozen["rows"][0]["review_text"])
                extension_path.write_text(manifest.canonical(frozen))
                with self.assertRaisesRegex(ValueError, "frozen extension row differs"):
                    manifest.load_extension(base, "base-sha", {"id1"})


if __name__ == "__main__":
    unittest.main()

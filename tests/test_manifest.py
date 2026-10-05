"""SYNTHETIC tests for manifest identity and full-corpus profile validation."""

import os
import tempfile
import unittest

from spotify_pipeline.contract import FULL_CORPUS_NAME, file_sha256
from spotify_pipeline.errors import ManifestError
from spotify_pipeline.manifest import (
    check_profile,
    declared_profile,
    validate_identity,
)

from tests.helpers import make_input, manifest_entry

COMPUTED = {
    "records": 5,
    "duplicate_review_ids": 0,
    "empty_review_text": 1,
    "missing_app_version": 2,
    "distinct_nonempty_texts": 4,
    "reviews_by_month": {"2022-05": 1, "2022-06": 2, "2023-01": 1, "2023-11": 1},
    "reviews_by_rating": {"5": 1, "4": 1, "3": 1, "2": 1, "1": 1},
    "first_review": "2022-05-17 00:01:07",
    "last_review": "2023-11-15 23:16:10",
}

DECLARED = {
    "counts": {
        "records": 5,
        "duplicate_review_ids": 0,
        "empty_review_text": 1,
        "missing_app_version": 2,
    },
    "reviews_by_month": {"2022-05": 1, "2022-06": 2, "2023-01": 1, "2023-11": 1},
    "reviews_by_rating": {"5": 1, "4": 1, "3": 1, "2": 1, "1": 1},
    "window": {
        "start_inclusive": "2022-05-17",
        "end_exclusive": "2023-11-17",
        "first_review": "2022-05-17 00:01:07",
        "last_review": "2023-11-15 23:16:10",
    },
}


def _full_manifest(entry):
    return {
        "files": {FULL_CORPUS_NAME: entry},
        "profile": dict(DECLARED["counts"]),
        "reviews_by_month": dict(DECLARED["reviews_by_month"]),
        "reviews_by_rating": dict(DECLARED["reviews_by_rating"]),
        "window": dict(DECLARED["window"]),
    }


class IdentityTests(unittest.TestCase):
    def test_valid_identity_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {"files": {"sample.csv": manifest_entry(path)}}
            status = validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))
            self.assertTrue(status["validated"])
            self.assertTrue(status["sha256_matched"])
            self.assertTrue(status["bytes_matched"])

    def test_missing_entry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            with self.assertRaises(ManifestError):
                validate_identity({"files": {}}, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_wrong_checksum_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {"files": {"sample.csv": {"sha256": "0" * 64, "bytes": os.path.getsize(path)}}}
            with self.assertRaises(ManifestError):
                validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_wrong_byte_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            entry = manifest_entry(path)
            entry["bytes"] = entry["bytes"] + 1
            with self.assertRaises(ManifestError):
                validate_identity({"files": {"sample.csv": entry}}, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_bare_string_entry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {"files": {"sample.csv": file_sha256(path)}}
            with self.assertRaises(ManifestError):
                validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_alias_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {
                "files": {
                    "sample.csv": {"checksum": file_sha256(path), "size": os.path.getsize(path)}
                }
            }
            with self.assertRaises(ManifestError):
                validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_missing_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {"files": {"sample.csv": {"sha256": file_sha256(path)}}}
            with self.assertRaises(ManifestError):
                validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))

    def test_invalid_sha_shape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp)
            manifest = {"files": {"sample.csv": {"sha256": "+" + "a" * 63, "bytes": os.path.getsize(path)}}}
            with self.assertRaises(ManifestError):
                validate_identity(manifest, "sample.csv", file_sha256(path), os.path.getsize(path))


class ProfileTests(unittest.TestCase):
    def test_declared_profile_parses_root_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp, name=FULL_CORPUS_NAME)
            manifest = _full_manifest(manifest_entry(path))
            declared = declared_profile(manifest, FULL_CORPUS_NAME)
            self.assertEqual(declared["counts"]["records"], 5)
            self.assertEqual(declared["window"]["end_exclusive"], "2023-11-17")
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_root_profile_missing_count_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_input(tmp, name=FULL_CORPUS_NAME)
            manifest = _full_manifest(manifest_entry(path))
            del manifest["profile"]["missing_app_version"]
            with self.assertRaises(ManifestError):
                declared_profile(manifest, FULL_CORPUS_NAME)

    def test_count_mismatch_rejected(self):
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, {"counts": {"records": 6}}, COMPUTED)

    def test_extra_computed_month_rejected(self):
        declared = dict(DECLARED)
        declared["reviews_by_month"] = {"2022-05": 1, "2022-06": 2, "2023-01": 1}
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_rating_mismatch_rejected(self):
        declared = dict(DECLARED)
        declared["reviews_by_rating"] = dict(DECLARED["reviews_by_rating"])
        declared["reviews_by_rating"]["5"] = 99
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_window_bound_rejected(self):
        declared = dict(DECLARED)
        declared["window"] = dict(DECLARED["window"])
        declared["window"]["end_exclusive"] = "2023-11-15"
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_window_first_review_mismatch_rejected(self):
        declared = dict(DECLARED)
        declared["window"] = dict(DECLARED["window"])
        declared["window"]["first_review"] = "2022-05-18 00:01:07"
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_window_bad_type_rejected(self):
        declared = dict(DECLARED)
        declared["window"] = {"start_inclusive": 20220517}
        with self.assertRaises(ManifestError):
            check_profile(FULL_CORPUS_NAME, declared, COMPUTED)

    def test_samples_skip_root_profile(self):
        check_profile("analysis_10000.csv", DECLARED, {"records": 999999})


if __name__ == "__main__":
    unittest.main()

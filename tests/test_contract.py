"""SYNTHETIC tests for the frozen hashing contract."""

import hashlib
import os
import tempfile
import unittest

from spotify_pipeline.contract import (
    canonical_row_payload,
    file_sha256,
    parsed_rows_sha256,
    row_sha256,
    text_sha256,
)

# Published SHA-256 test vectors used as literal golden values.
SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class ContractHashTests(unittest.TestCase):
    def test_file_sha256_known_literal_vectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty.bin")
            with open(empty, "wb") as handle:
                handle.write(b"")
            self.assertEqual(file_sha256(empty), SHA256_EMPTY)

            abc = os.path.join(tmp, "abc.bin")
            with open(abc, "wb") as handle:
                handle.write(b"abc")
            self.assertEqual(file_sha256(abc), SHA256_ABC)

    def test_row_sha256_canonical_literal_vector(self):
        fields = ["1", "hello", "5", "0", "1.0.0", "2022-05-17 00:01:07"]
        literal = '["1","hello","5","0","1.0.0","2022-05-17 00:01:07"]'
        self.assertEqual(canonical_row_payload(fields), literal)
        expected = hashlib.sha256(literal.encode("utf-8")).hexdigest()
        self.assertEqual(row_sha256(fields), expected)

    def test_multiline_and_unicode_preserved(self):
        fields = ["7", "line one\nline two \u2615", "2", "1", "1.3.0", "2023-01-01 00:00:00"]
        literal = (
            '["7","line one\\nline two \u2615","2","1","1.3.0","2023-01-01 00:00:00"]'
        )
        self.assertEqual(canonical_row_payload(fields), literal)
        self.assertEqual(
            row_sha256(fields), hashlib.sha256(literal.encode("utf-8")).hexdigest()
        )

    def test_whitespace_distinct_texts_hash_differently(self):
        a = ["1", "two spaces", "5", "0", "", "2022-05-17 00:01:07"]
        b = ["1", "two  spaces", "5", "0", "", "2022-05-17 00:01:07"]
        self.assertNotEqual(row_sha256(a), row_sha256(b))
        self.assertNotEqual(text_sha256(a[1]), text_sha256(b[1]))

    def test_parsed_rows_sha256_matches_concatenation(self):
        hashes = [
            row_sha256(["1", "a", "5", "0", "", "2022-05-17 00:01:07"]),
            row_sha256(["2", "b", "4", "1", "1.0.0", "2022-06-01 12:00:00"]),
        ]
        expected = hashlib.sha256(
            b"".join(bytes.fromhex(h) for h in hashes)
        ).hexdigest()
        self.assertEqual(parsed_rows_sha256(hashes), expected)


if __name__ == "__main__":
    unittest.main()

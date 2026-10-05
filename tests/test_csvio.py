"""SYNTHETIC tests for strict CSV parsing and field validation."""

import os
import tempfile
import unittest

from spotify_pipeline.contract import SOURCE_FIELDS
from spotify_pipeline.csvio import (
    iter_source_rows,
    validate_header,
    validate_likes,
    validate_rating,
    validate_timestamp,
)
from spotify_pipeline.errors import ValidationError

from tests.helpers import SYNTHETIC_ROWS, write_csv


class CsvParsingTests(unittest.TestCase):
    def test_reads_exact_rows_including_multiline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample.csv")
            write_csv(path, SYNTHETIC_ROWS)
            rows = list(iter_source_rows(path))
            self.assertEqual(len(rows), len(SYNTHETIC_ROWS))
            self.assertEqual(rows[3][1][1], "line one\nline two")
            self.assertEqual(rows[4][1][1], "caf\u00e9 \u2615")

    def test_golden_header_with_labels_rejected(self):
        header = list(SOURCE_FIELDS) + ["topic", "intent"]
        with self.assertRaises(ValidationError):
            validate_header(header)

    def test_reordered_or_extra_header_rejected(self):
        with self.assertRaises(ValidationError):
            validate_header(list(reversed(SOURCE_FIELDS)))
        with self.assertRaises(ValidationError):
            validate_header(["review_id", "review_text"])

    def test_malformed_row_width_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            write_csv(path, [["1", "text", "5", "0", "1.0.0"]])
            with self.assertRaises(ValidationError):
                list(iter_source_rows(path))

    def test_unterminated_quote_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(",".join(SOURCE_FIELDS) + "\n")
                handle.write('1,"unterminated text,5,0,1.0.0,2022-05-17 00:01:07\n')
            with self.assertRaises(ValidationError):
                list(iter_source_rows(path))

    def test_malformed_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            with open(path, "wb") as handle:
                handle.write((",".join(SOURCE_FIELDS) + "\n").encode("utf-8"))
                handle.write(b"1,invalid \xff\xfe text,5,0,1.0.0,2022-05-17 00:01:07\n")
            with self.assertRaises(ValidationError):
                list(iter_source_rows(path))

    def test_field_validation(self):
        validate_rating("5")
        with self.assertRaises(ValidationError):
            validate_rating("0")
        with self.assertRaises(ValidationError):
            validate_rating("5.0")
        with self.assertRaises(ValidationError):
            validate_rating("5\n")
        validate_likes("0")
        validate_likes("12345")
        with self.assertRaises(ValidationError):
            validate_likes("-1")
        with self.assertRaises(ValidationError):
            validate_likes("12\n")
        validate_timestamp("2022-05-17 00:01:07")
        with self.assertRaises(ValidationError):
            validate_timestamp("2022-05-17T00:01:07")
        with self.assertRaises(ValidationError):
            validate_timestamp("2022-13-40 99:99:99")


if __name__ == "__main__":
    unittest.main()

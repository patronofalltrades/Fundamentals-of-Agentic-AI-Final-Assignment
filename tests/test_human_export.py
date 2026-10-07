"""Synthetic workbook tests. No real golden answers are read or made here."""

import csv
import hashlib
import os
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

from tools.export_human_labels import HEADERS, LabelExportError, export_labels


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _make_fixture(directory, *, incomplete=False, changed_source=False, bad_quote=False, formula=False):
    source = os.path.join(directory, "synthetic-blank.csv")
    rows = [
        ["test-id-1", "Playback stops", "2", "0", "", "2023-01-01 12:00:00"],
        ["test-id-2", "Good downloads", "5", "1", "1.0", "2023-01-02 12:00:00"],
    ]
    with open(source, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(row + [""] * 7 for row in rows)
    with open(source, "rb") as handle:
        checksum = hashlib.sha256(handle.read()).hexdigest()

    workbook = os.path.join(directory, "synthetic.xlsx")
    all_rows = [list(HEADERS)] + [
        rows[0] + ["playback", "complaint", "-0.5", "3", "[]", "stops", "false"],
        rows[1] + ["downloads", "praise", "0.8", "1", "[]", "downloads", "true"],
    ]
    if incomplete:
        all_rows[2][6] = ""
    if changed_source:
        all_rows[1][0] = "changed-id"
    if bad_quote:
        all_rows[1][11] = "not present"

    root = ET.Element(f"{{{MAIN}}}worksheet")
    data = ET.SubElement(root, f"{{{MAIN}}}sheetData")
    for row_num, values in enumerate(all_rows, 1):
        row_node = ET.SubElement(data, f"{{{MAIN}}}row", {"r": str(row_num)})
        for index, value in enumerate(values):
            letter = chr(ord("A") + index)
            cell = ET.SubElement(row_node, f"{{{MAIN}}}c", {"r": f"{letter}{row_num}", "t": "inlineStr"})
            if formula and row_num == 2 and index == 6:
                ET.SubElement(cell, f"{{{MAIN}}}f").text = '"playback"'
            ET.SubElement(ET.SubElement(cell, f"{{{MAIN}}}is"), f"{{{MAIN}}}t").text = value

    book = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Label 50" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
            '</Relationships>')
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/workbook.xml", book)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(root, encoding="utf-8"))
    return source, workbook, checksum


class HumanExportTests(unittest.TestCase):
    def test_valid_manual_synthetic_workbook_exports_original_source_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            source, workbook, checksum = _make_fixture(directory)
            output = os.path.join(directory, "export.csv")
            self.assertEqual(export_labels(workbook, source, output, 2, checksum), 2)
            with open(source, encoding="utf-8", newline="") as handle:
                before = list(csv.reader(handle))
            with open(output, encoding="utf-8", newline="") as handle:
                after = list(csv.reader(handle))
            self.assertEqual([row[:6] for row in after], [row[:6] for row in before])
            self.assertEqual(after[1][6:8], ["playback", "complaint"])
            with self.assertRaisesRegex(LabelExportError, "already exists"):
                export_labels(workbook, source, output, 2, checksum)

    def test_incomplete_or_changed_answers_never_publish(self):
        for name in ("incomplete", "changed_source", "bad_quote", "formula"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                source, workbook, checksum = _make_fixture(directory, **{name: True})
                output = os.path.join(directory, "export.csv")
                with self.assertRaises(LabelExportError):
                    export_labels(workbook, source, output, 2, checksum)
                self.assertFalse(os.path.exists(output))

    def test_source_checksum_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            source, workbook, _ = _make_fixture(directory)
            output = os.path.join(directory, "export.csv")
            with self.assertRaisesRegex(LabelExportError, "checksum"):
                export_labels(workbook, source, output, 2, "0" * 64)
            self.assertFalse(os.path.exists(output))


if __name__ == "__main__":
    unittest.main()

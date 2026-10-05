"""Export a manually labeled golden-50 workbook to a validated CSV.

This tool checks structure and formatting only. It does not infer or judge labels.
The original source row strings must be byte-for-byte equal after CSV parsing.
"""

import argparse
import csv
import hashlib
import json
import os
import posixpath
import re
import sys
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET


HEADERS = (
    "review_id", "review_text", "review_rating", "review_likes",
    "app_version", "review_timestamp", "topic", "intent", "sentiment",
    "severity", "entities", "evidence_quote", "needs_review",
)
TOPICS = {"access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"}
INTENTS = {"cancellation", "complaint", "request", "praise", "unclear"}
PINNED_SOURCE_SHA256 = "1a125c3e509f58b0246ba16d0ea332675a53ffadb1928be4338a0bd7053a11c7"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
MAX_MEMBER_BYTES = 20_000_000
MAX_ARCHIVE_BYTES = 40_000_000


class LabelExportError(ValueError):
    pass


def _source_rows(path, expected_sha):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha:
        raise LabelExportError("source CSV checksum differs from the verified blank template")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, strict=True))
    if not rows or tuple(rows[0]) != HEADERS:
        raise LabelExportError("source CSV headers differ from the golden template")
    return rows


def _column_number(letters):
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - ord("A") + 1
    return value


def _sheet_path(archive):
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    candidates = [sheet for sheet in book.findall(f".//{{{MAIN}}}sheet") if sheet.get("name") == "Label 50"]
    if len(candidates) != 1:
        raise LabelExportError("expected one worksheet named 'Label 50'")
    relation_id = candidates[0].get(f"{{{DOC_REL}}}id")
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = [rel.get("Target") for rel in relationships.findall(f"{{{PKG_REL}}}Relationship") if rel.get("Id") == relation_id]
    if len(targets) != 1 or not targets[0]:
        raise LabelExportError("cannot resolve the labeling worksheet")
    target = targets[0]
    path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
    if not path.startswith("xl/worksheets/") or not path.endswith(".xml"):
        raise LabelExportError("unexpected worksheet path")
    return path


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(f"{{{MAIN}}}t")) for item in root.findall(f"{{{MAIN}}}si")]


def _cell_value(cell, strings):
    if cell.find(f"{{{MAIN}}}f") is not None:
        raise LabelExportError("formulas are not allowed in source or answer cells")
    kind = cell.get("t")
    if kind == "inlineStr":
        inline = cell.find(f"{{{MAIN}}}is")
        return "" if inline is None else "".join(node.text or "" for node in inline.iter(f"{{{MAIN}}}t"))
    value = cell.findtext(f"{{{MAIN}}}v")
    if value is None:
        return ""
    if kind == "s":
        try:
            return strings[int(value)]
        except (ValueError, IndexError) as exc:
            raise LabelExportError("invalid shared-string reference") from exc
    if kind == "b":
        return "true" if value == "1" else "false" if value == "0" else value
    if kind == "e":
        raise LabelExportError("spreadsheet error value in source or answer cells")
    return value


def _workbook_rows(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if any(info.file_size > MAX_MEMBER_BYTES for info in infos) or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
            raise LabelExportError("workbook is unexpectedly large")
        strings = _shared_strings(archive)
        root = ET.fromstring(archive.read(_sheet_path(archive)))
    rows = {}
    for row in root.findall(f".//{{{MAIN}}}sheetData/{{{MAIN}}}row"):
        try:
            number = int(row.get("r"))
        except (TypeError, ValueError) as exc:
            raise LabelExportError("invalid worksheet row number") from exc
        if number in rows:
            raise LabelExportError("duplicate worksheet row")
        values = [""] * len(HEADERS)
        seen = set()
        for cell in row.findall(f"{{{MAIN}}}c"):
            match = CELL_REF.fullmatch(cell.get("r", ""))
            if match is None or int(match.group(2)) != number:
                raise LabelExportError("invalid cell address")
            column = _column_number(match.group(1))
            if column > len(HEADERS):
                continue
            if column in seen:
                raise LabelExportError("duplicate cell address")
            seen.add(column)
            values[column - 1] = _cell_value(cell, strings)
        rows[number] = values
    return rows


def _decimal(value, name, row):
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise LabelExportError(f"row {row}: {name} must be numeric") from exc
    if not number.is_finite():
        raise LabelExportError(f"row {row}: {name} must be finite")
    return number


def _validate_answer(values, row):
    topic, intent, sentiment, severity, entities, quote, review = values[6:]
    if any(value == "" for value in values[6:]):
        raise LabelExportError(f"row {row}: all seven human answer fields are required")
    if topic not in TOPICS:
        raise LabelExportError(f"row {row}: invalid topic")
    if intent not in INTENTS:
        raise LabelExportError(f"row {row}: invalid intent")
    if not Decimal(-1) <= _decimal(sentiment, "sentiment", row) <= Decimal(1):
        raise LabelExportError(f"row {row}: sentiment must be between -1 and 1")
    if _decimal(severity, "severity", row) not in {Decimal(x) for x in range(1, 6)}:
        raise LabelExportError(f"row {row}: severity must be an integer from 1 to 5")
    try:
        parsed_entities = json.loads(entities)
    except json.JSONDecodeError as exc:
        raise LabelExportError(f"row {row}: entities must be a JSON array") from exc
    if not isinstance(parsed_entities, list) or any(not isinstance(item, str) or not item.strip() for item in parsed_entities):
        raise LabelExportError(f"row {row}: entities must be a JSON array of nonempty strings")
    if not quote.strip() or quote not in values[1]:
        raise LabelExportError(f"row {row}: evidence_quote must be an exact nonempty substring of review_text")
    if review.lower() not in {"true", "false"}:
        raise LabelExportError(f"row {row}: needs_review must be true or false")
    values[12] = review.lower()


def export_labels(workbook_path, source_path, output_path, expected_rows=50, expected_sha=PINNED_SOURCE_SHA256):
    paths = [os.path.realpath(os.path.abspath(path)) for path in (workbook_path, source_path, output_path)]
    if len(set(paths)) != 3:
        raise LabelExportError("workbook, source and output must be distinct paths")
    if os.path.exists(output_path):
        raise LabelExportError("output already exists; choose a new path")
    source = _source_rows(source_path, expected_sha)
    if len(source) != expected_rows + 1:
        raise LabelExportError("source CSV row count differs from expected")
    parsed = _workbook_rows(workbook_path)
    if set(parsed) != set(range(1, expected_rows + 2)):
        raise LabelExportError("workbook has missing, extra or shifted rows")
    if tuple(parsed[1]) != HEADERS:
        raise LabelExportError("workbook headers differ from the golden template")
    output = [list(HEADERS)]
    for index in range(1, expected_rows + 1):
        row = parsed[index + 1]
        if row[:6] != source[index][:6]:
            raise LabelExportError(f"row {index + 1}: original source cells changed")
        _validate_answer(row, index + 1)
        output.append(row)
    fd = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerows(output)
    except Exception:
        os.unlink(output_path)
        raise
    return len(output) - 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        count = export_labels(args.workbook, args.source, args.out)
    except (LabelExportError, OSError, zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        parser.exit(2, f"Export stopped: {exc}\n")
    print(f"Validated and exported {count} human-labeled rows to {args.out}")


if __name__ == "__main__":
    main()

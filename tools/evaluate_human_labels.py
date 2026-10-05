"""Offline agreement against isolated human golden answers.

Only aggregate counts and scores leave this tool. It never makes model calls.
Incomplete or mechanically invalid human answers stop evaluation.
"""

import argparse
import csv
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# Direct invocation (`python3 tools/evaluate_human_labels.py`) places `tools/`
# rather than the repository root on sys.path. Keep both documented routes
# usable without installing this offline project.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spotify_pipeline.contract import row_sha256
from spotify_pipeline.jsonutil import loads_strict
from spotify_pipeline.errors import ValidationError
from spotify_pipeline.schema import validate_completed, validate_quarantine
from tools.export_human_labels import (
    HEADERS,
    INTENTS,
    PINNED_SOURCE_SHA256,
    TOPICS,
    LabelExportError,
    _source_rows,
    _validate_answer,
)


def _ratio(numerator, denominator):
    return str((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _mean(values):
    if not values:
        return None
    return str((sum(values) / Decimal(len(values))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _macro_f1(gold, predictions, field, classes):
    values = []
    for label in sorted(classes):
        tp = sum(predictions.get(key, {}).get(field) == label for key, row in gold.items() if row[field] == label)
        fp = sum(predictions.get(key, {}).get(field) == label for key, row in gold.items() if row[field] != label)
        fn = sum(predictions.get(key, {}).get(field) != label for key, row in gold.items() if row[field] == label)
        if tp + fp + fn:
            values.append(Decimal(2 * tp) / Decimal(2 * tp + fp + fn))
    return _mean(values)


def _load_gold(source_path, answers_path, expected_rows, expected_sha):
    source = _source_rows(source_path, expected_sha)
    if len(source) != expected_rows + 1:
        raise LabelExportError("source row count differs from expected")
    with open(answers_path, "r", encoding="utf-8-sig", newline="") as handle:
        answers = list(csv.reader(handle, strict=True))
    if len(answers) != len(source) or not answers or tuple(answers[0]) != HEADERS:
        raise LabelExportError("human answer CSV has missing, extra or reordered rows/columns")
    gold = {}
    for index, (base, answer) in enumerate(zip(source[1:], answers[1:]), 2):
        if len(answer) != len(HEADERS) or answer[:6] != base[:6]:
            raise LabelExportError(f"row {index}: original source fields changed")
        _validate_answer(answer, index)
        review_id = base[0]
        if review_id in gold:
            raise LabelExportError(f"row {index}: duplicate source ID")
        gold[review_id] = {
            "source": {"review_id": review_id, "review_text": base[1], "row_sha256": row_sha256(base[:6])},
            "topic": answer[6],
            "intent": answer[7],
            "sentiment": Decimal(answer[8]),
            "severity": int(Decimal(answer[9])),
        }
    return gold


def evaluate(source_path, answers_path, predictions_path, expected_rows=50, expected_sha=PINNED_SOURCE_SHA256):
    """Return aggregate diagnostics; never return labels, texts or IDs."""
    gold = _load_gold(source_path, answers_path, expected_rows, expected_sha)
    predictions = {}
    with open(predictions_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = loads_strict(line)
            except ValidationError as exc:
                raise LabelExportError(f"prediction line {line_number}: invalid JSON") from exc
            if not isinstance(record, dict):
                raise LabelExportError(f"prediction line {line_number}: expected object")
            review_id = record.get("review_id")
            if not isinstance(review_id, str):
                raise LabelExportError(f"prediction line {line_number}: review_id must be a string")
            if review_id not in gold:
                continue
            if review_id in predictions:
                raise LabelExportError(f"prediction line {line_number}: duplicate golden ID")
            source = gold[review_id]["source"]
            if record.get("source_sha256") != source["row_sha256"]:
                raise LabelExportError(f"prediction line {line_number}: source hash mismatch")
            if record.get("status") == "completed":
                errors = validate_completed(record, source=source)
                if errors:
                    raise LabelExportError(f"prediction line {line_number}: invalid completed record ({errors[0]})")
                predictions[review_id] = record
            elif record.get("status") == "quarantined":
                errors = validate_quarantine(record, source=source)
                if errors:
                    raise LabelExportError(f"prediction line {line_number}: invalid quarantine ({errors[0]})")
                predictions[review_id] = {"status": record.get("status")}
            else:
                raise LabelExportError(f"prediction line {line_number}: invalid status")

    completed = {key: row for key, row in predictions.items() if row.get("status") == "completed"}
    topic_matches = sum(row["topic"] == gold[key]["topic"] for key, row in completed.items())
    intent_matches = sum(row["intent"] == gold[key]["intent"] for key, row in completed.items())
    exact_matches = sum(
        row["topic"] == gold[key]["topic"]
        and row["intent"] == gold[key]["intent"]
        and row["severity"] == gold[key]["severity"]
        for key, row in completed.items()
    )
    severity_errors = [Decimal(abs(row["severity"] - gold[key]["severity"])) for key, row in completed.items()]
    sentiment_errors = [abs(Decimal(str(row["sentiment"])) - gold[key]["sentiment"]) for key, row in completed.items()]
    return {
        "status": "offline_diagnostics",
        "human_answer_rows": len(gold),
        "prediction_rows_completed": len(completed),
        "prediction_rows_missing_or_uncompleted": len(gold) - len(completed),
        "topic_accuracy_all_human_rows": _ratio(topic_matches, len(gold)),
        "intent_accuracy_all_human_rows": _ratio(intent_matches, len(gold)),
        "exact_topic_intent_severity_agreement_all_human_rows": _ratio(exact_matches, len(gold)),
        "topic_macro_f1_observed_classes": _macro_f1(gold, completed, "topic", TOPICS),
        "intent_macro_f1_observed_classes": _macro_f1(gold, completed, "intent", INTENTS),
        "severity_mae_completed_only": _mean(severity_errors),
        "sentiment_mae_completed_only": _mean(sentiment_errors),
        "note": "Missing or uncompleted predictions count against agreement denominators. Error means use completed rows only. Mechanical label checks do not certify human judgment.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="verified blank golden CSV")
    parser.add_argument("--answers", required=True, help="completed human CSV")
    parser.add_argument("--predictions", required=True, help="saved pipeline records.jsonl")
    parser.add_argument("--out", required=True, help="new aggregate report outside the public repo")
    args = parser.parse_args(argv)
    paths = [os.path.realpath(os.path.abspath(path)) for path in (args.source, args.answers, args.predictions, args.out)]
    if len(set(paths)) != 4 or os.path.exists(args.out):
        parser.exit(2, "Evaluation stopped: output must be a new, distinct file\n")
    try:
        report = evaluate(args.source, args.answers, args.predictions)
        with open(args.out, "x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (LabelExportError, OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        parser.exit(2, f"Evaluation stopped: {exc}\n")
    print(f"Wrote aggregate offline diagnostics for {report['human_answer_rows']} human rows")


if __name__ == "__main__":
    main()

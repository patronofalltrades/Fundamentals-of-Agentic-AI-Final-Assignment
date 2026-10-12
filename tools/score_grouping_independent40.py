"""Score frozen private grouping predictions against blind human decisions.

Only aggregate counts reach stdout. Answer values and per-case differences stay local.
"""

import argparse
import csv
import json
from pathlib import Path

from tools.issue_grouping_handoff import sha256


MANIFEST_SHA256 = "65c3d9ad0342099860a1977765fa88c419c17c584464513b0cd8e22d44df0f28"
CATALOG_SHA256 = "f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b"
ANSWER_COLUMNS = ["case_ref", "source_text", "independent_issue_id",
                  "evidence_rationale", "uncertainty_notes"]
PREDICTION_COLUMNS = ["case_ref", "source_sha256", "predicted_issue_id"]


def _by_case(rows, expected, kind):
    result = {}
    for row in rows:
        case = row.get("case_ref")
        if case not in expected or case in result:
            raise ValueError(kind + " case coverage differs")
        result[case] = row
    if set(result) != set(expected):
        raise ValueError(kind + " case coverage differs")
    return result


def score(manifest, catalog, answers, predictions):
    sources = _by_case(manifest["rows"],
                       {row["case_ref"] for row in manifest["rows"]}, "manifest")
    human = _by_case(answers, sources, "answer")
    predicted = _by_case(predictions, sources, "prediction")
    valid = {item["issue_id"] for item in catalog["issues"]}
    if len(valid) != len(catalog["issues"]):
        raise ValueError("catalog issue IDs repeat")
    exact = family = uncertain = 0
    used_answers, used_predictions = set(), set()
    for case, source in sources.items():
        answer, prediction = human[case], predicted[case]
        if answer.get("source_text") != source["source_text"] or \
                prediction.get("source_sha256") != source["source_sha256"]:
            raise ValueError("source identity differs")
        human_issue = answer.get("independent_issue_id", "").strip()
        predicted_issue = prediction.get("predicted_issue_id", "").strip()
        if human_issue not in valid or not answer.get("evidence_rationale", "").strip():
            raise ValueError("invalid issue decision")
        if predicted_issue not in valid:
            raise ValueError("invalid prediction issue")
        exact += human_issue == predicted_issue
        family += human_issue.split("-", 1)[0] == predicted_issue.split("-", 1)[0]
        uncertain += bool(answer.get("uncertainty_notes", "").strip())
        used_answers.add(human_issue)
        used_predictions.add(predicted_issue)
    return {"cases": len(sources), "exact_agreement": exact,
            "family_agreement": family, "uncertain_answers": uncertain,
            "answer_issue_ids_used": len(used_answers),
            "prediction_issue_ids_used": len(used_predictions)}


def _csv(path, columns):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError("CSV columns differ")
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path,
                        default=Path("local/issue_grouping_independent40_blind.csv"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path,
                        default=Path("local/issue_grouping_independent40_manifest.json"))
    parser.add_argument("--catalog", type=Path,
                        default=Path("docs/issue-catalog-pilot-v3.json"))
    args = parser.parse_args()
    if sha256(args.manifest) != MANIFEST_SHA256 or \
            sha256(args.catalog) != CATALOG_SHA256:
        raise ValueError("frozen manifest or catalog digest differs")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "spotify-grouping-independent40-v1" or \
            len(manifest.get("rows", [])) != 40:
        raise ValueError("frozen manifest shape differs")
    result = score(manifest, json.loads(args.catalog.read_text(encoding="utf-8")),
                   _csv(args.answers, ANSWER_COLUMNS),
                   _csv(args.predictions, PREDICTION_COLUMNS))
    result.update({"answer_csv_sha256": sha256(args.answers),
                   "predictions_sha256": sha256(args.predictions),
                   "manifest_sha256": sha256(args.manifest),
                   "catalog_sha256": sha256(args.catalog)})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build the dashboard's aggregate-only golden report from frozen offline scores.

The human answer file is read only as bytes for its SHA-256. No answer row or
review text is parsed, printed, or saved. The output must stay under local/.
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from dashboard.evaluation import evaluation_record


ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FROZEN_PREDICTIONS = "42bbc688c71648206cde882c7d4eb72f8ecf8c5154298f5520ce645427228d44"
HUMAN_BENCHMARK = "ff084828aa2d88970e70508dd36362aaaade3d48a1d1ee1d09503e24ffaeb0f6"
LABEL_CONFIG = "0bda2b8478fab805c56f033227017f6f37da9feb7da6b6a79b98b859cb10c647"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(aggregate, detailed, prediction_sha256, benchmark_sha256, label_config):
    if not SHA256.fullmatch(prediction_sha256) or not SHA256.fullmatch(benchmark_sha256):
        raise ValueError("prediction and benchmark SHA-256 values must be lowercase hex")
    if not SHA256.fullmatch(label_config):
        raise ValueError("label configuration must be a lowercase SHA-256")
    if (prediction_sha256, benchmark_sha256, label_config) != (FROZEN_PREDICTIONS, HUMAN_BENCHMARK, LABEL_CONFIG):
        raise ValueError("frozen prediction, human benchmark, or classifier digest changed")
    if detailed.get("frozen_predictions_sha256") != prediction_sha256:
        raise ValueError("detailed score does not name the frozen prediction file")
    total = aggregate.get("human_answer_rows")
    if type(total) is not int or total != 50 or detailed.get("human_answer_rows") != total:
        raise ValueError("expected the complete 50-row human set")
    if aggregate.get("prediction_rows_completed") != total or aggregate.get("prediction_rows_missing_or_uncompleted") != 0:
        raise ValueError("all 50 predictions must be completed")
    if detailed.get("case_level_data_in_report") is not False:
        raise ValueError("detailed report must omit case-level data")
    if detailed.get("human_needs_review") != {"false": 38, "true": 12}:
        raise ValueError("human-review aggregate differs from the frozen score")
    agreement = {
        "topic": float(aggregate["topic_accuracy_all_human_rows"]),
        "intent": float(aggregate["intent_accuracy_all_human_rows"]),
        "severity": detailed["severity_exact"] / total,
        "joint": float(aggregate["exact_topic_intent_severity_agreement_all_human_rows"]),
    }
    if detailed.get("topic_exact") != round(total * agreement["topic"]) or detailed.get("intent_exact") != round(total * agreement["intent"]):
        raise ValueError("exact match counts and rates differ")
    report = {
        "benchmark_version": "golden-50-human-v1-source-only",
        "benchmark_sha256": benchmark_sha256,
        "approved_cases": total,
        "total_cases": total,
        "missing_or_invalid_predictions": 0,
        "agreement": agreement,
        "severity_mae_on_valid_predictions": float(aggregate["severity_mae_completed_only"]),
        "official": False,
        "label_configs": [label_config],
    }
    evaluation_record(report, "original", label_config)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", required=True)
    parser.add_argument("--detailed", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--benchmark-file", required=True, help="human CSV; hashed as bytes only")
    parser.add_argument("--label-config", required=True)
    parser.add_argument("--out", required=True, help="new ignored JSON file under local/")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if ROOT.joinpath("local").resolve() not in out.parents or out.exists():
        parser.error("output must be a new file under ignored local/")
    with open(args.aggregate, encoding="utf-8") as handle:
        aggregate = json.load(handle)
    with open(args.detailed, encoding="utf-8") as handle:
        detailed = json.load(handle)
    report = build(aggregate, detailed, digest(args.predictions), digest(args.benchmark_file), args.label_config)
    out.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(out), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps({"result": "saved", "approved_cases": report["approved_cases"],
                      "agreement": report["agreement"], "official": report["official"]}, sort_keys=True))


if __name__ == "__main__":
    main()

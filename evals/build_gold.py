"""Convert the human golden labels into the checker's --gold benchmark format.

    python3 evals/build_gold.py            # writes evals/gold_benchmark.json and evals/golden_50.jsonl

Golden labels are evaluation-only: no pipeline module reads this folder (tests/test_gold_isolation.py).
Standard library only; no model calls.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline.rowhash import INTENTS, TOPICS, canonical  # noqa: E402

SOURCE = ROOT / "evals" / "golden_50_human_labels.csv"
VERSION = "golden-50-human-v1"
REVIEWER = "Hanif Ramadhan"


def load_rows(path=SOURCE):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_case(row) -> dict:
    rid = row["review_id"]
    topic, intent = row["topic"], row["intent"]
    severity = int(row["severity"])
    needs_review = {"true": True, "false": False}[row["needs_review"].strip().lower()]
    sentiment = float(row["sentiment"])
    entities = json.loads(row["entities"] or "[]")
    quote = row["evidence_quote"]
    if topic not in TOPICS or intent not in INTENTS or not 1 <= severity <= 5 or not -1 <= sentiment <= 1:
        raise ValueError("invalid golden label for " + rid)
    if quote and quote not in row["review_text"]:
        raise ValueError("golden evidence quote is not an exact source substring: " + rid)
    return {"review_id": rid, "topic": topic, "intent": intent, "severity": severity, "sentiment": sentiment,
            "entities": entities, "evidence_quote": quote, "needs_review": needs_review,
            "accepted_topic": [topic], "accepted_intent": [intent], "accepted_severity": [severity],
            "labeller": REVIEWER, "notes": ""}


def build(rows):
    cases = [to_case(r) for r in rows]
    if len({c["review_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate golden review_id")
    benchmark = {"version": VERSION, "cases": [
        {"review_id": c["review_id"], "status": "approved", "reviewer": c["labeller"],
         "accepted_topic": c["accepted_topic"], "accepted_intent": c["accepted_intent"],
         "accepted_severity": c["accepted_severity"]} for c in cases]}
    return cases, benchmark


def main():
    cases, benchmark = build(load_rows())
    out = ROOT / "evals"
    (out / "gold_benchmark.json").write_text(json.dumps(benchmark, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with open(out / "golden_50.jsonl", "w", encoding="utf-8") as f:
        for c in cases:
            f.write(canonical(c) + "\n")
    print("wrote %d cases (%s)" % (len(cases), VERSION))


if __name__ == "__main__":
    main()

"""Write a private, reproducible human audit pack from saved development rows.

This samples model outputs for review. It never supplies or scores golden labels.
The output includes original review text and must stay in ignored local/.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from spotify_pipeline import deepinfra_batch
from tools.checkpoint5000_qa import audit
from tools.checkpoint5000_qa_bundle import make_bundle

RANDOM_COUNT = 100
RISK_COUNT = 10
RISK_CATEGORIES = ("low_confidence", "needs_review", "high_severity",
                   "cached_evidence", "partial_batch", "quarantined")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def _pick(rows, count, seed, category):
    return sorted(rows, key=lambda row: hashlib.sha256((seed + ":" + category + ":" +
        row["review_id"] + ":" + row["source_sha256"]).encode("utf-8")).digest())[:count]


def build_pack(manifest_path, budget_path, seed="spotify-checkpoint5000-audit-v1"):
    bundle = make_bundle(manifest_path, budget_path)
    report, _ = audit(bundle, evidence_prompt=deepinfra_batch.PROMPT_VERSION,
                      sample_size=0)
    if not report["structurally_clean"]:
        raise ValueError("checkpoint structural QA failed; no audit sample")
    positions = {row["review_id"]: index + 1 for index, row in enumerate(bundle["source_rows"])}
    batches = {batch["batch_id"]: batch["status"] for batch in bundle["batches"]}
    with sqlite3.connect("file:" + os.path.abspath(budget_path) + "?mode=ro", uri=True) as db:
        confidences = {rid: json.loads(value).get("confidence") for rid, value in db.execute(
            "SELECT review_id,label_json FROM checkpoint_labels")}
    accepted = []
    quarantined = []
    for item in bundle["results"]:
        row = dict(item)
        row["source_position"] = positions[row["review_id"]]
        if row["status"] == "completed":
            row["jev_confidence"] = confidences.get(row["review_id"])
            row["evidence_batch_status"] = batches.get(row["batch_id"])
            accepted.append(row)
        elif row["status"] == "quarantined":
            quarantined.append(row)
    if len(accepted) < RANDOM_COUNT:
        raise ValueError("fewer than 100 accepted source rows")
    accepted.sort(key=lambda row: row["source_position"])
    random_rows = _pick(accepted, RANDOM_COUNT, seed, "accepted_random")
    random_ids = {row["review_id"] for row in random_rows}
    used = set(random_ids)
    risk = {}
    for category in RISK_CATEGORIES:
        if category == "quarantined":
            pool = quarantined
        else:
            pool = [row for row in accepted if row["review_id"] not in used]
            if category == "low_confidence":
                pool = [row for row in pool if isinstance(row["jev_confidence"], dict)
                    and row["jev_confidence"]
                    and min(row["jev_confidence"].values()) < 0.75]
            elif category == "needs_review":
                pool = [row for row in pool if row["needs_review"]]
            elif category == "high_severity":
                pool = [row for row in pool if row["severity"] >= 3]
            elif category == "cached_evidence":
                pool = [row for row in pool if row["is_cached"]]
            elif category == "partial_batch":
                pool = [row for row in pool if row["evidence_batch_status"] == "partial_succeeded"]
        chosen = _pick(pool, RISK_COUNT, seed, category)
        risk[category] = sorted(chosen, key=lambda row: row["source_position"])
        used.update(row["review_id"] for row in chosen)
    return {"schema": "checkpoint5000-human-audit-v1", "seed": seed,
        "frame": {"accepted_rows": len(accepted), "quarantined_rows": len(quarantined),
            "accepted_id_source_hash_sha256": _digest([(row["review_id"], row["source_sha256"])
                for row in accepted]), "structurally_clean": True},
        "random_accepted": sorted(random_rows, key=lambda row: row["source_position"]),
        "risk_cases": risk,
        "note": "Model-output audit only; no human golden answers or accuracy estimate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="local/checkpoint5000_manifest.json")
    parser.add_argument("--budget", default="local/project_budget.db")
    parser.add_argument("--out", default="local/checkpoint5000_audit_sample.json")
    parser.add_argument("--seed", default="spotify-checkpoint5000-audit-v1")
    args = parser.parse_args()
    target = Path(args.out).resolve()
    if not target.is_relative_to(Path("local").resolve()):
        parser.error("audit pack contains review text; output must be under local/")
    pack = build_pack(args.manifest, args.budget, args.seed)
    temporary = target.with_suffix(target.suffix + ".tmp")
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(pack, stream, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, target)
    print(json.dumps({"status": "private_audit_pack_written",
        "accepted_frame": pack["frame"]["accepted_rows"],
        "random_accepted": len(pack["random_accepted"]),
        "risk_counts": {key: len(value) for key, value in pack["risk_cases"].items()},
        "frame_sha256": pack["frame"]["accepted_id_source_hash_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()

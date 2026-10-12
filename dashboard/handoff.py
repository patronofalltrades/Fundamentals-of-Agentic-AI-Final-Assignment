"""Convert the pipeline's checkpoint dashboard handoff into a dashboard bundle (rows.jsonl + manifest.json).

Inputs, all read only:

- the handoff JSON (``checkpoint5000-dashboard-handoff-v1``): accepted records with labels, evidence and
  provenance, plus every excluded review ID with its status and reason;
- the checkpoint manifest (``checkpoint5000-manifest-v1``): every selected row in source order, with its
  source row hash and text hash;
- the source CSV named by the manifest. It is used only to check the file hash and to read each selected
  row's timestamp month, because excluded rows carry no timestamp in the handoff.

Checks, all before anything is written:

1. The CSV's SHA-256 equals the manifest's ``source_file_sha256``.
2. Accepted and excluded IDs are disjoint and together equal the manifest's selected IDs.
3. Each accepted record has the manifest's source row hash, the manifest's text hash for its text, one label
   configuration hash, and an evidence quote that is an exact substring of its text.

The bundle has the same format as ``export_bundle`` and loads with ``load_bundle``. It holds no review
text, rating, likes, app version or timestamp. No model call happens here. Standard library only.
"""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict

from .bundle import BUNDLE_VERSION, ROW_FIELDS, _canonical, _sha256

HANDOFF_VERSION = "checkpoint5000-dashboard-handoff-v1"
MANIFEST_VERSION = "checkpoint5000-manifest-v1"
LABEL_FIELDS = ("topic", "intent", "sentiment", "severity", "needs_review", "model")


def _file_sha256(path: str) -> str:
    return _sha256(Path(path))


def _months_by_id(source_csv: str, wanted: set) -> Dict[str, str]:
    months = {}
    with open(source_csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["review_id"] in wanted:
                months[row["review_id"]] = row["review_timestamp"][:10]
                if len(months) == len(wanted):
                    break
    if len(months) != len(wanted):
        raise ValueError("source CSV is missing %d selected rows" % (len(wanted) - len(months)))
    return months


def handoff_to_bundle(handoff_path: str, manifest_path: str, source_csv: str, out_dir: str,
                      prompt_version: str = "jev-rubric-v2", schema_version: str = "jev-labels-v1") -> Dict[str, Any]:
    handoff = json.loads(Path(handoff_path).read_text(encoding="utf-8"))
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if handoff.get("schema_version") != HANDOFF_VERSION or manifest.get("schema_version") != MANIFEST_VERSION:
        raise ValueError("unsupported handoff or manifest version")
    if _file_sha256(source_csv) != manifest["source_file_sha256"]:
        raise ValueError("source CSV hash differs from the manifest")

    selected = {r["review_id"]: r for r in manifest["rows"]}
    accepted = {r["review_id"]: r for r in handoff["records"]}
    excluded = {r["review_id"]: r for r in handoff["excluded"]}
    if len(selected) != len(manifest["rows"]) or set(accepted) & set(excluded) or \
            set(accepted) | set(excluded) != set(selected):
        raise ValueError("accepted and excluded IDs must split the selected rows exactly")

    configs = {r["provenance"]["label"]["config_sha256"] for r in handoff["records"]}
    if configs != {manifest["label_config_hash"]}:
        raise ValueError("records must share the manifest's label configuration")
    config_hash = manifest["label_config_hash"]

    for rid, rec in accepted.items():
        src, text = selected[rid], rec["source"]["review_text"]
        if rec["source_sha256"] != src["source_sha256"] or rec["source"]["review_id"] != rid:
            raise ValueError("source row hash differs from the manifest")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != src["text_sha256"]:
            raise ValueError("review text hash differs from the manifest")
        if not rec["evidence"]["evidence_quote"] or rec["evidence"]["evidence_quote"] not in text:
            raise ValueError("evidence quote is not an exact source substring")
    for rid, exc in excluded.items():
        if exc["source_sha256"] != selected[rid]["source_sha256"]:
            raise ValueError("excluded row hash differs from the manifest")

    month_of = _months_by_id(source_csv, set(selected))
    rows, counts, months, days = [], Counter(), {}, {}
    labels = {"topic": Counter(), "intent": Counter(), "severity": Counter()}
    for src in sorted(manifest["rows"], key=lambda r: r["source_position"]):
        rid = src["review_id"]
        row = dict.fromkeys(ROW_FIELDS)
        row.update(row_index=src["source_position"] - 1, review_id=rid, row_sha256=src["source_sha256"],
                   text_sha256=src["text_sha256"], is_empty=0, config_hash=config_hash)
        month = months.setdefault(month_of[rid][:7], {"reviews": 0, "complaints": 0, "severity_sum": 0})
        day = days.setdefault(month_of[rid], {"reviews": 0, "complaints": 0, "severity_sum": 0})
        month["reviews"] += 1
        day["reviews"] += 1
        if rid in accepted:
            rec = accepted[rid]
            lab = rec["labels"]
            row.update({k: lab[k] for k in LABEL_FIELDS}, status="completed", reason=None,
                       needs_review=int(bool(lab["needs_review"])), severity=int(lab["severity"]),
                       entities=json.dumps(rec["evidence"]["entities"], ensure_ascii=False),
                       evidence_quote=rec["evidence"]["evidence_quote"],
                       is_cached=int(rec["provenance"]["label"]["kind"].endswith("_cache")),
                       label_config=config_hash, prompt_version=prompt_version, schema_version=schema_version)
            for dim in labels:
                labels[dim][str(row[dim])] += 1
            if row["intent"] in ("complaint", "cancellation"):
                for period in (month, day):
                    period["complaints"] += 1
                    period["severity_sum"] += row["severity"]
        else:
            row.update(status=excluded[rid]["status"], reason=excluded[rid]["reason"])
        counts["source_rows"] += 1
        counts["nonempty_rows"] += 1
        counts["%s_rows" % row["status"]] += 1
        rows.append(row)

    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("bundle directory is not empty")
    out.mkdir(parents=True, exist_ok=True)
    rows_path = out / "rows.jsonl"
    with rows_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(_canonical(row) + "\n")
    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "source": {"basename": "%s (first %d rows)" % (manifest["source_file"], len(rows)),
                   "file_sha256": manifest["source_file_sha256"],
                   "parsed_rows_sha256": hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()},
        "config_hash": config_hash,
        "counts": dict(sorted(counts.items()), distinct_nonempty_texts=manifest["counts"]["distinct_texts"]),
        "labels": {dim: dict(sorted(c.items())) for dim, c in labels.items()},
        "months": dict(sorted(months.items())),
        "days": dict(sorted(days.items())),
        "rows_sha256": _sha256(rows_path),
        "excluded_fields": ["review_text", "review_rating", "review_likes", "app_version", "review_timestamp"],
        "handoff_sha256": hashlib.sha256(Path(handoff_path).read_bytes()).hexdigest(),
    }
    (out / "manifest.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle

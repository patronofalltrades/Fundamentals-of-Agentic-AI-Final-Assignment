"""Load the pipeline's grading folder into the dashboard database, after checking every number.

Input: the folder written by the pipeline's grading export (``spotify_pipeline/grading.py``):
``run.json``, ``records.jsonl`` (or ``records.jsonl.gz``), ``membership.csv``, ``ranking.csv``,
``claims.csv`` and, when present, ``memo.md``. An optional JSON file maps issue IDs to display names.

Checks, all before any write:

1. ``run.json`` names the same source file hash as the dashboard database.
2. Every member review exists in the dashboard database with the same source row hash, intent and
   severity as in ``records.jsonl``. Different values mean a different run: the import stops.
3. The ranking recomputed from the dashboard's saved labels equals ``ranking.csv`` field by field.
4. ``claims.csv`` equals the claims derived from ``ranking.csv`` (IDs, issues, metrics, values).
5. The memo cites every claim ID with its saved value on the same line. If it does not, the memo is
   saved with ``claim_check = failed`` and the dashboard says so.

Then one transaction saves the analysis run, the issues, the membership, the claims and the memo.
After the write, the dashboard API ranking is compared with ``ranking.csv`` again.
No model call happens here. The pipeline's files are only read.
"""

import csv
import gzip
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .analysis import _identity, load_analysis, multi_row_insert
from .bundle import DDL

RANKING_FIELDS = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
CLAIM_FIELDS = ["claim_id", "issue_id", "metric", "value"]
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")
LOOKUP_CHUNK = 500


def _read_csv(path: Path, fields: List[str]) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != fields:
            raise ValueError("%s must have header %s" % (path.name, ",".join(fields)))
        return [dict(row) for row in reader]


def _records(folder: Path, wanted: set) -> Dict[str, Dict[str, Any]]:
    plain, packed = folder / "records.jsonl", folder / "records.jsonl.gz"
    if plain.exists() == packed.exists():
        raise ValueError("supply exactly one of records.jsonl and records.jsonl.gz")
    stream = plain.open(encoding="utf-8") if plain.exists() else gzip.open(packed, "rt", encoding="utf-8")
    found = {}
    with stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("review_id") in wanted:
                found[row["review_id"]] = row
    return found


def _mean(total: int, count: int) -> str:
    return format((Decimal(total) / Decimal(count)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), ".6f")


def rank(memberships: Iterable, labels: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """The course ranking: severity_sum desc, then issue_id asc. Same arithmetic as the checker."""
    members = defaultdict(list)
    for issue_id, review_id in memberships:
        members[issue_id].append(labels[review_id]["severity"])
    result = [{"issue_id": issue, "complaint_count": str(len(v)), "severity_sum": str(sum(v)),
               "mean_severity": _mean(sum(v), len(v)), "priority_score": str(sum(v))} for issue, v in members.items()]
    result.sort(key=lambda r: (-int(r["priority_score"]), r["issue_id"]))
    for n, row in enumerate(result, 1):
        row["rank"] = str(n)
    return [{k: r[k] for k in RANKING_FIELDS} for r in result]


def claims_from(ranking: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"claim_id": "claim-%04d-%s" % (int(row["rank"]), metric), "issue_id": row["issue_id"],
             "metric": metric, "value": row[metric]} for row in ranking for metric in METRICS]


def memo_claim_check(memo: str, claims: List[Dict[str, str]]) -> str:
    if not memo.strip():
        return "missing"
    lines = memo.splitlines()
    for claim in claims:
        if not any(claim["claim_id"] in line and claim["value"] in line for line in lines):
            return "failed"
    known = {c["claim_id"] for c in claims}
    if any(cid not in known for cid in re.findall(r"\bclaim-[A-Za-z0-9_.:-]+", memo)):
        return "failed"
    return "passed"


def _db_labels(backend, review_ids: List[str], config_hash: str) -> Dict[str, Dict[str, Any]]:
    out = {}
    for start in range(0, len(review_ids), LOOKUP_CHUNK):
        chunk = review_ids[start:start + LOOKUP_CHUNK]
        rows = backend.execute(
            "SELECT r.review_id, r.row_index, r.row_sha256, c.intent, c.severity FROM records r "
            "JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=? "
            "WHERE r.review_id IN (%s)" % ", ".join("?" for _ in chunk), [config_hash] + chunk).fetchall()
        for review_id, row_index, row_sha, intent, severity in rows:
            out[review_id] = {"row_index": row_index, "row_sha256": row_sha, "intent": intent, "severity": int(severity)}
    return out


def load_grading(backend, folder: str, issue_names: Optional[Dict[str, str]] = None,
                 run_id: Optional[str] = None) -> Dict[str, Any]:
    root = Path(folder)
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    ranking = _read_csv(root / "ranking.csv", RANKING_FIELDS)
    claims = _read_csv(root / "claims.csv", CLAIM_FIELDS)
    membership = [(r["issue_id"], r["review_id"]) for r in _read_csv(root / "membership.csv", ["issue_id", "review_id"])]
    memo = (root / "memo.md").read_text(encoding="utf-8") if (root / "memo.md").exists() else ""
    if not ranking or not membership:
        raise ValueError("grading folder has no ranking or membership")
    if len(set(membership)) != len(membership):
        raise ValueError("membership.csv repeats an (issue_id, review_id) pair")
    if run.get("allow_multi_issue") is not True and len({rid for _, rid in membership}) != len(membership):
        raise ValueError("membership puts a review in two issues without allow_multi_issue")

    for sql in DDL["common"] + DDL[backend.dialect]:
        backend.execute(sql)
    identity = _identity(backend)
    if run.get("analysis_sha256") != identity["source_sha256"]:
        raise ValueError("run.json analysis_sha256 differs from the dashboard source")

    member_ids = sorted({rid for _, rid in membership})
    exported = _records(root, set(member_ids))
    saved = _db_labels(backend, member_ids, identity["config_hash"])
    for review_id in member_ids:
        e, d = exported.get(review_id), saved.get(review_id)
        if e is None or d is None:
            raise ValueError("member review is missing from %s" % ("records.jsonl" if e is None else "the dashboard"))
        if e.get("status") != "completed" or e.get("intent") not in ("complaint", "cancellation"):
            raise ValueError("membership must contain completed complaint/cancellation records")
        if (e.get("source_sha256"), e.get("intent"), e.get("severity")) != (d["row_sha256"], d["intent"], d["severity"]):
            raise ValueError("export and dashboard hold different results for a member review")

    recomputed = rank(membership, saved)
    if recomputed != ranking:
        raise ValueError("ranking.csv differs from the ranking recomputed from saved labels")
    if claims != claims_from(ranking):
        raise ValueError("claims.csv differs from the claims derived from ranking.csv")
    check = memo_claim_check(memo, claims)

    run_id = run_id or "grading-" + hashlib.sha256((root / "ranking.csv").read_bytes()).hexdigest()[:16]
    names = issue_names or {}
    members_by_issue = defaultdict(list)
    for issue_id, review_id in membership:
        members_by_issue[issue_id].append(saved[review_id]["row_index"])
    payload = {"run_id": run_id, "source_sha256": identity["source_sha256"], "config_hash": identity["config_hash"],
               "issues": [{"issue_id": r["issue_id"], "title": names.get(r["issue_id"], r["issue_id"]),
                           "row_indices": sorted(members_by_issue[r["issue_id"]])} for r in ranking],
               "recommendations": []}
    extra = multi_row_insert("claim", ("run_id", "claim_id", "issue_id", "metric", "value"),
                             [(run_id, c["claim_id"], c["issue_id"], c["metric"], c["value"]) for c in claims])
    if memo.strip():
        extra.append(("INSERT INTO memo (run_id, text, sha256, claim_check) VALUES (?, ?, ?, ?)",
                      (run_id, memo, hashlib.sha256(memo.encode("utf-8")).hexdigest(), check)))
    result = load_analysis(backend, payload, extra_statements=extra)

    from .server import issues  # the API's own ranking query
    api = issues(backend)
    served = [{"rank": str(n), "issue_id": i["issue_id"], "complaint_count": str(i["review_count"]),
               "severity_sum": str(i["priority_score"]), "mean_severity": i["mean_severity"],
               "priority_score": str(i["priority_score"])} for n, i in enumerate(api["items"], 1)]
    if served != ranking:
        raise ValueError("saved, but the API ranking differs from ranking.csv; investigate before use")
    return dict(result, claims=len(claims), memo_claim_check=check, ranking_matches=True)

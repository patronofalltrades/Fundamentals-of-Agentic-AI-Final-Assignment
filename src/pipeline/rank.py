"""Rank stage: the baseline ranking with exactly the checker's arithmetic. Pure code, no model calls.

complaint_count = membership count; severity_sum = sum of member severity;
mean_severity = Decimal half-up to 6 dp (identical to check_submission.mean_string);
priority_score = severity_sum; order by (-priority_score, issue_id); rank from 1.
"""
from __future__ import annotations

import csv
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Union

from pipeline.claims import build_claims, write_claims, _csv_text
from pipeline.context import StageContext
from pipeline.io import atomic_write_text
from pipeline.rowhash import RANKED_INTENTS

RANKING_HEADER = ("rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score")


def mean_string(total, n) -> str:
    return str((Decimal(total) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _pairs(membership) -> Iterable[Tuple[str, str]]:
    for item in membership:
        if isinstance(item, dict):
            yield item.get("issue_id"), item.get("review_id")
        else:
            yield item[0], item[1]


def compute_ranking(membership: Iterable[Union[Tuple[str, str], dict]], records: Dict[str, dict]) -> List[dict]:
    """Mirror check_submission.audit: skip blank issue IDs, unknown/non-completed records, duplicate
    pairs and non-complaint intents; then aggregate, sort and rank."""
    members: Dict[str, List[int]] = {}
    seen = set()
    for iid, rid in _pairs(membership):
        rec = records.get(rid)
        if not iid or rec is None or rec.get("status") != "completed" or (iid, rid) in seen:
            continue
        seen.add((iid, rid))
        if rec.get("intent") not in RANKED_INTENTS:
            continue
        members.setdefault(iid, []).append(rec["severity"])
    rows = [{"issue_id": iid, "complaint_count": len(v), "severity_sum": sum(v),
             "mean_severity": mean_string(sum(v), len(v)), "priority_score": sum(v)} for iid, v in members.items()]
    rows.sort(key=lambda x: (-x["priority_score"], x["issue_id"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def ranking_csv_text(ranking: List[dict]) -> str:
    return _csv_text(RANKING_HEADER, [{k: str(r[k]) for k in RANKING_HEADER} for r in ranking])


def read_membership(path) -> List[Tuple[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return [(row["issue_id"], row["review_id"]) for row in csv.DictReader(f)]


def run(ctx: StageContext) -> dict:
    membership = read_membership(Path(ctx.run_dir) / "group" / "membership.csv")
    ranking = compute_ranking(membership, ctx.records)
    out = ctx.stage_dir("rank")
    atomic_write_text(out / "ranking.csv", ranking_csv_text(ranking))
    claims = build_claims(ranking)
    write_claims(out / "claims.csv", claims)
    return {"issues": len(ranking), "claims": len(claims),
            "top_issue": ranking[0]["issue_id"] if ranking else None}

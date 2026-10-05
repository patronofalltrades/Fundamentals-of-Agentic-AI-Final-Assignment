"""Claims: one row per ranked issue x supported metric, and memo citation checks.

``claim_id = C<rank:03d>-<metric>``; values are the exact ranking.csv strings (docs/INTERFACES.md §6).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")
CLAIM_HEADER = ("claim_id", "issue_id", "metric", "value")
CLAIM_RE = re.compile(r"^C(\d{3,})-(%s)$" % "|".join(METRICS))
BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
TOKEN_RE = re.compile(r"\bC\d+-[A-Za-z_]+\b")


def claim_id(rank: int, metric: str) -> str:
    return "C%03d-%s" % (rank, metric)


def build_claims(ranking: Iterable[dict]) -> List[dict]:
    rows = []
    for row in ranking:
        for metric in METRICS:
            rows.append({"claim_id": claim_id(int(row["rank"]), metric), "issue_id": row["issue_id"],
                         "metric": metric, "value": str(row[metric])})
    return rows


def write_claims(path, claims: List[dict]) -> None:
    from pipeline.io import atomic_write_text
    atomic_write_text(path, _csv_text(CLAIM_HEADER, claims))


def _csv_text(header, rows) -> str:
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[h] for h in header])
    return buf.getvalue()


def load_claims(path) -> Dict[str, dict]:
    """claim_id -> {claim_id, issue_id, metric, value} (file order preserved)."""
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return {row["claim_id"]: dict(row) for row in csv.DictReader(f)}


def cited_tokens(memo_text: str) -> List[str]:
    """Every claim-like token that appears inside square brackets, in order (duplicates kept)."""
    tokens = []
    for inner in BRACKET_RE.findall(memo_text):
        tokens.extend(TOKEN_RE.findall(inner))
    return tokens


def validate_memo_citations(memo_text: str, claims: Dict[str, dict], top_n: Optional[int] = None) -> dict:
    """Check ``[Cnnn-metric]`` citations against claims.

    Returns ``{ok, cited, unknown, n_citations, issues_cited, uncited_top_issues, uncited_top_claims}``.
    ``ok`` is True when there is at least one citation and every cited claim exists.
    ``uncited_top_*`` report (not fail) top-N issues the memo never cites.
    """
    tokens = cited_tokens(memo_text)
    cited = sorted(set(t for t in tokens if t in claims))
    unknown = sorted(set(t for t in tokens if t not in claims))
    issues_cited = sorted({claims[c]["issue_id"] for c in cited})
    top_issues: List[str] = []
    if top_n:
        for cid, row in claims.items():
            m = CLAIM_RE.match(cid)
            if m and int(m.group(1)) <= top_n and row["issue_id"] not in top_issues:
                top_issues.append(row["issue_id"])
    uncited_issues = [i for i in top_issues if i not in issues_cited]
    uncited_claims = [c for c, row in claims.items() if row["issue_id"] in top_issues and c not in cited]
    return {"ok": bool(cited) and not unknown, "n_citations": len(tokens), "cited": cited, "unknown": unknown,
            "issues_cited": issues_cited, "uncited_top_issues": uncited_issues,
            "uncited_top_claims": uncited_claims}

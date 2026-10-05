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


# --------------------------------------------------------------------------- memo lint (memo-v2)

# Claims the saved aggregates cannot support: the corpus has no revenue, churn, retention or
# engineering-cost data, and a stated intent to cancel is not evidence that anyone cancelled.
UNSUPPORTED_TERMS = re.compile(
    r"\b(churn\w*|retention|retain(?:ed|ing)?|revenue|monetiz\w*|monetis\w*|profit\w*|ROI|"
    r"lifetime value|LTV|market share|conversion rate|engineering (?:effort|cost|work|time)|"
    r"quick wins?|faster wins?|low[- ]hanging|easy fix\w*|cheap(?:er)? to fix|reversible|root causes?|"
    r"(?:may|might|will|would|could|should) (?:likely )?(?:reduce|fix|solve|eliminate|lower|prevent|"
    r"improve|increase|boost|drive|cut))\b",
    re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?")
SMALL_COUNT_LIMIT = 10  # "top 3", "2 of 4 areas", list numbering


def _input_numbers(value, out: set) -> set:
    """Every number that appears anywhere in the memo input, in the forms a writer may use."""
    if isinstance(value, bool) or value is None:
        return out
    if isinstance(value, (int, float)):
        out.add(_norm_number(str(value)))
        if isinstance(value, float) and 0 <= value <= 1:
            out.add(_norm_number("%g" % round(value * 100, 4)))  # 0.85 -> 85 (written as 85%)
            out.add(_norm_number("%.1f" % (value * 100)))
            out.add(_norm_number("%d" % round(value * 100)))
        return out
    if isinstance(value, str):
        for m in NUMBER_RE.findall(value):
            out.add(_norm_number(m))
        return out
    if isinstance(value, dict):
        for v in value.values():
            _input_numbers(v, out)
        return out
    if isinstance(value, (list, tuple)):
        for v in value:
            _input_numbers(v, out)
    return out


def _norm_number(text: str) -> str:
    text = text.replace(",", "").rstrip("%")
    try:
        number = float(text)
    except ValueError:
        return text
    return ("%.6f" % number).rstrip("0").rstrip(".")


def lint_memo(memo_text: str, claims: Dict[str, dict], inputs: dict) -> dict:
    """Problems that make a memo unfit to submit. ``ok`` is False when any list is non-empty.

    - ``bad_citations``: bracket tokens that look like citations but are not full claim IDs
      (bare ``[C004]``, ``[verify_agreement]``). Markdown links ``[text](url)`` are ignored.
    - ``unsupported_terms``: business/causal claims the data cannot support.
    - ``unknown_numbers``: numbers that do not appear in the memo inputs (beyond small counts).
    """
    bad = []
    for m in re.finditer(r"\[([^\[\]]*)\](?!\()", memo_text):
        inner = m.group(1).strip()
        parts = [p.strip() for p in re.split(r"[,;]", inner) if p.strip()]
        looks_like_citation = (re.match(r"^C\d", inner) or re.fullmatch(r"[a-z_]+(?:\.[a-z_]+)*", inner)
                               or any(re.match(r"^C\d", p) for p in parts))
        if looks_like_citation and not all(p in claims for p in parts):
            bad.append(inner)
    terms = sorted({m.group(0).lower() for m in UNSUPPORTED_TERMS.finditer(memo_text)})
    allowed = _input_numbers(inputs, set())
    stripped = re.sub(r"\[[^\[\]]*\]", " ", memo_text)          # citations carry claim numbers
    stripped = re.sub(r"`[^`]*`", " ", stripped)                # issue ids / field names
    stripped = re.sub(r"(?m)^\s*(?:#+|\d+\.|[-*])\s*", " ", stripped)  # headings and list markers
    unknown = []
    for m in NUMBER_RE.finditer(stripped):
        token = _norm_number(m.group(0))
        try:
            small = float(token).is_integer() and 0 <= float(token) <= SMALL_COUNT_LIMIT and "%" not in m.group(0)
        except ValueError:
            small = False
        if not small and token not in allowed:
            unknown.append(m.group(0))
    return {"ok": not (bad or terms or unknown), "bad_citations": sorted(set(bad)),
            "unsupported_terms": terms, "unknown_numbers": sorted(set(unknown))}

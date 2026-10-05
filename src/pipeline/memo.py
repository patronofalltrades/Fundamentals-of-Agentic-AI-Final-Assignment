"""Memo stage: one bounded `memo` call over saved aggregates; citations validated against claims.

Inputs (``memo/inputs.json``) come only from saved artifacts: rank/ranking.csv, rank/claims.csv,
group/issues.json, group/membership.csv (for <= 3 quotes per issue), verify/report.json and the
record store (coverage counts). The model never sees raw review rows beyond those quotes.
Dry-run (or no chat client) writes a deterministic template memo and logs no call.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from pipeline.claims import METRICS, claim_id, load_claims, validate_memo_citations
from pipeline.context import StageContext
from pipeline.group import fallback_name, select_quotes
from pipeline.io import atomic_write_json, atomic_write_text, dumps_line
from pipeline.rank import read_membership
from pipeline.rowhash import RANKED_INTENTS
from pipeline.verify import StageCache, cached_chat, chat_model_name, sha256_hex

STAGE = "memo"
PROMPT_VERSION = "memo-v1"
PRODUCT_QUESTION = ("Where should Spotify invest next quarter: access, usability, playback, or "
                    "billing/support?")
AREAS = ("access", "usability", "playback", "billing_support")
AREA_BY_TOPIC = {"access": "access", "usability": "usability", "playback": "playback",
                 "downloads": "playback", "billing": "billing_support", "support": "billing_support",
                 "catalog": "outside_question", "other": "outside_question"}
AREA_NOTE = ("Topic-to-area mapping: access->access; usability->usability; playback and downloads "
             "(offline listening)->playback; billing and support->billing_support; catalog and other are "
             "outside the four investment areas and reported separately.")

PROMPT = """You write a one-page decision memo for Spotify's product leadership.
Question: {question}
Use ONLY the numbers in the JSON input. Every issue-level number you state must be followed by its
claim ID in square brackets, e.g. "severity_sum 1234 [C001-severity_sum]". Area totals in
area_rollup are derived sums of claims: say so, and cite the issue claims they come from for the
leading area. Do not invent numbers, percentages or claim IDs. Quote reviews only from the quotes
given. Structure: Recommendation (1 paragraph), Evidence (top issues with citations), Why not the
other areas, Risks and data caveats (coverage, verifier agreement, keyword-based grouping).
Plain markdown, at most 600 words."""


def _read_csv(path) -> List[dict]:
    import csv
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def coverage(ctx: StageContext) -> dict:
    statuses, reasons = Counter(), Counter()
    cached = complaints = 0
    for rid in ctx.texts:
        rec = ctx.records.get(rid)
        if rec is None:
            statuses["pending"] += 1
            continue
        statuses[rec.get("status")] += 1
        if rec.get("status") == "quarantined":
            reason = str(rec.get("reason", ""))
            reasons[reason.split(":", 1)[0]] += 1
        elif rec.get("status") == "completed":
            cached += bool(rec.get("cache_source_id"))
            complaints += rec.get("intent") in RANKED_INTENTS
    return {"source_ids": len(ctx.texts), "completed": statuses["completed"],
            "completed_via_exact_text_cache": cached, "quarantined": statuses["quarantined"],
            "quarantine_reasons": dict(sorted(reasons.items())), "pending": statuses["pending"],
            "complaint_or_cancellation_records": complaints}


def build_inputs(ctx: StageContext, top_n: int = 10, quotes_per_issue: int = 3) -> dict:
    run_dir = Path(ctx.run_dir)
    ranking = _read_csv(run_dir / "rank" / "ranking.csv")
    claims = load_claims(run_dir / "rank" / "claims.csv")
    issues_path = run_dir / "group" / "issues.json"
    issue_meta = {i["issue_id"]: i for i in json.loads(issues_path.read_text(encoding="utf-8"))} \
        if issues_path.exists() else {}
    members: Dict[str, List[str]] = {}
    mpath = run_dir / "group" / "membership.csv"
    if mpath.exists():
        for iid, rid in read_membership(mpath):
            members.setdefault(iid, []).append(rid)

    top = []
    for row in ranking[:top_n]:
        iid, rank = row["issue_id"], int(row["rank"])
        meta = issue_meta.get(iid) or {}
        fb_name, fb_desc = fallback_name(iid)
        top.append({"rank": rank, "issue_id": iid, "name": meta.get("name") or fb_name,
                    "description": meta.get("description") or fb_desc,
                    "area": AREA_BY_TOPIC.get(iid.split(".", 1)[0], "outside_question"),
                    "metrics": {m: {"value": row[m], "claim_id": claim_id(rank, m)} for m in METRICS},
                    "quotes": [q["quote"] for q in select_quotes(members.get(iid, []), ctx.records, quotes_per_issue)]})

    rollup = {a: {"complaint_count": 0, "severity_sum": 0, "issues": 0, "derived_from_claims": []}
              for a in AREAS + ("outside_question",)}
    for row in ranking:
        area = AREA_BY_TOPIC.get(row["issue_id"].split(".", 1)[0], "outside_question")
        r = rollup[area]
        r["complaint_count"] += int(row["complaint_count"])
        r["severity_sum"] += int(row["severity_sum"])
        r["issues"] += 1
        r["derived_from_claims"] += [claim_id(int(row["rank"]), "complaint_count"),
                                     claim_id(int(row["rank"]), "severity_sum")]

    verify = None
    vpath = run_dir / "verify" / "report.json"
    if vpath.exists():
        rep = json.loads(vpath.read_text(encoding="utf-8"))
        verify = {k: rep.get(k) for k in ("n", "n_valid", "verifier_invalid", "agreement", "prompt_source")}

    top_ids = {t["issue_id"] for t in top}
    return {
        "product_question": PRODUCT_QUESTION, "prompt_version": PROMPT_VERSION,
        "ranking_rule": "baseline: complaint/cancellation records, one issue each; priority_score = severity_sum; "
                        "sorted by priority_score desc then issue_id",
        "ranked_issues_total": len(ranking), "top_issues": top,
        "claims": [c for c in claims.values() if c["issue_id"] in top_ids],
        "area_rollup": {"label": "DERIVED from claims: per-area sums of the listed issue-level claims "
                                 "(complaint_count and severity_sum). Not themselves claims.csv rows.",
                        "mapping": AREA_NOTE, "areas": rollup},
        "coverage": coverage(ctx), "verify_agreement": verify,
    }


def _fmt_rollup_cites(cids: List[str], metric: str, limit: int = 4) -> str:
    picked = [c for c in cids if c.endswith(metric)][:limit]
    return " + ".join("[%s]" % c for c in picked) + (" + ..." if len([c for c in cids if c.endswith(metric)]) > limit else "")


def template_memo(inputs: dict) -> str:
    """Deterministic memo from the same inputs; every issue-level number is cited."""
    areas = inputs["area_rollup"]["areas"]
    ranked_areas = sorted(AREAS, key=lambda a: (-areas[a]["severity_sum"], a))
    lead = ranked_areas[0]
    top = inputs["top_issues"]
    lead_issues = [t for t in top if t["area"] == lead]
    cov = inputs["coverage"]
    lines = ["# Investment memo (template, generated offline from saved aggregates)", "",
             "**Question.** " + inputs["product_question"], ""]
    if not top:
        lines += ["No complaint/cancellation issues were ranked, so no recommendation is made.", ""]
    else:
        lines += ["## Recommendation", "",
                  "Invest next quarter in **%s**. Summed over its ranked issues, this area has the highest "
                  "derived severity_sum (%d, a sum of %s; derived from claims, not a claim itself)."
                  % (lead.replace("_", "/"), areas[lead]["severity_sum"],
                     _fmt_rollup_cites(areas[lead]["derived_from_claims"], "severity_sum")), ""]
        if lead_issues:
            t = lead_issues[0]
            m = t["metrics"]
            lines += ["Its largest issue is **%s** (`%s`): %s complaints [%s], severity_sum %s [%s], mean severity %s [%s]."
                      % (t["name"], t["issue_id"], m["complaint_count"]["value"], m["complaint_count"]["claim_id"],
                         m["severity_sum"]["value"], m["severity_sum"]["claim_id"],
                         m["mean_severity"]["value"], m["mean_severity"]["claim_id"]), ""]
        lines += ["## Evidence: top issues by priority_score (= severity_sum)", "",
                  "| Rank | Issue | Area | Complaints | Severity sum | Mean severity |", "|---|---|---|---|---|---|"]
        for t in top:
            m = t["metrics"]
            lines.append("| %d | %s (`%s`) | %s | %s [%s] | %s [%s] | %s [%s] |" % (
                t["rank"], t["name"], t["issue_id"], t["area"], m["complaint_count"]["value"],
                m["complaint_count"]["claim_id"], m["severity_sum"]["value"], m["severity_sum"]["claim_id"],
                m["mean_severity"]["value"], m["mean_severity"]["claim_id"]))
        lines.append("")
        for t in top[:3]:
            if t["quotes"]:
                lines.append("- `%s`: \"%s\"" % (t["issue_id"], t["quotes"][0].replace("\n", " ")))
        lines += ["", "## Other areas (derived sums of claims)", ""]
        for a in ranked_areas[1:]:
            lines.append("- %s: severity_sum %d over %d issues (derived from %s)." % (
                a.replace("_", "/"), areas[a]["severity_sum"], areas[a]["issues"],
                _fmt_rollup_cites(areas[a]["derived_from_claims"], "severity_sum") or "no claims"))
        out = areas["outside_question"]
        lines.append("- Outside the four areas (catalog, other): severity_sum %d over %d issues." % (
            out["severity_sum"], out["issues"]))
        lines.append("")
    v = inputs.get("verify_agreement")
    lines += ["## Caveats", "",
              "- Coverage: %d source IDs; %d completed (%d via exact-text cache), %d quarantined, %d pending."
              % (cov["source_ids"], cov["completed"], cov["completed_via_exact_text_cache"], cov["quarantined"],
                 cov["pending"]),
              "- Verifier agreement: %s." % (
                  "not available" if not v else "topic %s, intent %s, severity exact %s on %s valid of %s sampled"
                  % (v["agreement"].get("topic"), v["agreement"].get("intent"), v["agreement"].get("severity_exact"),
                     v.get("n_valid"), v.get("n"))),
              "- Issues come from a fixed keyword table (%s); area totals are derived sums of issue claims."
              % inputs["area_rollup"]["mapping"].split(";")[0], ""]
    return "\n".join(lines)


def run(ctx: StageContext) -> dict:
    cfg = ctx.config.get("memo") or {}
    out = ctx.stage_dir(STAGE)
    inputs = build_inputs(ctx, int(cfg.get("top_n", 10)), int(cfg.get("quotes_per_issue", 3)))
    atomic_write_json(out / "inputs.json", inputs)
    claims = load_claims(Path(ctx.run_dir) / "rank" / "claims.csv")
    top_n = len(inputs["top_issues"])

    if ctx.dry_run or ctx.chat is None or not inputs["top_issues"]:
        memo = template_memo(inputs)
        report = validate_memo_citations(memo, claims, top_n)
        atomic_write_text(out / "memo.md", memo)
        atomic_write_json(out / "citations.json", dict(report, source="template"))
        return {"source": "template", "calls": 0, "citations_ok": report["ok"]}

    prompt = PROMPT.format(question=PRODUCT_QUESTION)
    max_tokens = int(cfg.get("max_tokens", 1500))
    model = chat_model_name(ctx, STAGE)
    cache = StageCache(ctx, STAGE)
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": "INPUT (memo/inputs.json):\n" + dumps_line(inputs)}]
    key = StageCache.key(STAGE, prompt, model, {"max_tokens": max_tokens, "temperature": 0.0}, inputs)

    def validate(text):
        rep = validate_memo_citations(text or "", claims, top_n)
        if not rep["ok"]:
            raise ValueError("citation check failed: %d citations, unknown %s" % (rep["n_citations"], rep["unknown"][:5]))
        return text, rep

    parsed, info = cached_chat(ctx, cache, role=STAGE, key=key, messages=messages, max_tokens=max_tokens,
                               review_ids=[], validate=validate, artifact="memo/inputs.json")
    cache.finish()
    if parsed is None:
        memo = template_memo(inputs)
        report = dict(validate_memo_citations(memo, claims, top_n), source="template_fallback",
                      model_errors=info.get("errors"))
    else:
        memo, report = parsed
        report = dict(report, source="model", request_id=info.get("request_id"), cache_hit=info["cache_hit"])
    atomic_write_text(out / "memo.md", memo if memo.endswith("\n") else memo + "\n")
    atomic_write_json(out / "citations.json", report)
    return {"source": report["source"], "calls": info.get("attempts", 0), "cache_hit": info["cache_hit"],
            "citations_ok": report["ok"], "inputs_sha256": sha256_hex(dumps_line(inputs))}

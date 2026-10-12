"""Load the pipeline's grading folder into a private accepted-evidence database (``import-accepted``).

``grading_import.load_grading`` calls this when the database has the public boundary (``public_example``).
The folder format is the course grading export: ``run.json``, ``records.jsonl``, ``membership.csv``,
``ranking.csv``, ``claims.csv`` and ``memo.md``. Extra checks for the accepted-evidence database, all
before any write:

1. Every exported record is a selected row of the database, with the same source row hash. Every accepted
   row is exported as ``completed``. Exported rows the database does not hold as accepted are refused.
2. Labels that differ from the saved labels must be declared, row by row, in ``run.json`` under
   ``human_label_corrections`` (a list of review IDs). A corrected quote must be an exact substring of the
   review's own source text. Any undeclared difference stops the import.
3. Membership equals the issue candidates exactly: every completed ``complaint`` or ``cancellation`` record,
   after corrections, belongs to one issue, and no other record does.
4. ``ranking.csv`` is the course baseline. It must equal the ranking recomputed from the corrected labels,
   flagged records included. The public ranking leaves out records with a known semantic flag.
5. When a catalog is given, every ranked issue is in it. Its hash is recorded.
6. The memo is public text. It must not contain a review ID, an email address, a link, a handle, a long
   number, or a quoted span of more than 30 words.

Then one transaction saves the run, issues, membership, claims, memo, the declared label corrections, the
refreshed public excerpts and label aggregates, and the updated import manifest. Nothing here publishes or
deploys anything.
"""

import hashlib
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from spotify_pipeline.contract import INTENTS, TOPICS

from .analysis import IDENTIFIER, multi_row_insert
from .public_boundary import MAX_EXCERPT_WORDS, excerpt, has_personal_info, new_ref, vocabulary

LABEL_FIELDS = ("topic", "intent", "severity", "evidence_quote")
CANDIDATE_INTENTS = ("complaint", "cancellation")
LABEL_DIMENSIONS = ("topic", "intent", "severity")
PERIOD_DIMENSIONS = ("month_reviews", "month_complaints", "month_severity_sum",
                     "day_reviews", "day_complaints", "day_severity_sum")
QUOTED = re.compile(r"[\"“]([^\"”]+)[\"”]")


def _saved_rows(backend, config_hash: str) -> Dict[str, Dict[str, Any]]:
    """Every selected row, with its saved labels when accepted. Read locally; never returned by the API."""
    rows = {}
    for (review_id, row_index, row_sha, state, topic, intent, severity, quote, blocked, text,
         timestamp) in backend.execute(
            "SELECT r.review_id, r.row_index, r.row_sha256, s.state, c.topic, c.intent, c.severity, "
            "c.evidence_quote, COALESCE(f.blocked, 0), t.review_text, t.review_timestamp FROM records r "
            "JOIN row_state s ON s.row_index=r.row_index "
            "LEFT JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=? "
            "LEFT JOIN semantic_flag f ON f.row_index=r.row_index "
            "JOIN source_text t ON t.row_index=r.row_index", (config_hash,)):
        rows[review_id] = {"row_index": row_index, "row_sha256": row_sha, "state": state, "topic": topic,
                           "intent": intent, "severity": severity, "evidence_quote": quote,
                           "blocked": bool(blocked), "text": text, "timestamp": timestamp}
    return rows


def _check_memo(memo: str, review_ids) -> int:
    """Public-text gate for the memo. Returns the number of quoted spans, for the human reviewer."""
    if not memo.strip():
        return 0
    if any(rid in memo for rid in review_ids):
        raise ValueError("the memo contains a review ID")
    if has_personal_info(memo, decimals=True):
        raise ValueError("the memo contains an email address, link, handle, name phrase or long number")
    quotes = QUOTED.findall(memo)
    if any(len(q.split()) > MAX_EXCERPT_WORDS for q in quotes):
        raise ValueError("the memo quotes more than %d words in one span" % MAX_EXCERPT_WORDS)
    return len(quotes)


def _aggregates(rows: Dict[str, Dict[str, Any]], labels: Dict[str, Dict[str, Any]]) -> List[tuple]:
    """Label and period aggregates over accepted rows, from the corrected labels."""
    counts = Counter()
    for review_id, lab in labels.items():
        row = rows[review_id]
        for dim in LABEL_DIMENSIONS:
            counts[(dim, str(lab[dim]))] += 1
        for prefix, period in (("month", row["timestamp"][:7]), ("day", row["timestamp"][:10])):
            counts[(prefix + "_reviews", period)] += 1
            if lab["intent"] in CANDIDATE_INTENTS:
                counts[(prefix + "_complaints", period)] += 1
                counts[(prefix + "_severity_sum", period)] += int(lab["severity"])
    return [(dim, value, n) for (dim, value), n in sorted(counts.items()) if n]


def prepare(backend, identity: Dict[str, str], run: Dict[str, Any], exported: Dict[str, Dict[str, Any]],
            membership: List[tuple], memo: str, catalog: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Check the folder against the database. Returns the corrected labels and the statements to save."""
    rows = _saved_rows(backend, identity["config_hash"])
    accepted = {rid for rid, r in rows.items() if r["state"] == "accepted"}
    for review_id, record in exported.items():
        row = rows.get(review_id)
        if row is None or record.get("source_sha256") != row["row_sha256"]:
            raise ValueError("an exported record is not a selected row of this database")
        if record.get("status") == "completed" and review_id not in accepted:
            raise ValueError("an exported completed record is not accepted in this database")
    if any(exported.get(rid, {}).get("status") != "completed" for rid in accepted):
        raise ValueError("an accepted row is missing from records.jsonl or not completed there")

    declared = run.get("human_label_corrections", [])
    if not isinstance(declared, list) or len(declared) != len(set(declared)):
        raise ValueError("human_label_corrections must be a list of unique review IDs")
    labels, changed = {}, set()
    for review_id in accepted:
        row, record = rows[review_id], exported[review_id]
        lab = {k: record.get(k) for k in LABEL_FIELDS}
        if lab != {k: row[k] for k in LABEL_FIELDS}:
            changed.add(review_id)
            if (lab["topic"] not in TOPICS or lab["intent"] not in INTENTS or type(lab["severity"]) is not int
                    or not 1 <= lab["severity"] <= 5 or not isinstance(lab["evidence_quote"], str)
                    or not lab["evidence_quote"].strip() or lab["evidence_quote"] not in row["text"]):
                raise ValueError("a corrected label is invalid or its quote is not in the source text")
        labels[review_id] = lab
    if changed != set(declared):
        raise ValueError("label differences (%d) do not match human_label_corrections (%d)"
                         % (len(changed), len(set(declared))))

    candidates = {rid for rid, lab in labels.items() if lab["intent"] in CANDIDATE_INTENTS}
    members = [rid for _, rid in membership]
    if len(members) != len(set(members)) or set(members) != candidates:
        raise ValueError("membership must hold every issue candidate exactly once (%d members, %d candidates)"
                         % (len(set(members)), len(candidates)))
    issue_ids = {issue for issue, _ in membership}
    if any(not IDENTIFIER.fullmatch(issue) for issue in issue_ids):
        raise ValueError("an issue ID is not a plain identifier")
    catalog_ids = None
    if catalog is not None:
        catalog_ids = {item["issue_id"] for item in catalog["issues"]}
        if not issue_ids <= catalog_ids:
            raise ValueError("membership names an issue that is not in the catalog")
    quoted = _check_memo(memo, set(rows))

    # Corrections: saved labels change only for the declared rows. Their public excerpts are rebuilt.
    statements = []
    for review_id in sorted(changed):
        lab, idx = labels[review_id], rows[review_id]["row_index"]
        statements.append(("UPDATE classifications SET topic=?, intent=?, severity=?, evidence_quote=? "
                           "WHERE row_index=? AND config_hash=?",
                           (lab["topic"], lab["intent"], lab["severity"], lab["evidence_quote"], idx,
                            identity["config_hash"])))
    common = vocabulary(lab["evidence_quote"] for lab in labels.values())
    saved_examples = {r[0]: (r[1], r[2]) for r in backend.execute("SELECT row_index, ref, shortened FROM public_example")}
    examples = Counter()  # change in the public example counts
    for review_id in sorted(changed):
        idx, blocked = rows[review_id]["row_index"], rows[review_id]["blocked"]
        if idx in saved_examples:
            examples["public"] -= 1
            examples["shortened"] -= saved_examples[idx][1]
        elif not blocked:
            examples["excluded_personal_info"] -= 1
        statements.append(("DELETE FROM public_example WHERE row_index=?", (idx,)))
        quote = labels[review_id]["evidence_quote"]
        if blocked:
            continue
        if has_personal_info(quote, common):
            examples["excluded_personal_info"] += 1
            continue
        text_excerpt, shortened = excerpt(quote)
        examples["public"] += 1
        examples["shortened"] += int(shortened)
        ref = saved_examples[idx][0] if idx in saved_examples else new_ref()
        statements.append(("INSERT INTO public_example (row_index, ref, excerpt, shortened) VALUES (?, ?, ?, ?)",
                           (idx, ref, text_excerpt, int(shortened))))
    dims = LABEL_DIMENSIONS + PERIOD_DIMENSIONS
    statements.append(("DELETE FROM dashboard_aggregate WHERE dimension IN (%s)" % ", ".join("?" for _ in dims), dims))
    statements += multi_row_insert("dashboard_aggregate", ("dimension", "value", "count"), _aggregates(rows, labels))

    flagged = sum(rows[rid]["blocked"] for rid in candidates)
    issue_import = {
        "ranking": "course baseline in ranking.csv; the public ranking leaves out flagged members",
        "issues": len(issue_ids),
        "issue_candidates": {"contract_baseline": len(candidates), "public_projection": len(candidates) - flagged,
                             "flagged_excluded": flagged},
        "human_label_corrections": len(changed),
        "catalog_sha256": catalog["sha256"] if catalog else None,
        "catalog_issues": len(catalog_ids) if catalog_ids is not None else None,
        "memo_quoted_spans": quoted,
        "not_human_accuracy": True,
    }
    return {"rows": rows, "labels": labels, "changed": changed, "statements": statements,
            "issue_import": issue_import, "examples_delta": dict(examples), "flagged": {rid for rid in candidates if rows[rid]["blocked"]}}


def manifest_statements(backend, issue_import: Dict[str, Any], examples_delta: Dict[str, int],
                        run_id: str) -> List[tuple]:
    """The import manifest, with issue candidates and public example counts after corrections."""
    saved = json.loads(backend.execute("SELECT value FROM dashboard_meta WHERE key='import_manifest'").fetchone()[0])
    saved["issue_candidates"] = issue_import["issue_candidates"]
    for key, delta in examples_delta.items():
        saved["public_examples"][key] += delta
    saved["issue_import"] = dict(issue_import, run_id=run_id)
    return [("INSERT INTO dashboard_meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value=excluded.value",
             ("import_manifest", json.dumps(saved, sort_keys=True)))]


def membership_rows(membership: List[tuple], rows: Dict[str, Dict[str, Any]], run_id: str) -> List[tuple]:
    by_issue = defaultdict(list)
    for issue_id, review_id in membership:
        by_issue[issue_id].append(rows[review_id]["row_index"])
    return [(run_id, issue_id, idx) for issue_id in sorted(by_issue) for idx in sorted(by_issue[issue_id])]


def catalog_from(path: str) -> Dict[str, Any]:
    raw = Path(path).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    issues = data.get("issues") if isinstance(data, dict) else None
    if not isinstance(issues, list) or not issues or any(
            not isinstance(i, dict) or not isinstance(i.get("issue_id"), str) or not isinstance(i.get("title"), str)
            for i in issues):
        raise ValueError("catalog must hold an issues list with issue_id and title")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "issues": issues}

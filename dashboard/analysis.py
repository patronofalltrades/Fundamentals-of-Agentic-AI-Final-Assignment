"""Save accepted issue membership and draft recommendations into SQLite or Postgres.

Same contract as the original SQLite importer (see docs/dashboard.md, "Accepted analysis handoff"):

- The payload must name the database's source hash and configuration hash.
- Members must be unique, completed ``complaint`` or ``cancellation`` rows under that configuration.
- Recommendation links must point to issues in the same payload.
- A run ID can be saved once. Saved runs are immutable.
- All inserts run in one transaction (one HTTPS request on Postgres).

Ranking is not stored: the API computes ``severity_sum`` from saved labels at read time.
No model call happens here.
"""

import re
from typing import Any, Dict

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")


def _identity(backend) -> Dict[str, str]:
    meta = {r[0]: r[1] for r in backend.execute("SELECT key, value FROM meta")}
    configs = [r[0] for r in backend.execute("SELECT DISTINCT config_hash FROM record_state")]
    if not meta.get("file_sha256") or len(configs) != 1:
        raise ValueError("database has no single loaded source and configuration")
    return {"source_sha256": meta["file_sha256"], "config_hash": configs[0]}


def load_analysis(backend, payload: Dict[str, Any]) -> Dict[str, Any]:
    identity = _identity(backend)
    if payload.get("source_sha256") != identity["source_sha256"] or payload.get("config_hash") != identity["config_hash"]:
        raise ValueError("analysis source/configuration identity mismatch")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
        raise ValueError("run_id is required")
    issues = payload.get("issues")
    recommendations = payload.get("recommendations", [])
    if not isinstance(issues, list) or not issues or not isinstance(recommendations, list):
        raise ValueError("accepted issues and recommendation list are required")

    known_rows = {r[0]: r[1] for r in backend.execute(
        "SELECT r.row_index, c.intent FROM records r JOIN record_state s ON s.row_index=r.row_index "
        "JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=s.config_hash "
        "WHERE s.status='completed' AND c.config_hash=?", (identity["config_hash"],))}
    issue_ids, memberships = set(), []
    for item in issues:
        issue_id, title, rows = item.get("issue_id"), item.get("title"), item.get("row_indices")
        if (not isinstance(issue_id, str) or not IDENTIFIER.fullmatch(issue_id) or issue_id in issue_ids
                or not isinstance(title, str) or not title.strip() or not isinstance(rows, list) or not rows):
            raise ValueError("issue needs unique ID, title, and nonempty membership")
        issue_ids.add(issue_id)
        if (any(type(row) is not int for row in rows) or len(rows) != len(set(rows))
                or any(known_rows.get(row) not in ("complaint", "cancellation") for row in rows)):
            raise ValueError("membership must contain unique completed complaint/cancellation rows")
        memberships.extend((run_id, issue_id, row) for row in rows)
    recommendation_ids = set()
    for item in recommendations:
        rid, body, refs = item.get("recommendation_id"), item.get("text"), item.get("issue_ids")
        if (not isinstance(rid, str) or not IDENTIFIER.fullmatch(rid) or rid in recommendation_ids
                or not isinstance(body, str) or not body.strip() or not isinstance(refs, list) or not refs
                or any(ref not in issue_ids for ref in refs) or len(refs) != len(set(refs))):
            raise ValueError("recommendation needs unique ID, text, and valid issue links")
        recommendation_ids.add(rid)
    if backend.execute("SELECT 1 FROM analysis_run WHERE run_id=?", (run_id,)).fetchone():
        raise ValueError("analysis run ID already exists; saved analysis is immutable")

    statements = [(
        "INSERT INTO analysis_run (run_id, source_sha256, config_hash, grouping_status, verifier_status, "
        "recommendation_status) VALUES (?, ?, ?, 'accepted', 'pending', ?)",
        (run_id, identity["source_sha256"], identity["config_hash"],
         "draft_unverified" if recommendations else "pending"))]
    statements += [("INSERT INTO issue (run_id, issue_id, title) VALUES (?, ?, ?)", (run_id, i["issue_id"], i["title"]))
                   for i in issues]
    statements += [("INSERT INTO issue_membership (run_id, issue_id, row_index) VALUES (?, ?, ?)", m)
                   for m in memberships]
    for item in recommendations:
        statements.append(("INSERT INTO recommendation (run_id, recommendation_id, text) VALUES (?, ?, ?)",
                           (run_id, item["recommendation_id"], item["text"])))
        statements += [("INSERT INTO recommendation_issue (run_id, recommendation_id, issue_id) VALUES (?, ?, ?)",
                        (run_id, item["recommendation_id"], issue_id)) for issue_id in item["issue_ids"]]
    backend.run_batch(statements)
    return {"run_id": run_id, "issues": len(issues), "memberships": len(memberships),
            "recommendations": len(recommendations)}

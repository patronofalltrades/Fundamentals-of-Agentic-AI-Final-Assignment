"""Read-only dashboard API and static UI. GET only; no browser credentials or writes.

``route()`` is the single request handler. The local ``http.server`` (``serve``) and the Vercel
WSGI entry (``dashboard.wsgi``) both call it, so local and deployed behavior match.
"""

import json
import mimetypes
import re
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .public_boundary import REF_RE
from .store import connect

STATIC = Path(__file__).with_name("static")
# The built Astro site (web/dist). When present it replaces the legacy static page.
DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
EVALS = Path(__file__).with_name("evals.json")  # built by tools/build_eval_registry.py
TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
TARGET_MINIMUM_SOURCE_ROWS = 100000  # instructor clarification; see AGENTS.md
SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
)
# Built HTML carries its own hash-based CSP <meta> (Astro security.csp); a strict header CSP would
# block its hashed inline scripts, so HTML pages only get the directives a <meta> cannot set.
HTML_HEADERS = tuple((k, v) for k, v in SECURITY_HEADERS if k != "Content-Security-Policy") + (
    ("Content-Security-Policy", "frame-ancestors 'none'"),
)


def headers_for(content_type):
    """Security headers for one response: API and assets keep the strict CSP."""
    return HTML_HEADERS if content_type.startswith("text/html") and DIST.is_dir() else SECURITY_HEADERS


ISSUE_RE = re.compile(r"^/api/issues/([^/]+)$")
REVIEW_RE = re.compile(r"^/api/reviews/([A-Za-z0-9]{1,40})$")
ROW_RE = re.compile(r"^[0-9]{1,9}$")


def _aggregates(conn):
    values = {}
    for row in conn.execute("SELECT dimension,value,count FROM dashboard_aggregate"):
        values.setdefault(row["dimension"], {})[row["value"]] = row["count"]
    return values


def _run(conn):
    row = conn.execute("SELECT * FROM analysis_run ORDER BY created_at DESC,run_id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def _stores_full_text(conn):
    # A raw sqlite3 connection (local copy) keeps the texts table; the deployed database does not.
    return getattr(conn, "stores_full_text", True)


def _mean(total, count):
    return str((Decimal(total) / Decimal(count)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


MIN_TREND_MONTHS = 3  # below this, use daily totals when the bundle saved them


def _trends(ag):
    """Monthly series from the month aggregates, or ``None`` when the database has none.

    When the data spans fewer than three months and daily totals exist, the series is daily instead.
    ``months`` then holds YYYY-MM-DD periods and ``granularity`` says so.
    """
    granularity = "month"
    reviews_by_month = ag.get("month_reviews", {})
    complaints, severity = ag.get("month_complaints", {}), ag.get("month_severity_sum", {})
    if len(set(reviews_by_month)) < MIN_TREND_MONTHS and ag.get("day_reviews"):
        granularity = "day"
        reviews_by_month = ag["day_reviews"]
        complaints, severity = ag.get("day_complaints", {}), ag.get("day_severity_sum", {})
    months = sorted(set(reviews_by_month) | set(complaints))
    if not months:
        return None
    return {"granularity": granularity, "months": months,
            "reviews": [int(reviews_by_month.get(m, 0)) for m in months],
            "complaints": [int(complaints.get(m, 0)) for m in months],
            "mean_severity": [_mean(severity.get(m, 0), complaints[m]) if complaints.get(m) else None for m in months]}


def _evaluations(conn):
    if not _has_table(conn, "dashboard_meta"):
        return {}
    sets = {}
    for row in conn.execute("SELECT key, value FROM dashboard_meta WHERE key LIKE ? ORDER BY key", ("evaluation:%",)):
        record = json.loads(row["value"])
        sets[record["label_set"]] = record
    return sets


def evaluation(conn):
    sets = _evaluations(conn)
    return {"status": "saved", "sets": sets} if sets else {"status": "pending"}


def top_issue(conn):
    items = issues(conn)["items"]
    if not items:
        return None
    first = items[0]
    return {"issue_id": first["issue_id"], "title": first["title"], "mean_severity": first["mean_severity"],
            "priority_score": first["priority_score"], "complaint_count": first["review_count"]}


STATE_ORDER = ("accepted", "quarantined", "unresolved", "empty", "pending")
PUBLIC_MANIFEST_KEYS = ("import_version", "handoff_sha256", "source_file_sha256", "label_config_hash", "selected_rows",
                        "accepted_rows", "state_counts", "representative_evidence_exclusions", "reason_category_counts",
                        "public_examples", "personal_info_screen", "issue_candidates", "imported_at", "scope", "not_human_accuracy")


def _states(ag):
    """Row states from an accepted-evidence import, or ``None`` for older databases."""
    saved = ag.get("row_state")
    if not saved:
        return None
    return {state: int(saved.get(state, 0)) for state in STATE_ORDER}


def _public(conn):
    """True for an accepted-evidence import: public responses then follow the approved boundary.

    Records are reached only by opaque references, quotes only as bounded excerpts, and nonaccepted rows only as
    counts. Older bundle databases keep their row-number routes.
    """
    return _has_table(conn, "public_example")


def _blocked_count(conn):
    if not _has_table(conn, "semantic_flag"):
        return None
    return conn.execute("SELECT COUNT(*) FROM semantic_flag WHERE blocked=1").fetchone()[0]


def _import_manifest(conn):
    """Counts, hashes and the import time. Paths and private fields are never included."""
    if not _has_table(conn, "dashboard_meta"):
        return None
    row = conn.execute("SELECT value FROM dashboard_meta WHERE key='import_manifest'").fetchone()
    if not row:
        return None
    saved = json.loads(row[0])
    return {key: saved[key] for key in PUBLIC_MANIFEST_KEYS if key in saved}


def _reason_categories(ag):
    """Counts of sanitized reason categories per nonaccepted state, or ``None`` for older databases."""
    saved = ag.get("reason_category")
    if not saved:
        return None
    result = {}
    for key, n in saved.items():
        state, category = key.split(":", 1)
        result.setdefault(state, {})[category] = int(n)
    return result


def summary(conn):
    ag = _aggregates(conn)
    rows = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    saved = ag.get("coverage", {}).get("distinct_nonempty_texts")
    distinct = saved if saved is not None else conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    source = dict(conn.execute("SELECT key,value FROM meta WHERE key IN ('file_sha256','source_basename')"))
    config = conn.execute("SELECT DISTINCT config_hash FROM record_state LIMIT 1").fetchone()
    run = _run(conn)
    saved_evaluation = evaluation(conn)
    return {
        "source": {"basename": source["source_basename"], "sha256": source["file_sha256"], "config_hash": config[0] if config else None},
        "coverage": {"source_rows": rows, "nonempty_rows": ag.get("source_status", {}).get("nonempty", 0), "distinct_nonempty_texts": distinct, "completed_rows": ag.get("processing_status", {}).get("completed", 0), "empty_rows": ag.get("source_status", {}).get("empty", 0)},
        "raw_labels": {"topic": ag.get("topic", {}), "intent": ag.get("intent", {}), "severity": ag.get("severity", {})},
        "quality": {"classifier_agreement": None, "blind_verifier": "pending", "human_evaluation": saved_evaluation["status"]},
        "analysis": {"grouping": run["grouping_status"] if run else "pending", "ranking": "saved_membership_severity_sum" if run else "pending", "recommendations": run["recommendation_status"] if run else "pending", "memo": memo(conn)["status"], "run_id": run["run_id"] if run else None},
        "trends": _trends(ag),
        "evaluation": saved_evaluation,
        "top_issue": top_issue(conn),
        "target": {"minimum_source_rows": TARGET_MINIMUM_SOURCE_ROWS, "is_demo": rows < TARGET_MINIMUM_SOURCE_ROWS},
        "states": _states(ag),
        "representative_exclusions": _blocked_count(conn),
        "import": _import_manifest(conn),
        "reason_categories": _reason_categories(ag),
        "note": "Development checkpoint only. Raw topic labels are not validated issue clusters or product prevalence. The 100,000-row minimum is not complete.",
    }


def reviews(conn, topic=None, limit=20, offset=0, issue_id=None, query=None):
    limit = min(max(int(limit), 1), 50)
    offset = max(int(offset), 0)
    if _public(conn):
        return _public_reviews(conn, topic, limit, offset, issue_id, query)
    args = []
    where = ["s.status='completed'"]
    join = ""
    if topic:
        where.append("c.topic=?")
        args.append(topic)
    if query:
        where.append("instr(lower(c.evidence_quote),lower(?))>0")
        args.append(query)
    if issue_id:
        run = _run(conn)
        if not run:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        join = "JOIN issue_membership m ON m.row_index=r.row_index AND m.run_id=? AND m.issue_id=?"
        args = [run["run_id"], issue_id] + args
    flagged = _has_table(conn, "semantic_flag")
    if flagged:  # records blocked by known semantic flags are never representative examples
        join += " LEFT JOIN semantic_flag f ON f.row_index=r.row_index"
        where.append("COALESCE(f.blocked, 0)=0")
    base = "FROM records r JOIN record_state s USING(row_index) JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=s.config_hash %s WHERE %s" % (join, " AND ".join(where))
    total = conn.execute("SELECT COUNT(*) " + base, args).fetchone()[0]
    items = [dict(row) for row in conn.execute("SELECT r.row_index, r.row_sha256 AS source_sha256, c.topic,c.intent,c.severity,c.evidence_quote,c.needs_review,c.is_cached " + base + " ORDER BY r.row_index LIMIT ? OFFSET ?", args + [limit, offset])]
    result = {"items": items, "total": total, "limit": limit, "offset": offset}
    if flagged:
        result["excluded_blocked"] = _blocked_count(conn)
    return result


def _public_reviews(conn, topic, limit, offset, issue_id, query):
    """Public examples: opaque reference, labels and a bounded excerpt. Never a row number, ID or hash.

    The order is by reference, which is random, so a page offset reveals nothing about source positions.
    Search reads the public excerpt only, never the private full quote.
    """
    args, where, join = [], ["1=1"], ""
    if topic:
        where.append("c.topic=?")
        args.append(topic)
    if query:
        where.append("instr(lower(p.excerpt),lower(?))>0")
        args.append(query)
    if issue_id:
        run = _run(conn)
        if not run:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        join = "JOIN issue_membership m ON m.row_index=p.row_index AND m.run_id=? AND m.issue_id=?"
        args = [run["run_id"], issue_id] + args
    base = ("FROM public_example p JOIN record_state s ON s.row_index=p.row_index AND s.status='completed' "
            "JOIN classifications c ON c.row_index=p.row_index AND c.config_hash=s.config_hash %s WHERE %s"
            % (join, " AND ".join(where)))
    total = conn.execute("SELECT COUNT(*) " + base, args).fetchone()[0]
    items = []
    for row in conn.execute("SELECT p.ref, c.topic, c.intent, c.severity, p.excerpt, p.shortened, c.needs_review, "
                            "c.is_cached " + base + " ORDER BY p.ref LIMIT ? OFFSET ?", args + [limit, offset]):
        item = dict(row)
        item["shortened"] = bool(item["shortened"])
        items.append(item)
    examples = (_import_manifest(conn) or {}).get("public_examples", {})
    return {"items": items, "total": total, "limit": limit, "offset": offset,
            "excluded_blocked": _blocked_count(conn),
            "excluded_personal_info": examples.get("excluded_personal_info")}


def public_review(conn, ref):
    """One public example by its opaque reference, or ``None``. Nonaccepted and flagged rows have none."""
    if not REF_RE.match(ref):
        return None
    row = conn.execute("""SELECT p.ref, c.topic, c.intent, c.severity, c.sentiment, p.excerpt, p.shortened,
        c.needs_review, c.is_cached, c.label_config, c.model, c.prompt_version
        FROM public_example p JOIN record_state s ON s.row_index=p.row_index AND s.status='completed'
        JOIN classifications c ON c.row_index=p.row_index AND c.config_hash=s.config_hash
        WHERE p.ref=?""", (ref,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["state"] = "accepted"
    result["shortened"] = bool(result["shortened"])
    result["human_validated"] = False
    result["review_text_exposed"] = False
    return result


def review(conn, row_index):
    row = conn.execute("""SELECT r.row_index,r.row_sha256 AS source_sha256,
        c.topic,c.intent,c.severity,c.sentiment,c.evidence_quote,
        c.needs_review,c.is_cached,c.label_config,c.model,c.prompt_version
        FROM records r JOIN classifications c USING(row_index) WHERE r.row_index=?""", (row_index,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["source_id_stored"] = True
    result["review_text_available_in_database"] = bool(_stores_full_text(conn))
    result["review_text_exposed"] = False
    return result


def issues(conn):
    run = _run(conn)
    if not run:
        return {"status": "pending", "ranking_method": "severity_sum", "items": []}
    flagged = _has_table(conn, "semantic_flag")
    # Public rankings leave out members with a known semantic flag until they are reviewed.
    flag_join = "LEFT JOIN semantic_flag f ON f.row_index=m.row_index" if flagged else ""
    flag_where = "AND COALESCE(f.blocked, 0)=0" if flagged else ""
    rows = conn.execute("""SELECT i.issue_id,i.title,COUNT(m.row_index) AS review_count,
       SUM(c.severity) AS priority_score
       FROM issue i JOIN issue_membership m USING(run_id,issue_id)
       JOIN classifications c ON c.row_index=m.row_index AND c.config_hash=? %s
       WHERE i.run_id=? AND c.intent IN ('complaint','cancellation') %s
       GROUP BY i.issue_id,i.title ORDER BY priority_score DESC,i.issue_id ASC""" % (flag_join, flag_where),
                        (run["config_hash"], run["run_id"])).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["mean_severity"] = _mean(item["priority_score"], item["review_count"])
        items.append(item)
    return {"status": "accepted_membership", "run_id": run["run_id"], "ranking_method": "severity_sum", "items": items}


def _has_table(conn, name):
    try:
        conn.execute("SELECT 1 FROM %s LIMIT 1" % name).fetchone()
        return True
    except Exception:  # older dashboard copies have no claim/memo tables
        return False


def claims(conn, issue_id=None):
    run = _run(conn)
    if not run or not _has_table(conn, "claim"):
        return {"status": "pending", "items": []}
    sql = "SELECT claim_id, issue_id, metric, value FROM claim WHERE run_id=?"
    args = [run["run_id"]]
    if issue_id:
        sql += " AND issue_id=?"
        args.append(issue_id)
    items = [dict(r) for r in conn.execute(sql + " ORDER BY claim_id", args)]
    return {"status": "saved" if items else "pending", "run_id": run["run_id"], "items": items}


def memo(conn):
    run = _run(conn)
    row = conn.execute("SELECT text, sha256, claim_check FROM memo WHERE run_id=?", (run["run_id"],)).fetchone() \
        if run and _has_table(conn, "memo") else None
    if not row:
        return {"status": "pending", "text": None}
    return {"status": "claims_checked" if row["claim_check"] == "passed" else "claim_check_" + row["claim_check"],
            "run_id": run["run_id"], "text": row["text"], "sha256": row["sha256"]}


def recommendations(conn):
    run = _run(conn)
    if not run:
        return {"status": "pending", "items": []}
    result = []
    for row in conn.execute("SELECT recommendation_id,text FROM recommendation WHERE run_id=? ORDER BY recommendation_id", (run["run_id"],)):
        item = dict(row)
        item["issue_ids"] = [r[0] for r in conn.execute("SELECT issue_id FROM recommendation_issue WHERE run_id=? AND recommendation_id=? ORDER BY issue_id", (run["run_id"], row["recommendation_id"]))]
        result.append(item)
    return {"status": run["recommendation_status"], "items": result}


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def evals(conn):
    """Saved benchmarks (evals.json) plus the live golden evaluation and integrity checks."""
    registry = json.loads(EVALS.read_text(encoding="utf-8")) if EVALS.exists() else {"items": []}
    run, saved_memo = _run(conn), memo(conn)
    source = conn.execute("SELECT value FROM meta WHERE key='file_sha256'").fetchone()
    memo_state = {"claims_checked": "passed", "pending": "pending"}.get(saved_memo["status"], "failed")
    checks = [
        _check("Ranking reproduced from saved labels", "passed" if run else "pending",
               "The import recomputes the ranking with the course rule and stops on any difference."),
        _check("Memo numbers match saved claims", memo_state,
               "Every claim ID in the memo must appear with its saved value."),
        _check("Source file fingerprint recorded", "passed" if source else "failed",
               "Each saved label is tied to the SHA-256 of the source file."),
        _check("Full review texts kept out of the public database", "failed" if _stores_full_text(conn) else "passed",
               "The deployed database holds labels and short evidence quotes only."),
    ]
    return {**registry, "golden": evaluation(conn), "checks": checks}


def _json_body(status, value):
    return status, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _api(conn, path, query):
    if path == "/api/summary":
        return _json_body(200, summary(conn))
    if path == "/api/reviews":
        q = parse_qs(query)
        topic = q.get("topic", [None])[0]
        if topic and topic not in TOPICS:
            return _json_body(400, {"error": "invalid topic"})
        text_query = q.get("q", [None])[0]
        if text_query and len(text_query) > 100:
            return _json_body(400, {"error": "query too long"})
        return _json_body(200, reviews(conn, topic, q.get("limit", [20])[0], q.get("offset", [0])[0],
                                       q.get("issue_id", [None])[0], text_query))
    if path == "/api/issues":
        return _json_body(200, issues(conn))
    if path == "/api/recommendations":
        return _json_body(200, recommendations(conn))
    if path == "/api/claims":
        issue = parse_qs(query).get("issue_id", [None])[0]
        return _json_body(200, claims(conn, issue))
    if path == "/api/memo":
        return _json_body(200, memo(conn))
    if path == "/api/evals":
        return _json_body(200, evals(conn))
    match = ISSUE_RE.match(path)
    if match:
        item = next((x for x in issues(conn)["items"] if x["issue_id"] == match.group(1)), None)
        if item is None:
            return _json_body(404, {"error": "issue not found"})
        return _json_body(200, {**item, "claims": claims(conn, match.group(1))["items"],
                                "reviews": reviews(conn, issue_id=match.group(1))})
    match = REVIEW_RE.match(path)
    if match:
        key = match.group(1)
        if _public(conn):  # opaque references only; row numbers never resolve
            result = public_review(conn, key)
        else:
            result = review(conn, int(key)) if ROW_RE.match(key) else None
        return _json_body(200, result) if result is not None else _json_body(404, {"error": "review not found"})
    return _json_body(404, {"error": "not found"})


def route(open_conn, method, path, query=""):
    """Handle one request. ``open_conn()`` returns a context-managed read-only connection.

    Returns ``(status, content_type, body_bytes)``. Only GET and HEAD are served.
    """
    if method not in ("GET", "HEAD"):
        return _json_body(405, {"error": "read-only API"})
    try:
        if path.startswith("/api/"):
            with open_conn() as conn:
                return _api(conn, path, query)
        name = "index.html" if path == "/" else path.lstrip("/")
        if DIST.is_dir():
            root = DIST.resolve()
            target = (root / name).resolve()
            if root not in target.parents or not target.is_file():
                return _json_body(404, {"error": "not found"})
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/"):
                content_type += "; charset=utf-8"
            return 200, content_type, target.read_bytes()
        if name not in ("index.html", "app.js", "style.css"):
            return _json_body(404, {"error": "not found"})
        return 200, mimetypes.guess_type(name)[0] or "application/octet-stream", (STATIC / name).read_bytes()
    except (ValueError, TypeError):
        return _json_body(400, {"error": "invalid query"})


def make_handler(db_path):
    def open_conn():
        return connect(db_path, readonly=True)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, method):
            parsed = urlparse(self.path)
            status, content_type, body = route(open_conn, method, parsed.path, parsed.query)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for name, value in headers_for(content_type):
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            self._send("GET")

        def do_HEAD(self):
            self._send("HEAD")

        def do_POST(self):
            self._send("POST")

        def log_message(self, fmt, *args):
            pass  # No request URLs or review details in local logs.

    return Handler


def serve(db_path, host="127.0.0.1", port=8765):
    with connect(db_path, readonly=True) as conn:
        summary(conn)
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print("Dashboard: http://%s:%s" % (host, server.server_port))
    server.serve_forever()

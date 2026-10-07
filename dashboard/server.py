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

from .store import connect

STATIC = Path(__file__).with_name("static")
TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
TARGET_MINIMUM_SOURCE_ROWS = 100000  # instructor clarification; see AGENTS.md
SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
)
ISSUE_RE = re.compile(r"^/api/issues/([^/]+)$")
REVIEW_RE = re.compile(r"^/api/reviews/([0-9]+)$")


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


def summary(conn):
    ag = _aggregates(conn)
    rows = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    saved = ag.get("coverage", {}).get("distinct_nonempty_texts")
    distinct = saved if saved is not None else conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    source = dict(conn.execute("SELECT key,value FROM meta WHERE key IN ('file_sha256','source_basename')"))
    config = conn.execute("SELECT DISTINCT config_hash FROM record_state LIMIT 1").fetchone()
    run = _run(conn)
    return {
        "source": {"basename": source["source_basename"], "sha256": source["file_sha256"], "config_hash": config[0] if config else None},
        "coverage": {"source_rows": rows, "nonempty_rows": ag.get("source_status", {}).get("nonempty", 0), "distinct_nonempty_texts": distinct, "completed_rows": ag.get("processing_status", {}).get("completed", 0), "empty_rows": ag.get("source_status", {}).get("empty", 0)},
        "raw_labels": {"topic": ag.get("topic", {}), "intent": ag.get("intent", {}), "severity": ag.get("severity", {})},
        "quality": {"classifier_agreement": None, "blind_verifier": "pending", "human_evaluation": "pending"},
        "analysis": {"grouping": run["grouping_status"] if run else "pending", "ranking": "saved_membership_severity_sum" if run else "pending", "recommendations": run["recommendation_status"] if run else "pending", "memo": memo(conn)["status"], "run_id": run["run_id"] if run else None},
        "target": {"minimum_source_rows": TARGET_MINIMUM_SOURCE_ROWS, "is_demo": rows < TARGET_MINIMUM_SOURCE_ROWS},
        "note": "Development checkpoint only. Raw topic labels are not validated issue clusters or product prevalence. The 100,000-row minimum is not complete.",
    }


def reviews(conn, topic=None, limit=20, offset=0, issue_id=None, query=None):
    limit = min(max(int(limit), 1), 50)
    offset = max(int(offset), 0)
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
    base = "FROM records r JOIN record_state s USING(row_index) JOIN classifications c ON c.row_index=r.row_index AND c.config_hash=s.config_hash %s WHERE %s" % (join, " AND ".join(where))
    total = conn.execute("SELECT COUNT(*) " + base, args).fetchone()[0]
    items = [dict(row) for row in conn.execute("SELECT r.row_index, r.row_sha256 AS source_sha256, c.topic,c.intent,c.severity,c.evidence_quote,c.needs_review,c.is_cached " + base + " ORDER BY r.row_index LIMIT ? OFFSET ?", args + [limit, offset])]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
    rows = conn.execute("""SELECT i.issue_id,i.title,COUNT(m.row_index) AS review_count,
       SUM(c.severity) AS priority_score
       FROM issue i JOIN issue_membership m USING(run_id,issue_id)
       JOIN classifications c ON c.row_index=m.row_index AND c.config_hash=?
       WHERE i.run_id=? AND c.intent IN ('complaint','cancellation')
       GROUP BY i.issue_id,i.title ORDER BY priority_score DESC,i.issue_id ASC""", (run["config_hash"], run["run_id"])).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["mean_severity"] = str((Decimal(item["priority_score"]) / Decimal(item["review_count"])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
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
    match = ISSUE_RE.match(path)
    if match:
        item = next((x for x in issues(conn)["items"] if x["issue_id"] == match.group(1)), None)
        if item is None:
            return _json_body(404, {"error": "issue not found"})
        return _json_body(200, {**item, "claims": claims(conn, match.group(1))["items"],
                                "reviews": reviews(conn, issue_id=match.group(1))})
    match = REVIEW_RE.match(path)
    if match:
        result = review(conn, int(match.group(1)))
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
            for name, value in SECURITY_HEADERS:
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

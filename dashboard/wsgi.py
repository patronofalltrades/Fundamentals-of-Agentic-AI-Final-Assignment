"""WSGI entry for Vercel's Python runtime (and any WSGI server). Read-only.

The backend comes from the environment: ``DATABASE_URL`` (Postgres over Neon HTTPS) or
``DASHBOARD_DB`` (a SQLite file, for local checks only). The page never calls a model.
"""

from .backend import from_env
from .server import SECURITY_HEADERS, route

STATUS_TEXT = {200: "200 OK", 400: "400 Bad Request", 404: "404 Not Found", 405: "405 Method Not Allowed",
               500: "500 Internal Server Error", 503: "503 Service Unavailable"}


def make_app(open_conn=None):
    def default_open():
        return from_env()

    opener = open_conn or default_open

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO") or "/"
        query = environ.get("QUERY_STRING", "")
        try:
            status, content_type, body = route(opener, method, path, query)
        except Exception:  # never echo database errors or connection details to the browser
            status, content_type, body = 503, "application/json; charset=utf-8", b'{"error":"saved results unavailable"}'
        headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))] + list(SECURITY_HEADERS)
        start_response(STATUS_TEXT.get(status, "%d Error" % status), headers)
        return [b"" if method == "HEAD" else body]

    return app


app = make_app()

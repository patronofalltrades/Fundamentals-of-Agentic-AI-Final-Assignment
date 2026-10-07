"""SYNTHETIC tests: serving a built web/dist (Astro) from the same route() and headers."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dashboard import server
from dashboard.server import headers_for, route


class DistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        dist = Path(self.temp.name) / "dist"
        (dist / "_astro").mkdir(parents=True)
        (dist / "index.html").write_text("<!doctype html><meta http-equiv=\"content-security-policy\" content=\"x\">built")
        (dist / "_astro" / "app.abc.js").write_text("console.log(1)")
        (Path(self.temp.name) / "secret.txt").write_text("outside")
        patcher = mock.patch.object(server, "DIST", dist)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_serves_built_files_with_types(self):
        status, ctype, body = route(lambda: None, "GET", "/")
        self.assertEqual((status, ctype), (200, "text/html; charset=utf-8"))
        self.assertIn(b"built", body)
        status, ctype, _ = route(lambda: None, "GET", "/_astro/app.abc.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)

    def test_blocks_traversal_and_missing_files(self):
        for path in ("/../secret.txt", "/_astro/../../secret.txt", "/missing.js", "/_astro"):
            self.assertEqual(route(lambda: None, "GET", path)[0], 404, path)

    def test_html_gets_meta_friendly_csp_and_api_keeps_strict_csp(self):
        html = dict(headers_for("text/html; charset=utf-8"))
        self.assertEqual(html["Content-Security-Policy"], "frame-ancestors 'none'")
        self.assertEqual(html["X-Content-Type-Options"], "nosniff")
        api = dict(headers_for("application/json; charset=utf-8"))
        self.assertIn("script-src 'self'", api["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()

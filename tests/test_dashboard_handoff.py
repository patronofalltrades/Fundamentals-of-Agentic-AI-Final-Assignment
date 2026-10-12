"""SYNTHETIC tests: converting the checkpoint dashboard handoff into a bundle, and daily trends."""

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dashboard.backend import SQLiteBackend
from dashboard.bundle import load_bundle
from dashboard.handoff import handoff_to_bundle
from dashboard.server import summary

CONFIG = "c" * 64
SOURCE = [
    ("synthetic-1", "Playback stops after every song", "2022-05-17 08:00:00"),
    ("synthetic-2", "Love the new playlists", "2022-05-17 09:00:00"),
    ("synthetic-3", "Charged twice this month", "2022-05-18 10:00:00"),
]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(rid, text, ts, topic, intent, severity, quote, cached=False):
    return {"review_id": rid, "source_sha256": sha("row:" + rid),
            "source": {"review_id": rid, "review_text": text, "review_timestamp": ts, "review_rating": 1},
            "labels": {"topic": topic, "intent": intent, "severity": severity, "sentiment": -0.5,
                       "needs_review": False, "model": "jev-synthetic", "confidence": {}},
            "evidence": {"evidence_quote": quote, "entities": ["playback"]},
            "provenance": {"label": {"config_sha256": CONFIG, "kind": "jev_exact_text_cache" if cached else "jev_direct"},
                           "evidence": {"kind": "deepinfra_direct"}}}


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.csv = self.tmp / "source.csv"
        with self.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"])
            for rid, text, ts in SOURCE:
                w.writerow([rid, text, 1, 0, "", ts])
        self.manifest = {"schema_version": "checkpoint5000-manifest-v1", "source_file": "source.csv",
                         "source_file_sha256": hashlib.sha256(self.csv.read_bytes()).hexdigest(),
                         "label_config_hash": CONFIG, "counts": {"distinct_texts": 3},
                         "rows": [{"review_id": rid, "source_position": i + 1, "source_sha256": sha("row:" + rid),
                                   "text_sha256": sha(text)} for i, (rid, text, _) in enumerate(SOURCE)]}
        self.handoff = {"schema_version": "checkpoint5000-dashboard-handoff-v1", "records": [
            record("synthetic-1", SOURCE[0][1], SOURCE[0][2], "playback", "complaint", 4, "Playback stops"),
            record("synthetic-2", SOURCE[1][1], SOURCE[1][2], "other", "praise", 1, "new playlists", True)],
            "excluded": [{"review_id": "synthetic-3", "source_sha256": sha("row:synthetic-3"), "status": "quarantined",
                          "reason": "ValidationError: evidence quote must be an exact source substring"}]}

    def convert(self, handoff=None, manifest=None, out="bundle"):
        h, m = self.tmp / "handoff.json", self.tmp / "manifest.json"
        h.write_text(json.dumps(handoff or self.handoff))
        m.write_text(json.dumps(manifest or self.manifest))
        return handoff_to_bundle(str(h), str(m), str(self.csv), str(self.tmp / out))

    def test_bundle_loads_without_review_text_and_with_daily_trends(self):
        manifest = self.convert()
        self.assertEqual(manifest["counts"], {"completed_rows": 2, "nonempty_rows": 3, "quarantined_rows": 1,
                                              "source_rows": 3, "distinct_nonempty_texts": 3})
        self.assertEqual(manifest["days"], {"2022-05-17": {"reviews": 2, "complaints": 1, "severity_sum": 4},
                                            "2022-05-18": {"reviews": 1, "complaints": 0, "severity_sum": 0}})
        rows = (self.tmp / "bundle" / "rows.jsonl").read_text()
        for _, text, ts in SOURCE:
            self.assertNotIn(text, rows)
            self.assertNotIn(ts, rows)
        db = str(self.tmp / "dash.db")
        with SQLiteBackend(db, readonly=False) as b:
            self.assertEqual(load_bundle(b, str(self.tmp / "bundle"))["result"], "imported")
        with SQLiteBackend(db) as b:
            s = summary(b)
        self.assertEqual(s["coverage"]["completed_rows"], 2)
        self.assertEqual((s["trends"]["granularity"], s["trends"]["months"], s["trends"]["complaints"]),
                         ("day", ["2022-05-17", "2022-05-18"], [1, 0]))

    def test_mismatches_stop_before_writing(self):
        bad_quote = copy.deepcopy(self.handoff)
        bad_quote["records"][0]["evidence"]["evidence_quote"] = "not in the review"
        bad_text = copy.deepcopy(self.handoff)
        bad_text["records"][0]["source"]["review_text"] = "edited text"
        missing = copy.deepcopy(self.handoff)
        missing["excluded"] = []
        bad_config = copy.deepcopy(self.handoff)
        bad_config["records"][1]["provenance"]["label"]["config_sha256"] = "d" * 64
        bad_source = dict(self.manifest, source_file_sha256="0" * 64)
        for i, (h, m) in enumerate([(bad_quote, None), (bad_text, None), (missing, None), (bad_config, None),
                                    (None, bad_source)]):
            with self.assertRaises(ValueError, msg=i):
                self.convert(h, m, out="b%d" % i)
            self.assertFalse((self.tmp / ("b%d" % i)).exists(), i)


if __name__ == "__main__":
    unittest.main()

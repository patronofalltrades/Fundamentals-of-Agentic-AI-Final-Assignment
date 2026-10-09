"""Offline checks for first-500 source identity and durable queue selection."""

import sqlite3
import unittest

from spotify_pipeline.config import config_hash
from spotify_pipeline.jev import label_config
from tools import deepinfra_recheck100 as recheck
from tools import next5000_checkpoint as checkpoint


class Next5000CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE next5000_rows(position INTEGER,review_id TEXT,review_text TEXT,source_sha TEXT,text_sha TEXT,blocked INTEGER)")
        self.db.execute("CREATE TABLE next5000_labels(review_id TEXT,label_json TEXT,config_sha TEXT,provenance TEXT,origin_id TEXT,request_key TEXT)")
        self.db.execute("CREATE TABLE next5000_evidence(review_id TEXT,entities_json TEXT,evidence_quote TEXT,config_sha TEXT,provenance TEXT,origin_id TEXT,request_key TEXT)")
        self.db.execute("CREATE TABLE next5000_requests(request_key TEXT,stage TEXT,status TEXT)")
        self.db.execute("CREATE TABLE next5000_members(request_key TEXT,review_id TEXT)")
        self.db.executemany("INSERT INTO next5000_rows VALUES (?,?,?,?,?,?)", [
            (5001, "a", "same text", "sha-a", "textsha-a", 0),
            (5002, "b", "same text", "sha-b", "textsha-b", 0),
            (5003, "c", "uncertain text", "sha-c", "textsha-c", 1),
            (5004, "d", "new text", "sha-d", "textsha-d", 0)])

    def tearDown(self):
        self.db.close()

    def test_exact_text_alias_keeps_both_source_ids(self):
        self.assertEqual([r["review_id"] for r in checkpoint.pending(self.db, "jev")], ["a", "d"])
        checkpoint.aliases(self.db, "jev", "same text", '{"topic":"other"}', "a")
        self.assertEqual(dict(self.db.execute("SELECT review_id,origin_id FROM next5000_labels")),
                         {"a": "a", "b": "a"})
        self.assertEqual([r["review_id"] for r in checkpoint.pending(self.db, "jev")], ["d"])
        self.assertEqual(config_hash(label_config()), self.db.execute(
            "SELECT config_sha FROM next5000_labels LIMIT 1").fetchone()[0])

    def test_attempted_text_and_prior_uncertainty_are_never_selected(self):
        self.db.execute("INSERT INTO next5000_requests VALUES ('held','jev','uncertain')")
        self.db.execute("INSERT INTO next5000_members VALUES ('held','a')")
        self.assertEqual([r["review_id"] for r in checkpoint.pending(self.db, "jev")], ["d"])

    def test_evidence_alias_keeps_exact_span_and_config(self):
        checkpoint.aliases(self.db, "evidence", "same text",
            {"entities": [], "evidence_quote": "same text"}, "a")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM next5000_evidence").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT config_sha FROM next5000_evidence LIMIT 1").fetchone()[0],
                         recheck.config_sha())

    def test_four_review_tail_has_own_config_and_exact_id_accounting(self):
        rows = [{"review_id": str(i), "review_text": "text " + str(i),
            "source_sha256": "hash" + str(i), "labels": {"topic": "other",
            "intent": "praise", "severity": 1, "sentiment": 0.5}}
            for i in range(4)]
        body = checkpoint.evidence_payload(rows)
        self.assertEqual(body["response_format"]["json_schema"]["schema"]
            ["properties"]["results"]["minItems"], 4)
        self.assertEqual(body["response_format"]["json_schema"]["schema"]
            ["properties"]["results"]["maxItems"], 4)
        self.assertEqual(body["provider"], {"only": [recheck.PROVIDER],
            "allow_fallbacks": False, "require_parameters": True,
            "data_collection": "deny", "zdr": True})
        self.assertNotEqual(checkpoint.evidence_config(rows), recheck.config_sha())
        self.assertEqual(checkpoint.evidence_payload(rows[:3])["response_format"]
            ["json_schema"]["schema"]["properties"]["results"]["minItems"], 3)
        self.assertRaises(ValueError, checkpoint.evidence_payload, [])
        self.assertRaises(ValueError, checkpoint.evidence_payload, rows + rows[:1])
        items = [{"review_id": r["review_id"], "entities": [],
            "evidence_quote": r["review_text"]} for r in rows]
        response = {"choices": [{"finish_reason": "stop", "message": {
            "content": checkpoint.canonical({"results": items})}}]}
        self.assertEqual(len(checkpoint.inspect_evidence(response, rows)[0]), 4)
        items[1]["review_id"] = "0"
        response["choices"][0]["message"]["content"] = checkpoint.canonical({"results": items})
        self.assertRaises(ValueError, checkpoint.inspect_evidence, response, rows)

    def test_remainder_activation_preserves_settled_first_500(self):
        self.db.execute("CREATE TABLE next5000_quarantines(review_id TEXT,reason TEXT,request_key TEXT)")
        self.db.execute("DELETE FROM next5000_rows")
        rows = [{"source_position": i, "review_id": "id" + str(i),
            "review_text": "text" + str(i), "source_sha256": "sha" + str(i),
            "text_sha256": "textsha" + str(i), "blocked_prior_uncertainty": False}
            for i in range(5001, 10001)]
        for row in rows[:500]:
            self.db.execute("INSERT INTO next5000_rows VALUES (?,?,?,?,?,?)",
                (row["source_position"], row["review_id"], row["review_text"],
                 row["source_sha256"], row["text_sha256"], 0))
            self.db.execute("INSERT INTO next5000_labels VALUES (?,?,?,?,?,?)",
                (row["review_id"], "{}", "cfg", "direct", None, "old"))
            self.db.execute("INSERT INTO next5000_evidence VALUES (?,?,?,?,?,?,?)",
                (row["review_id"], "[]", row["review_text"], "cfg", "direct", None, "old"))
        self.assertEqual(checkpoint.extend_remaining(self.db, {"rows": rows}), 4500)
        self.assertEqual(checkpoint.extend_remaining(self.db, {"rows": rows}), 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM next5000_rows").fetchone()[0], 5000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM next5000_evidence WHERE request_key='old'").fetchone()[0], 500)

    def test_uncertain_deferral_keeps_full_hold_and_excludes_attempted_text(self):
        self.db.execute("CREATE TABLE next5000_quarantines(review_id TEXT,reason TEXT,request_key TEXT)")
        self.db.execute("CREATE TABLE reservations(request_key TEXT,budget TEXT,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)")
        self.db.execute("INSERT INTO next5000_requests VALUES ('held','evidence','uncertain')")
        self.db.execute("INSERT INTO next5000_members VALUES ('held','a')")
        self.db.execute("INSERT INTO reservations VALUES ('held','openrouter','uncertain',?,NULL)",
            (recheck.reservation_nusd(),))
        self.assertEqual(checkpoint.assert_resume_safe(self.db, "evidence", True), 1)
        self.assertRaises(ValueError, checkpoint.assert_resume_safe, self.db, "evidence")
        self.db.execute("INSERT INTO next5000_labels VALUES ('a','{}','cfg','direct',NULL,'old')")
        self.db.execute("INSERT INTO next5000_labels VALUES ('d','{}','cfg','direct',NULL,'old')")
        self.assertEqual([r["review_id"] for r in checkpoint.pending(self.db, "evidence")], ["d"])
        self.db.execute("UPDATE reservations SET reserved_nusd=1 WHERE request_key='held'")
        self.assertRaises(ValueError, checkpoint.assert_resume_safe, self.db, "evidence", True)


if __name__ == "__main__":
    unittest.main()

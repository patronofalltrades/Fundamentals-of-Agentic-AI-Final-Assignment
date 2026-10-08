"""Offline recovery never invents a missing ID or changes a metered charge."""

import sqlite3
import unittest

from tools import deepinfra_recheck100 as recheck
from tools import next5000_recover as recovery
from tools.next5000_checkpoint import canonical


class Next5000RecoveryTest(unittest.TestCase):
    def test_salvages_only_unique_exact_span_rows(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE reservations(request_key TEXT,status TEXT,charged_nusd INTEGER)")
            db.execute("CREATE TABLE next5000_requests(request_key TEXT,status TEXT,response_json TEXT,config_sha TEXT)")
            db.execute("CREATE TABLE next5000_rows(review_id TEXT,review_text TEXT,source_sha TEXT,blocked INTEGER)")
            db.execute("CREATE TABLE next5000_members(request_key TEXT,review_id TEXT)")
            db.execute("CREATE TABLE next5000_quarantines(review_id TEXT,reason TEXT,request_key TEXT)")
            db.execute("CREATE TABLE next5000_evidence(review_id TEXT,entities_json TEXT,evidence_quote TEXT,config_sha TEXT,provenance TEXT,origin_id TEXT,request_key TEXT)")
            for i in range(10):
                rid = "id" + str(i)
                db.execute("INSERT INTO next5000_rows VALUES (?,?,?,0)",
                    (rid, "review text " + str(i), "sha" + str(i)))
                db.execute("INSERT INTO next5000_members VALUES ('saved',?)", (rid,))
                db.execute("INSERT INTO next5000_quarantines VALUES (?,'unknown ID','saved')", (rid,))
            items = [{"review_id": "id" + str(i), "entities": [],
                "evidence_quote": "review text " + str(i)} for i in range(9)]
            items.append({"review_id": "unknown", "entities": [],
                "evidence_quote": "untrusted"})
            response = {"provider": "DeepInfra", "model": recheck.MODEL, "id": "generation",
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
                "choices": [{"finish_reason": "stop", "message": {
                    "content": canonical({"results": items})}}]}
            charge = recheck.measured_usage(response)[-1]
            db.execute("INSERT INTO reservations VALUES ('saved','quarantined_metered',?)", (charge,))
            db.execute("INSERT INTO next5000_requests VALUES ('saved','quarantined_metered',?,?)",
                (canonical(response), recheck.config_sha()))
            self.assertEqual(recovery.recover(db), {"batches": 1,
                "new_accepted": 9, "remaining_quarantined": 1})
            self.assertEqual(db.execute("SELECT review_id FROM next5000_quarantines").fetchone()[0], "id9")
            self.assertEqual(db.execute("SELECT charged_nusd FROM reservations").fetchone()[0], charge)
            self.assertEqual(recovery.recover(db)["new_accepted"], 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
from pipeline import state


def rec(rid, status="completed", lc="lc1", **extra):
    r = {"review_id": rid, "source_sha256": "s", "status": status, "label_config": lc}
    r.update(extra)
    return r


class RecordStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "records.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_last_line_wins_and_reload(self):
        s = state.RecordStore(self.path)
        s.upsert([rec("a", "quarantined", None, reason="x"), rec("b")])
        s.upsert([rec("a"), rec("c", lc="lc2"), rec("d", cache_source_id="b")])
        self.assertEqual(s.latest("a")["status"], "completed")
        self.assertEqual(s.completed_ids("lc1"), {"a", "b", "d"})
        self.assertEqual(s.completed_ids("lc2"), {"c"})
        self.assertEqual(s.meta("d"), ("completed", "lc1", True))
        s2 = state.RecordStore(self.path)
        self.assertEqual(s2.completed_ids("lc1"), {"a", "b", "d"})
        self.assertEqual(len(s2), 4)
        self.assertEqual(s2.count_by_status(), {"completed": 4})
        self.assertEqual(list(s2.all_latest(["d", "a", "zz"])), ["d", "a"])

    def test_torn_last_line_is_repaired(self):
        s = state.RecordStore(self.path)
        s.upsert([rec("a"), rec("b")])
        with self.path.open("a", encoding="utf-8") as f:
            f.write('{"review_id":"c","status":"compl')
        s2 = state.RecordStore(self.path)
        self.assertGreater(s2.torn_bytes_repaired, 0)
        self.assertEqual(s2.completed_ids(), {"a", "b"})
        s2.upsert([rec("c")])
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["review_id"] for l in lines], ["a", "b", "c"])

    def test_no_repair_mode_is_read_only(self):
        s = state.RecordStore(self.path)
        s.upsert([rec("a")])
        with self.path.open("a", encoding="utf-8") as f:
            f.write('{"review_id":"b"')
        before = self.path.read_bytes()
        s2 = state.RecordStore(self.path, repair=False)
        self.assertEqual(s2.completed_ids(), {"a"})
        self.assertEqual(self.path.read_bytes(), before)


class CallLogTests(unittest.TestCase):
    def test_request_ids_unique(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "calls.jsonl"
            log = state.CallLog(path)
            log.log({"request_id": "r1", "attempt": 1})
            log.log({"request_id": "r1", "attempt": 2})
            log.log_many([{"request_id": "r1", "attempt": 2}, {"request_id": None, "attempt": 1}])
            log2 = state.CallLog(path)
            log2.log({"request_id": "r1", "attempt": 1})
            ids = [json.loads(l)["request_id"] for l in path.read_text().splitlines()]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids[:2], ["r1", "r1#2"])
            self.assertTrue(ids[3].startswith("local-"))


class CheckpointTests(unittest.TestCase):
    def test_roundtrip_sorted_unique(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c" / "x-start.json"
            n = state.save_checkpoint(p, ["b", "a", "b"])
            self.assertEqual(n, 2)
            self.assertEqual(state.load_checkpoint(p), ["a", "b"])
            self.assertEqual(json.loads(p.read_text()), {"completed_ids": ["a", "b"]})

    def test_invocations(self):
        with tempfile.TemporaryDirectory() as d:
            state.append_invocation(d, {"invocation_id": "1"})
            state.append_invocation(d, {"invocation_id": "2"})
            self.assertEqual([x["invocation_id"] for x in state.read_invocations(d)], ["1", "2"])


if __name__ == "__main__":
    unittest.main()

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import recover_grouping_trail as r


def write_tsv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["ref", "topic", "evidence_quote", "review_text"])
        w.writerows(rows)


def write_labels(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ref", "issue_id", "confidence"])
        w.writerows(rows)


class RecoverGroupingTrailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.d = Path(self.tmp.name)
        (d / "private").mkdir()
        mapping, agent = {}, []
        for i in range(1, 9):
            (d / "work" / ("chunk%d" % i)).mkdir(parents=True)
            refs = ["M%05d" % (i * 10 + j) for j in range(3)]
            write_tsv(d / "work" / ("chunk%d" % i) / "batch_001.tsv",
                      [[x, "playback", "synthetic quote", "synthetic text " + x] for x in refs])
            write_labels(d / "work" / ("out_chunk%d.csv" % i), [[x, "PLY-FAIL", "high"] for x in refs])
            for x in refs:
                mapping[x] = "id-" + x
                agent.append(["id-" + x, "PLY-FAIL", "high"])
        (d / "work" / "verify").mkdir()
        vrefs = ["V%04d" % j for j in range(1, 7)]
        write_tsv(d / "work" / "verify" / "batch_001.tsv", [[x, "playback", "q", "synthetic"] for x in vrefs])
        targets = list(mapping.values())[:6]
        write_labels(d / "work" / "verify" / "labels.csv",
                     [[x, "PLY-FAIL" if j < 5 else "USE-ADS", "high"] for j, x in enumerate(vrefs)])
        with open(d / "agent_labels_v1.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["review_id", "agent_issue_id", "confidence"]); w.writerows(agent)
        (d / "private" / "key.json").write_text(json.dumps({"map": mapping, "verify": dict(zip(vrefs, targets)),
                                                           "frame_sha256": "f" * 64, "max_words": 150}))
        sha = hashlib.sha256((d / "agent_labels_v1.csv").read_bytes()).hexdigest()
        (d / "report_v1.json").write_text(json.dumps({"files_sha256": {"agent_labels_v1.csv": sha},
            "catalog_sha256": "c" * 64, "verifier": {"agreed": 5, "cases": 6}}))

    def test_recovers_reported_agreement_without_text_or_ids(self):
        result, cases = r.recover(self.d)
        v = result["verifier"]
        self.assertEqual((v["agreed"], v["cases"]), (5, 6))
        self.assertTrue(v["matches_reported_511_of_600"])
        self.assertTrue(v["inputs_hold_no_grouping_output"])
        self.assertTrue(v["refs_separate_from_grouping_refs"])
        self.assertEqual(result["grouping"]["records"], 24)
        self.assertEqual(result["grouping"]["outputs_match_assembled_agent_labels"], "24 of 24")
        blob = json.dumps([result, cases])
        self.assertNotIn("synthetic", blob)
        self.assertNotIn("id-M", blob)

    def test_changed_file_is_refused(self):
        with open(self.d / "agent_labels_v1.csv", "a") as f:
            f.write("id-extra,PLY-FAIL,high\n")
        with self.assertRaisesRegex(ValueError, "differs from the hash"):
            r.recover(self.d)


if __name__ == "__main__":
    unittest.main()

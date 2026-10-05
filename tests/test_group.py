from __future__ import annotations

import csv
import json
import re
import unittest

from tests import _paths  # noqa: F401
from tests.test_export import FakeChat, TempDirCase, build_fixture, calls_of, make_ctx
from pipeline import group
from pipeline.rowhash import TOPICS


def c(topic, text, entities=()):
    return group.classify_issue({"topic": topic, "entities": list(entities)}, text)[0]


class ThemeRules(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(c("playback", "App crashes on launch"), "playback.crash")
        self.assertEqual(c("playback", "keeps buffering on wifi"), "playback.connection")
        self.assertEqual(c("playback", "the sound quality is awful"), "playback.audio_quality")
        self.assertEqual(c("playback", "songs stop when the screen is off"), "playback.stops_pausing")
        self.assertEqual(c("playback", "won't play in my car via bluetooth"), "playback.devices")
        self.assertEqual(c("usability", "so many ads"), "usability.ads")
        self.assertEqual(c("usability", "a bad experience overall"), "usability.general")  # 'bad ' is not ads
        self.assertEqual(c("usability", "shuffle plays the same 10 songs"), "usability.shuffle_queue")
        self.assertEqual(c("access", "can't log in"), "access.login")
        self.assertEqual(c("access", "my account was hacked"), "access.account_security")
        self.assertEqual(c("billing", "charged twice, want a refund"), "billing.charge_refund")
        self.assertEqual(c("billing", "too expensive"), "billing.price")
        self.assertEqual(c("catalog", "song is not available in my country"), "catalog.missing_content")
        self.assertEqual(c("downloads", "downloads disappeared"), "downloads.disappearing")
        self.assertEqual(c("downloads", "", ["download"]), "downloads.download_failure")
        self.assertEqual(c("other", "terrible"), "other.general")
        self.assertEqual(c("nonsense", "terrible"), "other.general")

    def test_ids_are_lowercase_ascii_and_named(self):
        for topic, themes in group.theme_table().items():
            self.assertIn(topic, TOPICS)
            for theme in themes:
                iid = "%s.%s" % (topic, theme)
                self.assertRegex(iid, r"^[a-z_]+\.[a-z_]+$")
                name, desc = group.fallback_name(iid)
                self.assertTrue(name and desc)
        self.assertEqual(set(group.theme_table()), set(TOPICS))

    def test_select_quotes_deterministic_distinct(self):
        recs = {"a": {"evidence_quote": "same quote text here!!"}, "b": {"evidence_quote": "same quote text here!!"},
                "c": {"evidence_quote": "short"}, "d": {"evidence_quote": "another quote that is long enough"}}
        q1 = group.select_quotes(["a", "b", "c", "d"], recs, 5)
        q2 = group.select_quotes(["d", "c", "b", "a"], recs, 5)
        self.assertEqual(q1, q2)
        self.assertEqual(len(q1), 3)
        self.assertEqual(q1[-1]["quote"], "short")  # out-of-band length last

    def test_parse_names_validation(self):
        text = json.dumps({"issues": [{"issue_id": "a.x", "name": "A", "description": "d"},
                                      {"issue_id": "zz.unknown", "name": "Z"},
                                      {"issue_id": "b.y", "name": "B1"}, {"issue_id": "b.y", "name": "B2"},
                                      {"issue_id": "c.z", "name": ""}]})
        acc, rej = group.parse_names(text, ["a.x", "b.y", "c.z"])
        self.assertEqual(sorted(acc), ["a.x"])
        self.assertEqual(len(rej), 3)


class GroupRun(TempDirCase):
    def setUp(self):
        super().setUp()
        self.csv, self.run = build_fixture(self.tmp)

    def read_membership(self, run):
        with (run / "group" / "membership.csv").open(newline="") as f:
            return list(csv.reader(f))

    def test_membership_complete_sorted_and_model_independent(self):
        ctx = make_ctx(self.run, self.csv, FakeChat({"group": "dupes"}))
        summary = group.run(ctx)
        rows = self.read_membership(self.run)
        self.assertEqual(rows[0], ["issue_id", "review_id"])
        body = rows[1:]
        complaints = [r for r, rec in ctx.records.items()
                      if rec.get("status") == "completed" and rec["intent"] in ("complaint", "cancellation")]
        self.assertEqual(sorted(r for _, r in body), sorted(complaints))
        self.assertEqual(len({r for _, r in body}), len(body))  # exactly one issue each
        order = list(ctx.texts)
        self.assertEqual(body, sorted(body, key=lambda p: (p[0], order.index(p[1]))))
        self.assertIn(["usability.ads", "r04"], body)
        self.assertIn(["usability.ads", "r09"], body)  # cached copy counted separately
        # model output with duplicates: first issue rejected (dup) -> fallback name; unknown rejected
        issues = {i["issue_id"]: i for i in json.loads((self.run / "group" / "issues.json").read_text())}
        report = json.loads((self.run / "group" / "naming_report.json").read_text())
        self.assertTrue(any("unknown" in r for r in report["rejected"]))
        self.assertTrue(any("duplicate" in r for r in report["rejected"]))
        self.assertIn("fallback", {i["name_source"] for i in issues.values()})
        self.assertIn("model", {i["name_source"] for i in issues.values()})
        # one group call; review_ids = ids whose quotes were sent
        gcalls = calls_of(self.run, "group")
        self.assertEqual(len(gcalls), 1)
        pack = json.loads((self.run / "group" / "evidence_pack.json").read_text())
        self.assertEqual(sorted(gcalls[0]["review_ids"]),
                         sorted({q["review_id"] for i in pack["issues"] for q in i["quotes"]}))
        self.assertEqual(summary["issues"], len(issues))

        csv2, run2 = build_fixture(self.tmp / "garbage")
        group.run(make_ctx(run2, csv2, FakeChat({"group": "garbage"})))
        self.assertEqual(self.read_membership(run2), rows)
        self.assertEqual([c["outcome"] for c in calls_of(run2, "group")], ["failed", "failed"])
        issues2 = json.loads((run2 / "group" / "issues.json").read_text())
        self.assertTrue(all(i["name_source"] == "fallback" for i in issues2))

    def test_evidence_pack_bounds(self):
        ctx = make_ctx(self.run, self.csv, None, config={"group": {"max_issues": 2, "quotes_per_issue": 1}})
        group.run(ctx)
        pack = json.loads((self.run / "group" / "evidence_pack.json").read_text())
        self.assertEqual(len(pack["issues"]), 2)
        self.assertTrue(all(len(i["quotes"]) <= 1 for i in pack["issues"]))
        self.assertEqual(calls_of(self.run, "group"), [])  # no chat -> no call, fallback names

    def test_stage_cache_hit_and_miss(self):
        group.run(make_ctx(self.run, self.csv, FakeChat()))
        self.assertFalse(json.loads((self.run / "group" / "cache.json").read_text())["hit"])
        csv2, warm = build_fixture(self.tmp / "warm")
        chat = FakeChat()
        s = group.run(make_ctx(warm, csv2, chat, extras={"warm_from": self.run}))
        self.assertEqual(chat.n, 0)
        self.assertTrue(s["cache_hit"])
        self.assertEqual(calls_of(warm, "group"), [])
        cache = json.loads((warm / "group" / "cache.json").read_text())
        self.assertTrue(cache["hit"] and cache["source"].endswith("group/responses.jsonl"))
        names = {i["issue_id"]: i["name"] for i in json.loads((warm / "group" / "issues.json").read_text())}
        self.assertTrue(all(n.startswith("Named ") for n in names.values() if n))
        # changed input (r01 no longer a complaint -> counts/quotes change) -> miss
        from pipeline.io import append_jsonl
        recs = [json.loads(l) for l in (warm / "records.jsonl").read_text().splitlines()]
        r01 = [r for r in recs if r["review_id"] == "r01"][-1]
        append_jsonl(warm / "records.jsonl", dict(r01, intent="praise"))
        chat = FakeChat()
        group.run(make_ctx(warm, csv2, chat, extras={"warm_from": self.run}))
        self.assertEqual(chat.n, 1)


if __name__ == "__main__":
    unittest.main()

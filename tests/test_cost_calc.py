"""Tests for cost/cost_calc.py (offline cost and runtime calculator). Standard library only."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests import _paths  # noqa: F401  (puts src/ on sys.path)

ROOT = Path(__file__).resolve().parents[1]
COST = ROOT / "cost"
FIX = COST / "fixtures"
if str(COST) not in sys.path:
    sys.path.insert(0, str(COST))

import cost_calc as cc  # noqa: E402

RATE_HEADER = "provider,model,item,unit,price,currency,per,source_url,checked_on,notes\n"
# TEST-ONLY prices (not real): used to make every fixture item priced so arithmetic is fully known.
TEST_RATES = RATE_HEADER + "\n".join([
    "typesafe,jev-*,input_uncached,token,42,USD,1000000000,test,2026-10-06,test",
    "typesafe,jev-*,output,token,0,USD,1000000000,test,2026-10-06,test",
    "anthropic,claude-*,input_uncached,token,0.5,USD,1000000,test,2026-10-06,TEST ONLY",
    "anthropic,claude-*,input_cached,token,0.05,USD,1000000,test,2026-10-06,TEST ONLY",
    "anthropic,claude-*,output,token,2,USD,1000000,test,2026-10-06,TEST ONLY",
    "*,*,uncertain_charge,usd,1,USD,1,,,pass-through",
]) + "\n"
TEST_LOCAL = ("machine,scope,hours,power_watts,usd_per_kwh,fixed_usd,source,notes\n"
              "test host,wall,,30,0.25,0,test,TEST ONLY\n")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def rates_from(text: str, tmp: Path):
    return cc.load_rates(write(tmp / "rates.csv", text))


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def known_source(self) -> Path:
        """Copy of the synthetic evidence with every item priced and the timeout reconciled."""
        src = self.tmp / "evidence"
        src.mkdir()
        for name in cc.EVIDENCE_FILES:
            shutil.copy(FIX / name, src / name)
        rows = cc.read_usage_csv(src / "usage.csv")
        for r in rows:
            if r["item"] == "uncertain_charge":
                r["billed_units"] = "0.001"
        write(src / "usage.csv", cc.usage_csv_text(rows))
        write(src / "rates.csv", TEST_RATES)
        write(src / "local_compute.csv", TEST_LOCAL)
        return src


class ArithmeticTests(TempDirCase):
    def test_per_million_price_is_divided_first(self):
        rates = rates_from(RATE_HEADER + "p,m,input_uncached,token,0.5,USD,1000000,,,\n", self.tmp)
        row = {"request_id": "r", "run": "cold", "role": "verify", "provider": "p", "model": "m",
               "item": "input_uncached", "billed_units": "2000000", "unit": "token"}
        [c] = cc.cost_usage([row], rates)
        self.assertEqual(c["price_per_unit"], Decimal("0.0000005"))
        self.assertEqual(c["cost"], Decimal("1.0"))

    def test_per_billion_jev_rate(self):
        rates = cc.load_rates(COST / "rates.csv")
        r = cc.find_rate(rates, "typesafe", "jev-1.13.0", "input_uncached")
        self.assertEqual(cc.price_per_unit(r), Decimal("42") / Decimal("1000000000"))
        self.assertEqual(cc.price_per_unit(cc.find_rate(rates, "typesafe", "jev-1.13.0", "output")), 0)

    def test_cached_input_subtracted_before_uncached_rate(self):
        rates = rates_from(TEST_RATES, self.tmp)
        call = {"request_id": "x", "role": "memo", "provider": "anthropic", "model": "claude-haiku-4-5",
                "outcome": "succeeded", "input_tokens": 1000, "cached_input_tokens": 300, "output_tokens": 100}
        rows = {r["item"]: r for r in cc.usage_rows_for_call(call, "cold", rates)}
        self.assertEqual(rows["input_uncached"]["billed_units"], "700")
        self.assertEqual(rows["input_cached"]["billed_units"], "300")
        costed = {r["item"]: r["cost"] for r in cc.cost_usage(list(rows.values()), rates)}
        self.assertEqual(costed["input_uncached"], Decimal(700) * Decimal("0.5") / Decimal(10 ** 6))
        self.assertEqual(costed["input_cached"], Decimal(300) * Decimal("0.05") / Decimal(10 ** 6))
        total_in = sum(int(rows[k]["billed_units"]) for k in ("input_uncached", "input_cached"))
        self.assertEqual(total_in, 1000)   # mutually exclusive: no token billed twice

    def test_cached_greater_than_input_is_rejected(self):
        with self.assertRaises(cc.CalcError):
            cc.usage_rows_for_call({"request_id": "x", "input_tokens": 10, "cached_input_tokens": 11}, "cold", [])

    def test_reasoning_not_double_counted(self):
        call = {"request_id": "x", "role": "verify", "provider": "openrouter", "model": "deepseek/x",
                "input_tokens": 100, "output_tokens": 120, "reasoning_tokens": 40}
        rows = cc.usage_rows_for_call(call, "cold", [], reasoning_included=True)
        items = [r["item"] for r in rows]
        self.assertNotIn("reasoning", items)
        self.assertEqual(sum(int(r["billed_units"]) for r in rows if r["item"] == "output"), 120)
        rows2 = cc.usage_rows_for_call(call, "cold", [], reasoning_included=False)
        self.assertEqual([r["billed_units"] for r in rows2 if r["item"] == "reasoning"], ["40"])

    def test_optional_request_and_classification_items(self):
        rates = rates_from(RATE_HEADER + "p,m,request,request,0.01,USD,1,,,\np,m,classification,classification,0.001,USD,1,,,\n", self.tmp)
        call = {"request_id": "x", "provider": "p", "model": "m", "outcome": "succeeded",
                "review_ids": ["a", "b", "c"], "input_tokens": 0, "output_tokens": 0}
        rows = {r["item"]: r for r in cc.usage_rows_for_call(call, "cold", rates)}
        self.assertEqual(rows["request"]["billed_units"], "1")
        self.assertEqual(rows["classification"]["billed_units"], "3")
        total = sum(c["cost"] for c in cc.cost_usage(list(rows.values()), rates))
        self.assertEqual(total, Decimal("0.013"))

    def test_unit_mismatch_is_an_error(self):
        rates = rates_from(RATE_HEADER + "p,m,output,request,1,USD,1,,,\n", self.tmp)
        row = {"request_id": "r", "run": "cold", "role": "memo", "provider": "p", "model": "m",
               "item": "output", "billed_units": "5", "unit": "token"}
        with self.assertRaises(cc.CalcError):
            cc.cost_usage([row], rates)


class UnknownTests(TempDirCase):
    def test_blank_price_is_unknown_not_zero(self):
        rates = cc.load_rates(COST / "rates.csv")
        row = {"request_id": "r", "run": "cold", "role": "memo", "provider": "openrouter",
               "model": "deepseek/deepseek-v4.1-flash", "item": "output", "billed_units": "100", "unit": "token"}
        [c] = cc.cost_usage([row], rates)
        self.assertIsNone(c["cost"])
        self.assertIn("price blank", c["reason"])
        zero = dict(row, billed_units="0")
        self.assertEqual(cc.cost_usage([zero], rates)[0]["cost"], 0)

    def test_missing_units_and_missing_rate_are_unknown(self):
        row = {"request_id": "r", "run": "cold", "role": "memo", "provider": "nobody", "model": "m",
               "item": "output", "billed_units": "", "unit": "token"}
        self.assertIsNone(cc.cost_usage([row], [])[0]["cost"])
        self.assertIsNone(cc.cost_usage([dict(row, billed_units="5")], [])[0]["cost"])

    def test_amount_propagates_unknown(self):
        a = cc.Amount(Decimal("1.5")) + cc.Amount.of(None, "x")
        self.assertIsNone(a.value)
        self.assertEqual(a.known, Decimal("1.5"))
        self.assertIn("unknown", a.fmt())
        self.assertEqual(cc.Amount(Decimal(2)).scale(Decimal(3)).value, Decimal(6))

    def test_local_compute_unknown_when_power_blank(self):
        rows = cc.load_local_compute(COST / "local_compute.csv")
        amt, notes = cc.local_compute_cost(rows, 3600.0)
        self.assertIsNone(amt.value)
        amt2, _ = cc.local_compute_cost(cc.load_local_compute(write(self.tmp / "l.csv", TEST_LOCAL)), 3600.0)
        self.assertEqual(amt2.value, Decimal("1") * Decimal(30) / Decimal(1000) * Decimal("0.25"))

    def test_no_data_report(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        res = cc.replay(empty, out=self.tmp / "r.md")
        self.assertEqual(res["data_source"], "none")
        self.assertIn("No measured pilot yet", res["text"])
        for run in cc.RUNS:
            self.assertIsNone(res["measured"]["runs"][run]["api"].value)
        self.assertIn("PRE-PILOT ESTIMATE", res["text"])
        self.assertIn("660,622", res["text"])
        self.assertIn("484,189", res["text"])

    def test_blank_deepseek_rates_reported_as_unknown(self):
        res = cc.replay(FIX, out=self.tmp / "r.md")
        self.assertIn("rate(s) are blank and therefore **unknown**", res["text"])
        self.assertIsNone(res["measured"]["runs"]["cold"]["api"].value)


class InvariantTests(TempDirCase):
    def test_doubling_rates_doubles_api_and_keeps_time_and_local(self):
        src = self.known_source()
        r1 = cc.replay(src, out=self.tmp / "r1.md")
        r2 = cc.replay(src, out=self.tmp / "r2.md", rates_multiplier="2")
        for run in cc.RUNS:
            a1, a2 = r1["measured"]["runs"][run], r2["measured"]["runs"][run]
            self.assertIsNotNone(a1["api"].value, run)
            self.assertEqual(a2["api"].value, 2 * a1["api"].value)
            self.assertEqual(a1["wall_seconds"], a2["wall_seconds"])
            self.assertEqual(a1["local"].value, a2["local"].value)
            self.assertIsNotNone(a1["local"].value)
            for role in cc.ROLES:
                self.assertEqual(a1["roles"][role]["duration_ms_sum"], a2["roles"][role]["duration_ms_sum"])
        self.assertGreater(r1["measured"]["runs"]["cold"]["api"].value, 0)
        for sc in cc.SCENARIOS:
            v1 = r1["projection"]["scenarios"][sc]["variants"]["reuse"]
            v2 = r2["projection"]["scenarios"][sc]["variants"]["reuse"]
            self.assertEqual(v2["api"].value, 2 * v1["api"].value)
            self.assertEqual(v1["seconds"], v2["seconds"])
            self.assertEqual(v1["local"].value, v2["local"].value)

    def test_doubling_via_edited_rates_csv(self):
        src = self.known_source()
        r1 = cc.replay(src, out=self.tmp / "r1.md")
        doubled = []
        for line in TEST_RATES.splitlines():
            parts = line.split(",")
            if parts[0] != "provider":
                parts[4] = str(Decimal(parts[4]) * 2)
            doubled.append(",".join(parts))
        write(src / "rates.csv", "\n".join(doubled) + "\n")
        r2 = cc.replay(src, out=self.tmp / "r2.md")
        self.assertEqual(r2["measured"]["runs"]["cold"]["api"].value, 2 * r1["measured"]["runs"]["cold"]["api"].value)

    def test_projection_counts_do_not_change_measured_results(self):
        src = self.known_source()
        r1 = cc.replay(src, out=self.tmp / "r1.md")
        r2 = cc.replay(src, out=self.tmp / "r2.md", overrides=[
            "projection.distinct_nonempty_texts=1000", "projection.rows_nonempty=2000",
            "projection.rows_accounted=2013", "budget_usd=1", "retry_rate.base=0.5"])

        def measured_view(r):
            out = {}
            for run in cc.RUNS:
                m = r["measured"]["runs"][run]
                out[run] = (m["api"].value, m["wall_seconds"], json.dumps(m["records"], sort_keys=True),
                            m["local"].value, m["api_per_completed"].value,
                            tuple((role, m["roles"][role]["attempts"], m["roles"][role]["cost"].value) for role in cc.ROLES))
            return out
        self.assertEqual(measured_view(r1), measured_view(r2))
        self.assertNotEqual(r1["projection"]["scenarios"]["base"]["variants"]["reuse"]["api"].value,
                            r2["projection"]["scenarios"]["base"]["variants"]["reuse"]["api"].value)
        sec1 = r1["text"].split("## 2.")[0]
        sec2 = r2["text"].split("## 2.")[0]
        self.assertEqual(sec1.replace(str(self.tmp / "r1.md"), ""), sec2.replace(str(self.tmp / "r2.md"), ""))

    def test_fixed_overhead_counted_once_not_per_row(self):
        src = self.known_source()
        r1 = cc.replay(src, out=self.tmp / "r1.md")
        r2 = cc.replay(src, out=self.tmp / "r2.md", overrides=["projection.distinct_nonempty_texts=968378"])
        for role in cc.FIXED_ROLES:
            c1 = r1["projection"]["scenarios"]["base"]["variants"]["reuse"]["stages"][role]["cost"].value
            c2 = r2["projection"]["scenarios"]["base"]["variants"]["reuse"]["stages"][role]["cost"].value
            self.assertEqual(c1, c2)
            measured = r1["measured"]["runs"]["cold"]["roles"][role]["cost_succeeded"].value
            self.assertEqual(c1, measured * Decimal("1.05"))   # x fixed multiplier 1.0 x (1 + base retry 0.05)
        e1 = r1["projection"]["scenarios"]["base"]["variants"]["reuse"]["stages"]["enrich"]["cost"].value
        e2 = r2["projection"]["scenarios"]["base"]["variants"]["reuse"]["stages"]["enrich"]["cost"].value
        self.assertEqual(e2, 2 * e1)

    def test_report_is_deterministic(self):
        src = self.known_source()
        a = cc.replay(src, out=self.tmp / "a.md")["text"]
        b = cc.replay(src, out=self.tmp / "a.md")["text"]
        self.assertEqual(a, b)


class BudgetTests(TempDirCase):
    def test_budget_exceeded_warning(self):
        src = self.known_source()
        res = cc.replay(src, out=self.tmp / "r.md", overrides=["budget_usd=0.01"])
        self.assertIn("⚠ EXCEEDS BUDGET", res["text"])
        res2 = cc.replay(src, out=self.tmp / "r.md", overrides=["budget_usd=100000"])
        self.assertNotIn("EXCEEDS BUDGET", res2["text"])
        self.assertIn("within budget", res2["text"])

    def test_unknown_items_block_budget_confirmation(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        res = cc.replay(empty, out=self.tmp / "r.md")
        self.assertIn("CANNOT CONFIRM within budget", res["text"])

    def test_fallback_fraction_above_cap_warns(self):
        src = self.known_source()
        res = cc.replay(src, out=self.tmp / "r.md", overrides=["fallback_fraction.conservative=0.1"])
        self.assertTrue(any("max_fallback_fraction" in w for w in res["projection"]["warnings"]))
        self.assertEqual(res["projection"]["scenarios"]["conservative"]["fallback_fraction"], 0.0)

    def test_output_cap_exceeded_warns(self):
        src = self.known_source()
        res = cc.replay(src, out=self.tmp / "r.md", overrides=["output_token_cap.memo=10"])
        self.assertTrue(any("memo: observed output" in w for w in res["projection"]["warnings"]))


class CollectTests(TempDirCase):
    def collect_fixture(self, out: Path, **kw):
        args = dict(cold_dir=FIX / "runs" / "pilot-cold", warm_dir=FIX / "runs" / "pilot-warm",
                    csv_path=FIX / "cost_10_synthetic.csv", out_dir=out,
                    manifest=FIX / "manifest_synthetic.json", expect_rows=10)
        args.update(kw)
        return cc.collect(**args)

    def test_collect_matches_committed_fixture_outputs(self):
        out = self.tmp / "out"
        t = self.collect_fixture(out)
        self.assertEqual(t["provenance"]["data_source"], "synthetic")
        for name in cc.EVIDENCE_FILES:
            self.assertEqual((out / name).read_text(encoding="utf-8"), (FIX / name).read_text(encoding="utf-8"), name)

    def test_collect_records_calls_usage(self):
        from pipeline.rowhash import row_sha
        out = self.tmp / "out"
        self.collect_fixture(out)
        with (FIX / "cost_10_synthetic.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        recs = cc.read_jsonl(out / "pilot_records.jsonl")
        self.assertEqual([r["review_id"] for r in recs], [r["review_id"] for r in rows])
        for rec, row in zip(recs, rows):
            self.assertEqual(rec["source_sha256"], row_sha(row))
            self.assertEqual(rec["source_sha256"], cc.row_sha(row))
        self.assertEqual(recs[3].get("cache_source_id"), "syn-002")
        self.assertEqual(recs[9]["reason"], "empty_review_text")
        calls = cc.read_jsonl(out / "pilot_calls.jsonl")
        self.assertEqual(len(calls), 8)
        self.assertEqual({c["run"] for c in calls}, {"cold", "warm"})
        self.assertTrue(all(c.get("run_id") for c in calls))
        self.assertEqual(len({c["request_id"] for c in calls}), len(calls))
        raw = (out / "pilot_calls.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("FAKE-KEY", raw)
        self.assertNotIn("api_key", raw)
        self.assertEqual([c for c in calls if c["run"] == "warm" and c["role"] == "enrich"], [])
        usage = cc.read_usage_csv(out / "usage.csv")
        call_keys = {(c["run"], c["request_id"]) for c in calls}
        self.assertTrue(all((u["run"], u["request_id"]) in call_keys for u in usage))
        unc = [u for u in usage if u["item"] == "uncertain_charge"]
        self.assertEqual(len(unc), 1)
        self.assertEqual(unc[0]["billed_units"], "")
        timing = json.loads((out / "pilot_timing.json").read_text(encoding="utf-8"))
        self.assertEqual(timing["runs"]["cold"]["wall_seconds"], 87.5)
        self.assertEqual(timing["runs"]["warm"]["records"]["cache_hits"], 9)
        self.assertEqual(timing["runs"]["cold"]["records"]["cache_hits"], 1)

    def test_checksum_mismatch_rejected(self):
        bad = self.tmp / "cost_10_synthetic.csv"
        bad.write_bytes((FIX / "cost_10_synthetic.csv").read_bytes() + b"\n")
        with self.assertRaisesRegex(cc.CalcError, "checksum mismatch"):
            self.collect_fixture(self.tmp / "out", csv_path=bad, manifest_key="cost_10_synthetic.csv")

    def test_id_mismatch_rejected(self):
        lines = (FIX / "cost_10_synthetic.csv").read_bytes().split(b"\n")
        data = b"\n".join(lines[:-2]) + b"\n"   # drop the last data row (syn-010)
        p = self.tmp / "cost_9.csv"
        p.write_bytes(data)
        man = write(self.tmp / "m.json", json.dumps({"files": {"cost_9.csv": {"sha256": hashlib.sha256(data).hexdigest()}}}))
        with self.assertRaisesRegex(cc.CalcError, "not in the CSV"):
            self.collect_fixture(self.tmp / "out", csv_path=p, manifest=man, expect_rows=9)
        with self.assertRaisesRegex(cc.CalcError, "expected 10"):
            self.collect_fixture(self.tmp / "out", csv_path=p, manifest=man, expect_rows=10)

    def test_real_manifest_has_cost_100_entry(self):
        m = json.loads(cc.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(m["files"]["cost_100.csv"]["sha256"],
                         "c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e")

    def test_replay_csv_recheck(self):
        res = cc.replay(FIX, out=self.tmp / "r.md", csv_path=FIX / "cost_10_synthetic.csv",
                        manifest=FIX / "manifest_synthetic.json")
        self.assertEqual(res["data_source"], "synthetic")

    def test_dry_run_is_not_measured(self):
        runs = self.tmp / "runs"
        shutil.copytree(FIX / "runs", runs)
        for d in ("pilot-cold", "pilot-warm"):
            cfg = json.loads((runs / d / "run_config.json").read_text(encoding="utf-8"))
            cfg.pop("synthetic"); cfg.pop("SYNTHETIC"); cfg["dry_run"] = True
            write(runs / d / "run_config.json", json.dumps(cfg))
        t = self.collect_fixture(self.tmp / "out", cold_dir=runs / "pilot-cold", warm_dir=runs / "pilot-warm")
        self.assertEqual(t["provenance"]["data_source"], "dry_run")
        res = cc.replay(self.tmp / "out", out=self.tmp / "r.md")
        self.assertIn("DRY-RUN", res["text"])
        self.assertNotIn("Data source: MEASURED", res["text"])


class SafetyTests(TempDirCase):
    def test_fixture_replay_is_labelled_synthetic(self):
        res = cc.replay(FIX, out=self.tmp / "r.md")
        self.assertEqual(res["data_source"], "synthetic")
        self.assertIn("SYNTHETIC FIXTURE DATA — NOT A MEASURED PILOT", res["text"])
        self.assertNotIn("Measured 100-review pilot (cold vs warm)", res["text"])

    def test_fixture_path_forces_synthetic_even_if_provenance_edited(self):
        shadow = FIX / "_tmp_shadow_for_test"
        try:
            shadow.mkdir()
            for name in cc.EVIDENCE_FILES:
                shutil.copy(FIX / name, shadow / name)
            t = json.loads((shadow / "pilot_timing.json").read_text(encoding="utf-8"))
            t["provenance"]["data_source"] = "measured"
            write(shadow / "pilot_timing.json", json.dumps(t))
            res = cc.replay(shadow, out=self.tmp / "r.md")
            self.assertEqual(res["data_source"], "synthetic")
        finally:
            shutil.rmtree(shadow, ignore_errors=True)

    def test_scrub_removes_keys(self):
        d = {"api_key": "x", "Authorization": "Bearer abcdefghijkl", "api_key_env": "TYPESAFE_API_KEY",
             "error": "failed with key sk-abcdefghijklmnopqrstuvwxyz", "input_tokens": 5}
        s = cc.scrub(d)
        self.assertNotIn("api_key", s)
        self.assertNotIn("Authorization", s)
        self.assertEqual(s["api_key_env"], "TYPESAFE_API_KEY")
        self.assertEqual(s["input_tokens"], 5)
        self.assertNotIn("sk-abc", s["error"])

    def test_import_and_replay_make_no_network_calls(self):
        code = r"""
import socket, sys
def boom(*a, **k):
    raise RuntimeError("network access attempted")
socket.socket = boom
socket.create_connection = boom
socket.getaddrinfo = boom
sys.path.insert(0, sys.argv[1])
import cost_calc
assert not any(m == "labelling" or m.startswith("labelling.") for m in sys.modules), "imported src/labelling"
rc = cost_calc.main(["replay", "--source", sys.argv[2], "--out", sys.argv[3] + "/a.md"])
assert rc == 0, rc
rc = cost_calc.main(["replay", "--source", sys.argv[3], "--out", sys.argv[3] + "/b.md", "--rates-multiplier", "2"])
assert rc == 0, rc
print("ok")
"""
        r = subprocess.run([sys.executable, "-c", code, str(COST), str(FIX), str(self.tmp)],
                           capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("ok", r.stdout)
        self.assertIn("SYNTHETIC", r.stdout)

    def test_source_does_not_reference_provider_clients(self):
        text = (COST / "cost_calc.py").read_text(encoding="utf-8")
        for bad in ("import labelling", "from labelling", "urllib", "http.client", "import requests", "import socket"):
            self.assertNotIn(bad, text)

    def test_cli_default_and_fixture_commands(self):
        out = self.tmp / "cli.md"
        r = subprocess.run([sys.executable, str(COST / "cost_calc.py"), "replay", "--source", str(FIX), "--out", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SYNTHETIC FIXTURE DATA", r.stdout)
        self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()

import csv
import json
from pathlib import Path
import tempfile
import unittest

from tools import cost100_harness as h


class FakeBudget:
    def __init__(self): self.events=[]
    def reserve(self,*a): self.events.append(("reserve",)+a)
    def settle(self,*a): self.events.append(("settle",)+a)
    def uncertain(self,*a): self.events.append(("uncertain",)+a)
    def cancel_unsent(self,*a): self.events.append(("cancel",)+a)


class Cost100HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/"source.csv"
        with self.source.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(h.SOURCE_FIELDS)
            for i in range(100):
                w.writerow(("synthetic-%03d"%i,"synthetic complaint %03d"%i,
                            "1","0","1.0","2026-01-01"))
        self.db=h.open_run(Path(self.tmp.name)/"private",str(self.source),h.bound())
        self.addCleanup(self.db.close)

    def test_source_identity_and_bound(self):
        self.assertEqual(len(h.rows(self.db)),100)
        self.assertEqual(h.bound(),362758144)
        self.assertEqual((Path(self.tmp.name)/"private/pilot.db").stat().st_mode&0o777,0o600)
        self.assertEqual(len(h.selected_verify(h.file_sha256(str(self.source)),h.rows(self.db))),10)
        group=h.openrouter_request("group",[{"review_id":"synthetic-000"}],"synthetic")
        enum=group["response_format"]["json_schema"]["schema"]["properties"]["results"]["items"]["properties"]["issue_id"]["enum"]
        self.assertEqual(len(enum),42)
        self.assertIn("abstain",enum)
        with self.assertRaisesRegex(ValueError,"numeric claim mismatch"):
            h.check_memo_claims([{"issue_id":"PLY-FAIL","complaint_count":2}],
                {"recommendation":"synthetic","referenced_claims":[{"issue_id":"PLY-FAIL",
                    "metric":"complaint_count","value":3}]})

    def test_atomic_reserve_and_saved_checkpoint(self):
        old=h.SHARED_BUDGET;fake=FakeBudget();h.SHARED_BUDGET=fake
        self.addCleanup(setattr,h,"SHARED_BUDGET",old)
        value=h.paid(self.db,"synthetic:one","verify",{"synthetic":1},100,200,
                     lambda request:{"ok":True},lambda response:({"ok":True},1,1,10))
        self.assertTrue(value["ok"])
        self.assertEqual([e[0] for e in fake.events],["reserve","settle"])
        with self.assertRaisesRegex(ValueError,"already recorded"):
            h.paid(self.db,"synthetic:one","verify",{},100,200,lambda q:None,lambda q:None)
        h.save_output(self.db,"enrich_evidence","synthetic-000",{"quote":"synthetic"},"a")
        h.checkpoint(self.db,Path(self.tmp.name)/"private","checkpoint_before")
        x=json.loads((Path(self.tmp.name)/"private/checkpoint_before.json").read_text())
        self.assertEqual(len(x["completed_ids"]),1)

    def test_unresolved_call_keeps_reservation(self):
        old=h.SHARED_BUDGET;fake=FakeBudget();h.SHARED_BUDGET=fake
        self.addCleanup(setattr,h,"SHARED_BUDGET",old)
        with self.assertRaisesRegex(ValueError,"uncertain"):
            h.paid(self.db,"synthetic:bad","verify",{},100,200,
                   lambda q: (_ for _ in ()).throw(TimeoutError()),lambda q:None)
        self.assertEqual([e[0] for e in fake.events],["reserve","uncertain"])
        self.assertEqual(h.exposure(self.db),100)

    def test_interruption_after_dispatch_blocks_duplicate(self):
        old=h.SHARED_BUDGET;fake=FakeBudget();h.SHARED_BUDGET=fake
        self.addCleanup(setattr,h,"SHARED_BUDGET",old)
        with self.assertRaises(KeyboardInterrupt):
            h.paid(self.db,"synthetic:interrupted","verify",{},100,200,
                   lambda q: (_ for _ in ()).throw(KeyboardInterrupt()),lambda q:None)
        self.assertEqual([e[0] for e in fake.events],["reserve"])
        self.assertEqual(self.db.execute("select status from calls").fetchone()[0],"reserved")
        with self.assertRaisesRegex(ValueError,"already recorded"):
            h.paid(self.db,"synthetic:interrupted","verify",{},100,200,lambda q:None,lambda q:None)

    def test_warm_replays_saved_outputs_without_calls(self):
        all_rows=h.rows(self.db)
        for r in all_rows:
            h.save_output(self.db,"enrich_label",r["review_id"],
                          {"topic":"other","intent":"praise","severity":1,
                           "sentiment":0.5,"needs_review":False},
                          h.digest(h.build_request(r["review_text"])))
        for offset in range(0,100,25):
            chunk=all_rows[offset:offset+25]
            items=[{"review_id":r["review_id"],"review_text":r["review_text"],
                "source_sha256":h.row_sha256([r[k] for k in h.SOURCE_FIELDS]),
                "labels":h.output(self.db,"enrich_label",r["review_id"])} for r in chunk]
            request_sha=h.digest(h.evidence.payload(items))
            for r in chunk:
                h.save_output(self.db,"enrich_evidence",r["review_id"],
                              {"evidence_quote":r["review_text"],"entities":[]},request_sha)
        sample=h.selected_verify(h.file_sha256(str(self.source)),all_rows)
        h.save_output(self.db,"verify","seeded10",
                      [{"review_id":r["review_id"]} for r in sample],"synthetic")
        ranking=h.compute_ranking(self.db,all_rows)
        h.save_output(self.db,"rank","baseline",ranking,"synthetic")
        h.save_output(self.db,"memo","baseline",
                      {"recommendation":"synthetic","referenced_claims":[]},"synthetic")
        h.warm(self.db)
        self.assertEqual(self.db.execute("select count(*) from calls").fetchone()[0],0)
        self.assertEqual(self.db.execute("select count(*) from events where phase='warm'").fetchone()[0],1)
        report=h.replay(self.db,Path(self.tmp.name)/"private")
        self.assertEqual(report["completed"],100)
        self.assertEqual(report["recomputed_api_nusd"],0)
        with (Path(self.tmp.name)/"private/pilot_records.jsonl").open() as f:
            self.assertEqual(sum(1 for _ in f),100)
        self.db.execute("update outputs set input_sha='wrong' where stage='enrich_label' and key='synthetic-000'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError,"warm label cache input differs"):
            h.warm(self.db,record=False)

    def test_mock_full_pipeline_pause_resume_blind_verify(self):
        old_budget=h.SHARED_BUDGET;budget=FakeBudget();h.SHARED_BUDGET=budget
        self.addCleanup(setattr,h,"SHARED_BUDGET",old_budget)
        old_jev=h.post_systemone;old_or=h.openrouter.request_json
        self.addCleanup(setattr,h,"post_systemone",old_jev)
        self.addCleanup(setattr,h.openrouter,"request_json",old_or)
        observed={"jev":0,"evidence":0,"verify":0,"group":0,"memo":0}
        def jev(request,key):
            observed["jev"]+=1
            return {"model":h.JEV_MODEL,"answers":{
                "topic":{"type":"choice","choice":"playback","confidence":.9},
                "intent":{"type":"choice","choice":"complaint","confidence":.9},
                "severity":{"type":"choice","choice":"3","confidence":.9},
                "sentiment":{"type":"score","score":1.0,"confidence":.9}},
                "usage":{"input_tokens":410,"output_tokens":40}}
        def openrouter(request_url,request,key):
            name=request["response_format"]["json_schema"]["name"]
            items=json.loads(request["messages"][0]["content"].split("\n")[-1])
            if name.startswith("spotify_exact_evidence_25"):
                observed["evidence"]+=1
                vals=[{"review_id":x["review_id"],"entities":[],
                       "evidence_quote":"synthetic complaint"} for x in items]
            elif name=="cost100_verify":
                observed["verify"]+=1
                self.assertTrue(all(set(x)=={"review_id","review_text"} for x in items))
                self.assertNotIn("enrich_label",request["messages"][0]["content"])
                vals=[{"review_id":x["review_id"],"topic":"playback",
                       "intent":"complaint","severity":3} for x in items]
            elif name=="cost100_group":
                observed["group"]+=1
                vals=[{"review_id":x["review_id"],"issue_id":"PLY-FAIL"} for x in items]
            else:
                observed["memo"]+=1
                vals=[{"recommendation":"Review playback failures before a product change.",
                       "referenced_claims":[{"issue_id":"PLY-FAIL",
                           "metric":"complaint_count","value":100}]}]
            return {"id":"synthetic-response","model":h.MODEL,"provider":"DeepInfra",
                "usage":{"prompt_tokens":100,"completion_tokens":100,
                         "completion_tokens_details":{"reasoning_tokens":0}},
                "choices":[{"finish_reason":"stop","message":{"content":json.dumps({"results":vals})}}]}
        h.post_systemone=jev;h.openrouter.request_json=openrouter
        h.execute(self.db,str(self.source),h.bound(),"synthetic-key","synthetic-key","label")
        h.checkpoint(self.db,Path(self.tmp.name)/"private","checkpoint_before")
        before=json.loads((Path(self.tmp.name)/"private/checkpoint_before.json").read_text())
        self.assertEqual(len(before["completed_ids"]),0)
        self.assertEqual(observed["verify"],0)
        h.execute(self.db,str(self.source),h.bound(),"synthetic-key","synthetic-key")
        h.checkpoint(self.db,Path(self.tmp.name)/"private","checkpoint_after")
        after=json.loads((Path(self.tmp.name)/"private/checkpoint_after.json").read_text())
        self.assertEqual(observed,{"jev":100,"evidence":4,"verify":1,"group":10,"memo":1})
        self.assertEqual(len(after["completed_ids"]),100)
        self.assertGreater(after["output_counts"].get("group",0),0)
        h.warm(self.db)
        self.assertEqual(observed,{"jev":100,"evidence":4,"verify":1,"group":10,"memo":1})
        cold=h.replay(self.db,Path(self.tmp.name)/"private")
        doubled=h.replay(self.db,Path(self.tmp.name)/"private",h.Decimal(2))
        self.assertEqual(doubled["recomputed_api_nusd"],2*cold["recomputed_api_nusd"])
        self.assertEqual(doubled["warm_seconds"],cold["warm_seconds"])

    def test_metered_partial_batch_quarantines_and_blocks_retry(self):
        for r in h.rows(self.db):
            h.save_output(self.db,"enrich_label",r["review_id"],
                {"topic":"playback","intent":"complaint","severity":3,
                 "sentiment":-.5,"needs_review":False},"synthetic")
        old_budget=h.SHARED_BUDGET;h.SHARED_BUDGET=FakeBudget()
        self.addCleanup(setattr,h,"SHARED_BUDGET",old_budget)
        old_or=h.openrouter.request_json
        self.addCleanup(setattr,h.openrouter,"request_json",old_or)
        def partial(url,request,key):
            items=json.loads(request["messages"][0]["content"].split("\n")[-1])
            vals=[{"review_id":x["review_id"],"entities":[],
                   "evidence_quote":"not in source" if i==0 else "synthetic complaint"}
                  for i,x in enumerate(items)]
            return {"id":"synthetic-partial","model":h.MODEL,"provider":"DeepInfra",
                "usage":{"prompt_tokens":100,"completion_tokens":100,
                         "completion_tokens_details":{"reasoning_tokens":0}},
                "choices":[{"finish_reason":"stop","message":{"content":json.dumps({"results":vals})}}]}
        h.openrouter.request_json=partial
        with self.assertRaisesRegex(ValueError,"partial batch"):
            h.execute(self.db,str(self.source),h.bound(),"unused","synthetic-key","evidence")
        self.assertEqual(self.db.execute("select status from calls").fetchone()[0],"quarantined_metered")
        self.assertEqual(self.db.execute("select count(*) from outputs where stage='enrich_evidence'").fetchone()[0],24)
        self.assertEqual(self.db.execute("select count(*) from outputs where stage='quarantine_evidence'").fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,"partial batch"):
            h.execute(self.db,str(self.source),h.bound(),"unused","synthetic-key","evidence")
        self.assertEqual(self.db.execute("select count(*) from calls where key='evidence:000'").fetchone()[0],1)
        self.assertEqual(self.db.execute("select count(*) from calls where key='evidence:025'").fetchone()[0],1)


if __name__=="__main__":unittest.main()

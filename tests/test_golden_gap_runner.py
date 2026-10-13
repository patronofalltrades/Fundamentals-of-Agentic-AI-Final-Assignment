"""Synthetic, offline safety checks for the one-attempt golden gap runner."""
import json
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from tools import golden_gap_runner as gap


class FakeBudget:
    def __init__(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('''CREATE TABLE reservations(request_key TEXT PRIMARY KEY,
            budget TEXT,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER)''')
        gap.init_tables(self.db)
    def exposure(self,budget):
        return 0
    def reserve(self,key,budget,amount,record=None):
        with self.db:
            self.db.execute("INSERT INTO reservations VALUES (?,?, 'reserved',?,NULL)",(key,budget,amount))
            if record:record(self.db)
    def settle(self,key,status,charge,record=None):
        with self.db:
            row=self.db.execute('SELECT status,reserved_nusd FROM reservations WHERE request_key=?',(key,)).fetchone()
            if row is None or row[0]!='reserved' or charge>row[1]:raise ValueError('invalid settlement')
            self.db.execute('UPDATE reservations SET status=?,charged_nusd=? WHERE request_key=?',(status,charge,key))
            if record:record(self.db)
    def uncertain(self,key,record=None):
        with self.db:
            self.db.execute("UPDATE reservations SET status='uncertain' WHERE request_key=? AND status='reserved'",(key,))
            if record:record(self.db)


class GoldenGapSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.out=patch.object(gap,'OUT',Path(self.tmp.name));self.out.start()
        self.addCleanup(self.out.stop)
        self.addCleanup(self.tmp.cleanup)
        self.b=FakeBudget()
        self.row={'review_id':'synthetic-one','source_sha256':'0'*64}

    @unittest.skipUnless(gap.PLAN.exists(), 'needs the private golden-gap plan in local/ (not in Git)')
    def test_pinned_source_and_cache_provenance(self):
        plan,source=gap.load_plan()
        self.assertEqual((len(plan['rows']),len(source)),(41,50))
        gap.cache_import(self.b,plan,source)
        self.assertEqual(self.b.db.execute('SELECT COUNT(*) FROM golden_gap_labels').fetchone()[0],5)
        self.assertEqual(self.b.db.execute('SELECT COUNT(*) FROM golden_gap_evidence').fetchone()[0],4)
        self.assertEqual(self.b.db.execute("SELECT COUNT(*) FROM golden_gap_labels WHERE provenance='exact_text_cache' AND origin_id IS NOT NULL").fetchone()[0],4)

    def test_ambiguous_dispatch_holds_and_never_retries(self):
        n=[]
        def broken(*_):n.append(1);raise TimeoutError()
        with self.assertRaises(TimeoutError):gap.call_once(self.b,'jev',[self.row],{},'fake',broken)
        self.assertEqual(len(n),1)
        self.assertEqual(self.b.db.execute('SELECT status FROM reservations').fetchone()[0],'uncertain')
        with self.assertRaises(ValueError):gap.call_once(self.b,'jev',[self.row],{},'fake',broken)
        self.assertEqual(len(n),1)

    def test_crash_after_reservation_is_not_replayed(self):
        key=gap.PREFIX+'jev-'+__import__('hashlib').sha256(json.dumps([self.row['review_id']]).encode()).hexdigest()
        self.b.reserve(key,'jev',gap.RESERVATION_NANODOLLARS,
            lambda db:db.execute("INSERT INTO golden_gap_calls VALUES (?,?,'reserved',?,NULL,NULL)",(key,'jev',json.dumps([self.row['review_id']]))))
        called=[]
        with self.assertRaises(ValueError):gap.call_once(self.b,'jev',[self.row],{},'fake',lambda *_:called.append(1))
        self.assertEqual(called,[])

    def test_success_settles_once_with_measured_usage(self):
        labels=SimpleNamespace(input_tokens=100,output_tokens=10,topic='usability',
            intent='complaint',severity=3,sentiment=-1.0,needs_review=False,
            confidence={'topic':1.0})
        with patch.object(gap.jev,'parse_response',return_value=labels):
            gap.call_once(self.b,'jev',[self.row],{},'fake',lambda *_:{'model':'synthetic'})
        self.assertEqual(self.b.db.execute('SELECT status FROM reservations').fetchone()[0],'succeeded')
        self.assertEqual(self.b.db.execute('SELECT COUNT(*) FROM golden_gap_labels').fetchone()[0],1)
        with self.assertRaises(ValueError):
            gap.call_once(self.b,'jev',[self.row],{},'fake',lambda *_:self.fail('replayed'))

    @unittest.skipUnless(gap.PLAN.exists(), 'needs the private golden-gap plan in local/ (not in Git)')
    def test_scope_and_incremental_cap(self):
        plan,_=gap.load_plan()
        work=[r for r in plan['rows'] if r['action']!='reuse_saved']
        self.assertEqual((len(work[:25]),len(work[25:])),(25,12))
        self.assertEqual(36*gap.RESERVATION_NANODOLLARS+2*gap.evidence.reservation_nusd(),110645248)
        self.b.db.execute("INSERT INTO reservations VALUES (?,?,'uncertain',?,NULL)",
            (gap.PREFIX+'held','jev',gap.MAX_INCREMENT_NUSD))
        with self.assertRaises(ValueError):gap.exposure_check(self.b,1)

    def test_one_named_retry_has_new_key_and_no_second_attempt(self):
        self.b.db.execute("INSERT INTO reservations VALUES (?,?,'uncertain',?,NULL)",
            (gap.PREFIX+'prior','openrouter',gap.evidence.reservation_nusd()))
        with patch.object(gap.evidence,'measured_usage',return_value=(10,10,0,100)), \
             patch.object(gap.evidence,'inspect',return_value=({'synthetic-one':
                {'entities':[],'evidence_quote':'synthetic'}},{})):
            gap.call_once(self.b,'evidence',[self.row],{},'fake',lambda *_:{},
                attempt_tag='approved-uncertain-retry-1')
            with self.assertRaises(ValueError):
                gap.call_once(self.b,'evidence',[self.row],{},'fake',
                    lambda *_:self.fail('second retry'),attempt_tag='approved-uncertain-retry-1')
        self.assertEqual(self.b.db.execute("SELECT status FROM reservations WHERE request_key=?",
            (gap.PREFIX+'prior',)).fetchone()[0],'uncertain')


if __name__=='__main__':unittest.main()

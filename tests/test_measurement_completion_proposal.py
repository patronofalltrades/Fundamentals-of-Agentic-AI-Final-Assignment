"""Offline synthetic scope and ledger checks for a proposal with no execute path."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tests.test_bounded_gap_followup import synthetic_calls
from tools import gap_closure_eval as g
from tools import prepare_measurement_completion as p


class CompletionProposalTests(unittest.TestCase):
    def setUp(self):
        self.calls = synthetic_calls()[:3]
        group = self.calls[2][3]
        content = group['messages'][0]['content']
        instruction, payload = content.rsplit('\n', 1)
        items = json.loads(payload)
        for item in items:
            item.update(labels={'topic': 'playback', 'intent': 'complaint', 'severity': 3}, evidence_quote='Synthetic')
        group['messages'][0]['content'] = instruction + '\n' + g.canon(items)
        self.plan = {'verify_ids': self.calls[0][2] + self.calls[1][2], 'group_ids': self.calls[2][2]}
        self.text = {r: 'Synthetic review' for r in self.plan['verify_ids'] + self.plan['group_ids']}
        self.values = {'verify': {}, 'group': {}}

    def pending(self):
        with patch.object(g, 'build_calls', return_value=self.calls):
            return p.pending_calls(self.plan, self.text, self.values)

    def test_only_three_missing_batches_with_new_identity_schemas(self):
        before = copy.deepcopy(self.calls)
        rows = self.pending()
        self.assertEqual([r['role'] for r in rows], ['verify', 'verify', 'group'])
        self.assertEqual(self.calls, before)
        for row, original in zip(rows, self.calls):
            self.assertNotEqual(row['request_sha256'], g.digest(original[3]))
            self.assertEqual(row['request_sha256'], g.digest(row['request']))

    def test_changed_coverage_overlap_and_missing_text_fail_closed(self):
        self.values['verify'][self.plan['verify_ids'][0]] = {}
        with self.assertRaisesRegex(ValueError, 'coverage changed'): self.pending()
        self.values['verify'].clear()
        self.plan['group_ids'][0] = self.plan['verify_ids'][0]
        with self.assertRaisesRegex(ValueError, 'distinct original IDs'): self.pending()

    def test_blind_verifier_rejects_machine_claims(self):
        req = self.calls[0][3]
        instruction, payload = req['messages'][0]['content'].rsplit('\n', 1)
        items = json.loads(payload); items[0]['claimed'] = {'topic': 'synthetic'}
        req['messages'][0]['content'] = instruction + '\n' + g.canon(items)
        with self.assertRaisesRegex(ValueError, 'source fields only'): self.pending()

    def test_reservation_holds_and_legacy_exposure_stay_in_headroom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.db'
            with sqlite3.connect(path) as c:
                c.executescript('CREATE TABLE caps(budget TEXT,cap_nusd INTEGER); CREATE TABLE legacy_sources(name TEXT,budget TEXT,exposure_nusd INTEGER,state_sha TEXT); CREATE TABLE reservations(request_key TEXT,budget TEXT,status TEXT,reserved_nusd INTEGER,charged_nusd INTEGER);')
                c.executemany('INSERT INTO caps VALUES(?,?)', [('openrouter', 5000000000), ('jev', 5000000000)])
                c.execute("INSERT INTO legacy_sources VALUES('synthetic','openrouter',100,'hash')")
                c.executemany('INSERT INTO reservations VALUES(?,?,?,?,?)', [('a','openrouter','uncertain',200,None), ('b','openrouter','quarantined_metered',400,10)])
            before = path.read_bytes()
            result = p.ledger_snapshot(path)
            self.assertEqual(result['exposure_nusd']['openrouter'], 310)
            self.assertEqual(result['reservation_holds']['openrouter'], {'attempts': 1, 'held_nusd': 200})
            self.assertEqual(before, path.read_bytes())
            with sqlite3.connect(path) as c:
                c.execute("UPDATE reservations SET reserved_nusd=4999999999 WHERE request_key='a'")
            with self.assertRaisesRegex(ValueError, 'headroom'): p.ledger_snapshot(path)


if __name__ == '__main__':
    unittest.main()

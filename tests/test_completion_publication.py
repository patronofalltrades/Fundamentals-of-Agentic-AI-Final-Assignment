"""Aggregate-only completion checks; human answers and original texts stay private."""
import copy
import json
import unittest

from tools import build_eval_registry as r
from tools import build_completion_publication as p


class CompletionPublicationTests(unittest.TestCase):
    def setUp(self):
        self.completion = json.loads((r.ROOT / r.COMPLETION).read_text())
        self.followup = json.loads((r.ROOT / r.FOLLOWUP).read_text())
        self.measured = json.loads((r.ROOT / r.MEASUREMENT).read_text())
        self.gap = json.loads((r.ROOT / r.GAP).read_text())

    def items(self):
        items = r.gap_closure(self.gap, self.measured)
        items += r.operational_measurements(json.loads((r.ROOT / r.COST_PILOT).read_text()),
                                           json.loads((r.ROOT / r.FULL_WARM).read_text()), self.measured)
        r.apply_followup(items, self.followup, self.measured)
        return items

    def test_complete_coverage_is_not_perfect_agreement(self):
        result = r.build()
        verify = result['verification']
        self.assertEqual((verify['selected'], verify['observed'], verify['missing']), (1000, 1000, 0))
        self.assertEqual(verify['agreement_counts'], {'topic': 808, 'intent': 917, 'severity': 853, 'joint': 660})
        self.assertTrue(verify['not_human_accuracy'])
        items = {v['id']: v for v in result['items']}
        self.assertEqual([(m['value'], m['of']) for m in items['grouping-stage']['metrics']], [(600, 600), (462, 600), (522, 600), (3, 600)])
        for key in ('blind-verifier-batch10', 'grouping-stage', 'planted-and-injection'):
            self.assertEqual(items[key]['status'], 'measured')
            self.assertEqual(items[key]['gaps'], [])
        ops = items['gap-operations']
        self.assertEqual(ops['compare']['rows'][2]['values'], ['0.373186624', '0.216267600', '0.000000000'])
        self.assertIn('125 attempts', ops['gaps'][0]['detail'])
        self.assertIn('6 additional', ops['gaps'][1]['detail'])

    def test_mismatched_baseline_source_denominator_and_accounting_rejected(self):
        for change in ('baseline', 'source', 'denominator', 'accounting'):
            d = copy.deepcopy(self.completion)
            if change == 'baseline': d['before']['coverage']['verify']['n'] = 979
            if change == 'source': d['source_sha256'] = 'wrong'
            if change == 'denominator': d['after']['coverage']['verify']['of'] = 999
            if change == 'accounting': d['cost']['exposure_nusd'] += 1
            with self.assertRaises(ValueError): r.apply_completion(self.items(), d, self.followup, self.measured)

    def test_saved_completion_is_safe_and_does_not_rewrite_prior_reports(self):
        d = self.completion
        self.assertEqual(d['cost']['attempts'], 3)
        self.assertEqual((d['cost']['known_charges_nusd'], d['cost']['unresolved_reservations_nusd']), (809700, 0))
        self.assertEqual(d['before'], self.followup['after'])
        self.assertEqual(d['after']['label_auditor'], self.followup['after']['label_auditor'])
        self.assertEqual(d['after']['issue_auditor'], self.followup['after']['issue_auditor'])
        self.assertTrue(all(x['response_headers_saved'] for x in d['receipts']))
        self.assertEqual([x['next_admission_respected_cooldown'] for x in d['receipts']], [True, True, None])
        for token in ('review_id', 'review_text', 'source_ids', '/Users/', 'user_id'):
            self.assertNotIn(token, json.dumps(d))

    def test_verifier_statistics_use_only_observed_outputs(self):
        plan = {'verify_ids': ['synthetic-a', 'synthetic-missing'], 'jev_labels': {
            'synthetic-a': {'topic': 'playback', 'intent': 'complaint', 'severity': 3}}}
        values = {'verify': {'synthetic-a': {'topic': 'playback', 'intent': 'complaint', 'severity': 4}}}
        self.assertEqual(p.verifier_statistics(plan, values)['severity_mae'], 1)


if __name__ == '__main__':
    unittest.main()

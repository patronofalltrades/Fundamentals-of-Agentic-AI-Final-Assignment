"""Synthetic and aggregate-only checks. No human answers or source text."""
import copy
import json
import unittest

from tools import build_followup_publication as p
from tools import build_eval_registry as registry


class FollowupPublicationTests(unittest.TestCase):
    def test_identity_diagnosis_distinguishes_unknown_from_duplicate(self):
        unknown = p.identity_counts(['synthetic-a', 'synthetic-b'], ['synthetic-a', 'synthetic-c'])
        duplicate = p.identity_counts(['synthetic-a', 'synthetic-b'], ['synthetic-a', 'synthetic-a'])
        self.assertEqual((unknown['unknown'], unknown['missing'], unknown['duplicate_values']), (1, 1, 0))
        self.assertEqual((duplicate['unknown'], duplicate['missing'], duplicate['duplicate_values']), (0, 1, 1))
        for result in (unknown, duplicate):
            self.assertFalse(result['complete_exact_bijection'])
            self.assertFalse(result['repair_by_position_or_similarity_permitted'])
            self.assertNotIn('synthetic', json.dumps(result))

    def test_pair_requires_both_auditor_and_blind_output(self):
        labels = {'topic': 'playback', 'intent': 'complaint', 'severity': 3}
        plan = {'label_claims': {r: {'planted': 'topic', 'claim': labels} for r in ('a', 'b', 'c')},
                'group_claims': {}, 'historical_issue': {}, 'group_ids': [],
                'verify_ids': ['a', 'b', 'c'], 'jev_labels': {r: labels for r in ('a', 'b', 'c')}}
        values = {'verify': {'a': labels, 'b': labels}, 'group': {}, 'audit_group': {},
                  'audit_label': {r: {'topic_supported': True, 'intent_supported': True, 'severity_supported': True}
                                  for r in ('a', 'c')}}
        paired = p.comparisons(plan, values)['paired_labels']
        self.assertEqual((paired['coverage']['n'], paired['coverage']['of'], paired['missing']), (1, 3, 2))
        self.assertEqual(sum(paired['table'].values()), 1)

    def test_aggregate_preserves_scores_holds_and_unknown_headers(self):
        d = json.loads((registry.ROOT / registry.FOLLOWUP).read_text())
        self.assertEqual(d['before']['verifier_agreement'], d['after']['verifier_agreement'])
        self.assertEqual(d['after']['coverage']['verify']['n'], 980)
        self.assertEqual(d['after']['coverage']['group']['n'], 590)
        self.assertEqual(d['after']['coverage']['audit_label']['n'], 100)
        self.assertEqual(d['before']['paired_labels']['coverage']['n'], 41)
        self.assertEqual(d['after']['paired_labels']['coverage']['n'], 48)
        self.assertEqual(d['cost']['unresolved_reservations_nusd'], 216267600)
        http = d['diagnosis']['http429']
        self.assertFalse(http['response_headers_saved'])
        for key in ('exact_rate_limit', 'retry_after_presence', 'retry_after_respected', 'rate_headers_respected'):
            self.assertIsNone(http[key])
        for token in ('review_id', 'review_text', 'source_ids', '/Users/', 'user_id', 'claimed_topic'):
            self.assertNotIn(token, json.dumps(d))

    def test_publication_rejects_changed_source_score_cost_and_baseline(self):
        d = json.loads((registry.ROOT / registry.FOLLOWUP).read_text())
        measured = json.loads((registry.ROOT / registry.MEASUREMENT).read_text())
        gap = json.loads((registry.ROOT / registry.GAP).read_text())
        for change in ('source', 'score', 'cost', 'baseline'):
            bad = copy.deepcopy(d)
            if change == 'source': bad['provenance']['source_sha256'] = 'wrong'
            if change == 'score': bad['after']['verifier_agreement']['joint']['n'] += 1
            if change == 'cost': bad['cost']['exposure_nusd'] += 1
            if change == 'baseline': bad['before']['coverage']['group']['n'] += 1
            with self.assertRaises(ValueError):
                registry.apply_followup(registry.gap_closure(gap, measured), bad, measured)


if __name__ == '__main__':
    unittest.main()

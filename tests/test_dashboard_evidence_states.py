"""Render native dashboard copy against supplied backend states; no HA or target I/O."""
from pathlib import Path
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'sensor.hi_lab_controller_'
FEED = PREFIX + 'feed'


class DashboardEvidenceStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = yaml.safe_load((ROOT / 'dashboards/hi-lab-operations.yaml').read_text())
        cls.evidence = {card.get('title'): card for view in cls.dashboard['views']
                        if view['title'] == 'Evidence' for section in view['sections']
                        for card in section['cards'] if card['type'] == 'markdown'}

    def render(self, title, states=None, attrs=None):
        states = {FEED: 'fresh', **(states or {})}
        attrs = attrs or {}
        environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
        return environment.from_string(self.evidence[title]['content']).render(
            states=lambda entity: states.get(entity, 'unknown'),
            state_attr=lambda entity, attribute: attrs.get(entity, {}).get(attribute))

    def test_stale_feed_cannot_represent_retained_attributes_as_current(self):
        for feed in ['stale', 'missing', 'invalid_signature', 'schema_mismatch',
                     'clock_invalid', 'unknown', 'unavailable']:
            for title, key in [('Active deployment evidence', 'active_deployment'),
                               ('Prepared deployment evidence', 'pending_deployment'),
                               ('Historical accepted baseline', 'accepted_baseline'),
                               ('Deployment validation evidence', 'last_validation'),
                               ('Historical deployment outcome', 'last_outcome')]:
                with self.subTest(feed=feed, title=title):
                    text = self.render(title, {FEED: feed, PREFIX+key: 'retained_record'},
                                       {PREFIX+key: {'profile': 'retained_profile', 'manifest_version': 'retained_version'}})
                    self.assertIn('Controller evidence unavailable', text)
                    self.assertNotIn('retained_record', text)
                    self.assertNotIn('retained_profile', text)
                    self.assertNotIn('retained_version', text)

    def test_no_pending_is_distinct_from_unavailable(self):
        clear = self.render('Prepared deployment evidence', {PREFIX+'pending_deployment': 'none'})
        absent = self.render('Prepared deployment evidence', {PREFIX+'pending_deployment': 'unavailable'})
        self.assertIn('No pending deployment', clear)
        self.assertIn('fields do not apply', clear)
        self.assertIn('Pending deployment truth unavailable', absent)
        self.assertNotIn('No pending deployment', absent)

    def test_active_identity_gap_does_not_claim_stopped_integration(self):
        text = self.render('Active deployment evidence', {PREFIX+'active_deployment': 'unavailable'})
        self.assertIn('has not proved a managed active identity', text)
        self.assertIn('completed soak does not fill this gap', text)
        text = self.render('Active deployment evidence', {PREFIX+'active_deployment': 'none'})
        self.assertIn('does not mean the integration is absent or stopped', text)

    def test_clear_lock_has_no_missing_owner_and_retains_zero_revision(self):
        text = self.render('Readiness and lock',
                           {PREFIX+'readiness': 'BLOCKED', PREFIX+'mutation_lock': 'CLEAR'},
                           {PREFIX+'readiness': {'state_revision': 0, 'blocker_codes': ['ACTIVE_IDENTITY_UNPROVED'], 'overflow_count': 0}})
        self.assertIn('Status revision: `0`', text)
        self.assertIn('Additional blockers: `0`', text)
        self.assertIn('No lock owner or held-at timestamp applies', text)
        self.assertIn('does not prove deployment readiness', text)
        self.assertNotIn('not reported', text)
        stale = self.render('Readiness and lock', {FEED: 'stale', PREFIX+'mutation_lock': 'CLEAR'})
        self.assertNotIn('controller reports the lock clear', stale)

    def test_historical_records_keep_dates_and_cannot_accept_current_package(self):
        text = self.render('Historical accepted baseline', {PREFIX+'accepted_baseline': 'example-record'},
                           {PREFIX+'accepted_baseline': {'manifest_version': '2.0.0', 'accepted_at': '2026-01-01T00:00:00Z'}})
        self.assertIn('2.0.0', text)
        self.assertIn('2026-01-01T00:00:00Z', text)
        self.assertIn('does not identify the currently running package', text)
        text = self.render('Historical deployment outcome', {PREFIX+'last_outcome': 'ACTIVE'},
                           {PREFIX+'last_outcome': {'completed_at': '2026-01-02T00:00:00Z', 'error_codes': []}})
        self.assertIn('2026-01-02T00:00:00Z', text)
        self.assertIn('ACTIVE is a historical result', text)
        self.assertIn('Recorded error codes: `[]`', text)

    def test_missing_validation_stays_unproved_and_zero_counts_are_not_dashes(self):
        text = self.render('Deployment validation evidence')
        self.assertIn('Stage 3) and installed identity remain unproved', text)
        self.assertIn('completed observation soak is separate evidence', text)
        text = self.render('Deployment validation evidence', {PREFIX+'last_validation': '2026-01-01T00:00:00Z'},
                           {PREFIX+'last_validation': {'stage_b_passed': 0, 'stage_b_expected': 2,
                            'stage_3_passed': 0, 'stage_3_expected': 1}})
        self.assertIn('Integration services available: `0`', text)
        self.assertIn('Runtime entities healthy: `0`', text)
        self.assertIn('Installed identity: `not reported`', text)

    def test_disabled_queue_retains_false_zero_and_independent_enablement(self):
        text = self.render('Bounded prepare queue', {PREFIX+'prepare_queue': 'DISABLED'},
                           {PREFIX+'prepare_queue': {'enabled': False, 'depth': 0, 'max_depth': 3, 'entries': []}})
        self.assertIn('Enabled: `False`', text)
        self.assertIn('Depth: `0`', text)
        self.assertIn('No queue work is enabled', text)
        self.assertNotIn('not reported', text)

    def test_operations_validation_has_complementary_record_and_missing_states(self):
        cards = [c for view in self.dashboard['views'] if view['title'] == 'Operations'
                 for section in view['sections'] for c in section['cards']]
        record = next(c for c in cards if c.get('card', {}).get('title') == 'Validation coverage')
        fallback = next(c for c in cards if c.get('card', {}).get('title') == 'Deployment validation unavailable')
        def matches(conditions, states):
            for condition in conditions:
                if condition['condition'] == 'or':
                    if not any(matches([c], states) for c in condition['conditions']): return False
                else:
                    actual = states.get(condition['entity'], 'unknown')
                    if 'state' in condition and actual != condition['state']: return False
                    if 'state_not' in condition and actual == condition['state_not']: return False
            return True
        for feed in ['fresh', 'stale', 'unavailable']:
            for value in ['unknown', 'unavailable', 'none', '', '2026-01-01T00:00:00Z']:
                with self.subTest(feed=feed, validation=value):
                    states = {FEED: feed, PREFIX+'last_validation': value}
                    expected = feed == 'fresh' and value not in ['unknown', 'unavailable', 'none', '']
                    self.assertEqual(matches(record['conditions'], states), expected)
                    self.assertEqual(matches(fallback['conditions'], states), not expected)
        self.assertEqual(record['grid_options'], fallback['grid_options'])

    def test_unknown_restart_has_the_same_explicit_unavailable_explanation(self):
        cards = [c for view in self.dashboard['views'] if view['title'] == 'Operations'
                 for section in view['sections'] for c in section['cards']]
        unavailable = next(c for c in cards if c.get('card', {}).get('title') == 'Restart truth unavailable')
        branches = unavailable['conditions'][0]
        self.assertEqual(branches['condition'], 'or')
        self.assertEqual({c['state'] for c in branches['conditions']}, {'unknown', 'unavailable'})
        self.assertIn('does not mean restart-not-required', unavailable['card']['content'])
        self.assertIn('does not supply restart truth', unavailable['card']['content'])


if __name__ == '__main__':
    unittest.main()

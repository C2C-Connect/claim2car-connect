"""Regression tests for strict 0017-0019 authority-migration inventory diagnostics."""
import unittest

from scripts.database_authority_diagnostics import validate_authority_migration_inventory
from verify_gates import verify_db_02


class AuthorityMigrationInventoryTests(unittest.TestCase):
    def inventory(self, names):
        return [(name, '0' * 64) for name in names]

    def test_accepts_ordered_event_capture_and_manifest_migrations(self):
        validate_authority_migration_inventory(self.inventory([
            '0017_event_contract_parity.sql',
            '0018_capture_protocol_session_binding.sql',
            '0019_manifest_root_protocol_binding.sql',
        ]))

    def test_requires_event_contract_parity_migration(self):
        with self.assertRaisesRegex(AssertionError, 'EVENT_CONTRACT_PARITY_MIGRATION_REQUIRED'):
            validate_authority_migration_inventory(self.inventory([
                '0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
            ]))

    def test_requires_capture_protocol_session_migration(self):
        with self.assertRaisesRegex(AssertionError, 'CAPTURE_PROTOCOL_SESSION_MIGRATION_REQUIRED'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0019_manifest_root_protocol_binding.sql',
            ]))

    def test_requires_manifest_root_protocol_migration(self):
        with self.assertRaisesRegex(AssertionError, 'MANIFEST_ROOT_PROTOCOL_BINDING_MIGRATION_REQUIRED'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0018_capture_protocol_session_binding.sql',
            ]))

    def test_rejects_out_of_order_authority_migrations(self):
        with self.assertRaisesRegex(AssertionError, 'AUTHORITY_MIGRATION_ORDER_INVALID'):
            validate_authority_migration_inventory(self.inventory([
                '0018_capture_protocol_session_binding.sql',
                '0017_event_contract_parity.sql',
                '0019_manifest_root_protocol_binding.sql',
            ]))

    def test_rejects_duplicate_authority_migration_names(self):
        with self.assertRaisesRegex(AssertionError, 'DUPLICATE_AUTHORITY_MIGRATION'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
            ]))

    def test_db02_accepts_the_complete_19_migration_inventory(self):
        names = [
            '0001_tenant_registry.sql', '0002_event_journal.sql',
            '0003_completion_lock.sql', '0004_manifest_roots.sql',
            '0005_completion_receipts.sql', '0006_event_timestamp_validity.sql',
            '0007_event_payload_compactness.sql', '0008_tenant_login_authority.sql',
            '0009_integer_financial_ledger.sql', '0010_claim_case_registry.sql',
            '0011_claim_case_idempotency_conflicts.sql', '0012_claim_case_retry_without_update_lock.sql',
            '0013_claim_case_capture_session.sql', '0014_claim_case_incident_intake.sql',
            '0015_incident_event_kinds.sql', '0016_claim_case_incident_read_boundary.sql',
            '0017_event_contract_parity.sql', '0018_capture_protocol_session_binding.sql',
            '0019_manifest_root_protocol_binding.sql',
        ]
        selectors = (
            'test_migration_plan.MigrationPlanTests.test_order',
            'test_migration_preflight.MigrationPreflightTests.test_initial_execution',
            'test_migration_controls_integration.MigrationControlsIntegration.test_first_application',
            'test_candidate_manifest.CandidateManifestTests.test_unchanged_candidate_compares',
        )
        counted = {
            'discovered': len(selectors), 'executed': len(selectors),
            'failures': 0, 'errors': 0, 'skipped': 0,
            'expected_failures': 0, 'unexpected_successes': 0,
            'successful': True,
            'tests': [{'id': item, 'outcome': 'passed'} for item in selectors],
        }
        result = verify_db_02({
            'diagnostics': {
                'diagnostics_successful': True,
                'migration_inventory': self.inventory(names),
            },
            'counted_tests': counted,
        })
        self.assertEqual(result['status'], 'PASS', result['failed_sql_checks'])

    def test_rejects_unreviewed_migration_after_0019(self):
        with self.assertRaisesRegex(AssertionError, 'UNEXPECTED_AUTHORITY_MIGRATION_AFTER_0019'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
                '0020_unreviewed.sql',
            ]))


if __name__ == '__main__':
    unittest.main()

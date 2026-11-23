"""Regression tests for strict 0017-0029 inventory and DB-01/DB-02 acceptance diagnostics."""
import unittest

from scripts.database_authority_diagnostics import validate_authority_migration_inventory
from verify_gates import verify_db_01, verify_db_02


class AuthorityMigrationInventoryTests(unittest.TestCase):
    def inventory(self, names):
        return [(name, '0' * 64) for name in names]

    def test_accepts_ordered_event_capture_and_manifest_migrations(self):
        validate_authority_migration_inventory(self.inventory([
            '0017_event_contract_parity.sql',
            '0018_capture_protocol_session_binding.sql',
            '0019_manifest_root_protocol_binding.sql',
            '0020_collision_lifecycle_record.sql',
            '0021_collision_claim_link.sql',
            '0022_collision_vehicle_capture_link.sql',
            '0023_consented_vehicle_profile.sql',
            '0024_audited_capture_exceptions_pause_resume.sql',
            '0025_square_sandbox_payment_intents.sql',
            '0026_square_sandbox_webhook_reconciliation.sql',
            '0027_capture_protocol_16_v2.sql',
            '0028_persistent_event_hash_chain.sql',
            '0029_manifest_root_chain_context_binding.sql',
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
                '0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql',
                '0022_collision_vehicle_capture_link.sql',
                '0023_consented_vehicle_profile.sql',
                '0024_audited_capture_exceptions_pause_resume.sql',
            ]))

    def test_rejects_duplicate_authority_migration_names(self):
        with self.assertRaisesRegex(AssertionError, 'DUPLICATE_AUTHORITY_MIGRATION'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
                '0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql',
            ]))

    def test_db01_accepts_the_29_migration_synthetic_environment(self):
        names = [f'{number:04d}_' + suffix for number, suffix in enumerate((
            'tenant_registry.sql', 'event_journal.sql', 'completion_lock.sql',
            'manifest_roots.sql', 'completion_receipts.sql',
            'event_timestamp_validity.sql', 'event_payload_compactness.sql',
            'tenant_login_authority.sql', 'integer_financial_ledger.sql',
            'claim_case_registry.sql', 'claim_case_idempotency_conflicts.sql',
            'claim_case_retry_without_update_lock.sql', 'claim_case_capture_session.sql',
            'claim_case_incident_intake.sql', 'incident_event_kinds.sql',
            'claim_case_incident_read_boundary.sql', 'event_contract_parity.sql',
            'capture_protocol_session_binding.sql', 'manifest_root_protocol_binding.sql', 'collision_lifecycle_record.sql', 'collision_claim_link.sql', 'collision_vehicle_capture_link.sql', 'consented_vehicle_profile.sql', 'audited_capture_exceptions_pause_resume.sql', 'square_sandbox_payment_intents.sql', 'square_sandbox_webhook_reconciliation.sql', 'capture_protocol_16_v2.sql', 'persistent_event_hash_chain.sql', 'manifest_root_chain_context_binding.sql',
        ), start=1)]
        selectors = (
            'test_candidate_manifest.CandidateManifestTests.test_unchanged_candidate_compares',
            'test_migration_plan.MigrationPlanTests.test_order',
            'test_migration_preflight.MigrationPreflightTests.test_initial_execution',
            'test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_clean_full_initialization_and_rerun',
            'test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_upgrades_legacy_seven_migration_schema',
        )
        counted = {
            'discovered': len(selectors), 'executed': len(selectors),
            'failures': 0, 'errors': 0, 'skipped': 0,
            'expected_failures': 0, 'unexpected_successes': 0,
            'successful': True,
            'tests': [{'id': item, 'outcome': 'passed'} for item in selectors],
        }
        connections = {
            'admin': {'user': 'postgres', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
            'application': {'user': 'faos_app', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
            'migrator': {'user': 'faos_migrator', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
        }
        diagnostics = {
            'diagnostics_successful': True,
            'database': ['claim2car_test', 'PostgreSQL 16 synthetic test instance'],
            'extensions': [['plpgsql', '1.0'], ['postgis', '3.4.3'], ['pgcrypto', '1.3']],
            'migration_inventory': self.inventory(names),
            'environment': {'classification': 'synthetic_isolated', 'connections': connections},
        }
        result = verify_db_01({
            'diagnostics': diagnostics,
            'counted_tests': counted,
            'environment_is_synthetic': True,
        })
        self.assertEqual(result['status'], 'PASS', result['failed_sql_checks'])

    def test_db02_accepts_the_complete_29_migration_inventory(self):
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
            '0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql',
            '0022_collision_vehicle_capture_link.sql',
            '0023_consented_vehicle_profile.sql',
            '0024_audited_capture_exceptions_pause_resume.sql',
            '0025_square_sandbox_payment_intents.sql',
            '0026_square_sandbox_webhook_reconciliation.sql',
            '0027_capture_protocol_16_v2.sql',
            '0028_persistent_event_hash_chain.sql', '0029_manifest_root_chain_context_binding.sql',
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

    def test_requires_manifest_chain_context_binding_migration(self):
        with self.assertRaisesRegex(AssertionError, 'MANIFEST_ROOT_CHAIN_CONTEXT_BINDING_MIGRATION_REQUIRED'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql','0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql','0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql','0022_collision_vehicle_capture_link.sql',
                '0023_consented_vehicle_profile.sql','0024_audited_capture_exceptions_pause_resume.sql',
                '0025_square_sandbox_payment_intents.sql','0026_square_sandbox_webhook_reconciliation.sql',
                '0027_capture_protocol_16_v2.sql','0028_persistent_event_hash_chain.sql',
            ]))

    def test_rejects_0029_before_0028(self):
        with self.assertRaisesRegex(AssertionError, 'AUTHORITY_MIGRATION_ORDER_INVALID'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql','0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql','0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql','0022_collision_vehicle_capture_link.sql',
                '0023_consented_vehicle_profile.sql','0024_audited_capture_exceptions_pause_resume.sql',
                '0025_square_sandbox_payment_intents.sql','0026_square_sandbox_webhook_reconciliation.sql',
                '0027_capture_protocol_16_v2.sql','0029_manifest_root_chain_context_binding.sql',
                '0028_persistent_event_hash_chain.sql',
            ]))

    def test_rejects_unreviewed_migration_after_0029(self):
        with self.assertRaisesRegex(AssertionError, 'UNEXPECTED_AUTHORITY_MIGRATION_AFTER_0029'):
            validate_authority_migration_inventory(self.inventory([
                '0017_event_contract_parity.sql',
                '0018_capture_protocol_session_binding.sql',
                '0019_manifest_root_protocol_binding.sql',
                '0020_collision_lifecycle_record.sql',
                '0021_collision_claim_link.sql',
                '0022_collision_vehicle_capture_link.sql',
                '0023_consented_vehicle_profile.sql',
                '0024_audited_capture_exceptions_pause_resume.sql',
                '0025_square_sandbox_payment_intents.sql',
                '0026_square_sandbox_webhook_reconciliation.sql',
                '0027_capture_protocol_16_v2.sql',
                '0028_persistent_event_hash_chain.sql',
                '0029_manifest_root_chain_context_binding.sql',
                '0030_unreviewed.sql',
            ]))


if __name__ == '__main__':
    unittest.main()
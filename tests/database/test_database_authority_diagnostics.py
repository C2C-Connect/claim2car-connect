"""Regression tests for strict authority-migration diagnostics."""
import unittest

from scripts.database_authority_diagnostics import validate_authority_migration_inventory


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

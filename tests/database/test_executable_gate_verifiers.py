"""Unit tests for 14-gate acceptance, 30 migrations, and 16-v1 root binding."""
import unittest

from verify_gates import (
    GATE_FUNCTIONS,
    GATE_TESTS,
    _matrix_ok,
    _counted_report_ok,
    preflight_counted_report,
    run_all_gate_verifiers,
    verify_db_01,
    verify_db_02,
    verify_db_06,
    verify_db_07,
    verify_db_10,
    verify_db_14,
)


class ExecutableGateVerifierTests(unittest.TestCase):
    def test_all_fourteen_gate_functions_are_explicit_and_ordered(self):
        self.assertEqual(len(GATE_FUNCTIONS), 14)
        self.assertEqual(
            [function.__name__ for function in GATE_FUNCTIONS],
            [f"verify_db_{number:02d}" for number in range(1, 15)],
        )

    def test_missing_evidence_never_awards_a_gate(self):
        results = run_all_gate_verifiers(
            {"checks": [], "diagnostics_successful": False, "migration_inventory": []},
            None,
        )
        self.assertEqual(len(results), 14)
        self.assertEqual(sum(row["status"] == "PASS" for row in results), 0)
        self.assertEqual(results[-1]["id"], "DB-14")
        self.assertEqual(results[-1]["status"], "NOT AWARDED")

    def test_authority_migration_inventory_requires_all_thirty_ordered_files(self):
        names = [
            '0001_tenant_registry.sql',
            '0002_event_journal.sql',
            '0003_completion_lock.sql',
            '0004_manifest_roots.sql',
            '0005_completion_receipts.sql',
            '0006_event_timestamp_validity.sql',
            '0007_event_payload_compactness.sql',
            '0008_tenant_login_authority.sql',
            '0009_integer_financial_ledger.sql',
            '0010_claim_case_registry.sql',
            '0011_claim_case_idempotency_conflicts.sql',
            '0012_claim_case_retry_without_update_lock.sql',
            '0013_claim_case_capture_session.sql',
            '0014_claim_case_incident_intake.sql',
            '0015_incident_event_kinds.sql',
            '0016_claim_case_incident_read_boundary.sql',
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
            '0030_runtime_manifest_registration.sql',
        ]
        selectors = (
            'test_candidate_manifest.CandidateManifestTests.test_added_migration_detected',
            'test_migration_plan.MigrationPlanTests.test_initial',
            'test_migration_preflight.MigrationPreflightTests.test_initial_execution',
            'test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_clean_full_initialization_and_rerun',
            'test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_upgrades_legacy_seven_migration_schema',
        )
        counted = {
            'discovered': len(selectors), 'executed': len(selectors), 'failures': 0,
            'errors': 0, 'skipped': 0, 'expected_failures': 0,
            'unexpected_successes': 0, 'successful': True,
            'tests': [{'id': value, 'outcome': 'passed'} for value in selectors],
        }
        inventory = [(name, '0' * 64) for name in names]
        diagnostics = {
            'diagnostics_successful': True,
            'checks': [],
            'database': ['claim2car_test', 'PostgreSQL synthetic'],
            'extensions': [('plpgsql', '1.0'), ('postgis', '3.4'), ('pgcrypto', '1.3')],
            'migration_inventory': inventory,
            'environment': {'connections': {
                'admin': {'user': 'postgres', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
                'application': {'user': 'faos_app', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
                'migrator': {'user': 'faos_migrator', 'host': '127.0.0.1', 'port': '55432', 'dbname': 'claim2car_test'},
            }},
        }
        context = {'diagnostics': diagnostics, 'counted_tests': counted, 'environment_is_synthetic': True}
        self.assertEqual(verify_db_01(context)['status'], 'PASS')
        self.assertEqual(verify_db_02(context)['status'], 'PASS')

    def test_db14_requires_complete_30_migration_same_run_evidence(self):
        selectors = (
            "test_counted_runner.CountedRunnerTests.test_passing_case_is_recorded",
            "test_evidence_finalizer.EvidenceFinalizerTests.test_success_verifies_checksums",
        )
        counted = {
            "discovered": 2, "executed": 2, "failures": 0, "errors": 0,
            "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
            "successful": True,
            "tests": [{"id": value, "outcome": "passed"} for value in selectors],
        }
        diagnostics = {
            "diagnostics_successful": True,
            "commit": "candidate",
            "candidate_commit": "candidate",
            "tested_checkout_commit": "checkout",
            "migration_inventory": [
                (f"{number:04d}_migration.sql", "0" * 64)
                for number in range(1, 31)
            ],
        }
        context = {
            "diagnostics": diagnostics,
            "counted_tests": counted,
            "prior_gate_results": [{"status": "PASS"} for _ in range(13)],
        }
        self.assertEqual(verify_db_14(context)["status"], "PASS")
        diagnostics["migration_inventory"].pop()
        failed = verify_db_14(context)
        self.assertEqual(failed["status"], "FAIL")
        self.assertIn(
            "SAME_RUN_COMPLETE_GATE_EVIDENCE_AND_FAILURE_ACCOUNTING",
            failed["failed_sql_checks"],
        )

    def test_manifest_root_gate_requires_16_v1_session_binding_integration(self):
        required = "test_migration_controls_integration.MigrationControlsIntegration.test_manifest_root_protocol_binding_accepts_16_and_rejects_mismatch"
        selectors = GATE_TESTS["DB-10"][1]
        self.assertIn(required, selectors)
        tests = [
            {"id": prefix + "fixture", "outcome": "passed"}
            for prefix in selectors if prefix != required
        ]
        counted = {
            "discovered": len(tests), "executed": len(tests), "failures": 0,
            "errors": 0, "skipped": 0, "expected_failures": 0,
            "unexpected_successes": 0, "successful": True, "tests": tests,
        }
        result = verify_db_10({
            "diagnostics": {"diagnostics_successful": True, "checks": []},
            "counted_tests": counted,
        })
        self.assertEqual(result["status"], "FAIL")
        self.assertIn(required, result["missing_test_selectors"])

    def test_gate_requires_each_mapped_test_and_sql_assertion(self):
        ids = (
            "test_journal_integration.TestJournalIntegration.test_duplicate_is_idempotent",
            "test_tenant_authority_integration.TenantAuthorityIntegration.test_bound_logins_append_retry_and_read_actual_journal",
            "test_event_contract_regression.EventContractRegression.test_valid_history_reconstructs_independent_journal",
        )
        counted = {
            "suite": "database",
            "discovered": len(ids),
            "executed": len(ids),
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "expected_failures": 0,
            "unexpected_successes": 0,
            "successful": True,
            "tests": [{"id": value, "outcome": "passed"} for value in ids],
        }
        context = {
            "diagnostics": {
                "diagnostics_successful": True,
                "checks": [{"id": "BOUND-APPEND-RETRY-READBACK", "status": "PASS"}],
            },
            "counted_tests": counted,
        }
        self.assertEqual(verify_db_07(context)["status"], "PASS")

    def test_gate_fails_when_a_required_sql_check_is_absent(self):
        ids = (
            "test_event_contract_regression.EventContractRegression.test_valid_history_reconstructs_independent_journal",
            "test_adapter_validation.TestAdapterValidation.test_invalid_event_fields_rejected_before_database_calls",
            "test_migration_controls_integration.MigrationControlsIntegration.test_full_migration_enforces_python_sql_event_contract_parity",
            "test_migration_controls_integration.MigrationControlsIntegration.test_parity_migration_preserves_existing_event_payload_bytes",
            "test_migration_controls_integration.MigrationControlsIntegration.test_noncanonical_historical_event_blocks_parity_migration_without_rewrite",
        )
        counted = {
            "discovered": len(ids), "executed": len(ids), "failures": 0, "errors": 0,
            "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
            "successful": True, "tests": [{"id": value, "outcome": "passed"} for value in ids],
        }
        result = verify_db_06({
            "diagnostics": {"diagnostics_successful": True, "checks": []},
            "counted_tests": counted,
        })
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("G06-unicode_escape", result["missing_sql_checks"])

    def test_skipped_or_unaccounted_tests_never_pass_preflight(self):
        base = {
            "suite": "database", "discovered": 1, "executed": 1, "failures": 0,
            "errors": 0, "skipped": 0, "expected_failures": 0,
            "unexpected_successes": 0, "successful": True,
            "tests": [{"id": "test_example.Example.test_ok", "outcome": "passed"}],
        }
        self.assertTrue(_counted_report_ok(base))
        skipped = dict(base, skipped=1, successful=False,
                       tests=[{"id": "test_example.Example.test_skip", "outcome": "skipped"}])
        self.assertFalse(_counted_report_ok(skipped))

    def test_tenant_matrix_requires_all_280_adversarial_assertions(self):
        self.assertFalse(_matrix_ok({
            "status": "PASS", "table_count": 14, "tenant_directions": 2,
            "assertion_count": 280, "results": [],
        }))

    def test_contract_is_not_silently_adopted_by_a_green_gate_run(self):
        report = {"checks": [], "diagnostics_successful": False, "migration_inventory": []}
        run_all_gate_verifiers(report, None)
        self.assertEqual(report["contract_status"], "PROPOSED_PENDING_OWNER_ADOPTION")
        self.assertEqual(report["gate_passes_awarded"], 0)
        self.assertTrue(all(row["status"] == "NOT AWARDED" for row in report["complete_gate_results"]))
        self.assertEqual(report["overall_acceptance"], "NOT ACCEPTED")
        self.assertIn("CONTRACT_OWNER_ADOPTION_AND_INDEPENDENT_REVIEW_PENDING",
                      report["acceptance_blockers"])


if __name__ == "__main__":
    unittest.main()

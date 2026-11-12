"""Unit tests for the executable 14-gate acceptance accounting."""
import unittest

from verify_gates import (
    GATE_FUNCTIONS,
    _matrix_ok,
    _counted_report_ok,
    preflight_counted_report,
    run_all_gate_verifiers,
    verify_db_06,
    verify_db_07,
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

"""Executable DB-01..DB-14 acceptance gates.

Each gate consumes recorded test outcomes and post-cutover PostgreSQL assertions.
A test count alone never awards a gate: each gate requires its own mapped tests
and any gate-specific SQL evidence defined by C2C-DB-AC-001 section 3.
"""
import argparse
import json
from pathlib import Path


GATE_TESTS = {
    "DB-01": (
        "Reproducible environment and configuration",
        (
            "test_candidate_manifest.CandidateManifestTests.",
            "test_migration_plan.MigrationPlanTests.",
            "test_migration_preflight.MigrationPreflightTests.",
            "test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_clean_full_initialization_and_rerun",
            "test_migration_controls_integration.MigrationControlsIntegration.test_default_entry_point_upgrades_legacy_seven_migration_schema",
        ),
        (),
    ),
    "DB-02": (
        "Migration integrity and schema versioning",
        (
            "test_migration_plan.MigrationPlanTests.",
            "test_migration_preflight.MigrationPreflightTests.",
            "test_migration_controls_integration.MigrationControlsIntegration.",
            "test_candidate_manifest.CandidateManifestTests.",
        ),
        (),
    ),
    "DB-03": (
        "Restricted application privileges",
        (
            "test_access_hardening.TestAccessHardening.",
            "test_adapter_validation.TestAdapterValidation.",
            "test_identity_boundary.IdentityBoundaryTests.",
            "test_tenant_authority_integration.TenantAuthorityIntegration.test_application_cannot_read_or_modify_authority_registry",
            "test_completion_receipts.CompletionReceiptTests.test_application_cannot_record_or_insert",
            "test_manifest_roots.ManifestRootTests.test_application_cannot_register_or_insert_root",
        ),
        ("PRIVATE-AUTHORITY-REGISTRY", "UNBOUND-SHARED-LOGIN-DENIED"),
    ),
    "DB-04": (
        "Tenant isolation and row-level security",
        (
            "test_remaining_integration.TestRemainingIntegration.",
            "test_identity_bound_prototype.IdentityBoundPrototype.",
            "test_schema_integrity.SchemaIntegrityTests.",
            "test_tenant_authority_integration.TenantAuthorityIntegration.",
        ),
        ("G04-DIRECT-SQL-TENANT-SWITCH", "UNBOUND-SHARED-LOGIN-DENIED", "POSTCUTOVER-PER-TABLE-ISOLATION"),
    ),
    "DB-05": (
        "Tenant-context lifecycle",
        (
            "test_tenant_context_regression.TenantContextRegression.",
            "test_completion_lock.CompletionLockTests.",
            "test_locked_evaluation.LockedEvaluationTests.",
        ),
        (),
    ),
    "DB-06": (
        "Event schema and domain-contract validation",
        (
            "test_event_contract_regression.EventContractRegression.",
            "test_adapter_validation.TestAdapterValidation.",
            "test_migration_controls_integration.MigrationControlsIntegration.test_full_migration_enforces_python_sql_event_contract_parity",
            "test_migration_controls_integration.MigrationControlsIntegration.test_parity_migration_preserves_existing_event_payload_bytes",
            "test_migration_controls_integration.MigrationControlsIntegration.test_noncanonical_historical_event_blocks_parity_migration_without_rewrite",
        ),
        (
            "G06-timestamp", "G06-naive_timestamp", "G06-compact_payload",
            "G06-key_order", "G06-numeric_exponent", "G06-unicode_escape",
            "G06-unicode-positive-control", "COMPACT-JSON-POSITIVE-CONTROL",
        ),
    ),
    "DB-07": (
        "Durable event append and idempotency",
        (
            "test_journal_integration.TestJournalIntegration.",
            "test_tenant_authority_integration.TenantAuthorityIntegration.test_bound_logins_append_retry_and_read_actual_journal",
            "test_event_contract_regression.EventContractRegression.",
        ),
        ("BOUND-APPEND-RETRY-READBACK",),
    ),
    "DB-08": (
        "Sequence integrity and concurrent writes",
        (
            "test_journal_integration.TestConcurrentJournal.",
            "test_completion_concurrency.CompletionConcurrencyTests.",
            "test_completion_lock.CompletionLockTests.",
        ),
        (),
    ),
    "DB-09": (
        "Event immutability and history integrity",
        (
            "test_access_hardening.TestAccessHardening.",
            "test_event_contract_regression.EventContractRegression.",
            "test_journal_integration.TestJournalIntegration.",
            "test_journal_integration.TestConcurrentJournal.",
            "test_migration_controls_integration.MigrationControlsIntegration.test_parity_migration_preserves_existing_event_payload_bytes",
            "test_migration_controls_integration.MigrationControlsIntegration.test_noncanonical_historical_event_blocks_parity_migration_without_rewrite",
        ),
        (),
    ),
    "DB-10": (
        "Evidence-manifest integrity and root registration",
        (
            "test_completion_coverage.CompletionCoverage.",
            "test_manifest_roots.ManifestRootTests.",
            "test_registered_completion.RegisteredCompletionTests.",
        ),
        (),
    ),
    "DB-11": (
        "Completion receipts and protected completion state",
        (
            "test_completion_receipts.CompletionReceiptTests.",
            "test_atomic_completion.AtomicCompletionTests.",
            "test_completion_concurrency.CompletionConcurrencyTests.",
        ),
        (),
    ),
    "DB-12": (
        "Revocation, tampering, and invalidation behavior",
        (
            "test_atomic_completion.AtomicCompletionTests.",
            "test_registered_completion.RegisteredCompletionTests.",
            "test_receipt_inspection.ReceiptInspectionTests.",
            "test_process_recovery.PersistedEvidenceRecovery.",
        ),
        ("BINDING-REVOCATION-NEXT-TRANSACTION",),
    ),
    "DB-13": (
        "Restart, recovery, and replay",
        (
            "test_process_recovery.ProcessRecovery.",
            "test_process_recovery.PersistedEvidenceRecovery.",
            "test_receipt_inspection.ReceiptInspectionTests.",
            "test_tenant_authority_vertical_slice.TenantAuthorityVerticalSlice.",
        ),
        (),
    ),
    "DB-14": (
        "Failure handling, end-to-end acceptance, and evidence reporting",
        (
            "test_counted_runner.CountedRunnerTests.",
            "test_evidence_finalizer.EvidenceFinalizerTests.",
        ),
        (),
    ),
}


def _check_map(diagnostics):
    return {row.get("id"): row for row in diagnostics.get("checks", []) if isinstance(row, dict)}


def _matrix_ok(check):
    if not isinstance(check, dict) or check.get("status") != "PASS":
        return False
    if check.get("table_count") != 14 or check.get("tenant_directions") != 2:
        return False
    if check.get("assertion_count") != 280 or len(check.get("results", [])) != 28:
        return False
    required = {
        "rls_flags", "own_read", "cross_read", "cross_insert", "cross_update",
        "cross_delete", "tenant_reassignment", "spoofed_context",
        "missing_context", "malformed_context",
    }
    return all(
        set(row.get("checks", {})) == required
        and all(item.get("status") == "PASS" for item in row["checks"].values())
        for row in check["results"]
    )


def _counted_report_ok(record):
    if not isinstance(record, dict):
        return False
    tests = record.get("tests")
    if type(tests) is not list or not tests:
        return False
    discovered = record.get("discovered")
    executed = record.get("executed")
    if type(discovered) is not int or discovered <= 0 or executed != discovered or len(tests) != discovered:
        return False
    if any(record.get(key) != 0 for key in (
        "failures", "errors", "skipped", "expected_failures", "unexpected_successes"
    )):
        return False
    return record.get("successful") is True and all(
        isinstance(row, dict) and row.get("outcome") == "passed" and isinstance(row.get("id"), str)
        for row in tests
    )


def _gate(context, gate_id):
    title, selectors, required_checks = GATE_TESTS[gate_id]
    diagnostics = context.get("diagnostics") or {}
    counted = context.get("counted_tests")
    rows = counted.get("tests", []) if isinstance(counted, dict) else []
    selected = [row for row in rows if any(row.get("id", "").startswith(prefix) for prefix in selectors)]
    missing_selectors = [prefix for prefix in selectors if not any(
        row.get("id", "").startswith(prefix) for row in rows
    )]
    check_map = _check_map(diagnostics)
    missing_checks = [key for key in required_checks if key not in check_map]
    failed_checks = [key for key in required_checks if key in check_map and check_map[key].get("status") != "PASS"]
    if gate_id == "DB-04" and "POSTCUTOVER-PER-TABLE-ISOLATION" in check_map:
        if not _matrix_ok(check_map["POSTCUTOVER-PER-TABLE-ISOLATION"]):
            failed_checks.append("POSTCUTOVER-PER-TABLE-ISOLATION:INCOMPLETE_OR_FAILED_MATRIX")
    failures = [row.get("id") for row in selected if row.get("outcome") != "passed"]
    if not diagnostics.get("diagnostics_successful"):
        failed_checks.append("POSTCUTOVER_DIAGNOSTICS_NOT_SUCCESSFUL")
    report_ok = _counted_report_ok(counted)
    if not report_ok:
        failed_checks.append("COUNTED_DATABASE_TEST_REPORT_NOT_CLEAN")
    status = "PASS" if selected and not missing_selectors and not missing_checks and not failed_checks and not failures else "FAIL"
    return {
        "id": gate_id,
        "title": title,
        "status": status,
        "test_count": len(selected),
        "test_ids": sorted(row["id"] for row in selected),
        "required_test_selectors": list(selectors),
        "missing_test_selectors": missing_selectors,
        "failed_tests": failures,
        "required_sql_checks": list(required_checks),
        "missing_sql_checks": missing_checks,
        "failed_sql_checks": sorted(set(failed_checks)),
        "evidence_commit": diagnostics.get("commit"),
    }


def verify_db_01(context):
    result = _gate(context, "DB-01")
    diagnostics = context.get("diagnostics") or {}
    database = diagnostics.get("database") or []
    extensions = {row[0] for row in diagnostics.get("extensions", []) if isinstance(row, (list, tuple)) and row}
    inventory = diagnostics.get("migration_inventory") or []
    environment = diagnostics.get("environment") or {}
    expected_connections = {
        "admin": ("postgres", "127.0.0.1", "55432", "claim2car_test"),
        "application": ("faos_app", "127.0.0.1", "55432", "claim2car_test"),
        "migrator": ("faos_migrator", "127.0.0.1", "55432", "claim2car_test"),
    }
    connections_ok = all(
        isinstance(environment.get(name), dict)
        and tuple(environment[name].get(key) for key in ("user", "host", "port", "dbname")) == expected
        for name, expected in expected_connections.items()
    )
    env_ok = bool(
        database and database[0] == "claim2car_test"
        and "PostgreSQL" in str(database[1] if len(database) > 1 else "")
        and {"plpgsql", "postgis"}.issubset(extensions)
        and len(inventory) == 18
        and connections_ok
        and context.get("environment_is_synthetic") is True
    )
    if not env_ok:
        result["status"] = "FAIL"
        result["failed_sql_checks"].append("EXPLICIT_REPRODUCIBLE_SYNTHETIC_ENVIRONMENT")
    return result


def verify_db_02(context):
    result = _gate(context, "DB-02")
    inventory = (context.get("diagnostics") or {}).get("migration_inventory") or []
    names = [row[0] for row in inventory if isinstance(row, (list, tuple)) and row]
    expected = [f"{number:04d}_" for number in range(1, 19)]
    if len(names) != 18 or any(not name.startswith(prefix) for name, prefix in zip(names, expected)):
        result["status"] = "FAIL"
        result["failed_sql_checks"].append("ORDERED_COMPLETE_MIGRATION_INVENTORY")
    if (len(inventory) != 18 or any(
            not isinstance(row, (list, tuple)) or len(row) != 2
            or not isinstance(row[1], str) or len(row[1]) != 64
            or any(character not in "0123456789abcdef" for character in row[1])
            for row in inventory)):
        result["status"] = "FAIL"
        result["failed_sql_checks"].append("MIGRATION_SHA256_INVENTORY")
    return result


def verify_db_03(context):
    return _gate(context, "DB-03")


def verify_db_04(context):
    return _gate(context, "DB-04")


def verify_db_05(context):
    return _gate(context, "DB-05")


def verify_db_06(context):
    return _gate(context, "DB-06")


def verify_db_07(context):
    return _gate(context, "DB-07")


def verify_db_08(context):
    return _gate(context, "DB-08")


def verify_db_09(context):
    return _gate(context, "DB-09")


def verify_db_10(context):
    return _gate(context, "DB-10")


def verify_db_11(context):
    return _gate(context, "DB-11")


def verify_db_12(context):
    return _gate(context, "DB-12")


def verify_db_13(context):
    return _gate(context, "DB-13")


def verify_db_14(context):
    result = _gate(context, "DB-14")
    counted = context.get("counted_tests")
    diagnostics = context.get("diagnostics") or {}
    prior = context.get("prior_gate_results", [])
    if (not _counted_report_ok(counted)
            or len(prior) != 13
            or any(row.get("status") != "PASS" for row in prior)
            or not diagnostics.get("diagnostics_successful")
            or not diagnostics.get("commit")
            or len(diagnostics.get("migration_inventory") or []) != 18):
        result["status"] = "FAIL"
        result["failed_sql_checks"].append("SAME_RUN_COMPLETE_GATE_EVIDENCE_AND_FAILURE_ACCOUNTING")
    return result


GATE_FUNCTIONS = (
    verify_db_01, verify_db_02, verify_db_03, verify_db_04, verify_db_05,
    verify_db_06, verify_db_07, verify_db_08, verify_db_09, verify_db_10,
    verify_db_11, verify_db_12, verify_db_13, verify_db_14,
)


def run_all_gate_verifiers(diagnostics, counted_tests, *, environment_is_synthetic=True):
    context = {
        "diagnostics": diagnostics,
        "counted_tests": counted_tests,
        "environment_is_synthetic": environment_is_synthetic,
        "prior_gate_results": [],
    }
    results = []
    for function in GATE_FUNCTIONS[:-1]:
        result = function(context)
        results.append(result)
        context["prior_gate_results"] = results
    results.append(verify_db_14(context))
    awarded = sum(row["status"] == "PASS" for row in results)
    diagnostics["complete_gate_results"] = results
    diagnostics["gate_passes_awarded"] = awarded
    diagnostics["gate_verification_successful"] = awarded == 14
    diagnostics["counted_test_summary"] = {
        key: counted_tests.get(key) for key in (
            "suite", "discovered", "executed", "failures", "errors", "skipped",
            "expected_failures", "unexpected_successes", "successful",
        )
    } if isinstance(counted_tests, dict) else None
    # C2C-DB-AC-001 is still explicitly marked PROPOSED in the source document.
    # Individual gate passes are real, but overall acceptance cannot be declared
    # until the owner-adoption/review requirement in the contract is resolved.
    diagnostics["contract_status"] = "PROPOSED_PENDING_OWNER_ADOPTION"
    diagnostics["overall_acceptance"] = "NOT ACCEPTED"
    diagnostics["acceptance_blockers"] = (
        [] if awarded == 14 else ["ONE_OR_MORE_DATABASE_GATES_NOT_PASS"]
    ) + ["CONTRACT_OWNER_ADOPTION_AND_INDEPENDENT_REVIEW_PENDING"]
    diagnostics["classification"] = "executable-db-01-through-db-14-gate-results"
    return results


def preflight_counted_report(path):
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"status": "BLOCKED", "reason": "COUNTED_DATABASE_TEST_REPORT_UNAVAILABLE"}
    if not _counted_report_ok(record):
        return {
            "status": "FAIL",
            "reason": "COUNTED_DATABASE_TEST_REPORT_NOT_CLEAN",
            "summary": {key: record.get(key) for key in (
                "discovered", "executed", "failures", "errors", "skipped",
                "expected_failures", "unexpected_successes", "successful",
            )},
        }
    return {
        "status": "PASS",
        "reason": "ALL_COUNTED_DATABASE_TESTS_PASSED_WITH_ZERO_SKIPS",
        "summary": {key: record.get(key) for key in (
            "discovered", "executed", "failures", "errors", "skipped",
            "expected_failures", "unexpected_successes", "successful",
        )},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args()
    if not args.preflight or not args.report:
        parser.error("use --preflight --report PATH after the counted database suite")
    result = preflight_counted_report(args.report)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

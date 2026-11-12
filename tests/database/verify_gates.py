"""Executable DB-01..DB-14 acceptance verifiers; synthetic PostgreSQL only."""
from __future__ import annotations
import io, json, os, sys, unittest
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = ROOT / "tests" / "database"
for item in (str(TEST_DIR), str(ROOT)):
    if item not in sys.path:
        sys.path.insert(0, item)

GATE_TESTS = {
    "DB-01": ("test_migration_preflight.py",),
    "DB-02": ("test_migration_plan.py", "test_migration_controls_integration.py", "test_schema_integrity.py"),
    "DB-03": ("test_access_hardening.py",),
    "DB-04": ("test_tenant_authority_integration.py", "test_tenant_authority_vertical_slice.py"),
    "DB-05": ("test_tenant_context_regression.py",),
    "DB-06": ("test_event_contract_regression.py", "test_adapter_validation.py", "test_journal_integration.py", "test_migration_controls_integration.py"),
    "DB-07": ("test_journal_integration.py",),
    "DB-08": ("test_journal_integration.py",),
    "DB-09": ("test_access_hardening.py",),
    "DB-10": ("test_manifest_roots.py", "test_candidate_manifest.py", "test_evidence_finalizer.py"),
    "DB-11": ("test_completion_receipts.py", "test_registered_completion.py", "test_completion_concurrency.py", "test_atomic_completion.py"),
    "DB-12": ("test_completion_coverage.py", "test_evidence_finalizer.py", "test_registered_completion.py", "test_receipt_inspection.py"),
    "DB-13": ("test_process_recovery.py",),
}
REQUIREMENTS = {
    "DB-01": "Reproducible isolated database, explicit synthetic config, dependency and target identity.",
    "DB-02": "Complete ordered migrations, hashes, schema assertions, failure and recovery behavior.",
    "DB-03": "Least-privilege app role; deny prohibited DDL, escalation, protected writes and RLS bypass.",
    "DB-04": "Adversarial cross-tenant reads/writes for every in-scope tenant table.",
    "DB-05": "Context reset after commit, rollback, exceptions and pooled-connection reuse.",
    "DB-06": "Python/SQL event parity for timestamps, canonical JSON, Unicode, numeric spelling and kinds.",
    "DB-07": "Durable append/readback, identical retry, conflicting retry and rollback safety.",
    "DB-08": "Concurrent writers and sequence races resolve deterministically.",
    "DB-09": "Ordinary application role cannot rewrite history; unauthorized history changes are detectable.",
    "DB-10": "Manifest canonicalization, tenant/protocol binding, tamper detection and protected root registration.",
    "DB-11": "Authorized completion, receipt references, duplicate/conflict behavior and protected state.",
    "DB-12": "Revocation/tampering invalidates downstream reads and completion decisions.",
    "DB-13": "Committed state survives process restart and deterministic replay.",
    "DB-14": "All gates run in one traceable report; failures, skips and blocked checks prevent acceptance.",
}
KNOWN_UNVERIFIED = {}
def _recorded_files(files, context):
    report=context.get("counted_test_report") or {}
    records=report.get("tests") or []
    wanted={name[:-3] for name in files}
    selected=[row for row in records if any(row.get("id","").startswith(module+".") for module in wanted)]
    missing=sorted(module for module in wanted if not any(row.get("id","").startswith(module+".") for row in selected))
    bad=[row for row in selected if row.get("outcome")!="passed"]
    return {"status":"PASS" if selected and not missing and not bad else "FAIL",
            "tests_run":len(selected),"failures":sum(row.get("outcome") in ("failed","subtest_failed") for row in bad),
            "errors":sum(row.get("outcome")=="error" for row in bad),
            "skipped":sum(row.get("outcome")=="skipped" for row in bad),
            "missing_modules":missing,"details":bad}

def _config(url, user):
    p = conninfo_to_dict(url)
    return p.get("host")=="127.0.0.1" and p.get("port")=="55432" and p.get("dbname")=="claim2car_test" and p.get("user")==user
def verify_db_01(context):
    base={"requirement":REQUIREMENTS["DB-01"],"assertions":["explicit isolated admin/app URLs","database identity","server version"]}
    if not (_config(context["admin_url"],"postgres") and _config(context["app_url"],"faos_app")):
        return {"status":"FAIL",**base,"details":["EXPLICIT_SYNTHETIC_TARGET_REQUIRED"]}
    with psycopg.connect(context["admin_url"]) as conn:
        db,version=conn.execute("SELECT current_database(),version()").fetchone()
        ext=sorted(row[0] for row in conn.execute("SELECT extname FROM pg_extension"))
    tests=_recorded_files(GATE_TESTS["DB-01"],context)
    return {"status":"PASS" if db=="claim2car_test" and tests["status"]=="PASS" else "FAIL",
            **base,"database":db,"server_version":version,"extensions":ext,"tests":tests}
def verify_db_02(context):
    from database.migration_plan import discover_authority
    expected=[(m.name,m.sha256) for m in discover_authority(ROOT)]
    with psycopg.connect(context["admin_url"]) as conn:
        actual=conn.execute("SELECT name,sha256 FROM public.faos_migration_history ORDER BY ordinal").fetchall()
    tests=_recorded_files(GATE_TESTS["DB-02"],context)
    ok=actual==expected and tests["status"]=="PASS"
    return {"status":"PASS" if ok else "FAIL","requirement":REQUIREMENTS["DB-02"],
            "migration_count":len(actual),"migration_inventory_matches":actual==expected,"tests":tests,
            "details":[] if actual==expected else ["MIGRATION_LEDGER_MISMATCH"]}
def _test_gate(gate,context):
    tests=_recorded_files(GATE_TESTS[gate],context)
    limits=[KNOWN_UNVERIFIED[gate]] if gate in KNOWN_UNVERIFIED else []
    status="PASS" if tests["status"]=="PASS" and not limits else "IMPLEMENTED — UNVERIFIED"
    return {"status":status,"requirement":REQUIREMENTS[gate],"tests":tests,"limitations":limits}
def verify_db_03(context):
    with psycopg.connect(context["app_url"]) as conn:
        role=conn.execute("SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
    result=_test_gate("DB-03",context)
    result["role_assertion"]={"status":"PASS" if role==("faos_app",False,False) else "FAIL","value":role}
    if result["role_assertion"]["status"]!="PASS": result["status"]="FAIL"
    return result
def verify_db_04(context):
    result=_test_gate("DB-04",context)
    matrix=next((row for row in context.get("diagnostic_checks",[]) if row.get("id")=="POSTCUTOVER-PER-TABLE-ISOLATION"),None)
    result["tenant_isolation_matrix"]={"status":"PASS" if matrix and matrix.get("status")=="PASS" else "MISSING_OR_FAILED"}
    if result["tenant_isolation_matrix"]["status"]!="PASS": result["status"]="FAIL"
    return result
def verify_db_05(context):
    result=_test_gate("DB-05",context)
    probe=next((row for row in context.get("diagnostic_checks",[]) if row.get("id")=="POSTCUTOVER-CONTEXT-RESET"),None)
    result["postcutover_context_reset"]={"status":"PASS" if probe and probe.get("status")=="PASS" else "MISSING_OR_FAILED"}
    if result["postcutover_context_reset"]["status"]!="PASS": result["status"]="FAIL"
    return result
def verify_db_06(context):
    result=_test_gate("DB-06",context)
    required={"G06-timestamp","G06-naive_timestamp","G06-compact_payload","G06-key_order","G06-numeric_exponent","G06-unicode_escape","CANONICAL-UNICODE-DECIMAL-POSITIVE-CONTROL"}
    observed={row.get("id") for row in context.get("diagnostic_checks",[]) if row.get("status")=="PASS"}
    missing=sorted(required-observed)
    result["direct_sql_parity_probes"]={"required":sorted(required),"missing":missing}
    if missing: result["status"]="IMPLEMENTED — UNVERIFIED"
    return result
def verify_db_07(context): return _test_gate("DB-07",context)
def verify_db_08(context): return _test_gate("DB-08",context)
def verify_db_09(context): return _test_gate("DB-09",context)
def verify_db_10(context):
    result=_test_gate("DB-10",context)
    probe=next((row for row in context.get("diagnostic_checks",[]) if row.get("id")=="POSTCUTOVER-ROOT-16-PROTOCOL-BINDING"),None)
    result["protocol_16_root_binding"]={"status":"PASS" if probe and probe.get("status")=="PASS" else "MISSING_OR_FAILED"}
    if result["protocol_16_root_binding"]["status"]!="PASS": result["status"]="FAIL"
    return result
def verify_db_11(context): return _test_gate("DB-11",context)
def verify_db_12(context): return _test_gate("DB-12",context)
def verify_db_13(context): return _test_gate("DB-13",context)
def verify_db_14(context, prior):
    report=context.get("counted_test_report") or {}
    discovered=report.get("discovered",0)
    executed=report.get("executed",0)
    failures=report.get("failures",0)
    errors=report.get("errors",0)
    skipped=report.get("skipped",0)
    records=report.get("tests") or []
    prior_pass=all(v["status"]=="PASS" for v in prior.values())
    enough=discovered>=297 and executed>=297
    no_skips=skipped==0 and all(row.get("outcome")=="passed" for row in records)
    successful=bool(report.get("successful")) and failures==0 and errors==0 and executed==discovered
    limits=[]
    if not prior_pass: limits.append("ONE_OR_MORE_MANDATORY_GATES_NOT_PASS")
    if not enough: limits.append("DATABASE_TEST_COUNT_BELOW_297")
    if not no_skips: limits.append("SKIPPED_OR_NONPASS_TEST_RECORDS_PRESENT")
    if not successful: limits.append("RECORDED_DATABASE_SUITE_NOT_SUCCESSFUL")
    ok=successful and prior_pass and enough and no_skips
    return {"status":"PASS" if ok else "FAIL","requirement":REQUIREMENTS["DB-14"],
            "tests":{"tests_run":executed,"discovered":discovered,"failures":failures,"errors":errors,
                     "skipped":skipped,"successful":successful},
            "prior_gates_all_pass":prior_pass,"minimum_test_count":297,
            "test_count_requirement_met":enough,"no_skips":no_skips,"limitations":limits}

def run_gate_verification(admin_url=None,app_url=None,commit=None,diagnostic_checks=None,counted_test_report=None):
    admin_url=admin_url or os.getenv("MIGRATION_TEST_ADMIN_URL") or os.getenv("MIGRATION_DATABASE_URL")
    app_url=app_url or os.getenv("APP_DATABASE_URL")
    if not admin_url or not app_url: raise RuntimeError("GATE_DATABASE_URLS_REQUIRED")
    if not counted_test_report: raise RuntimeError("COUNTED_DATABASE_TEST_REPORT_REQUIRED")
    context={"admin_url":admin_url,"app_url":app_url,"diagnostic_checks":diagnostic_checks or [],"counted_test_report":counted_test_report}
    funcs=(verify_db_01,verify_db_02,verify_db_03,verify_db_04,verify_db_05,verify_db_06,
           verify_db_07,verify_db_08,verify_db_09,verify_db_10,verify_db_11,verify_db_12,verify_db_13)
    gates={}
    for fn in funcs:
        gate=fn.__name__.replace("verify_","").upper().replace("_","-")
        gates[gate]=fn(context)
    gates["DB-14"]=verify_db_14(context,gates)
    awarded=sum(v["status"]=="PASS" for v in gates.values())
    accepted=awarded==14
    final_tests=gates["DB-14"]["tests"]
    return {"contract":"C2C-DB-AC-001 v1.0","commit":commit or os.getenv("GITHUB_SHA") or "working-tree",
            "environment":"isolated synthetic PostgreSQL","run_timestamp":datetime.now(timezone.utc).isoformat(),
            "gate_results":gates,"gate_passes_awarded":awarded,
            "complete_gate_results":"PASS" if accepted else "INCOMPLETE",
            "overall_acceptance":"ACCEPTED" if accepted else "NOT ACCEPTED",
            "total_tests":final_tests["tests_run"],"failures":final_tests["failures"],
            "errors":final_tests["errors"],"skipped":final_tests["skipped"]}
if __name__=="__main__":
    reports=sorted((ROOT/"output"/"database-runs").rglob("counted-tests.json"))
    if len(reports)!=1:
        raise SystemExit("COUNTED_DATABASE_TEST_REPORT_NOT_UNIQUE")
    counted=json.loads(reports[0].read_text())
    report=run_gate_verification(counted_test_report=counted)
    output=ROOT/"output"/"acceptance-diagnostics"/"gate-report.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report["overall_acceptance"]=="ACCEPTED" else 1)

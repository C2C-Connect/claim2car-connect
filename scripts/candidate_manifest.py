import argparse, hashlib, json, subprocess
from pathlib import Path
REQUIRED = ['requirements.txt', 'requirements-database.txt', 'database/__init__.py', 'database/bootstrap.sql', 'database/migrate.py', 'database/journal.py', 'migrations/0001_tenant_registry.sql', 'migrations/0002_event_journal.sql', 'tests/database/seed.sql', 'tests/database/test_journal_integration.py', 'tests/database/test_adapter_validation.py', 'tests/database/test_remaining_integration.py', 'tests/database/test_access_hardening.py', 'tests/database/test_completion_coverage.py', 'tests/database/test_migration_preflight.py', 'tests/database/test_migration_controls_integration.py', 'scripts/candidate_manifest.py', 'scripts/run_database_acceptance.sh', 'scripts/run_guarded_database_acceptance.sh', 'scripts/run_counted_tests.py', 'compose.database-tests.yml', 'app/domain_events.py', 'app/synthetic_evidence.py', 'app/evidence_manifest.py', 'contracts/shot-list.json', 'test_lifecycle.py', 'database/readback.py', 'tests/database/test_event_contract_regression.py', 'tests/database/test_process_recovery.py', 'tests/database/test_tenant_context_regression.py', 'tests/database/verify_gates.py', '.github/workflows/database-smoke-run.yml', 'database/migration_plan.py', 'tests/database/test_migration_plan.py', 'tests/database/test_candidate_manifest.py', 'tests/database/test_counted_runner.py', 'tests/database/test_schema_integrity.py', 'tests/database/test_evidence_finalizer.py', 'migrations/0003_completion_lock.sql', 'tests/database/test_completion_lock.py', 'tests/database/test_locked_evaluation.py', 'migrations/0004_manifest_roots.sql', 'tests/database/test_manifest_roots.py', 'database/eligibility.py', 'tests/database/test_registered_completion.py', 'migrations/0005_completion_receipts.sql', 'tests/database/test_completion_receipts.py', 'database/completion.py', 'tests/database/test_atomic_completion.py', 'tests/database/test_completion_concurrency.py', 'database/receipts.py', 'tests/database/test_receipt_inspection.py', 'tests/database/test_identity_bound_prototype.py']

def snapshot():
    root = Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip()).resolve()
    migration_dir = root / 'migrations'
    if migration_dir.is_symlink():
        raise ValueError('INVALID_CANDIDATE_PATH:migrations')
    names = set(REQUIRED)
    names.update(path.relative_to(root).as_posix() for path in migration_dir.glob('*.sql'))
    rows = []
    for name in sorted(names):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('INVALID_CANDIDATE_PATH:' + name)
        if not path.is_file():
            raise ValueError('REQUIRED_FILE_MISSING:' + name)
        data = path.read_bytes()
        rows.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),'files':rows}

def compare(first, second):
    if first != second:
        raise SystemExit('CANDIDATE_CHANGED_DURING_RUN')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['capture','compare'])
    parser.add_argument('first')
    parser.add_argument('second',nargs='?')
    args=parser.parse_args()
    if args.mode=='capture':
        Path(args.first).write_text(json.dumps(snapshot(),indent=2)+'\n',encoding='utf-8')
    else:
        if args.second is None:
            parser.error('compare requires two manifests')
        compare(json.loads(Path(args.first).read_text()), json.loads(Path(args.second).read_text()))

import argparse, hashlib, json, os, subprocess
from pathlib import Path
REQUIRED = [
 'requirements.txt','requirements-database.txt','database/__init__.py',
 'database/bootstrap.sql','database/migrate.py','database/journal.py',
 'migrations/0001_tenant_registry.sql','migrations/0002_event_journal.sql',
 'tests/database/seed.sql','tests/database/test_journal_integration.py',
 'tests/database/test_adapter_validation.py','tests/database/test_remaining_integration.py',
 'tests/database/test_access_hardening.py','tests/database/test_completion_coverage.py',
 'tests/database/test_migration_preflight.py','tests/database/test_migration_controls_integration.py',
 'scripts/candidate_manifest.py','scripts/run_database_acceptance.sh',
 'scripts/run_guarded_database_acceptance.sh','scripts/run_counted_tests.py',
 'compose.database-tests.yml','app/domain_events.py','app/synthetic_evidence.py',
 'app/evidence_manifest.py','contracts/shot-list.json','test_lifecycle.py']
def snapshot():
    root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip()).resolve()
    for name in REQUIRED:
        p=Path(name)
        if not p.is_file(): raise ValueError('REQUIRED_FILE_MISSING:'+name)
    rows=[]
    for name in sorted(REQUIRED):
        p=Path(name)
        data=p.read_bytes()
        rows.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    return {'head':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),'files':rows}
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['capture','compare'])
    parser.add_argument('first')
    parser.add_argument('second',nargs='?')
    args=parser.parse_args()
    if args.mode=='capture':
        res=snapshot()
        Path(args.first).write_bytes((json.dumps(res,indent=2)+'\n').encode())
    else:
        if json.loads(Path(args.first).read_text())!=json.loads(Path(args.second).read_text()):
            raise SystemExit('CANDIDATE_CHANGED_DURING_RUN')

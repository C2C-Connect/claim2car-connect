import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_bootstrap_credentials_and_permissions(tmp_path):
 s=ROOT/"scripts/oci_staging_runtime_bootstrap.py"; out=tmp_path/"runtime"
 subprocess.run(["python3",str(s),"--dir",str(out)],check=True,capture_output=True,text=True)
 for n in ("runtime.env","postgres-init.sql","seed-tenant.sql","operator-tokens.txt"): assert (out/n).stat().st_mode&0o777==0o600
 assert (out/"capture-runtime.json").stat().st_mode&0o777==0o640
 c=json.loads((out/"capture-runtime.json").read_text()); assert len(c["credentials"])==3
 assert {x["actor_role"] for x in c["credentials"]}=={"owner","operator","reviewer"}
 assert len({x["token_sha256"] for x in c["credentials"]})==3 and all("token" not in x for x in c["credentials"])
 r=subprocess.run(["python3",str(s),"--dir",str(out)],capture_output=True,text=True); assert r.returncode and "NOT_EMPTY" in r.stderr
def test_runtime_deployment_guardrails(tmp_path):
 s=ROOT/"scripts/oci_staging_runtime_bootstrap.py"; out=tmp_path/"runtime"; subprocess.run(["python3",str(s),"--dir",str(out)],check=True,capture_output=True,text=True)
 assert "CREATE DATABASE claim2car" in (out/"postgres-init.sql").read_text()
 assert "tenant_login_bindings" in (out/"seed-tenant.sql").read_text()
 d=(ROOT/"scripts/oci_staging_runtime_deploy.sh").read_text()
 assert "mkfs" not in d and "wipefs" not in d and "rm -rf" not in d
 assert "@sha256:" in d and "mountpoint -q" in d and "python -m database.migrate" in d
 assert "health/ready" in d and "health/build" in d and "127.0.0.1" in d


def test_generated_database_init_is_single_connect_and_postgis(tmp_path):
    script=ROOT/"scripts/oci_staging_runtime_bootstrap.py"; out=tmp_path/"runtime"
    subprocess.run(["python3",str(script),"--dir",str(out)],check=True,capture_output=True,text=True)
    sql=(out/"postgres-init.sql").read_text()
    assert sql.count("\\connect claim2car")==1
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql

def test_deploy_script_shell_syntax_and_expanded_variables():
    script=ROOT/"scripts/oci_staging_runtime_deploy.sh"
    subprocess.run(["bash","-n",str(script)],check=True)
    content=script.read_text()
    assert "\\${OCI_IMAGE_REF" not in content
    assert "PGDATA=/var/lib/postgresql/data/pgdata" in content
    assert "podman-restart.service" in content


def test_host_bootstrap_installs_deploy_dependencies():
    cloud=(ROOT/"infra/oci/staging/cloud-init.yaml").read_text()
    assert "  - git" in cloud and "  - curl" in cloud


def test_runtime_deploy_requires_digest_pinned_database_and_distinct_mounts():
    d=(ROOT/"scripts/oci_staging_runtime_deploy.sh").read_text()
    assert "C2C_POSTGRES_IMAGE must be pinned by sha256 digest" in d
    assert "findmnt -rn -o SOURCE --mountpoint" in d
    assert "PostgreSQL and evidence storage must be distinct mounted volumes" in d
    assert "Storage mount root must be UID 10001" in d
    assert "runtime.env must be root-owned mode 0600" in d
    assert "capture-runtime.json must be root-owned mode 0640" in d
    assert "Existing PostgreSQL container is bound to unexpected storage" in d
    assert "Existing PostgreSQL container image differs from requested digest" in d


def test_synthetic_live_staging_acceptance_harness_is_16_slot_and_guarded():
    script=ROOT/"scripts/oci_staging_capture_acceptance.py"
    subprocess.run(["python3","-m","py_compile",str(script)],check=True)
    result=subprocess.run(["python3",str(script),"--help"],capture_output=True,text=True,check=True)
    assert "--confirm-synthetic" in result.stdout
    source=script.read_text()
    from app.capture_protocols import resolve_capture_protocol
    assert source.count('"00_front_exterior"')==1
    slots=resolve_capture_protocol().slots
    assert len(slots)==16
    assert all(f'"{slot}"' in source for slot in slots)
    assert all(part in source for part in ('\"podman\"', '\"restart\"', '\"claim2car-app\"'))
    assert "EVIDENCE_ARTIFACT_CONFLICT" in source
    assert "atexit.register(cleanup_synthetic_consent)" in source
    assert "automatic consent cleanup failed" in source
    assert "withdrawal did not remove synthetic original bytes" in source
    assert "base-url must be HTTP loopback only" in source
    missing_confirmation=subprocess.run(["python3",str(script)],capture_output=True,text=True)
    assert missing_confirmation.returncode==2
    assert "confirm-synthetic" in missing_confirmation.stderr

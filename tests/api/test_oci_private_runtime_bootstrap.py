import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_bootstrap_credentials_and_permissions(tmp_path):
 s=ROOT/"scripts/oci_staging_runtime_bootstrap.py"; out=tmp_path/"runtime"
 subprocess.run(["python3",str(s),"--dir",str(out)],check=True,capture_output=True,text=True)
 for n in ("runtime.env","capture-runtime.json","postgres-init.sql","seed-tenant.sql","operator-tokens.txt"): assert (out/n).stat().st_mode&0o777==0o600
 assert out.stat().st_mode&0o777==0o700
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

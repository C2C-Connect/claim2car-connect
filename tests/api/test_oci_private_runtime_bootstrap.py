import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def _read_root_owned_file(path: Path) -> str:
    sudo=subprocess.run(["sudo","cat",str(path)],check=True,capture_output=True,text=True)
    return sudo.stdout
def test_bootstrap_credentials_and_permissions(tmp_path):
 s=ROOT/"scripts/oci_staging_runtime_bootstrap.py"; out=tmp_path/"runtime"
 subprocess.run(["python3",str(s),"--dir",str(out)],check=True,capture_output=True,text=True)
 for n in ("runtime.env","postgres-init.sql","seed-tenant.sql","operator-tokens.txt"): assert (out/n).stat().st_mode&0o777==0o600
 runtime_env=(out/"runtime.env").read_text()
 for name in ("SQUARE_ENVIRONMENT","SQUARE_SANDBOX_ACCESS_TOKEN","SQUARE_SANDBOX_LOCATION_ID","SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY","SQUARE_SANDBOX_WEBHOOK_URL"):
  assert f"export {name}=" in runtime_env
  assert f"export {name}=''" in runtime_env
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
 for name in ("SQUARE_ENVIRONMENT","SQUARE_SANDBOX_ACCESS_TOKEN","SQUARE_SANDBOX_LOCATION_ID","SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY","SQUARE_SANDBOX_WEBHOOK_URL"):
  assert f"-e {name}=" in d


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
    assert 'mktemp /run/claim2car-ocir-auth.' in content
    assert 'podman login --authfile "$authfile"' in content
    assert 'podman pull --authfile "$authfile"' in content
    assert 'trap cleanup_authfile EXIT' in content
    assert content.index('trap cleanup_authfile EXIT') < content.index('chmod 0600 "$authfile"')
    assert 'cleanup_authfile\ntrap - EXIT' in content
    assert 'unset REGISTRY_TOKEN' in content
    assert 'OCI_IMAGE_REF must use the authenticated OCI_REGISTRY host' in content
    assert 'podman image inspect "$DB_IMAGE" --format' in content
    assert 'Expected ARM64 PostgreSQL image' in content
    assert '--read-only --cap-drop=ALL --security-opt=no-new-privileges' in content
    assert '--tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001' in content
    assert '--user 10001:10001' in content
    assert 'PostgreSQL storage mount root must be mode 0750' in content
    assert 'Evidence storage mount root must be mode 0700' in content
    entrypoint=ROOT/"config/claim2car-entrypoint.sh"
    subprocess.run(["sh","-n",str(entrypoint)],check=True)
    entry_content=entrypoint.read_text()
    assert "EVIDENCE_STORAGE_OWNER_OR_MODE_INVALID" in entry_content
    assert 'exec "$@"' in entry_content
    assert 'podman login "$REGISTRY"' not in content


def test_host_bootstrap_installs_deploy_dependencies():
    cloud=(ROOT/"infra/oci/staging/cloud-init.yaml").read_text()
    assert "  - git" in cloud and "  - curl" in cloud


def test_runtime_deploy_requires_digest_pinned_database_and_distinct_mounts():
    d=(ROOT/"scripts/oci_staging_runtime_deploy.sh").read_text()
    assert "C2C_POSTGRES_IMAGE must be pinned by sha256 digest" in d
    assert "findmnt -rn -o SOURCE --mountpoint" in d
    assert "PostgreSQL and evidence storage must be distinct mounted volumes" in d
    assert "Storage mount root must be UID/GID 10001" in d
    assert "PostgreSQL storage mount root must be mode 0750" in d
    assert "Evidence storage mount root must be mode 0700" in d
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
    assert "unsafe path components" in source
    assert "must not be symlinks" in source
    assert "tenant_dir.is_symlink()" in source
    assert source.rindex("withdrawal did not remove synthetic original bytes") < source.rindex("CLEANUP_CONSENT = False")
    missing_confirmation=subprocess.run(["python3",str(script)],capture_output=True,text=True)
    assert missing_confirmation.returncode==2
    assert "confirm-synthetic" in missing_confirmation.stderr

def test_synthetic_original_path_guard_rejects_unsafe_components(tmp_path):
    import importlib.util
    script = ROOT / "scripts" / "oci_staging_capture_acceptance.py"
    spec = importlib.util.spec_from_file_location("c2c_staging_acceptance_path", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for bad in ("", ".", "..", "../escape", "tenant\\escape"):
        try:
            module.synthetic_original_path(tmp_path, bad, "session", "artifact")
        except RuntimeError as exc:
            assert "unsafe path components" in str(exc)
        else:
            raise AssertionError(f"unsafe tenant component accepted: {bad!r}")


def test_synthetic_original_path_guard_rejects_symlinked_tenant_and_artifact(tmp_path):
    import importlib.util
    script = ROOT / "scripts" / "oci_staging_capture_acceptance.py"
    spec = importlib.util.spec_from_file_location("c2c_staging_acceptance_path_symlink", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "evidence"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (root / "tenant").symlink_to(target, target_is_directory=True)
    try:
        module.synthetic_original_path(root, "tenant", "session", "artifact")
    except RuntimeError as exc:
        assert "must not be symlinks" in str(exc)
    else:
        raise AssertionError("symlinked tenant directory accepted")
    (root / "tenant").unlink()
    real_root = tmp_path / "evidence-real"
    real_root.mkdir()
    real_tenant = real_root / "tenant"
    real_tenant.mkdir()
    real_session = real_tenant / "session"
    real_session.mkdir()
    (real_session / "artifact.original").write_bytes(b"synthetic")
    root_link = tmp_path / "evidence-link"
    root_link.symlink_to(real_root, target_is_directory=True)
    try:
        module.synthetic_original_path(root_link, "tenant", "session", "artifact")
    except RuntimeError as exc:
        assert "must not be symlinks" in str(exc)
    else:
        raise AssertionError("symlinked evidence root accepted")
    tenant = root / "tenant"
    tenant.mkdir()
    session_target = tmp_path / "session-target"
    session_target.mkdir()
    session = tenant / "session"
    session.symlink_to(session_target, target_is_directory=True)
    try:
        module.synthetic_original_path(root, "tenant", "session", "artifact")
    except RuntimeError as exc:
        assert "must not be symlinks" in str(exc)
    else:
        raise AssertionError("symlinked session directory accepted")
    session.unlink()
    session.mkdir()
    (session / "artifact.original").symlink_to(target / "payload")
    try:
        module.synthetic_original_path(root, "tenant", "session", "artifact")
    except RuntimeError as exc:
        assert "must not be symlinks" in str(exc)
    else:
        raise AssertionError("symlinked original artifact accepted")


def test_synthetic_original_path_guard_accepts_regular_file(tmp_path):
    import importlib.util
    script = ROOT / "scripts" / "oci_staging_capture_acceptance.py"
    spec = importlib.util.spec_from_file_location("c2c_staging_acceptance_path_regular", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "tenant" / "session" / "artifact.original"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic")
    assert module.synthetic_original_path(tmp_path, "tenant", "session", "artifact") == path


def test_capture_acceptance_source_revision_guard(monkeypatch, tmp_path):
    import importlib.util
    script = ROOT / "scripts" / "oci_staging_capture_acceptance.py"
    spec = importlib.util.spec_from_file_location("c2c_staging_acceptance_revision", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sha = "a" * 40
    calls = []
    def fake_run(args, cwd, capture_output, text, check):
        calls.append(args)
        if args == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, sha + "\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.verify_source_checkout(sha, tmp_path)
    assert calls == [["git", "rev-parse", "HEAD"], ["git", "status", "--porcelain"]]
    for invalid in ("shortsha", "A" * 40, "f" * 39, "f" * 41):
        try:
            module.verify_source_checkout(invalid, tmp_path)
        except RuntimeError as exc:
            assert "full 40-character commit SHA" in str(exc)
        else:
            raise AssertionError(f"invalid build revision accepted: {invalid!r}")

    def mismatched_run(args, cwd, capture_output, text, check):
        return subprocess.CompletedProcess(args, 0, "b" * 40 + "\n", "") if args[-1] == "HEAD" else subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(module.subprocess, "run", mismatched_run)
    try:
        module.verify_source_checkout(sha, tmp_path)
    except RuntimeError as exc:
        assert "revision mismatch" in str(exc)
    else:
        raise AssertionError("source revision mismatch accepted")

    def dirty_run(args, cwd, capture_output, text, check):
        return subprocess.CompletedProcess(args, 0, sha + "\n", "") if args[-1] == "HEAD" else subprocess.CompletedProcess(args, 0, " M file.py\n", "")
    monkeypatch.setattr(module.subprocess, "run", dirty_run)
    try:
        module.verify_source_checkout(sha, tmp_path)
    except RuntimeError as exc:
        assert "uncommitted or untracked changes" in str(exc)
    else:
        raise AssertionError("dirty source checkout accepted")


def test_runtime_deploy_verifies_exact_revision_for_rollback_and_only_records_ready_image():
    script=ROOT/"scripts/oci_staging_runtime_deploy.sh"
    subprocess.run(["bash","-n",str(script)],check=True)
    content=script.read_text()
    assert "image_revision()" in content
    assert "wait_for_app()" in content
    assert 'data.get("revision")==sys.argv[1]' in content
    assert "grep -Fq \"$expected_revision\"" not in content
    assert 'wait_for_app "$revision"' in content
    assert 'if ! run_app "$IMAGE_REF" || ! wait_for_app "$revision"; then' in content
    assert 'if run_app "$previous" && wait_for_app "$previous_revision"; then' in content
    assert 'previous_revision="$(image_revision "$previous")"' in content
    assert 'wait_for_app "$previous_revision"' in content
    assert "rollback image readiness and exact revision verified" in content
    assert "rollback image also failed readiness/revision verification" in content
    assert "Database migrations are not automatically reversed" in content
    record_image_line=content.index("printf",content.index("systemctl enable --now podman-restart.service"))
    assert content.index('wait_for_app "$revision"') < record_image_line


def _oci_deploy_harness(tmp_path, image_ref, previous_ref="", fail_ready_sha="", fail_launch_sha="", fail_rollback_sha=""):
    import os
    import shutil
    import pytest

    sudo=shutil.which("sudo")
    if not sudo:
        pytest.skip("sudo is required for root-owned OCI staging deployment harness")
    fakebin=tmp_path/"fakebin"; fakebin.mkdir()
    state=tmp_path/"state"; state.mkdir()
    root=tmp_path/"claim2car"; config=tmp_path/"runtime"
    (root/"postgres").mkdir(parents=True); (root/"evidence").mkdir(parents=True)
    config.mkdir()
    (config/"runtime.env").write_text(
        "export PG_ADMIN_PASSWORD=test-admin\n"
        "export MIGRATION_DATABASE_URL=postgresql://faos_migrator:test@claim2car-db:5432/claim2car\n"
        "export APP_DATABASE_URL=postgresql://faos_app:test@claim2car-db:5432/claim2car\n"
        "export C2C_INTERNAL_SERVICE_TOKEN=test-service\n"
        "export C2C_VIN_HMAC_PEPPER=test-pepper\n"
        "export SQUARE_ENVIRONMENT=''\n"
        "export SQUARE_SANDBOX_ACCESS_TOKEN=''\n"
        "export SQUARE_SANDBOX_LOCATION_ID=''\n"
        "export SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY=''\n"
        "export SQUARE_SANDBOX_WEBHOOK_URL=''\n"
    )
    for name in ("capture-runtime.json","postgres-init.sql","seed-tenant.sql"):
        (config/name).write_text("{}\n")
    if previous_ref:
        (config/"last-image-ref").write_text(previous_ref+"\n")
    pg=root/"postgres"; ev=root/"evidence"
    (pg/"pgdata").mkdir()
    os.chmod(pg,0o750); os.chmod(ev,0o700)
    subprocess.run([sudo,"chown","-R","10001:10001",str(pg),str(ev)],check=True)
    subprocess.run([sudo,"chown","root:root",str(config)],check=True)
    subprocess.run([sudo,"chmod","700",str(config)],check=True)
    subprocess.run([sudo,"chown","root:root",str(config/"runtime.env")],check=True)
    subprocess.run([sudo,"chmod","600",str(config/"runtime.env")],check=True)
    subprocess.run([sudo,"chown","root:root",str(config/"postgres-init.sql"),str(config/"seed-tenant.sql")],check=True)
    subprocess.run([sudo,"chmod","600",str(config/"postgres-init.sql"),str(config/"seed-tenant.sql")],check=True)
    subprocess.run([sudo,"chown","root:10001",str(config/"capture-runtime.json")],check=True)
    subprocess.run([sudo,"chmod","640",str(config/"capture-runtime.json")],check=True)
    if previous_ref:
        subprocess.run([sudo,"chown","root:root",str(config/"last-image-ref")],check=True)
        subprocess.run([sudo,"chmod","600",str(config/"last-image-ref")],check=True)

    podman_script = """#!/usr/bin/env python3
import os, re, sys
from pathlib import Path
args=sys.argv[1:]
state=Path(os.environ["STATE"])
if args[:2]==["image","inspect"]:
    print("linux/arm64" if "{{.Os}}/{{.Architecture}}" in args else "image-id")
    sys.exit(0)
if args[:2]==["container","exists"]:
    sys.exit(1)
if args[:2]==["network","exists"]:
    sys.exit(0)
if args and args[0]=="run":
    if "--name" in args and args[args.index("--name")+1]=="claim2car-app":
        ref=args[-1]
        match=re.search(r":sha-([a-f0-9]{40})@",ref)
        sha=match.group(1) if match else ""
        if sha==os.environ.get("FAIL_LAUNCH_SHA",""):
            sys.exit(42)
        (state/"current-app").write_text(ref)
    sys.exit(0)
if args and args[0] in ("stop","rm"):
    if "claim2car-app" in args:
        (state/"current-app").unlink(missing_ok=True)
    sys.exit(0)
sys.exit(0)
"""
    curl_script = """#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
url=sys.argv[-1]
ref=(Path(os.environ["STATE"])/"current-app").read_text() if (Path(os.environ["STATE"])/"current-app").exists() else ""
match=re.search(r":sha-([a-f0-9]{40})@",ref)
sha=match.group(1) if match else ""
if url.endswith("/health/ready"):
    sys.exit(1 if sha in (os.environ.get("FAIL_READY_SHA",""),os.environ.get("FAIL_ROLLBACK_SHA","")) and sha else 0)
if url.endswith("/health/build"):
    print(json.dumps({"revision":sha,"runtime_mode":"integrated"}))
    sys.exit(0)
sys.exit(0)
"""
    simple = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
    findmnt_script = "#!/usr/bin/env python3\nimport sys\nprint('/dev/fake-postgres' if 'postgres' in sys.argv[-1] else '/dev/fake-evidence')\n"
    for name,script in {
        "podman":podman_script,"curl":curl_script,"systemctl":simple,
        "mountpoint":simple,"sleep":simple,"findmnt":findmnt_script,
    }.items():
        p=fakebin/name; p.write_text(script); p.chmod(0o755)
    env={
        "PATH":str(fakebin)+":/usr/bin:/bin",
        "STATE":str(state),
        "FAIL_READY_SHA":fail_ready_sha,
        "FAIL_LAUNCH_SHA":fail_launch_sha,
        "FAIL_ROLLBACK_SHA":fail_rollback_sha,
        "C2C_STAGING_ROOT":str(root),
        "C2C_STAGING_RUNTIME_CONFIG":str(config),
        "OCI_IMAGE_REF":image_ref,
        "OCI_REGISTRY":"registry.example.test",
        "OCI_REGISTRY_USERNAME":"test-user",
        "OCI_REGISTRY_TOKEN":"test-token",
        "C2C_POSTGRES_IMAGE":"registry.example.test/ns/postgres@sha256:"+"b"*64,
        "C2C_STAGING_LOOPBACK_PORT":"18000",
    }
    command=[sudo,"env"]+[f"{k}={v}" for k,v in env.items()]+["bash",str(ROOT/"scripts/oci_staging_runtime_deploy.sh")]
    return command,state,config


def _pinned_image(revision, digest):
    return f"registry.example.test/ns/app:sha-{revision}@sha256:{digest}"


def _oci_harness_cleanup(tmp_path):
    import shutil
    sudo=shutil.which("sudo")
    if sudo:
        subprocess.run([sudo,"rm","-rf","--",str(tmp_path)],check=False,capture_output=True)


def test_oci_runtime_deploy_harness_success_records_verified_image(tmp_path):
    revision="a"*40; image=_pinned_image(revision,"c"*64)
    command,state,config=_oci_deploy_harness(tmp_path,image)
    try:
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode==0, result.stderr
        assert _read_root_owned_file(config/"last-image-ref").strip()==image
        assert (state/"current-app").read_text()==image
        assert "PASS: image deployed, readiness and exact revision checked" in result.stdout
    finally:
        _oci_harness_cleanup(tmp_path)


def test_oci_runtime_deploy_harness_rolls_back_after_readiness_failure(tmp_path):
    new_revision="a"*40; old_revision="b"*40
    new_image=_pinned_image(new_revision,"c"*64); old_image=_pinned_image(old_revision,"d"*64)
    command,state,config=_oci_deploy_harness(tmp_path,new_image,old_image,fail_ready_sha=new_revision)
    try:
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0
        assert "previous image was restored and verified" in result.stderr
        assert (state/"current-app").read_text()==old_image
        assert _read_root_owned_file(config/"last-image-ref").strip()==old_image
    finally:
        _oci_harness_cleanup(tmp_path)


def test_oci_runtime_deploy_harness_rolls_back_after_container_start_failure(tmp_path):
    new_revision="a"*40; old_revision="b"*40
    new_image=_pinned_image(new_revision,"c"*64); old_image=_pinned_image(old_revision,"d"*64)
    command,state,config=_oci_deploy_harness(tmp_path,new_image,old_image,fail_launch_sha=new_revision)
    try:
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0
        assert "previous image was restored and verified" in result.stderr
        assert (state/"current-app").read_text()==old_image
        assert _read_root_owned_file(config/"last-image-ref").strip()==old_image
    finally:
        _oci_harness_cleanup(tmp_path)


def test_oci_runtime_deploy_harness_fails_if_rollback_image_is_unhealthy(tmp_path):
    new_revision="a"*40; old_revision="b"*40
    new_image=_pinned_image(new_revision,"c"*64); old_image=_pinned_image(old_revision,"d"*64)
    command,state,config=_oci_deploy_harness(tmp_path,new_image,old_image,fail_ready_sha=new_revision,fail_rollback_sha=old_revision)
    try:
        result=subprocess.run(command,capture_output=True,text=True)
        assert result.returncode!=0
        assert "rollback image also failed readiness/revision verification" in result.stderr
        assert not (state/"current-app").exists()
        assert _read_root_owned_file(config/"last-image-ref").strip()==old_image
    finally:
        _oci_harness_cleanup(tmp_path)


def test_oci_deploy_harness_cleans_root_owned_tmp_paths():
    content=(ROOT/"tests/api/test_oci_private_runtime_bootstrap.py").read_text()
    assert "def _oci_harness_cleanup(tmp_path):" in content
    assert 'sudo,"rm","-rf","--",str(tmp_path)' in content
    assert content.count("_oci_harness_cleanup(tmp_path)") >= 4


def test_oci_deploy_harness_uses_privileged_file_read_and_cleanup_helpers():
    content=(ROOT/"tests/api/test_oci_private_runtime_bootstrap.py").read_text()
    assert "def _read_root_owned_file(path):" in content
    assert 'sudo,"cat",str(path)' in content
    assert content.count('_read_root_owned_file(config/"last-image-ref")') >= 4
    assert "def _oci_harness_cleanup(tmp_path):" in content
    assert 'sudo,"rm","-rf","--",str(tmp_path)' in content


def test_root_owned_last_image_ref_assertions_use_sudo_reader():
    content=(ROOT/"tests/api/test_oci_private_runtime_bootstrap.py").read_text()
    assert content.count('_read_root_owned_file(config/"last-image-ref")') >= 4

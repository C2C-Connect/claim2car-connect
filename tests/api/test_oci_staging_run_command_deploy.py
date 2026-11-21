from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
MODULE_PATH=ROOT/"scripts/oci_staging_run_command_deploy.py"
spec=importlib.util.spec_from_file_location("oci_run_command_deploy",MODULE_PATH)
deploy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def _remote_script():
    sha="a"*40
    image=f"us-chicago-1.ocir.io/ns/repo:sha-{sha}@sha256:"+"b"*64
    hashes={name:"c"*64 for name in deploy.SCRIPT_NAMES}
    return deploy.build_remote_script(
        source_sha=sha,
        region="us-chicago-1",
        registry="us-chicago-1.ocir.io",
        registry_username="test-user",
        image_ref=image,
        postgres_image="docker.io/library/postgres@sha256:"+"d"*64,
        vault_secret_ocid="ocid1.secret.oc1.test",
        hashes=hashes,
    )


def test_image_reference_requires_source_sha_digest_and_repository_alignment():
    sha="a"*40
    image=f"us-chicago-1.ocir.io/ns/repo:sha-{sha}@sha256:"+"b"*64
    assert deploy.validate_image_ref(image,"us-chicago-1.ocir.io","ns","repo")==sha
    with pytest.raises(ValueError):
        deploy.validate_image_ref(image,"us-chicago-1.ocir.io","other","repo")
    with pytest.raises(ValueError):
        deploy.extract_source_sha("repo:latest")
    with pytest.raises(ValueError):
        deploy.validate_image_ref(image.replace("sha256:","sha256:bad"),"us-chicago-1.ocir.io","ns","repo")


def test_remote_run_command_script_is_small_pinned_and_does_not_embed_token():
    script=_remote_script()
    assert len(script.encode())<3900
    assert "sha256sum -c -" in script
    assert "instance_principal" in script
    assert "--region" in script
    assert "claim2car-runtime-deploy" in script
    assert "claim2car-runtime-acceptance" in script
    assert "OCI_REGISTRY_TOKEN" in script
    assert "super-secret-token-value" not in script
    assert "C2C_DEPLOY_SCRIPT_PATH" in script
    assert "C2C_ACCEPTANCE_SCRIPT_PATH" in script


def test_run_command_create_and_execution_polling_success(tmp_path,monkeypatch):
    fakebin=tmp_path/"bin"; fakebin.mkdir()
    state=tmp_path/"state"; state.mkdir()
    cli=fakebin/"oci"
    cli.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
state=Path(os.environ["FAKE_OCI_STATE"])
if args[:3]==["instance-agent","command","create"]:
    content=Path(args[args.index("--content")+1].removeprefix("file://")).read_text()
    target=Path(args[args.index("--target")+1].removeprefix("file://")).read_text()
    (state/"content.json").write_text(content)
    (state/"target.json").write_text(target)
    print(json.dumps({"data":{"id":"ocid1.command.test"}}))
elif args[:3]==["instance-agent","command-execution","get"]:
    counter=state/"polls"
    n=int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n+1))
    state_name="IN_PROGRESS" if n==0 else "SUCCEEDED"
    print(json.dumps({"data":{"lifecycleState":state_name,"content":{"exitCode":0,"message":"","text":"acceptance PASS"}}}))
else:
    sys.exit(2)
""")
    cli.chmod(0o755)
    monkeypatch.setenv("PATH",str(fakebin)+os.pathsep+os.environ.get("PATH",""))
    monkeypatch.setenv("FAKE_OCI_STATE",str(state))
    result=deploy.execute_command(compartment_ocid="ocid1.compartment.test",instance_ocid="ocid1.instance.test",
                                  script=_remote_script(),display_name="test deploy",poll_seconds=0,max_wait_seconds=10)
    assert result["command_id"]=="ocid1.command.test"
    assert result["lifecycle_state"]=="SUCCEEDED"
    assert result["text"]=="acceptance PASS"
    content=json.loads((state/"content.json").read_text())
    target=json.loads((state/"target.json").read_text())
    assert content["source"]["sourceType"]=="TEXT"
    assert content["source"]["text"].startswith("#!/usr/bin/env bash")
    assert target=={"instanceId":"ocid1.instance.test"}


def test_run_command_failure_reports_terminal_state_and_exit_code(tmp_path,monkeypatch):
    fakebin=tmp_path/"bin"; fakebin.mkdir()
    cli=fakebin/"oci"
    cli.write_text("""#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
if args[:3]==["instance-agent","command","create"]:
 print(json.dumps({"data":{"id":"ocid1.command.fail"}}))
elif args[:3]==["instance-agent","command-execution","get"]:
 print(json.dumps({"data":{"lifecycle-state":"FAILED","content":{"exit-code":2,"message":"deploy acceptance failed","text":"FAIL: test-only"}}}))
else:
 sys.exit(2)
""")
    cli.chmod(0o755)
    monkeypatch.setenv("PATH",str(fakebin)+os.pathsep+os.environ.get("PATH",""))
    with pytest.raises(RuntimeError,match="FAILED"):
        deploy.execute_command(compartment_ocid="ocid1.compartment.test",instance_ocid="ocid1.instance.test",
                               script=_remote_script(),display_name="fail",poll_seconds=0,max_wait_seconds=10)


def test_cloud_init_installs_oci_cli_and_limits_ocarun_sudo_to_wrappers():
    content=(ROOT/"infra/oci/staging/cloud-init.yaml").read_text()
    assert "  - oci-cli" in content
    assert "ocarun ALL=(root) NOPASSWD: SETENV:" in content
    for wrapper in ("claim2car-runtime-bootstrap","claim2car-runtime-deploy","claim2car-runtime-acceptance"):
        assert f"/usr/local/sbin/{wrapper}" in content


def test_terraform_enables_instance_agent_run_command_plugin():
    content=(ROOT/"infra/oci/staging/main.tf").read_text()
    assert 'name          = "Compute Instance Run Command"' in content
    assert 'desired_state = "ENABLED"' in content
    assert "is_management_disabled  = false" in content

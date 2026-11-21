from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/oci_staging_runcommand_deploy.py"
spec = importlib.util.spec_from_file_location("oci_runcommand_deploy", SCRIPT)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def _valid_env():
    commit = "a" * 40
    return {
        "OCI_COMPARTMENT_OCID": "ocid1.compartment.oc1..compartment",
        "OCI_STAGING_INSTANCE_OCID": "ocid1.instance.oc1..instance",
        "OCI_REGISTRY": "us-chicago-1.ocir.io",
        "OCIR_NAMESPACE": "namespace",
        "OCIR_REPOSITORY": "claim2car",
        "OCI_OCIR_AUTH_SECRET_OCID": "ocid1.vaultsecret.oc1..secret",
        "C2C_IMAGE_REF": f"us-chicago-1.ocir.io/namespace/claim2car:sha-{commit}@sha256:" + "b" * 64,
        "C2C_POSTGRES_IMAGE": "us-chicago-1.ocir.io/namespace/postgres@sha256:" + "c" * 64,
        "C2C_DEPLOY_SCRIPT_SHA256": "d" * 64,
    }


def test_runcommand_deploy_validates_exact_ocir_repository_and_digest():
    values = deploy.validate_inputs(_valid_env())
    assert values["C2C_IMAGE_COMMIT"] == "a" * 40


def test_runcommand_deploy_rejects_image_tag_commit_mismatch():
    env = _valid_env()
    env["C2C_IMAGE_REF"] = env["C2C_IMAGE_REF"].replace("sha-" + "a" * 40, "sha-" + "e" * 40)
    with pytest.raises(ValueError, match="configured OCIR repo"):
        deploy.validate_inputs(env)


def test_runcommand_deploy_rejects_unpinned_database_image():
    env = _valid_env()
    env["C2C_POSTGRES_IMAGE"] = "us-chicago-1.ocir.io/namespace/postgres:latest"
    with pytest.raises(ValueError, match="digest-pinned"):
        deploy.validate_inputs(env)


def test_runcommand_payload_is_secret_free_and_shell_safe():
    values = deploy.validate_inputs(_valid_env())
    text = deploy.build_command_text(values)
    assert "sudo -n /usr/local/sbin/claim2car-staging-deploy" in text
    assert values["OCI_OCIR_AUTH_SECRET_OCID"] in text
    assert values["C2C_IMAGE_REF"] in text
    assert "OCI_REGISTRY_TOKEN" not in text
    assert "auth_token" not in text
    assert len(text.encode()) <= 4096


def test_submit_command_sends_text_content_and_exact_instance_target(tmp_path):
    values = deploy.validate_inputs(_valid_env())
    text = deploy.build_command_text(values)
    output = subprocess.CompletedProcess([], 0, stdout="ocid1.instanceagentcommand.oc1..command\n", stderr="")
    with patch.object(deploy, "_run_cli", return_value=output) as run:
        command_id = deploy.submit_command(values, text)
    assert command_id == "ocid1.instanceagentcommand.oc1..command"
    args = run.call_args.args[0]
    content_file = Path(args[args.index("--content") + 1].removeprefix("file://"))
    target_file = Path(args[args.index("--target") + 1].removeprefix("file://"))
    # Temp files are intentionally removed when submit_command returns.
    assert not content_file.exists() and not target_file.exists()
    assert args[args.index("--timeout-in-seconds") + 1] == "1800"


def test_poll_command_returns_success_for_exact_command_id():
    values = deploy.validate_inputs(_valid_env())
    response = subprocess.CompletedProcess(
        [], 0, stdout=json.dumps({"data": [{"commandId": "wanted", "lifecycleState": "SUCCEEDED"}]}), stderr=""
    )
    with patch.object(deploy, "_run_cli", return_value=response), patch.object(deploy.time, "sleep"):
        assert deploy.poll_command(values, "wanted", timeout=1, interval=0) == "SUCCEEDED"


def test_poll_command_fails_closed_for_failed_execution():
    values = deploy.validate_inputs(_valid_env())
    response = subprocess.CompletedProcess(
        [], 0, stdout=json.dumps({"data": [{"commandId": "wanted", "lifecycleState": "FAILED"}]}), stderr=""
    )
    with patch.object(deploy, "_run_cli", return_value=response), patch.object(deploy.time, "sleep"):
        with pytest.raises(RuntimeError, match="FAILED"):
            deploy.poll_command(values, "wanted", timeout=1, interval=0)


def test_cloud_init_enables_private_runcommand_without_broad_sudo():
    cloud_init=(ROOT/"infra/oci/staging/cloud-init.yaml").read_text()
    assert "oci-cli==3.96.3" in cloud_init
    terraform=(ROOT/"infra/oci/staging/main.tf").read_text()
    assert 'name = "Compute Instance Run Command"' in terraform
    assert 'desired_state = "ENABLED"' in terraform
    assert "ocarun ALL=(root) NOPASSWD: /usr/local/sbin/claim2car-staging-deploy" in cloud_init
    assert "NOPASSWD:ALL" not in cloud_init
    assert "ocir_auth_secret" in cloud_init or "secret-bundle get" in cloud_init


def test_terraform_runcommand_secret_access_is_scoped_to_secret_ocid():
    terraform=(ROOT/"infra/oci/staging/main.tf").read_text()
    variables=(ROOT/"infra/oci/staging/variables.tf").read_text()
    assert "enable_private_runcommand_deploy" in variables
    assert "target.secret.id='${var.ocir_auth_secret_ocid}'" in terraform
    assert "instance.id = '${oci_core_instance.staging.id}'" in terraform


def test_private_runtime_deploy_workflow_is_manual_main_only_and_secret_free():
    workflow=(ROOT/".github/workflows/oci-staging-runtime-deploy.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/main' && inputs.confirm_deploy == 'yes'" in workflow
    assert "environment: oci-staging-apply" in workflow
    assert "OCI_OCIR_AUTH_SECRET_OCID" in workflow
    assert "OCI_REGISTRY_TOKEN" not in workflow
    assert "OCIR_AUTH_TOKEN" not in workflow
    assert "scripts/oci_staging_runcommand_deploy.py" in workflow
    assert "persist-credentials: false" in workflow

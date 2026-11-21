#!/usr/bin/env python3
"""Submit a digest-pinned deployment and synthetic acceptance through OCI Run Command."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_RE = re.compile(r":sha-([0-9a-f]{40})@(sha256:[0-9a-f]{64})$")
REPO = "C2C-Connect/claim2car-connect"
SCRIPT_NAMES = {
    "bootstrap": "oci_staging_runtime_bootstrap.py",
    "deploy": "oci_staging_runtime_deploy.sh",
    "acceptance": "oci_staging_capture_acceptance.py",
}


def extract_source_sha(image_ref: str) -> str:
    match = IMAGE_RE.search(image_ref)
    if not match:
        raise ValueError("OCI image reference must include :sha-<40hex>@sha256:<64hex>.")
    return match.group(1)


def validate_image_ref(image_ref: str, registry: str, namespace: str, repository: str) -> str:
    source_sha = extract_source_sha(image_ref)
    prefix = f"{registry}/{namespace}/{repository}:sha-{source_sha}@"
    if not image_ref.startswith(prefix):
        raise ValueError("Image reference does not match the configured OCIR registry/namespace/repository.")
    if not DIGEST_RE.fullmatch(image_ref.split("@", 1)[1]):
        raise ValueError("Image reference must be pinned to a full SHA-256 digest.")
    return source_sha


def q(value: str) -> str:
    return shlex.quote(value)


def build_remote_script(
    *,
    source_sha: str,
    region: str,
    registry: str,
    registry_username: str,
    image_ref: str,
    postgres_image: str,
    vault_secret_ocid: str,
    hashes: dict[str, str],
) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", region):
        raise ValueError("Invalid OCI region.")
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be a full 40-character lowercase SHA.")
    if extract_source_sha(image_ref) != source_sha:
        raise ValueError("OCI image source revision and source checkout SHA differ.")
    if not re.fullmatch(r"^(docker\.io|registry-1\.docker\.io)/postgis/postgis:16-[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$", postgres_image):
        raise ValueError("PostGIS 16 image must be pinned by sha256 digest.")
    for name in SCRIPT_NAMES:
        if not re.fullmatch(r"[0-9a-f]{64}", hashes.get(name, "")):
            raise ValueError(f"Missing/invalid checksum for {name} script.")
    if not vault_secret_ocid.startswith("ocid1.secret."):
        raise ValueError("OCIR token Vault secret OCID is invalid.")

    urls = {
        name: f"https://raw.githubusercontent.com/{REPO}/{source_sha}/scripts/{filename}"
        for name, filename in SCRIPT_NAMES.items()
    }
    paths = {
        name: f"/tmp/claim2car-runtime-{name}-{source_sha}.{ 'py' if name != 'deploy' else 'sh' }"
        for name, filename in SCRIPT_NAMES.items()
    }
    lines = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "umask 077",
        f"C2C_SOURCE_SHA={q(source_sha)}",
        f"C2C_BOOTSTRAP_SCRIPT_PATH={q(paths['bootstrap'])}",
        f"C2C_BOOTSTRAP_SCRIPT_SHA256={q(hashes['bootstrap'])}",
        f"curl --fail --silent --show-error --location --retry 3 --output {q(paths['bootstrap'])} {q(urls['bootstrap'])}",
        f"echo {q(hashes['bootstrap'] + '  ' + paths['bootstrap'])} | sha256sum -c - >/dev/null",
        f"C2C_DEPLOY_SCRIPT_PATH={q(paths['deploy'])}",
        f"C2C_DEPLOY_SCRIPT_SHA256={q(hashes['deploy'])}",
        f"curl --fail --silent --show-error --location --retry 3 --output {q(paths['deploy'])} {q(urls['deploy'])}",
        f"echo {q(hashes['deploy'] + '  ' + paths['deploy'])} | sha256sum -c - >/dev/null",
        f"C2C_ACCEPTANCE_SCRIPT_PATH={q(paths['acceptance'])}",
        f"C2C_ACCEPTANCE_SCRIPT_SHA256={q(hashes['acceptance'])}",
        f"curl --fail --silent --show-error --location --retry 3 --output {q(paths['acceptance'])} {q(urls['acceptance'])}",
        f"echo {q(hashes['acceptance'] + '  ' + paths['acceptance'])} | sha256sum -c - >/dev/null",
        "export C2C_SOURCE_SHA C2C_BOOTSTRAP_SCRIPT_PATH C2C_BOOTSTRAP_SCRIPT_SHA256",
        'if [[ ! -s /etc/claim2car/runtime/runtime.env ]]; then',
        "  sudo --preserve-env=C2C_SOURCE_SHA,C2C_BOOTSTRAP_SCRIPT_PATH,C2C_BOOTSTRAP_SCRIPT_SHA256 /usr/local/sbin/claim2car-runtime-bootstrap",
        'else echo "Synthetic runtime credentials already exist; bootstrap is not repeated."; fi',
        '[[ -s /etc/claim2car/runtime/capture-runtime.json && -s /etc/claim2car/runtime/operator-tokens.txt ]] || { echo "Runtime bootstrap is incomplete." >&2; exit 1; }',
        f"OCI_REGISTRY={q(registry)}",
        f"OCI_REGISTRY_USERNAME={q(registry_username)}",
        f"OCI_IMAGE_REF={q(image_ref)}",
        f"C2C_POSTGRES_IMAGE={q(postgres_image)}",
        f"OCI_VAULT_SECRET_OCID={q(vault_secret_ocid)}",
        'bundle="$(oci secrets secret-bundle get --secret-id "$OCI_VAULT_SECRET_OCID" --auth instance_principal --region "$OCI_REGION" --output json)"',
        'token_b64="$(jq -er \'.data["secret-bundle-content"].content // .data.secretBundleContent.content\' <<<"$bundle")"',
        'OCI_REGISTRY_TOKEN="$(printf "%s" "$token_b64" | base64 --decode)"',
        '[[ -n "$OCI_REGISTRY_TOKEN" ]] || { echo "Vault OCIR token secret is empty." >&2; exit 1; }',
        "export OCI_REGISTRY OCI_REGISTRY_USERNAME OCI_REGISTRY_TOKEN OCI_IMAGE_REF C2C_POSTGRES_IMAGE C2C_SOURCE_SHA C2C_DEPLOY_SCRIPT_PATH C2C_DEPLOY_SCRIPT_SHA256",
        "sudo --preserve-env=OCI_REGISTRY,OCI_REGISTRY_USERNAME,OCI_REGISTRY_TOKEN,OCI_IMAGE_REF,C2C_POSTGRES_IMAGE,C2C_SOURCE_SHA,C2C_DEPLOY_SCRIPT_PATH,C2C_DEPLOY_SCRIPT_SHA256 /usr/local/sbin/claim2car-runtime-deploy",
        "unset OCI_REGISTRY_TOKEN",
        "export C2C_ACCEPTANCE_SCRIPT_PATH C2C_ACCEPTANCE_SCRIPT_SHA256 C2C_SOURCE_SHA",
        "export C2C_ACCEPTANCE_BASE_URL=http://127.0.0.1:8000",
        "sudo --preserve-env=C2C_SOURCE_SHA,C2C_ACCEPTANCE_SCRIPT_PATH,C2C_ACCEPTANCE_SCRIPT_SHA256,C2C_ACCEPTANCE_BASE_URL /usr/local/sbin/claim2car-runtime-acceptance",
    ]
    script = "\n".join(lines) + "\n"
    if len(script.encode()) > 3900:
        raise ValueError(f"OCI Run Command text exceeds safe 3.9 KB limit ({len(script.encode())} bytes).")
    return script


def run_oci(args: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(["oci", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"OCI CLI failed ({result.returncode}): {detail[:1500]}")
    return result.stdout.strip()


def get_state(data: dict) -> str:
    return str(data.get("lifecycle-state") or data.get("lifecycleState") or data.get("lifecycle_state") or "UNKNOWN").upper()


def get_execution_content(data: dict) -> dict:
    return data.get("content") or data.get("execution-content") or data.get("executionContent") or {}


def execute_command(
    *,
    compartment_ocid: str,
    instance_ocid: str,
    script: str,
    display_name: str,
    timeout_seconds: int = 1800,
    poll_seconds: int = 15,
    max_wait_seconds: int = 1800,
) -> dict:
    content = {"source": {"sourceType": "TEXT", "text": script}}
    target = {"instanceId": instance_ocid}
    with tempfile.TemporaryDirectory(prefix="c2c-oci-run-command-") as tmp:
        content_path = Path(tmp) / "content.json"
        target_path = Path(tmp) / "target.json"
        content_path.write_text(json.dumps(content))
        target_path.write_text(json.dumps(target))
        os.chmod(content_path, 0o600)
        os.chmod(target_path, 0o600)
        output = run_oci([
            "instance-agent", "command", "create",
            "--compartment-id", compartment_ocid,
            "--content", f"file://{content_path}",
            "--target", f"file://{target_path}",
            "--timeout-in-seconds", str(timeout_seconds),
            "--display-name", display_name,
            "--output", "json",
        ])
    response = json.loads(output)
    command_id = (response.get("data") or {}).get("id") or response.get("data", {}).get("commandId")
    if not command_id:
        raise RuntimeError("OCI Run Command create response did not include a command ID.")

    deadline = time.monotonic() + max_wait_seconds
    last_state = "UNKNOWN"
    last_data: dict = {}
    while time.monotonic() < deadline:
        try:
            output = run_oci([
                "instance-agent", "command-execution", "get",
                "--command-id", command_id,
                "--instance-id", instance_ocid,
                "--output", "json",
            ], timeout=120)
        except RuntimeError as error:
            # The execution record can lag command creation. Retry only transient not-found
            # responses briefly; persistent 404s usually indicate IAM or plugin readiness.
            detail = str(error)
            if ("404" in detail or "NotAuthorizedOrNotFound" in detail) and time.monotonic() < deadline:
                time.sleep(max(1, poll_seconds))
                continue
            raise
        payload = json.loads(output)
        last_data = payload.get("data") or payload
        last_state = get_state(last_data)
        if last_state in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED"}:
            break
        time.sleep(max(0, poll_seconds))
    else:
        raise TimeoutError(f"OCI Run Command timed out waiting for execution; command ID {command_id}, last state {last_state}.")

    content_data = get_execution_content(last_data)
    exit_code = content_data.get("exit-code", content_data.get("exitCode", content_data.get("exit_code")))
    message = content_data.get("message", "")
    text_output = content_data.get("text", "")
    result = {
        "command_id": command_id,
        "lifecycle_state": last_state,
        "exit_code": exit_code,
        "message": message,
        "text": text_output,
    }
    if last_state != "SUCCEEDED" or exit_code != 0:
        raise RuntimeError(
            f"OCI Run Command failed: state={last_state}, exit_code={exit_code}, "
            f"command_id={command_id}, message={str(message)[:1000]}, output={str(text_output)[-1000:]}"
        )
    return result


def main() -> int:
    env = os.environ
    image_ref = env["OCI_IMAGE_REF"]
    registry = env["OCI_REGISTRY"]
    namespace = env["OCIR_NAMESPACE"]
    repository = env["OCIR_REPOSITORY"]
    source_sha = validate_image_ref(image_ref, registry, namespace, repository)
    workflow_sha = env.get("GITHUB_SHA", "")
    if workflow_sha != source_sha:
        raise ValueError("Image source SHA must equal the protected workflow commit.")
    source_dir = Path(env.get("C2C_DEPLOY_SOURCE_DIR", "source"))
    hashes = {
        name: hashlib.sha256((source_dir / "scripts" / filename).read_bytes()).hexdigest()
        for name, filename in SCRIPT_NAMES.items()
    }
    script = build_remote_script(
        source_sha=source_sha,
        registry=registry,
        registry_username=env["OCI_REGISTRY_USERNAME"],
        image_ref=image_ref,
        postgres_image=env["C2C_POSTGRES_IMAGE"],
        vault_secret_ocid=env["OCI_OCIR_VAULT_SECRET_OCID"],
        hashes=hashes,
    )
    result = execute_command(
        compartment_ocid=env["OCI_COMPARTMENT_OCID"],
        instance_ocid=env["OCI_STAGING_INSTANCE_OCID"],
        script=script,
        display_name=f"Claim2Car staging deploy {source_sha[:12]}",
        timeout_seconds=int(env.get("OCI_RUN_COMMAND_TIMEOUT_SECONDS", "1800")),
        poll_seconds=int(env.get("OCI_RUN_COMMAND_POLL_SECONDS", "15")),
        max_wait_seconds=int(env.get("OCI_RUN_COMMAND_MAX_WAIT_SECONDS", "1800")),
    )
    print(f"OCI Run Command succeeded: {result['command_id']}")
    if result.get("text"):
        print(str(result["text"])[-3000:])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)

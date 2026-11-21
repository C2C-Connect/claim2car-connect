#!/usr/bin/env python3
"""Submit a secret-free OCI Instance Agent Run Command and poll its execution."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _required_env(name: str, env: dict[str, str]) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required deployment input: {name}")
    return value


def validate_inputs(env: dict[str, str]) -> dict[str, str]:
    names = (
        "OCI_COMPARTMENT_OCID",
        "OCI_STAGING_INSTANCE_OCID",
        "OCI_REGISTRY",
        "OCIR_NAMESPACE",
        "OCIR_REPOSITORY",
        "OCI_OCIR_AUTH_SECRET_OCID",
        "C2C_IMAGE_REF",
        "C2C_POSTGRES_IMAGE",
        "C2C_DEPLOY_SCRIPT_SHA256",
    )
    values = {name: _required_env(name, env) for name in names}
    if not re.fullmatch(r"ocid1\.compartment\.[a-zA-Z0-9.]+", values["OCI_COMPARTMENT_OCID"]):
        raise ValueError("OCI_COMPARTMENT_OCID is malformed.")
    if not re.fullmatch(r"ocid1\.instance\.[a-zA-Z0-9.]+", values["OCI_STAGING_INSTANCE_OCID"]):
        raise ValueError("OCI_STAGING_INSTANCE_OCID is malformed.")
    if not re.fullmatch(r"ocid1\.vaultsecret\.[a-zA-Z0-9.]+", values["OCI_OCIR_AUTH_SECRET_OCID"]):
        raise ValueError("OCI_OCIR_AUTH_SECRET_OCID is malformed.")
    if values["OCI_REGISTRY"] != "us-chicago-1.ocir.io":
        raise ValueError("OCI_REGISTRY must be the configured Chicago OCIR host.")
    if not re.fullmatch(r"[a-z0-9]+", values["OCIR_NAMESPACE"]):
        raise ValueError("OCIR_NAMESPACE is malformed.")
    if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", values["OCIR_REPOSITORY"]):
        raise ValueError("OCIR_REPOSITORY is malformed.")
    if not re.fullmatch(r"[a-f0-9]{64}", values["C2C_DEPLOY_SCRIPT_SHA256"]):
        raise ValueError("C2C_DEPLOY_SCRIPT_SHA256 must be a lowercase SHA-256.")
    image_pattern = (
        rf"^{re.escape(values['OCI_REGISTRY'])}/{re.escape(values['OCIR_NAMESPACE'])}/"
        rf"{re.escape(values['OCIR_REPOSITORY'])}:sha-([a-f0-9]{{40}})@sha256:([a-f0-9]{{64}})$"
    )
    match = re.fullmatch(image_pattern, values["C2C_IMAGE_REF"])
    if not match:
        raise ValueError("C2C_IMAGE_REF must match the configured OCIR repo, commit tag, and pinned digest.")
    values["C2C_IMAGE_COMMIT"] = match.group(1)
    db_image = values["C2C_POSTGRES_IMAGE"]
    if not re.fullmatch(r"docker.io/postgis/postgis(?::[a-zA-Z0-9._-]+)?@sha256:[a-f0-9]{64}", db_image):
        raise ValueError("C2C_POSTGRES_IMAGE must be the official docker.io/postgis/postgis image pinned by digest.")
    return values


def build_command_text(values: dict[str, str]) -> str:
    args = [
        values["C2C_IMAGE_COMMIT"],
        values["C2C_IMAGE_REF"],
        values["C2C_DEPLOY_SCRIPT_SHA256"],
        values["C2C_POSTGRES_IMAGE"],
        values["OCI_REGISTRY"],
        values["OCI_OCIR_AUTH_SECRET_OCID"],
        values["OCIR_NAMESPACE"],
        values["OCIR_REPOSITORY"],
    ]
    command = "sudo -n /usr/local/sbin/claim2car-staging-deploy " + " ".join(
        shlex.quote(arg) for arg in args
    )
    text = "#!/usr/bin/env bash\nset -euo pipefail\n" + command + "\n"
    if len(text.encode("utf-8")) > 4096:
        raise ValueError("Run Command text exceeds OCI's 4 KB inline script limit.")
    return text


def _run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def submit_command(values: dict[str, str], script_text: str) -> str:
    content = {
        "source": {"sourceType": "TEXT", "text": script_text},
        "output": {"outputType": "TEXT"},
    }
    target = {"instanceId": values["OCI_STAGING_INSTANCE_OCID"]}
    with tempfile.TemporaryDirectory(prefix="c2c-oci-runcommand-") as temp:
        content_path = Path(temp) / "content.json"
        target_path = Path(temp) / "target.json"
        content_path.write_text(json.dumps(content), encoding="utf-8")
        target_path.write_text(json.dumps(target), encoding="utf-8")
        content_path.chmod(0o600)
        target_path.chmod(0o600)
        result = _run_cli(
            [
                os.environ.get("OCI_CLI", "oci"),
                "instance-agent",
                "command",
                "create",
                "--compartment-id",
                values["OCI_COMPARTMENT_OCID"],
                "--content",
                f"file://{content_path}",
                "--target",
                f"file://{target_path}",
                "--timeout-in-seconds",
                "1800",
                "--display-name",
                f"Claim2Car-staging-deploy-{values['C2C_IMAGE_COMMIT'][:12]}",
                "--query",
                "data.id",
                "--raw-output",
            ]
        )
    command_id = result.stdout.strip()
    if not command_id.startswith("ocid1.instanceagentcommand."):
        raise RuntimeError("OCI command creation returned no valid command OCID.")
    return command_id


def poll_command(values: dict[str, str], command_id: str, *, timeout: int = 1860, interval: int = 10) -> str:
    deadline = time.monotonic() + timeout
    terminal = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED"}
    while time.monotonic() < deadline:
        result = _run_cli(
            [
                os.environ.get("OCI_CLI", "oci"),
                "instance-agent",
                "command-execution",
                "list",
                "--compartment-id",
                values["OCI_COMPARTMENT_OCID"],
                "--instance-id",
                values["OCI_STAGING_INSTANCE_OCID"],
                "--all",
                "--output",
                "json",
            ]
        )
        try:
            executions = json.loads(result.stdout).get("data", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RuntimeError("OCI returned an invalid command-execution response.") from exc
        matching = [
            item for item in executions
            if item.get("command-id", item.get("commandId")) == command_id
        ]
        if matching:
            state = matching[-1].get("lifecycle-state", matching[-1].get("lifecycleState", ""))
            if state in terminal:
                if state != "SUCCEEDED":
                    raise RuntimeError(f"OCI deployment command ended in {state}. Command OCID: {command_id}")
                return state
        time.sleep(interval)
    _run_cli(
        [
            os.environ.get("OCI_CLI", "oci"),
            "instance-agent",
            "command",
            "cancel",
            "--command-id",
            command_id,
            "--force",
        ],
        check=False,
    )
    raise TimeoutError(f"OCI Run Command polling timed out. Command OCID: {command_id}")


def main() -> int:
    try:
        values = validate_inputs(dict(os.environ))
        script_text = build_command_text(values)
        command_id = submit_command(values, script_text)
        print(f"OCI Run Command submitted: {command_id}")
        state = poll_command(values, command_id)
        print(f"PASS: private staging deployment command finished: {state}")
        print(f"Command OCID: {command_id}")
        return 0
    except (ValueError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Synthetic live-staging acceptance: 16-slot capture, restart, reviewer retrieval, integrity, withdrawal."""
from __future__ import annotations
import argparse
import atexit
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

SLOTS = (
    "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior",
    "03_rear_right_exterior", "04_rear_exterior", "05_rear_left_exterior",
    "06_left_side_exterior", "07_front_left_exterior", "08_wheel_front_left",
    "09_wheel_front_right", "10_wheel_rear_right", "11_wheel_rear_left",
    "12_cabin_front_airbags", "13_instrument_cluster_odometer", "14_physical_vin",
    "15_license_and_insurance_docs",
)
TEST_VIN = "1HGCM82633A004352"
CLEANUP_BASE = CLEANUP_SESSION = CLEANUP_OWNER = ""
CLEANUP_CONSENT = False

def synthetic_original_path(evidence_root: Path, tenant_id: str, session_id: str, artifact_id: str) -> Path:
    """Resolve a synthetic original only after validating each path component."""
    components = (tenant_id, session_id, artifact_id)
    if any(not isinstance(value, str) or not value or value in {".", ".."} or Path(value).name != value or "/" in value or "\\" in value for value in components):
        raise RuntimeError("Synthetic evidence identifiers contain unsafe path components.")
    tenant_dir = evidence_root / tenant_id
    session_dir = tenant_dir / session_id
    artifact_path = session_dir / (artifact_id + ".original")
    if evidence_root.is_symlink() or tenant_dir.is_symlink() or session_dir.is_symlink() or artifact_path.is_symlink():
        raise RuntimeError("Evidence storage root, tenant, session, and artifact must not be symlinks.")
    if not artifact_path.is_file():
        raise RuntimeError("Expected synthetic original is absent from persistent evidence storage.")
    return artifact_path


def cleanup_synthetic_consent():
    if CLEANUP_CONSENT and CLEANUP_BASE and CLEANUP_SESSION and CLEANUP_OWNER:
        try:
            json_request(CLEANUP_BASE, "POST", f"/v1/capture-sessions/{CLEANUP_SESSION}/consent",
                        CLEANUP_OWNER, {"request_id": rid(), "accepted": False, "scope": "capture_review"}, 200)
        except Exception as error:
            print(f"WARNING: automatic consent cleanup failed for synthetic session {CLEANUP_SESSION}: {error}", file=sys.stderr)


atexit.register(cleanup_synthetic_consent)


def rid():
    return str(uuid.uuid4())


def request(base, method, path, token, body=None, expected=200):
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            status = response.status
            response_headers = response.headers
    except urllib.error.HTTPError as error:
        raw, status, response_headers = error.read(), error.code, error.headers
    if status != expected:
        raise RuntimeError(f"{method} {path}: expected HTTP {expected}, got {status}: {raw[:500]!r}")
    return raw, response_headers


def json_request(base, method, path, token, body=None, expected=200):
    raw, _ = request(base, method, path, token, body, expected)
    return json.loads(raw) if raw else {}




def verify_source_checkout(expected_revision: str, checkout: Path | None = None) -> None:
    """Fail if acceptance is run from a checkout that does not match the deployed image."""
    root = checkout or Path(__file__).resolve().parents[1]
    if not isinstance(expected_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise RuntimeError("Deployed build endpoint must report a full 40-character commit SHA.")
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    if current != expected_revision:
        raise RuntimeError(f"Acceptance source revision mismatch: checkout={current}, deployed={expected_revision}.")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout
    if dirty.strip():
        raise RuntimeError("Acceptance source checkout has uncommitted or untracked changes; use a clean matching checkout.")


def wait_ready(base, revision, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/health/ready", timeout=5) as r:
                if r.status == 200:
                    with urllib.request.urlopen(base + "/health/build", timeout=5) as b:
                        build = json.loads(b.read())
                    if revision in json.dumps(build):
                        return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Application did not return ready/build identity after restart.")


def main():
    global CLEANUP_BASE, CLEANUP_SESSION, CLEANUP_OWNER, CLEANUP_CONSENT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--confirm-synthetic", action="store_true",
                        help="Required: creates and withdraws consent for a synthetic case.")
    parser.add_argument("--skip-container-restart", action="store_true",
                        help="Skip the host Podman restart check (not full acceptance).")
    args = parser.parse_args()
    if not args.confirm_synthetic:
        parser.error("Pass --confirm-synthetic; this acceptance run creates synthetic records and withdraws consent.")
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.path:
        parser.error("base-url must be HTTP loopback only; use an SSH/Bastion port-forward.")
    base = args.base_url.rstrip("/")
    operator = os.environ.get("C2C_ACCEPTANCE_OPERATOR_TOKEN", "")
    owner = os.environ.get("C2C_ACCEPTANCE_OWNER_TOKEN", "")
    reviewer = os.environ.get("C2C_ACCEPTANCE_REVIEWER_TOKEN", "")
    if not all(len(token) >= 32 for token in (operator, owner, reviewer)):
        parser.error("Set the synthetic operator, owner, and reviewer tokens in the environment.")
    revision = ""
    build_raw, _ = request(base, "GET", "/health/build", operator, expected=200)
    build = json.loads(build_raw)
    revision = str(build.get("revision") or build.get("git_sha") or build.get("commit") or "")
    verify_source_checkout(revision)

    collision_id, claim_id = rid(), rid()
    collision = json_request(base, "POST", "/v1/collisions", operator,
                             {"collision_id": collision_id, "request_id": rid()}, 201)
    case = json_request(base, "POST", "/v1/claim-cases", operator,
                        {"claim_id": claim_id, "request_id": rid()}, 201)
    session_id = case["capture_session_id"]
    CLEANUP_BASE, CLEANUP_SESSION, CLEANUP_OWNER = base, session_id, owner
    json_request(base, "POST", f"/v1/collisions/{collision_id}/claims", operator,
                 {"claim_id": claim_id, "request_id": rid()}, 201)
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/consent", owner,
                 {"request_id": rid(), "accepted": True, "scope": "capture_review"}, 200)
    CLEANUP_CONSENT = True
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/vehicle-reference", operator,
                 {"request_id": rid(), "vin": TEST_VIN}, 200)

    originals = {}
    for slot in SLOTS:
        artifact_id = rid()
        raw = ("CLAIM2CAR-SYNTHETIC-STAGING:" + session_id + ":" + slot).encode("ascii")
        digest = hashlib.sha256(raw).hexdigest()
        originals[artifact_id] = (slot, raw, digest)
        json_request(base, "POST", f"/v1/capture-sessions/{session_id}/artifacts", operator,
                     {"request_id": rid(), "artifact_id": artifact_id, "slot": slot,
                      "payload_base64": base64.b64encode(raw).decode("ascii"), "sha256": digest}, 200)
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/quality", operator,
                 {"request_id": rid(), "results": {slot: True for slot in SLOTS}}, 200)
    sealed = json_request(base, "POST", f"/v1/capture-sessions/{session_id}/seal", operator,
                          {"request_id": rid()}, 200)
    manifest_digest = sealed["manifest_digest"]

    details = json_request(base, "GET", f"/v1/review-sessions/{session_id}", reviewer, expected=200)
    if details.get("manifest_digest") != manifest_digest or len(details.get("artifacts", [])) != len(SLOTS):
        raise RuntimeError("Reviewer manifest or artifact count does not match sealed 16-slot capture.")
    for artifact_id, (_slot, expected_bytes, expected_digest) in originals.items():
        raw, _ = request(base, "GET", f"/v1/review-sessions/{session_id}/artifacts/{artifact_id}", reviewer)
        if raw != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_digest:
            raise RuntimeError("Reviewer original-byte retrieval or SHA-256 mismatch.")

    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/review", reviewer,
                 {"request_id": rid(), "disposition": "NOTE_ONLY",
                  "reason": "Synthetic staging acceptance only; not a real claim review."}, 200)

    if not args.skip_container_restart:
        restarted = subprocess.run(["podman", "restart", "claim2car-app"], capture_output=True, text=True, timeout=120)
        if restarted.returncode:
            raise RuntimeError("Podman restart failed: " + restarted.stderr[-500:])
        wait_ready(base, revision)
        details_after = json_request(base, "GET", f"/v1/review-sessions/{session_id}", reviewer, expected=200)
        if details_after.get("manifest_digest") != manifest_digest:
            raise RuntimeError("Manifest digest changed or did not survive runtime restart.")
        for artifact_id, (_slot, expected_bytes, expected_digest) in originals.items():
            raw, _ = request(base, "GET", f"/v1/review-sessions/{session_id}/artifacts/{artifact_id}", reviewer)
            if raw != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_digest:
                raise RuntimeError("Original bytes failed post-restart retrieval/integrity check.")

    # Deliberately tamper with only this synthetic test artifact, confirm the reviewer API
    # rejects it, then withdraw capture consent so the originals are deleted.
    config_path = Path(os.environ.get("C2C_CAPTURE_CONFIG_FILE", "/etc/claim2car/runtime/capture-runtime.json"))
    evidence_root = Path(os.environ.get("C2C_ARTIFACT_STORAGE_ROOT", "/var/lib/claim2car/evidence"))
    config = json.loads(config_path.read_text())
    tenant_id = next((entry["tenant_id"] for entry in config["credentials"]
                      if entry.get("actor_role") == "owner"), None)
    artifact_id = next(iter(originals))
    artifact_path = synthetic_original_path(evidence_root, tenant_id, session_id, artifact_id)
    artifact_path.write_bytes(b"CLAIM2CAR SYNTHETIC TAMPER CHECK")
    tamper = json_request(base, "GET", f"/v1/review-sessions/{session_id}", reviewer, expected=409)
    if tamper.get("detail") != "EVIDENCE_ARTIFACT_CONFLICT":
        raise RuntimeError("Tampered synthetic evidence was not rejected with the integrity conflict.")
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/consent", owner,
                 {"request_id": rid(), "accepted": False, "scope": "capture_review"}, 200)
    if artifact_path.exists():
        raise RuntimeError("Consent withdrawal did not remove synthetic original bytes.")
    CLEANUP_CONSENT = False

    print(json.dumps({
        "status": "PASS",
        "synthetic_only": True,
        "capture_protocol": "claims2car-16-v1",
        "slots_uploaded": len(SLOTS),
        "manifest_sha256": manifest_digest,
        "restart_verified": not args.skip_container_restart,
        "reviewer_retrieval_verified": True,
        "tamper_rejection_verified": True,
        "consent_withdrawal_deletion_verified": True,
        "claim_id": claim_id,
        "capture_session_id": session_id,
        "revision": revision,
        "note": "This does not validate camera authenticity, device qualification, real claim adjudication, or production readiness."
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(2)

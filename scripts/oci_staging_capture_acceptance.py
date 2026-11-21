#!/usr/bin/env python3
"""Synthetic live-staging acceptance: 16-slot capture, restart, reviewer retrieval, integrity, withdrawal."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
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
    if len(revision) < 7:
        raise RuntimeError("Build endpoint did not identify the deployed revision.")

    collision_id, claim_id = rid(), rid()
    collision = json_request(base, "POST", "/v1/collisions", operator,
                             {"collision_id": collision_id, "request_id": rid()}, 201)
    case = json_request(base, "POST", "/v1/claim-cases", operator,
                        {"claim_id": claim_id, "request_id": rid()}, 201)
    session_id = case["capture_session_id"]
    json_request(base, "POST", f"/v1/collisions/{collision_id}/claims", operator,
                 {"claim_id": claim_id, "request_id": rid()}, 201)
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/consent", owner,
                 {"request_id": rid(), "accepted": True, "scope": "capture_review"}, 200)
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
    artifact_path = evidence_root / tenant_id / session_id / (artifact_id + ".original")
    if not artifact_path.is_file():
        raise RuntimeError("Expected synthetic original is absent from persistent evidence storage.")
    artifact_path.write_bytes(b"CLAIM2CAR SYNTHETIC TAMPER CHECK")
    tamper = json_request(base, "GET", f"/v1/review-sessions/{session_id}", reviewer, expected=409)
    if tamper.get("detail") != "EVIDENCE_ARTIFACT_CONFLICT":
        raise RuntimeError("Tampered synthetic evidence was not rejected with the integrity conflict.")
    json_request(base, "POST", f"/v1/capture-sessions/{session_id}/consent", owner,
                 {"request_id": rid(), "accepted": False, "scope": "capture_review"}, 200)
    if artifact_path.exists():
        raise RuntimeError("Consent withdrawal did not remove synthetic original bytes.")

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

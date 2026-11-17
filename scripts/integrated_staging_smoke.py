#!/usr/bin/env python3
"""Provider-neutral smoke checks for an integrated Claim2Car staging deployment."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base, path):
    req = Request(base.rstrip("/") + path, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=12) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def verify(base, expected_revision, attempts=24, interval_seconds=5):
    """Verify readiness, exact build identity, and protected route boundaries."""
    if not base.startswith("https://") or len(expected_revision) != 40:
        raise RuntimeError("INVALID_INTEGRATED_STAGING_TARGET")
    if attempts < 1 or interval_seconds < 0:
        raise RuntimeError("INVALID_RETRY_POLICY")

    ready = None
    for attempt in range(attempts):
        try:
            status, body = request(base, "/health/ready")
            if status == 200 and json.loads(body).get("status") == "ready":
                ready = body
                break
        except (URLError, TimeoutError, json.JSONDecodeError):
            pass
        if attempt + 1 < attempts:
            time.sleep(interval_seconds)
    if ready is None:
        raise RuntimeError("INTEGRATED_STAGING_NOT_READY")

    status, _ = request(base, "/health/live")
    if status != 200:
        raise RuntimeError("INTEGRATED_STAGING_NOT_LIVE")

    status, body = request(base, "/health/build")
    if status != 200:
        raise RuntimeError("BUILD_REVISION_ENDPOINT_UNAVAILABLE")
    build = json.loads(body)
    if build.get("revision") != expected_revision or build.get("runtime_mode") != "integrated":
        raise RuntimeError("DEPLOYED_REVISION_OR_RUNTIME_MODE_MISMATCH")

    if request(base, "/")[0] != 200:
        raise RuntimeError("INTEGRATED_OPERATOR_SHELL_UNAVAILABLE")
    if request(base, "/api/v1/capture-sessions")[0] != 401:
        raise RuntimeError("CAPTURE_API_AUTH_BOUNDARY_FAILED")
    if request(base, "/api/v1/review-queue")[0] != 401:
        raise RuntimeError("REVIEW_API_AUTH_BOUNDARY_FAILED")
    if request(base, "/internal/v1/analysis/health")[0] != 401:
        raise RuntimeError("INTERNAL_ANALYSIS_AUTH_BOUNDARY_FAILED")
    if request(base, "/api/v1/analysis/physics")[0] != 404:
        raise RuntimeError("PUBLIC_ANALYSIS_ROUTE_EXPOSED")
    return {"result": "passed", "revision": expected_revision, "runtime_mode": "integrated"}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: integrated_staging_smoke.py HTTPS_URL FULL_GIT_SHA")
    try:
        result = verify(sys.argv[1].rstrip("/"), sys.argv[2])
    except (RuntimeError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print("PASS integrated staging revision", result["revision"])
    print("PASS liveness, readiness, operator shell, and API authorization boundaries")


if __name__ == "__main__":
    main()

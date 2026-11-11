#!/usr/bin/env python3
"""Verify the integrated Claim2Car staging deployment without sending business data."""
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


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: railway_integrated_smoke.py HTTPS_URL FULL_GIT_SHA")
    base, expected_revision = sys.argv[1].rstrip("/"), sys.argv[2]
    if not base.startswith("https://") or len(expected_revision) != 40:
        raise SystemExit("INVALID_STAGING_SMOKE_TARGET")

    ready = None
    for _ in range(24):
        try:
            status, body = request(base, "/health/ready")
            if status == 200 and json.loads(body).get("status") == "ready":
                ready = body
                break
        except (URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(5)
    if ready is None:
        raise SystemExit("INTEGRATED_STAGING_NOT_READY")
    print("PASS /health/ready")

    status, body = request(base, "/health/live")
    if status != 200:
        raise SystemExit("INTEGRATED_STAGING_NOT_LIVE")
    print("PASS /health/live")

    status, body = request(base, "/health/build")
    if status != 200:
        raise SystemExit("BUILD_REVISION_ENDPOINT_UNAVAILABLE")
    build = json.loads(body)
    if build.get("revision") != expected_revision or build.get("runtime_mode") != "integrated":
        raise SystemExit("DEPLOYED_REVISION_OR_RUNTIME_MODE_MISMATCH")
    print("PASS exact revision and integrated runtime mode")

    if request(base, "/")[0] != 200:
        raise SystemExit("INTEGRATED_OPERATOR_SHELL_UNAVAILABLE")
    print("PASS operator shell")

    if request(base, "/api/v1/capture-sessions")[0] != 401:
        raise SystemExit("CAPTURE_API_AUTH_BOUNDARY_FAILED")
    if request(base, "/api/v1/review-queue")[0] != 401:
        raise SystemExit("REVIEW_API_AUTH_BOUNDARY_FAILED")
    if request(base, "/internal/v1/analysis/health")[0] != 401:
        raise SystemExit("INTERNAL_ANALYSIS_AUTH_BOUNDARY_FAILED")
    if request(base, "/api/v1/analysis/physics")[0] != 404:
        raise SystemExit("PUBLIC_ANALYSIS_ROUTE_EXPOSED")
    print("PASS unauthenticated API and internal-route boundaries")


if __name__ == "__main__":
    main()

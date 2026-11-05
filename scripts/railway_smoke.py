"""Verify an exact restricted-staging revision with synthetic requests only."""
from __future__ import annotations

import argparse
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def request(base_url, path, payload=None, *, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(base_url + path, data=data, headers={"Content-Type": "application/json"})
    try:
        response = urlopen(req, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        text = response.read().decode()
        return response.status, response.headers, json.loads(text)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_for_health(base_url, expected_revision, wait_seconds):
    """Poll both health endpoints on one deadline; never retry unsafe flags."""
    require(wait_seconds > 0, "POSITIVE_WAIT_REQUIRED")
    deadline = time.monotonic() + wait_seconds
    last_error = "HEALTH_NOT_READY"
    while True:
        pending = False
        for path, expected_status in (("/health/live", "alive"), ("/health/ready", "ready")):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("HEALTH_NOT_READY_BEFORE_DEADLINE:" + last_error)
            try:
                status, headers, body = request(
                    base_url, path, timeout=min(10, remaining)
                )
            except (OSError, ValueError, URLError):
                pending = True
                last_error = "HEALTH_REQUEST_FAILED:" + path
                continue
            if status != 200 or not isinstance(body, dict):
                pending = True
                last_error = "HEALTH_NOT_200_OR_INVALID_BODY:" + path
                continue
            # A successful health response must prove the safety boundary even
            # while waiting for an older revision or a warming status to change.
            require(body.get("scope") == "synthetic-staging-containment-only", "SCOPE_MISMATCH")
            require(headers.get("Cache-Control") == "no-store", "HEALTH_CACHE_POLICY")
            for key in (
                "business_ready", "database_integrated", "capture_enabled",
                "analysis_enabled", "dispatch_build_enabled", "payments_enabled",
            ):
                require(body.get(key) is False, "UNEXPECTED_BUSINESS_ENABLEMENT:" + key)
            if (body.get("revision") != expected_revision
                    or body.get("status") != expected_status):
                pending = True
                last_error = "EXPECTED_HEALTH_REVISION_OR_STATUS_NOT_READY:" + path
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("HEALTH_NOT_READY_BEFORE_DEADLINE:" + last_error)
        if not pending:
            return
        time.sleep(min(2, remaining))


def verify(base_url, expected_revision, wait_seconds=120):
    parsed = urlsplit(base_url)
    require(
        parsed.scheme == "https"
        or (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")),
        "HTTPS_REQUIRED_EXCEPT_LOOPBACK",
    )
    require(
        parsed.hostname and not parsed.username and not parsed.password
        and not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
        "BASE_URL_MUST_BE_ORIGIN_WITHOUT_CREDENTIALS",
    )
    require(re.fullmatch(r"[0-9a-f]{40}", expected_revision), "FULL_COMMIT_REQUIRED")
    base_url = base_url.rstrip("/")
    wait_for_health(base_url, expected_revision, wait_seconds)
    status, _, body = request(base_url, "/api/v1/dispatch/health")
    require(status == 200 and body.get("status") == "disabled"
            and body.get("build_enabled") is False, "DISPATCH_HEALTH_UNSAFE")
    require(body.get("scope") == "synthetic-staging-containment-only"
            and body.get("redact_enabled") is False
            and body.get("verify_enabled") is False, "DISPATCH_SCOPE_UNSAFE")
    for provenance in ({}, {"execution_mode": "synthetic"},
                       {"execution_mode": "model", "provenance_verified": True}):
        status, headers, body = request(
            base_url, "/api/v1/dispatch/build",
            {"adjudication": {"session_id": "synthetic-deployment-smoke", **provenance}},
        )
        require(status == 503 and body.get("detail", {}).get("code") == "dispatch_build_disabled",
                "DISPATCH_BUILD_NOT_BLOCKED")
        require(headers.get("Cache-Control") == "no-store", "DISPATCH_CACHE_POLICY")
    for path in ("/docs", "/openapi.json", "/api/v1/verify/synthetic",
                 "/v1/capture-sessions/synthetic"):
        require(request(base_url, path)[0] == 404, "UNEXPECTED_PUBLIC_ROUTE:" + path)
    for path in ("/api/v1/analysis/run", "/api/v1/triage/adjudicate"):
        require(request(base_url, path, {})[0] == 404, "UNEXPECTED_BUSINESS_ROUTE:" + path)
    return {
        "result": "passed",
        "revision": expected_revision,
        "scope": "synthetic-staging-containment-only",
        "business_acceptance": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--wait-seconds", type=int, default=120)
    args = parser.parse_args()
    print(json.dumps(verify(args.base_url, args.expected_revision, args.wait_seconds)))


if __name__ == "__main__":
    main()

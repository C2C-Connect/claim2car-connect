"""Restricted staging rehearsal, not the integrated business application.

No database, capture, analysis, valuation, payments, reports, or verification
routes are mounted. Dispatch build stays unconditionally disabled using the
existing containment handler. Railway's readiness probe covers this narrow
surface only, not database readiness or product acceptance.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.api.dispatch import DispatchRequest, dispatch_build, dispatch_health


SCOPE = "synthetic-staging-containment-only"
REVISION_FILE = Path(__file__).with_name("_build_revision.txt")


def read_build_revision() -> str:
    try:
        revision = REVISION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("BUILD_REVISION_UNAVAILABLE") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("BUILD_REVISION_INVALID")
    return revision


def listen_port() -> int:
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError as exc:
        raise RuntimeError("PORT_INVALID") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT_INVALID")
    return port


def create_staging_app() -> FastAPI:
    revision = read_build_revision()
    api = FastAPI(
        title="Claim2Car Connect restricted staging",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )

    def health(status: str) -> JSONResponse:
        return JSONResponse(
            {
                "status": status,
                "service": "claim2car-connect",
                "scope": SCOPE,
                "revision": revision,
                "business_ready": False,
                "database_integrated": False,
                "capture_enabled": False,
                "analysis_enabled": False,
                "dispatch_build_enabled": False,
                "payments_enabled": False,
            },
            headers={"Cache-Control": "no-store"},
        )

    @api.get("/health/live")
    def live() -> JSONResponse:
        return health("alive")

    @api.get("/health/ready")
    def ready() -> JSONResponse:
        return health("ready")

    @api.get("/api/v1/dispatch/health")
    def dispatch_status() -> JSONResponse:
        return JSONResponse(dispatch_health(), headers={"Cache-Control": "no-store"})

    @api.post("/api/v1/dispatch/build")
    def disabled_dispatch():
        # Reject without reading caller data or trusting caller provenance.
        return dispatch_build(DispatchRequest(adjudication={}))

    return api


def main() -> None:
    import uvicorn

    uvicorn.run(
        create_staging_app(),
        host="0.0.0.0",
        port=listen_port(),
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()

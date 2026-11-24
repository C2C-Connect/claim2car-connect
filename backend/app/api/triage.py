"""Layer 3 adjudication API.

The calculation modules remain available for controlled, synthetic tests. The
HTTP adjudication boundary is disabled until it can derive integrity, evidence,
vehicle identity, market valuation, and jurisdiction inputs from server-owned
verified records. Client-supplied values are never accepted as forensic truth.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from config import forensic_constants as C
from backend.app.security import require_internal_service

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])


@router.get("/health")
def triage_health() -> Dict[str, Any]:
    return {
        "status": "disabled",
        "layer": 3,
        "constants_version": C.VERSION,
        "adjudication_enabled": False,
        "reason": "SERVER_VERIFIED_EVIDENCE_REQUIRED",
        "calculation_modules": "controlled_testing_only",
    }


@router.post("/adjudicate", dependencies=[Depends(require_internal_service)])
def adjudicate() -> Dict[str, Any]:
    """Fail closed until the request is bound to server-verified evidence."""
    raise HTTPException(
        status_code=503,
        detail={
            "code": "SERVER_VERIFIED_EVIDENCE_REQUIRED",
            "message": (
                "Adjudication is unavailable until evidence integrity, manifest, "
                "vehicle identity, market sources, and jurisdiction inputs are "
                "derived from server-owned verified records."
            ),
        },
        headers={"Cache-Control": "no-store"},
    )

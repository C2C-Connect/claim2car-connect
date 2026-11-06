"""
Claim2Car Connect — FastAPI entrypoint (Milestone 5 surface).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.analysis import router as analysis_router
from backend.app.api.triage import router as triage_router
from backend.app.api.dispatch import router as dispatch_router
from backend.app.security import parse_cors_origins
from config import forensic_constants as C

app = FastAPI(
    title="Claim2Car Connect",
    version=C.VERSION,
    description="Physics-first forensic claims platform — Milestone 5 Reports & Dispatch",
)

# CORS: explicit allowlist only. Never allow_origins=["*"] with credentials.
_CORS_CREDENTIALS = True
_CORS_ORIGINS = parse_cors_origins(os.environ.get("CORS_ORIGINS"), allow_credentials=_CORS_CREDENTIALS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=_CORS_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

app.include_router(analysis_router)
app.include_router(triage_router)
app.include_router(dispatch_router)


@app.get("/health/live")
def live():
    return {"status": "alive", "service": "claim2car-connect", "version": C.VERSION}


@app.get("/health/ready")
def ready():
    return {
        "status": "ready",
        "environment": os.environ.get("C2C_ENVIRONMENT", os.environ.get("ENVIRONMENT", "development")),
        "constants_version": C.VERSION,
        "scope": "milestone_5_dispatch",
        "operator_payout_usd": C.OPERATOR_PAYOUT_USD,
        "owner_payout": None,
        "cors_origins": _CORS_ORIGINS,
    }


@app.get("/api/v1/config/constants")
def constants():
    return {
        "version": C.VERSION,
        "OPERATOR_PAYOUT_USD": C.OPERATOR_PAYOUT_USD,
        "ENSEMBLE_PHYSICS_WEIGHT": C.ENSEMBLE_PHYSICS_WEIGHT,
        "ENSEMBLE_AI_WEIGHT": C.ENSEMBLE_AI_WEIGHT,
        "S_I_PASS": C.S_I_PASS,
        "DEFAULT_SHOT_LIST": C.DEFAULT_SHOT_LIST,
        "LOW_IMPACT_EK_KJ": C.LOW_IMPACT_EK_KJ,
        "RTV_REVIEW_LOW": C.RTV_REVIEW_LOW,
    }

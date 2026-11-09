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
from config import forensic_constants as C

# Explicit origin allowlist only (no wildcard with credentials).
# Internal analysis surface: default is no cross-origin browser access.
ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("C2C_ANALYSIS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)

app = FastAPI(
    title="Claim2Car Connect",
    version=C.VERSION,
    description="Physics-first forensic claims platform — Milestone 5 Reports & Dispatch",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
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
        "environment": "development",
        "constants_version": C.VERSION,
        "scope": "milestone_5_dispatch",
    }


@app.get("/api/v1/config/constants")
def constants():
    return {
        "version": C.VERSION,
        "ENSEMBLE_PHYSICS_WEIGHT": C.ENSEMBLE_PHYSICS_WEIGHT,
        "ENSEMBLE_AI_WEIGHT": C.ENSEMBLE_AI_WEIGHT,
        "S_I_PASS": C.S_I_PASS,
        "DEFAULT_SHOT_LIST": C.DEFAULT_SHOT_LIST,
        "LOW_IMPACT_EK_KJ": C.LOW_IMPACT_EK_KJ,
        "RTV_REVIEW_LOW": C.RTV_REVIEW_LOW,
    }

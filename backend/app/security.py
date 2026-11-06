"""
Minimal service authentication for sensitive API endpoints.

Tokens from environment:
  C2C_SERVICE_TOKEN   – primary bearer token
  C2C_API_KEYS        – optional comma-separated alternate tokens

If no tokens are configured, protected routes fail closed (503).
"""
from __future__ import annotations

import os
import secrets
from typing import List, Optional

from fastapi import Header, HTTPException, status


def _configured_tokens() -> List[str]:
    tokens: List[str] = []
    primary = (os.environ.get("C2C_SERVICE_TOKEN") or "").strip()
    if primary:
        tokens.append(primary)
    raw = (os.environ.get("C2C_API_KEYS") or "").strip()
    if raw:
        tokens.extend(t.strip() for t in raw.split(",") if t.strip())
    seen = set()
    out: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def tokens_configured() -> bool:
    return bool(_configured_tokens())


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def require_service_token(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> str:
    configured = _configured_tokens()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "auth_not_configured",
                "message": "Service token is not configured. Set C2C_SERVICE_TOKEN.",
            },
            headers={"Cache-Control": "no-store"},
        )

    presented = _extract_bearer(authorization)
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_bearer_token",
                "message": "Authorization: Bearer <token> is required.",
            },
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )

    for expected in configured:
        if secrets.compare_digest(presented, expected):
            return presented

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_bearer_token",
            "message": "Invalid service token.",
        },
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )


def parse_cors_origins(
    raw: Optional[str] = None,
    *,
    allow_credentials: bool = True,
) -> List[str]:
    value = raw if raw is not None else os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in (value or "").split(",") if o.strip()]

    if not origins:
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]

    if allow_credentials and any(o == "*" for o in origins):
        origins = [o for o in origins if o != "*"]
        if not origins:
            origins = ["http://localhost:5173"]

    return origins

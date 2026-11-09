"""Fail-closed service authentication for internal analysis operations.

Configure C2C_INTERNAL_SERVICE_TOKEN out of band with a high-entropy
URL-safe bearer token (43-128 characters). Never commit the token.
This is a service boundary, not end-user identity or tenant authorization.
"""
from __future__ import annotations

import hmac
import os
import re

from fastapi import Header, HTTPException


def require_internal_service(authorization: str | None = Header(default=None)) -> str:
    expected = os.environ.get("C2C_INTERNAL_SERVICE_TOKEN", "")
    if not isinstance(expected, str) or re.fullmatch(r"[A-Za-z0-9_-]{43,128}", expected) is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "INTERNAL_SERVICE_AUTH_NOT_CONFIGURED"},
            headers={"Cache-Control": "no-store"},
        )
    supplied = authorization if isinstance(authorization, str) else ""
    if not supplied.isascii():
        raise HTTPException(
            status_code=400,
            detail={"code": "NON_ASCII_AUTHORIZATION_HEADER"},
            headers={"Cache-Control": "no-store"},
        )
    if not hmac.compare_digest(supplied, f"Bearer {expected}"):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED"},
            headers={"Cache-Control": "no-store", "WWW-Authenticate": "Bearer"},
        )
    return "claim2car_internal_service"

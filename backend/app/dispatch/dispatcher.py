"""Dispatch containment.

The prior builder accepted caller-assembled adjudication dictionaries and photo
hash lists. Those values are not a server-owned authorization context. Package
construction stays disabled until a tenant-bound verifier supplies a durable,
manifest-bound, consent- and review-authorized context.
"""
from __future__ import annotations

from typing import Any, Dict, List


class DispatchBlocked(RuntimeError):
    """Dispatch blocked because trusted evidence authorization is unavailable."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def build_dispatch(
    adjudication: Dict[str, Any],
    *,
    photo_hashes: List[str] | None = None,
    vin: str = "",
    vehicle: Dict[str, Any] | None = None,
):
    """No dict or caller-supplied hash list can authorize package construction."""
    raise DispatchBlocked("SERVER_VERIFIED_EVIDENCE_CONTEXT_REQUIRED")

"""Versioned, deterministic SHA-256 commitments for FAOS event-chain records.

This is integrity verification of the persisted event bytes/fields, not capture
authenticity, trusted timestamping, or independent notarization.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Iterable, Mapping
from uuid import UUID

from app.domain_events import DomainEvent

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GENESIS_DOMAIN = "FAOS_EVENT_CHAIN_GENESIS_V1"
ENTRY_DOMAIN = "FAOS_EVENT_HASH_V1"
HASH_VERSION = "event-hash-v1"


def _hex_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("EVENT_HASH_FIELD_MUST_BE_TEXT")
    return value.encode("utf-8").hex()


def normalize_tenant_id(tenant_id: str) -> str:
    try:
        return str(UUID(str(tenant_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("INVALID_TENANT_ID") from None


def genesis_hash(tenant_id: str, session_id: str) -> str:
    tenant = normalize_tenant_id(tenant_id)
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("INVALID_SESSION_ID")
    material = "\n".join((GENESIS_DOMAIN, tenant, _hex_text(session_id))).encode("ascii")
    return hashlib.sha256(material).hexdigest()


def event_hash(tenant_id: str, event: DomainEvent, previous_hash: str) -> str:
    """Commit to all persisted event fields and the previous link.

    The newline-separated encoding is unambiguous because free-text fields are
    UTF-8 hex encoded; sequence and UUID are canonical ASCII; the hash is
    lowercase hexadecimal. Payload JSON is committed as its exact stored text.
    """
    tenant = normalize_tenant_id(tenant_id)
    if not isinstance(event, DomainEvent):
        raise ValueError("DOMAIN_EVENT_REQUIRED")
    event.validate()
    if not isinstance(previous_hash, str) or not _HASH_RE.fullmatch(previous_hash):
        raise ValueError("INVALID_PREVIOUS_HASH")
    material = "\n".join((
        ENTRY_DOMAIN,
        tenant,
        _hex_text(event.session_id),
        _hex_text(event.event_id),
        str(event.sequence),
        _hex_text(event.kind),
        _hex_text(event.actor),
        _hex_text(event.occurred_at),
        _hex_text(event.reason),
        _hex_text(event.payload_json),
        _hex_text(event.schema_version),
        previous_hash,
    )).encode("ascii")
    return hashlib.sha256(material).hexdigest()


def _row_event(row: Mapping) -> DomainEvent:
    try:
        return DomainEvent(
            session_id=row["session_id"],
            event_id=row["event_id"],
            sequence=row["sequence"],
            kind=row["kind"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
            reason=row["reason"],
            payload_json=row["payload_json"],
            schema_version=row["schema_version"],
        )
    except KeyError:
        raise ValueError("MISSING_CONTEXT") from None


def verify_event_chain(tenant_id: str, session_id: str, rows: Iterable[Mapping]) -> dict:
    """Recompute the entire session chain from its deterministic genesis.

    Rows must include previous_hash and entry_hash persisted by the authority.
    Missing, out-of-order, altered, or unbound records fail closed. The result
    deliberately does not imply an external trust anchor.
    """
    tenant = normalize_tenant_id(tenant_id)
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("INVALID_SESSION_ID")
    records = list(rows)
    if not records:
        return {"valid": False, "reason": "EMPTY_EVENT_CHAIN", "tenant_id": tenant,
                "session_id": session_id, "event_count": 0, "chain_head": None}
    previous = genesis_hash(tenant, session_id)
    for expected_sequence, row in enumerate(records, start=1):
        try:
            if row["session_id"] != session_id:
                return {"valid": False, "reason": "SESSION_BINDING_MISMATCH", "failed_sequence": expected_sequence}
            if row["sequence"] != expected_sequence:
                return {"valid": False, "reason": "EVENT_SEQUENCE_GAP_OR_REORDER", "failed_sequence": expected_sequence}
            if row.get("hash_version") != HASH_VERSION:
                return {"valid": False, "reason": "UNSUPPORTED_EVENT_HASH_VERSION", "failed_sequence": expected_sequence}
            if row["previous_hash"] != previous:
                return {"valid": False, "reason": "PREVIOUS_HASH_MISMATCH", "failed_sequence": expected_sequence}
            stored_hash = row.get("entry_hash")
            if not isinstance(stored_hash, str) or not _HASH_RE.fullmatch(stored_hash):
                return {"valid": False, "reason": "INVALID_STORED_ENTRY_HASH", "failed_sequence": expected_sequence}
            computed = event_hash(tenant, _row_event(row), previous)
            if not hmac.compare_digest(computed, stored_hash):
                return {"valid": False, "reason": "EVENT_HASH_MISMATCH", "failed_sequence": expected_sequence}
            previous = computed
        except (KeyError, TypeError, ValueError) as error:
            reason = "MISSING_CONTEXT" if isinstance(error, KeyError) else str(error) or "INVALID_EVENT_RECORD"
            return {"valid": False, "reason": reason, "failed_sequence": expected_sequence}
    return {"valid": True, "reason": "CHAIN_VALID", "tenant_id": tenant, "session_id": session_id,
            "event_count": len(records), "chain_head": previous, "genesis_hash": genesis_hash(tenant, session_id)}

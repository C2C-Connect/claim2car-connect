"""Persistent Collision Lifecycle Record identity.

A collision is a platform-owned incident identity, independent of any insurer
claim number. This first slice establishes the CLR root and its PostgreSQL
authority boundary; related vehicles, participants, claims, events and outbox
records are owned by the same tenant-scoped aggregate.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import psycopg

from database.capture_sessions import CaptureAuthorizationError, CaptureSessionStore


class CollisionLifecycleNotFound(LookupError):
    pass


class CollisionLifecycleConflict(ValueError):
    pass


@dataclass(frozen=True)
class CollisionLifecycleRecord:
    collision_id: str
    tenant_id: str
    request_id: str
    created_by: str
    created_at: str
    state: str
    version: int
    created: bool


@dataclass(frozen=True)
class CollisionClaimLink:
    collision_id: str
    claim_id: str
    capture_session_id: str
    capture_protocol_version: str
    linked_by: str
    linked_at: str
    created: bool


class CollisionLifecycleStore:
    """Tenant-authorized CLR identity operations over the PostgreSQL authority DB."""

    def __init__(self, sessions: CaptureSessionStore):
        if not isinstance(sessions, CaptureSessionStore):
            raise ValueError("INVALID_COLLISION_LIFECYCLE_CONFIGURATION")
        self.sessions = sessions

    @staticmethod
    def _uuid(value, code):
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(code) from None

    @staticmethod
    def _record(row, created=False):
        if row is None:
            raise CollisionLifecycleNotFound("COLLISION_LIFECYCLE_NOT_FOUND")
        return CollisionLifecycleRecord(
            collision_id=str(row[0]),
            tenant_id=str(row[1]),
            request_id=str(row[2]),
            created_by=row[3],
            created_at=row[4].isoformat(),
            state=row[5],
            version=row[6],
            created=created,
        )

    @staticmethod
    def _require_operator(actor):
        if actor.actor_role not in ("operator", "supervisor"):
            raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")

    def create(self, authorization, *, collision_id, request_id, occurred_at=None):
        collision_id = self._uuid(collision_id, "INVALID_COLLISION_ID")
        request_id = self._uuid(request_id, "INVALID_COLLISION_REQUEST_ID")
        occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
        if not isinstance(occurred_at, str) or not occurred_at.strip():
            raise ValueError("INVALID_COLLISION_TIMESTAMP")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            outcome = conn.execute(
                "SELECT faos.create_collision_lifecycle_record("
                "%s::uuid,%s::uuid,%s::uuid,%s::text,%s::timestamptz)",
                (actor.tenant_id, collision_id, request_id, actor.actor_id, occurred_at),
            ).fetchone()[0]
            if outcome not in ("ACCEPTED", "DUPLICATE"):
                raise CollisionLifecycleConflict("COLLISION_RECORD_NOT_ACCEPTED")
            row = conn.execute(
                "SELECT collision_id,tenant_id,request_id,created_by,created_at,state,version "
                "FROM faos.collision_lifecycle_records "
                "WHERE tenant_id=%s AND request_id=%s",
                (actor.tenant_id, request_id),
            ).fetchone()
            if row is None or str(row[0]) != collision_id:
                raise CollisionLifecycleConflict("COLLISION_RECORD_READBACK_MISMATCH")
            return self._record(row, created=(outcome == "ACCEPTED"))


    def link_claim(self, authorization, *, collision_id, claim_id, request_id, occurred_at=None):
        collision_id = self._uuid(collision_id, "INVALID_COLLISION_ID")
        claim_id = self._uuid(claim_id, "INVALID_CLAIM_CASE_ID")
        request_id = self._uuid(request_id, "INVALID_COLLISION_LINK_REQUEST_ID")
        occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()
        if not isinstance(occurred_at, str) or not occurred_at.strip():
            raise ValueError("INVALID_COLLISION_TIMESTAMP")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            try:
                outcome = conn.execute(
                    "SELECT faos.link_collision_claim(%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::text,%s::timestamptz)",
                    (actor.tenant_id, collision_id, claim_id, request_id, actor.actor_id, occurred_at),
                ).fetchone()[0]
            except psycopg.errors.RaiseException as error:
                code = error.diag.message_primary
                if code == "COLLISION_CLAIM_LINK_AUTHORITY_DENIED":
                    raise CaptureAuthorizationError(code) from None
                if code in ("COLLISION_EVENT_IDEMPOTENCY_CONFLICT", "COLLISION_CLAIM_LINK_CONFLICT"):
                    raise CollisionLifecycleConflict(code) from None
                raise
            if outcome == "CONFLICT":
                raise CollisionLifecycleConflict("COLLISION_CLAIM_LINK_CONFLICT")
            if outcome not in ("ACCEPTED", "DUPLICATE"):
                raise CollisionLifecycleConflict("COLLISION_CLAIM_LINK_NOT_ACCEPTED")
            row = conn.execute(
                "SELECT l.collision_id,l.claim_id,c.capture_session_id,s.capture_protocol_version,l.linked_by,l.linked_at "
                "FROM faos.collision_claim_links l "
                "JOIN faos.collision_lifecycle_records r ON r.tenant_id=l.tenant_id AND r.collision_id=l.collision_id "
                "JOIN faos.claim_cases c ON c.tenant_id=l.tenant_id AND c.claim_id=l.claim_id "
                "JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id "
                "WHERE l.tenant_id=%s AND l.collision_id=%s AND l.claim_id=%s "
                "AND r.created_by=%s AND c.created_by=%s",
                (actor.tenant_id, collision_id, claim_id, actor.actor_id, actor.actor_id),
            ).fetchone()
            if row is None:
                raise CollisionLifecycleConflict("COLLISION_CLAIM_LINK_READBACK_MISMATCH")
            return CollisionClaimLink(
                collision_id=str(row[0]), claim_id=str(row[1]),
                capture_session_id=str(row[2]), capture_protocol_version=row[3],
                linked_by=row[4], linked_at=row[5].isoformat(),
                created=(outcome == "ACCEPTED"),
            )

    def list_claims(self, authorization, collision_id):
        collision_id = self._uuid(collision_id, "INVALID_COLLISION_ID")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            rows = conn.execute(
                "SELECT l.collision_id,l.claim_id,c.capture_session_id,s.capture_protocol_version,l.linked_by,l.linked_at "
                "FROM faos.collision_claim_links l "
                "JOIN faos.collision_lifecycle_records r ON r.tenant_id=l.tenant_id AND r.collision_id=l.collision_id "
                "JOIN faos.claim_cases c ON c.tenant_id=l.tenant_id AND c.claim_id=l.claim_id "
                "JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id "
                "WHERE l.tenant_id=%s AND l.collision_id=%s "
                "AND (r.created_by=%s OR %s='supervisor') "
                "AND (c.created_by=%s OR %s='supervisor') "
                "ORDER BY l.linked_at,l.claim_id",
                (actor.tenant_id, collision_id, actor.actor_id, actor.actor_role,
                 actor.actor_id, actor.actor_role),
            ).fetchall()
            return [CollisionClaimLink(
                collision_id=str(row[0]), claim_id=str(row[1]),
                capture_session_id=str(row[2]), capture_protocol_version=row[3],
                linked_by=row[4], linked_at=row[5].isoformat(), created=False,
            ) for row in rows]


    def list_review_claims(self, authorization, collision_id):
        """List only collision-linked capture sessions for an independent reviewer."""
        collision_id = self._uuid(collision_id, "INVALID_COLLISION_ID")
        with self.sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("reviewer", "supervisor"):
                raise CaptureAuthorizationError("REVIEWER_IDENTITY_REQUIRED")
            rows = conn.execute(
                "SELECT l.collision_id,l.claim_id,c.capture_session_id,s.capture_protocol_version,l.linked_by,l.linked_at "
                "FROM faos.collision_claim_links l "
                "JOIN faos.collision_lifecycle_records r ON r.tenant_id=l.tenant_id AND r.collision_id=l.collision_id "
                "JOIN faos.claim_cases c ON c.tenant_id=l.tenant_id AND c.claim_id=l.claim_id "
                "JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id "
                "WHERE l.tenant_id=%s AND l.collision_id=%s "
                "AND r.created_by<>%s AND c.created_by<>%s "
                "ORDER BY l.linked_at,l.claim_id",
                (actor.tenant_id, collision_id, actor.actor_id, actor.actor_id),
            ).fetchall()
            return [CollisionClaimLink(
                collision_id=str(row[0]), claim_id=str(row[1]),
                capture_session_id=str(row[2]), capture_protocol_version=row[3],
                linked_by=row[4], linked_at=row[5].isoformat(), created=False,
            ) for row in rows]

    def get(self, authorization, collision_id):
        collision_id = self._uuid(collision_id, "INVALID_COLLISION_ID")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            row = conn.execute(
                "SELECT collision_id,tenant_id,request_id,created_by,created_at,state,version "
                "FROM faos.collision_lifecycle_records "
                "WHERE tenant_id=%s AND collision_id=%s "
                "AND (created_by=%s OR %s='supervisor')",
                (actor.tenant_id, collision_id, actor.actor_id, actor.actor_role),
            ).fetchone()
            return self._record(row)

"""Persistent Collision Lifecycle Record identity.

A collision is a platform-owned incident identity, independent of any insurer
claim number. This first slice establishes the CLR root and its PostgreSQL
authority boundary; related vehicles, participants, claims, events and outbox
records are owned by the same tenant-scoped aggregate.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

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

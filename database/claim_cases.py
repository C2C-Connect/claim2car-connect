"""Tenant-scoped persistent claim-case identity and capture-session association."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from database.capture_sessions import CaptureAuthorizationError, CaptureSessionStore
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, validate_protocol_version


class ClaimCaseNotFound(LookupError):
    pass


class ClaimCaseConflict(ValueError):
    pass


@dataclass(frozen=True)
class ClaimCase:
    claim_id: str
    tenant_id: str
    created_by: str
    created_at: str
    state: str
    created: bool
    capture_session_id: str | None
    capture_protocol_version: str = DEFAULT_CAPTURE_PROTOCOL


class ClaimCaseStore:
    def __init__(self, sessions):
        if not isinstance(sessions, CaptureSessionStore):
            raise ValueError("INVALID_CLAIM_CASE_CONFIGURATION")
        self.sessions = sessions

    @staticmethod
    def _identifier(value, code):
        try:
            return str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(code) from None

    @staticmethod
    def _record(row, created=False):
        if row is None:
            raise ClaimCaseNotFound("CLAIM_CASE_NOT_FOUND")
        return ClaimCase(
            claim_id=str(row[0]), tenant_id=str(row[1]), created_by=row[2],
            created_at=row[3].isoformat(), state=row[4], created=created,
            capture_session_id=str(row[5]) if row[5] is not None else None,
            capture_protocol_version=row[6],
        )

    @staticmethod
    def _require_operator(actor):
        if actor.actor_role not in ("operator", "supervisor"):
            raise CaptureAuthorizationError("OPERATOR_IDENTITY_REQUIRED")

    def create(self, authorization, *, claim_id, request_id, capture_protocol_version=DEFAULT_CAPTURE_PROTOCOL):
        claim_id = self._identifier(claim_id, "INVALID_CLAIM_CASE_ID")
        request_id = self._identifier(request_id, "INVALID_CLAIM_CASE_REQUEST_ID")
        capture_protocol_version = validate_protocol_version(capture_protocol_version)
        session_id = str(uuid4())
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            outcome = conn.execute(
                "SELECT faos.create_claim_case(%s::uuid,%s::uuid,%s::uuid,%s::text,%s::text,%s::text)",
                (actor.tenant_id, claim_id, request_id, actor.actor_id, session_id, capture_protocol_version),
            ).fetchone()[0]
            if outcome not in ("ACCEPTED", "DUPLICATE"):
                raise ClaimCaseConflict("CLAIM_CASE_CREATE_NOT_ACCEPTED")
            row = conn.execute(
                "SELECT c.claim_id,c.tenant_id,c.created_by,c.created_at,c.state,c.capture_session_id,s.capture_protocol_version "
                "FROM faos.claim_cases c JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id WHERE c.tenant_id=%s AND c.request_id=%s",
                (actor.tenant_id, request_id),
            ).fetchone()
            return self._record(row, created=(outcome == "ACCEPTED"))

    def get(self, authorization, claim_id):
        claim_id = self._identifier(claim_id, "INVALID_CLAIM_CASE_ID")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            row = conn.execute(
                "SELECT c.claim_id,c.tenant_id,c.created_by,c.created_at,c.state,c.capture_session_id,s.capture_protocol_version "
                "FROM faos.claim_cases c JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id WHERE c.tenant_id=%s AND c.claim_id=%s AND c.created_by=%s",
                (actor.tenant_id, claim_id, actor.actor_id),
            ).fetchone()
            return self._record(row)

    def list_owned(self, authorization, *, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("INVALID_CLAIM_CASE_LIMIT")
        with self.sessions._authorized(authorization) as (conn, actor):
            self._require_operator(actor)
            rows = conn.execute(
                "SELECT c.claim_id,c.tenant_id,c.created_by,c.created_at,c.state,c.capture_session_id,s.capture_protocol_version "
                "FROM faos.claim_cases c JOIN faos.sessions s ON s.tenant_id=c.tenant_id AND s.session_id=c.capture_session_id WHERE c.tenant_id=%s AND c.created_by=%s "
                "ORDER BY created_at DESC,claim_id DESC LIMIT %s",
                (actor.tenant_id, actor.actor_id, limit),
            ).fetchall()
            return [self._record(row) for row in rows]

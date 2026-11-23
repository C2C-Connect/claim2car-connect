"""Tenant-scoped journal reads with server-owned persisted-chain verification.

A legacy schema without the M1 hash columns is explicitly reported as
LEGACY_UNHASHED for controlled compatibility tests. On an authority schema,
readback recomputes every persisted hash and fails closed before replay or
completion evaluation.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from app.domain_events import DomainEvent, EventJournal
from database.event_hash_chain import HASH_VERSION, verify_event_chain
from database.journal import tenant_transaction

HASH_COLUMNS = ("previous_hash", "entry_hash", "hash_version")


@dataclass(frozen=True)
class PersistedJournalReadback:
    tenant_id: str
    session_id: str
    chain_verification: dict
    journal: EventJournal | None

    @property
    def verified(self):
        return self.chain_verification.get("valid") is True

    @property
    def status(self):
        if self.verified:
            return "CHAIN_VERIFIED"
        return self.chain_verification.get("status", "CHAIN_INVALID")


def _validate_session(session_id):
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("INVALID_SESSION")


def _hash_columns_available(conn):
    found = conn.execute(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_schema='faos' AND table_name='events' AND column_name=ANY(%s)",
        (list(HASH_COLUMNS),),
    ).fetchone()[0]
    return found == len(HASH_COLUMNS)


def _read_journal_readback(conn, tenant, session_id):
    tenant = str(UUID(str(tenant)))
    session = conn.execute(
        "SELECT 1 FROM faos.sessions WHERE tenant_id=%s AND session_id=%s",
        (tenant, session_id),
    ).fetchone()
    if session is None:
        raise ValueError("SESSION_NOT_FOUND_OR_NOT_VISIBLE")

    if not _hash_columns_available(conn):
        legacy_rows = conn.execute(
            "SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,"
            "payload_json,schema_version FROM faos.events "
            "WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
            (tenant, session_id),
        ).fetchall()
        journal = EventJournal.replay(session_id, (DomainEvent(*row) for row in legacy_rows))
        report = {
            "valid": False,
            "status": "LEGACY_UNHASHED",
            "reason": "HASH_COLUMNS_NOT_PRESENT",
            "tenant_id": tenant,
            "session_id": session_id,
            "event_count": len(legacy_rows),
            "chain_head": None,
        }
        journal.chain_verification = report
        journal.integrity_status = "LEGACY_UNHASHED"
        return PersistedJournalReadback(tenant, session_id, report, journal)

    rows = conn.execute(
        "SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,"
        "payload_json,schema_version,previous_hash,entry_hash,hash_version "
        "FROM faos.events WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
        (tenant, session_id),
    ).fetchall()
    records = [dict(zip(
        ("session_id","event_id","sequence","kind","actor","occurred_at","reason",
         "payload_json","schema_version","previous_hash","entry_hash","hash_version"),
        row,
    )) for row in rows]
    report = verify_event_chain(tenant, session_id, records)
    report["status"] = "CHAIN_VERIFIED" if report.get("valid") else "CHAIN_INVALID"
    if not report.get("valid"):
        return PersistedJournalReadback(tenant, session_id, report, None)
    journal = EventJournal.replay(session_id, (DomainEvent(
        row["session_id"],row["event_id"],row["sequence"],row["kind"],row["actor"],
        row["occurred_at"],row["reason"],row["payload_json"],row["schema_version"],
    ) for row in records))
    journal.chain_verification = report
    journal.integrity_status = "CHAIN_VERIFIED"
    return PersistedJournalReadback(tenant, session_id, report, journal)


def read_persisted_journal(conn, tenant, session_id):
    """Read DB-owned rows and return their independently recomputed integrity result."""
    _validate_session(session_id)
    tenant = str(UUID(str(tenant)))
    with tenant_transaction(conn, tenant):
        return _read_journal_readback(conn, tenant, session_id)


def verify_persisted_event_chain(conn, tenant, session_id):
    """Return integrity evidence only; no client-provided hashes or roots are accepted."""
    result = read_persisted_journal(conn, tenant, session_id)
    return result.chain_verification


def load_journal(conn, tenant, session_id):
    """Compatibility read that refuses replay when a migrated chain is invalid."""
    result = read_persisted_journal(conn, tenant, session_id)
    if result.journal is None:
        raise ValueError("EVENT_CHAIN_INVALID:" + str(result.chain_verification.get("reason")))
    return result.journal


@contextmanager
def locked_journal(conn, tenant, session_id):
    """Hold append-serialization lock while reading and validating persisted chain.

    Requires an idle autocommit connection. Missing/invisible sessions are
    rejected. The database rows and their hashes are recomputed within the same
    transaction and lock, before completion eligibility is evaluated.
    """
    _validate_session(session_id)
    tenant = str(UUID(str(tenant)))
    with tenant_transaction(conn, tenant):
        conn.execute(
            "SELECT faos.lock_session_for_completion(%s::uuid,%s::text)",
            (tenant, session_id),
        )
        result = _read_journal_readback(conn, tenant, session_id)
        if result.journal is None:
            raise ValueError("EVENT_CHAIN_INVALID:" + str(result.chain_verification.get("reason")))
        yield result.journal

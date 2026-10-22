"""Tenant-scoped journal reads and transaction-held snapshots; no completion write."""
from contextlib import contextmanager
from app.domain_events import DomainEvent, EventJournal
from database.journal import tenant_transaction


def _validate_session(session_id):
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('INVALID_SESSION')


def _read_journal(conn, tenant, session_id):
    session = conn.execute(
        'SELECT 1 FROM faos.sessions WHERE tenant_id=%s AND session_id=%s',
        (str(tenant), session_id),
    ).fetchone()
    if session is None:
        raise ValueError('SESSION_NOT_FOUND_OR_NOT_VISIBLE')
    rows = conn.execute(
        'SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,'
        'payload_json,schema_version FROM faos.events '
        'WHERE tenant_id=%s AND session_id=%s ORDER BY sequence',
        (str(tenant), session_id),
    ).fetchall()
    return EventJournal.replay(session_id, (DomainEvent(*row) for row in rows))


def load_journal(conn, tenant, session_id):
    _validate_session(session_id)
    with tenant_transaction(conn, tenant):
        journal = _read_journal(conn, tenant, session_id)
    return journal


@contextmanager
def locked_journal(conn, tenant, session_id):
    """Hold the append-serialization lock until the caller exits this context.

    Requires an idle autocommit connection. Missing/invisible sessions are
    rejected by the database lock function. Caller supplies trusted bytes/root;
    this context neither authenticates those inputs nor persists completion.
    """
    _validate_session(session_id)
    with tenant_transaction(conn, tenant):
        conn.execute('SELECT faos.lock_session_for_completion(%s::uuid,%s::text)',
                     (str(tenant), session_id))
        yield _read_journal(conn, tenant, session_id)

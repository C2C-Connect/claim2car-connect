"""Read persisted synthetic event history; not evidence-state reconstruction."""
from app.domain_events import DomainEvent, EventJournal
from database.journal import tenant_transaction


def load_journal(conn, tenant, session_id):
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('INVALID_SESSION')
    with tenant_transaction(conn, tenant):
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
        journal = EventJournal.replay(session_id, (DomainEvent(*row) for row in rows))
    return journal

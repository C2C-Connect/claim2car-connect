from contextlib import contextmanager
from dataclasses import fields
from uuid import UUID
from psycopg.pq import TransactionStatus
from app.domain_events import DomainEvent, EventJournal

@contextmanager
def tenant_transaction(conn, tenant):
    tenant = str(UUID(str(tenant)))
    if not conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError('IDLE_AUTOCOMMIT_CONNECTION_REQUIRED')
    with conn.transaction():
        if conn.execute("SELECT NULLIF(current_setting('faos.tenant_id',true),'')").fetchone()[0] is not None:
            raise ValueError('STALE_TENANT_CONTEXT')
        conn.execute("SELECT set_config('faos.tenant_id',%s,true)",(tenant,))
        yield conn

def append(conn, tenant, event):
    if not isinstance(event,DomainEvent):
        raise ValueError('INVALID_EVENT')
    event.validate()
    tenant = str(UUID(str(tenant)))
    with tenant_transaction(conn,tenant):
        args=(tenant,event.session_id,event.event_id,event.sequence,event.kind,event.actor,
              event.occurred_at,event.reason,event.payload_json,event.schema_version)
        result=conn.execute('SELECT faos.append_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',args).fetchone()[0]
    return result

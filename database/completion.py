"""Atomic evaluated historical receipts for trusted synthetic writer code.

The writer is privileged and can bypass this Python policy through direct SQL.
This is not an authenticated public endpoint, terminal lifecycle transition,
production sealing service, or guarantee of eligibility after later events.
"""
from dataclasses import dataclass
from uuid import UUID
from app.synthetic_evidence import Decision
from database.eligibility import _check_registered_journal
from database.readback import locked_journal

@dataclass(frozen=True)
class CompletionResult:
    tenant_id: str
    session_id: str
    request_id: str
    seal_event_id: str
    event_sequence: int
    receipt_status: str
    decision: Decision


def record_registered_completion(conn, tenant, session_id, request_id, supplied_bytes):
    tenant = str(UUID(str(tenant)))
    request_id = str(UUID(str(request_id)))
    with locked_journal(conn, tenant, session_id) as journal:
        if conn.execute('SELECT current_user').fetchone()[0] != 'faos_writer':
            raise ValueError('TRUSTED_WRITER_ROLE_REQUIRED')
        decision, seal = _check_registered_journal(conn, tenant, session_id, journal, supplied_bytes)
        sequence = journal.events[-1].sequence
        status = conn.execute(
            'SELECT faos.record_completion_receipt(%s::uuid,%s::text,%s::uuid,%s::text,%s::bigint)',
            (tenant, session_id, request_id, seal.event_id, sequence),
        ).fetchone()[0]
        if status not in ('RECORDED', 'DUPLICATE'):
            raise RuntimeError('UNEXPECTED_RECEIPT_RESULT')
        result = CompletionResult(tenant, session_id, request_id, seal.event_id, sequence, status, decision)
    return result

"""Historical receipt inspection; matching history is not current eligibility.

Tenant identity must come from a trusted boundary. This module does not provide
authentication, validate current artifact bytes, or advance lifecycle state.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from database.readback import locked_journal

@dataclass(frozen=True)
class ReceiptInspection:
    tenant_id: str
    session_id: str
    request_id: str
    seal_event_id: str
    event_sequence: int
    manifest_digest: str
    shot_list_version: str
    recorded_at: datetime
    authority_role: str
    authority_session: str
    current_event_sequence: int
    snapshot_matches_current_history: bool


def inspect_completion_receipt(conn, tenant, session_id, request_id):
    """Read receipt/root metadata under the session lock; never assert eligibility."""
    tenant = str(UUID(str(tenant)))
    request_id = str(UUID(str(request_id)))
    with locked_journal(conn, tenant, session_id) as journal:
        row = conn.execute(
            'SELECT r.request_id::text,r.seal_event_id,r.event_sequence,'
            'm.manifest_digest,m.shot_list_version,r.recorded_at,'
            'r.authority_role::text,r.authority_session::text '
            'FROM faos.completion_receipts r JOIN faos.manifest_roots m '
            'USING(tenant_id,session_id,seal_event_id) '
            'WHERE r.tenant_id=%s AND r.session_id=%s AND r.request_id=%s',
            (tenant, session_id, request_id),
        ).fetchone()
        if row is None:
            raise ValueError('RECEIPT_NOT_FOUND_OR_NOT_VISIBLE')
        current = journal.events[-1].sequence if journal.events else 0
        result = ReceiptInspection(tenant, session_id, *row, current, row[2] == current)
    return result

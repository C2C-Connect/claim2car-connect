"""Registry-backed synthetic completion decisions; never persists completion.

Roots require fixture/admin endorsement. This is not authenticated production
sealing, legal consent verification, or proof of artifact authenticity.
"""
from app.synthetic_evidence import reconstruct, check_completion
from database.readback import locked_journal


def check_registered_completion(conn, tenant, session_id, supplied_bytes):
    """Evaluate current history using the matching stored root, not a caller root.

    The session lock spans reconstruction, root lookup, and evaluation. A returned
    decision describes that snapshot; it does not freeze later session changes.
    """
    with locked_journal(conn, tenant, session_id) as journal:
        state = reconstruct(session_id, journal.events)
        if state.seal is None:
            raise ValueError('REGISTERED_MANIFEST_SEAL_REQUIRED')
        root = conn.execute(
            'SELECT manifest_digest,shot_list_version FROM faos.manifest_roots '
            'WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s',
            (str(tenant), session_id, state.seal.event_id),
        ).fetchone()
        if root is None:
            raise ValueError('MANIFEST_ROOT_NOT_REGISTERED')
        if root != (state.seal.manifest_digest, state.seal.shot_list_version):
            raise ValueError('REGISTERED_ROOT_MISMATCH')
        return check_completion(session_id, journal.events, supplied_bytes, root[0])

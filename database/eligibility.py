"""Registry-backed synthetic decisions; fixture authority is not production sealing."""
from app.synthetic_evidence import reconstruct, check_completion
from database.readback import locked_journal


def _check_registered_journal(conn, tenant, session_id, journal, supplied_bytes):
    """Internal helper: caller must already hold the session's transaction lock."""
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
    decision = check_completion(session_id, journal.events, supplied_bytes, root[0])
    return decision, state.seal


def check_registered_completion(conn, tenant, session_id, supplied_bytes):
    """Evaluate a locked snapshot; never writes a receipt or freezes later events."""
    with locked_journal(conn, tenant, session_id) as journal:
        decision, seal = _check_registered_journal(conn, tenant, session_id, journal, supplied_bytes)
    return decision

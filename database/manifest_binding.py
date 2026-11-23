"""Consumer-side fail-closed checks for registered seal bindings."""
from uuid import UUID


def verify_registered_manifest_binding(conn, tenant, session_id, seal_event_id):
    """Verify the stored seal binding inside caller's tenant-scoped transaction."""
    tenant = str(UUID(str(tenant)))
    valid = conn.execute(
        "SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)",
        (tenant, session_id, seal_event_id),
    ).fetchone()[0]
    if valid is not True:
        raise ValueError("MANIFEST_ROOT_BINDING_INVALID")
    return True

"""Independent Python and PostgreSQL verification of a registered seal binding."""
import hashlib
import hmac
import json
import re
from uuid import UUID

from database.event_hash_chain import verify_event_chain

_HEX_256 = re.compile(r"^[0-9a-f]{64}$")


def manifest_context_binding_hash(tenant, session_id, protocol, sequence, chain_hash):
    tenant = str(UUID(str(tenant)))
    if not all(isinstance(value, str) and value for value in (session_id, protocol)):
        raise ValueError("INVALID_MANIFEST_CONTEXT")
    if not isinstance(sequence, int) or sequence < 1 or not isinstance(chain_hash, str) or not _HEX_256.fullmatch(chain_hash):
        raise ValueError("INVALID_MANIFEST_CHAIN_BINDING")
    material = "\n".join((
        "FAOS_MANIFEST_CONTEXT_BINDING_V1",
        tenant,
        session_id.encode("utf-8").hex(),
        protocol.encode("utf-8").hex(),
        str(sequence),
        chain_hash,
    )).encode("ascii")
    return hashlib.sha256(material).hexdigest()


def verify_registered_manifest_binding(conn, tenant, session_id, seal_event_id):
    """Independently recompute chain prefix/context and require SQL verifier agreement.

    Caller must hold tenant context and the session serialization lock.
    """
    tenant = str(UUID(str(tenant)))
    root = conn.execute(
        "SELECT manifest_digest,shot_list_version,seal_sequence,seal_chain_hash,"
        "context_binding_hash,binding_version FROM faos.manifest_roots "
        "WHERE tenant_id=%s AND session_id=%s AND seal_event_id=%s",
        (tenant, session_id, seal_event_id),
    ).fetchone()
    if root is None:
        raise ValueError("MANIFEST_ROOT_NOT_REGISTERED")
    if root[5] != "manifest-context-v1":
        raise ValueError("UNSUPPORTED_MANIFEST_BINDING_VERSION")
    protocol = conn.execute(
        "SELECT capture_protocol_version FROM faos.sessions WHERE tenant_id=%s AND session_id=%s",
        (tenant, session_id),
    ).fetchone()
    if protocol is None or protocol[0] != root[1]:
        raise ValueError("MANIFEST_ROOT_PROTOCOL_MISMATCH")
    rows = conn.execute(
        "SELECT session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,"
        "schema_version,previous_hash,entry_hash,hash_version FROM faos.events "
        "WHERE tenant_id=%s AND session_id=%s ORDER BY sequence",
        (tenant, session_id),
    ).fetchall()
    columns = ("session_id","event_id","sequence","kind","actor","occurred_at","reason",
               "payload_json","schema_version","previous_hash","entry_hash","hash_version")
    records = [dict(zip(columns, row)) for row in rows]
    full_chain = verify_event_chain(tenant, session_id, records)
    if not full_chain.get("valid"):
        raise ValueError("MANIFEST_ROOT_EVENT_CHAIN_INVALID")
    prefix_records = [record for record in records if record["sequence"] <= root[2]]
    chain = verify_event_chain(tenant, session_id, prefix_records)
    if not chain.get("valid") or chain.get("event_count") != root[2]:
        raise ValueError("MANIFEST_ROOT_CHAIN_PREFIX_INVALID")
    seal = prefix_records[-1] if prefix_records else None
    if seal is None or seal["event_id"] != seal_event_id or seal["kind"] != "MANIFEST_SEALED":
        raise ValueError("MANIFEST_ROOT_SEAL_SEQUENCE_MISMATCH")
    try:
        seal_payload = json.loads(seal["payload_json"])
    except (TypeError, ValueError):
        raise ValueError("MANIFEST_ROOT_SEAL_PAYLOAD_INVALID") from None
    if seal_payload.get("manifest_digest") != root[0] or seal_payload.get("shot_list_version") != root[1]:
        raise ValueError("MANIFEST_ROOT_SEAL_PAYLOAD_MISMATCH")
    if not hmac.compare_digest(chain["chain_head"], root[3]):
        raise ValueError("MANIFEST_ROOT_CHAIN_HASH_MISMATCH")
    expected_context = manifest_context_binding_hash(tenant, session_id, protocol[0], root[2], root[3])
    if not hmac.compare_digest(expected_context, root[4]):
        raise ValueError("MANIFEST_ROOT_CONTEXT_HASH_MISMATCH")
    sql_valid = conn.execute(
        "SELECT faos.verify_manifest_root_binding(%s::uuid,%s::text,%s::text)",
        (tenant, session_id, seal_event_id),
    ).fetchone()[0]
    if sql_valid is not True:
        raise ValueError("MANIFEST_ROOT_BINDING_INVALID")
    return {
        "valid": True,
        "binding_version": root[5],
        "seal_sequence": root[2],
        "seal_chain_hash": root[3],
        "context_binding_hash": root[4],
        "verified_event_count": full_chain["event_count"],
        "python_sql_agreement": True,
    }

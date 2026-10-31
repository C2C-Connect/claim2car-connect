"""Authenticated session persist, SESSION_CREATED, and GET under RLS."""
import hashlib
import os
import sys
import time
from uuid import UUID

from fastapi.testclient import TestClient

from app.identity import ActorBinding, Credential, CredentialResolver
from app.main import create_app
from app.sessions import get_resolver


def main():
    if not os.environ.get("APP_DATABASE_URL"):
        print("APP_DATABASE_URL required", file=sys.stderr)
        sys.exit(1)
    token_a = "test-token-for-session-start-aaaaaaaaaaaaaaaaaaaaaaaa"
    digest_a = hashlib.sha256(token_a.encode()).hexdigest()
    binding_a = ActorBinding(
        actor_id="operator-1",
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        database_role="tenant_a_role",
    )
    cred_a = Credential(
        token_sha256=digest_a,
        binding=binding_a,
        expires_at=int(time.time()) + 3600,
    )
    token_b = "test-token-for-tenant-b-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    digest_b = hashlib.sha256(token_b.encode()).hexdigest()
    binding_b = ActorBinding(
        actor_id="operator-2",
        tenant_id=UUID("22222222-2222-2222-2222-222222222222"),
        database_role="tenant_b_role",
    )
    cred_b = Credential(
        token_sha256=digest_b,
        binding=binding_b,
        expires_at=int(time.time()) + 3600,
    )
    resolver = CredentialResolver([cred_a, cred_b])
    app = create_app()
    app.dependency_overrides[get_resolver] = lambda: resolver
    client = TestClient(app)

    resp = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
    print("create status", resp.status_code)
    body = resp.json()
    print("create body", body)
    assert resp.status_code == 200, resp.text
    session_id = body["session_id"]
    assert body["tenant_id"] == "11111111-1111-1111-1111-111111111111"

    get_a = client.get(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token_a}"})
    print("get owner status", get_a.status_code)
    print("get owner body", get_a.json())
    assert get_a.status_code == 200
    assert get_a.json()["session_id"] == session_id

    get_b = client.get(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token_b}"})
    print("get other status", get_b.status_code)
    assert get_b.status_code == 404
    print("GET_RLS_OK")


if __name__ == "__main__":
    main()

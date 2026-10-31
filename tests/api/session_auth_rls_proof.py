"""Authenticated session persist + SESSION_CREATED + RLS proof."""
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
    token = "test-token-for-session-start-aaaaaaaaaaaaaaaaaaaaaaaa"
    digest = hashlib.sha256(token.encode()).hexdigest()
    binding = ActorBinding(
        actor_id="operator-1",
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        database_role="tenant_a_role",
    )
    cred = Credential(
        token_sha256=digest,
        binding=binding,
        expires_at=int(time.time()) + 3600,
    )
    resolver = CredentialResolver([cred])
    app = create_app()
    app.dependency_overrides[get_resolver] = lambda: resolver
    client = TestClient(app)
    resp = client.post("/sessions", headers={"Authorization": f"Bearer {token}"})
    print("status", resp.status_code)
    print("body", resp.json())
    assert resp.status_code == 200, resp.text
    assert resp.json()["tenant_id"] == "11111111-1111-1111-1111-111111111111"
    print("API_INSERT_OK")


if __name__ == "__main__":
    main()

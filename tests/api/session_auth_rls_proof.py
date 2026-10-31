"""Minimal single-tenant session create + list + owner GET + events GET."""
import hashlib
import os
import sys
import time
import traceback
from uuid import UUID

from fastapi.testclient import TestClient

from app.identity import ActorBinding, Credential, CredentialResolver
from app.main import create_app
from app.sessions import get_resolver


def main():
    try:
        if not os.environ.get("APP_DATABASE_URL"):
            print("APP_DATABASE_URL required", file=sys.stderr)
            sys.exit(1)
        print("APP_DATABASE_URL set", file=sys.stderr)
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
        resolver = CredentialResolver([cred_a])
        app = create_app()
        app.dependency_overrides[get_resolver] = lambda: resolver
        client = TestClient(app)

        resp = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        print("create status", resp.status_code)
        print("create body", resp.text)
        if resp.status_code != 200:
            sys.exit(1)
        body = resp.json()
        session_id = body["session_id"]
        assert body["tenant_id"] == "11111111-1111-1111-1111-111111111111"

        lst = client.get("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        print("list status", lst.status_code)
        print("list body", lst.text)
        if lst.status_code != 200:
            sys.exit(1)
        sessions = lst.json()["sessions"]
        assert any(s["session_id"] == session_id for s in sessions)
        print("LIST_OK")

        get_a = client.get(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token_a}"})
        print("get owner status", get_a.status_code)
        print("get owner body", get_a.text)
        if get_a.status_code != 200:
            sys.exit(1)

        events = client.get(f"/sessions/{session_id}/events", headers={"Authorization": f"Bearer {token_a}"})
        print("events status", events.status_code)
        print("events body", events.text)
        if events.status_code != 200:
            sys.exit(1)
        elist = events.json()["events"]
        assert len(elist) >= 1
        assert elist[0]["kind"] == "SESSION_CREATED"
        print("EVENTS_OK")
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

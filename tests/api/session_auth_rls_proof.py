"""Minimal single-tenant session create + list + owner GET + events GET + tenant health + consent + vehicle + artifact + quality + review."""
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

        health = client.get("/health/tenant", headers={"Authorization": f"Bearer {token_a}"})
        print("tenant health status", health.status_code)
        print("tenant health body", health.text)
        if health.status_code != 200:
            sys.exit(1)
        hbody = health.json()
        assert hbody["status"] == "ok"
        assert hbody["tenant_id"] == "11111111-1111-1111-1111-111111111111"
        assert hbody["actor_id"] == "operator-1"
        print("TENANT_HEALTH_OK")

        resp = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        print("create status", resp.status_code)
        print("create body", resp.text)
        if resp.status_code != 200:
            sys.exit(1)
        body = resp.json()
        session_id = body["session_id"]
        assert body["tenant_id"] == "11111111-1111-1111-1111-111111111111"

        consent = client.post(f"/sessions/{session_id}/consent", headers={"Authorization": f"Bearer {token_a}"})
        print("consent status", consent.status_code)
        print("consent body", consent.text)
        if consent.status_code != 200:
            sys.exit(1)
        cbody = consent.json()
        assert cbody["kind"] == "CONSENT_RECORDED"
        print("CONSENT_OK")

        vehicle = client.post(f"/sessions/{session_id}/vehicle", headers={"Authorization": f"Bearer {token_a}"})
        print("vehicle status", vehicle.status_code)
        print("vehicle body", vehicle.text)
        if vehicle.status_code != 200:
            sys.exit(1)
        vbody = vehicle.json()
        assert vbody["kind"] == "VEHICLE_RECORDED"
        assert vbody["vin"] == "1HGCM82633A004352"
        print("VEHICLE_OK")

        artifact = client.post(f"/sessions/{session_id}/artifact", headers={"Authorization": f"Bearer {token_a}"})
        print("artifact status", artifact.status_code)
        print("artifact body", artifact.text)
        if artifact.status_code != 200:
            sys.exit(1)
        abody = artifact.json()
        assert abody["kind"] == "ARTIFACT_REGISTERED"
        assert abody["content_hash"].startswith("sha256:")
        print("ARTIFACT_OK")

        quality = client.post(f"/sessions/{session_id}/quality", headers={"Authorization": f"Bearer {token_a}"})
        print("quality status", quality.status_code)
        print("quality body", quality.text)
        if quality.status_code != 200:
            sys.exit(1)
        qbody = quality.json()
        assert qbody["kind"] == "QUALITY_RECORDED"
        assert qbody["score"] == 0.87
        assert qbody["shot_slot"] == "front-left-damage"
        print("QUALITY_OK")

        review = client.post(f"/sessions/{session_id}/review", headers={"Authorization": f"Bearer {token_a}"})
        print("review status", review.status_code)
        print("review body", review.text)
        if review.status_code != 200:
            sys.exit(1)
        rbody = review.json()
        assert rbody["kind"] == "REVIEW_RECORDED"
        assert rbody["note"] == "human-review-required"
        print("REVIEW_OK")

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
        assert len(elist) >= 6
        kinds = [e["kind"] for e in elist]
        assert "SESSION_CREATED" in kinds
        assert "CONSENT_RECORDED" in kinds
        assert "VEHICLE_RECORDED" in kinds
        assert "ARTIFACT_REGISTERED" in kinds
        assert "QUALITY_RECORDED" in kinds
        assert "REVIEW_RECORDED" in kinds
        print("EVENTS_OK")
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Minimal single-tenant session create + list + owner GET + events GET + tenant health + consent + vehicle + artifact + quality + review + seal + routing (ROUTED and forced HUMAN_REVIEW)."""
import hashlib
import os
import sys
import time
import traceback
from uuid import UUID, uuid4

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
        if consent.status_code != 200:
            sys.exit(1)
        print("CONSENT_OK")

        vehicle = client.post(f"/sessions/{session_id}/vehicle", headers={"Authorization": f"Bearer {token_a}"})
        print("vehicle status", vehicle.status_code)
        if vehicle.status_code != 200:
            sys.exit(1)
        print("VEHICLE_OK")

        artifact = client.post(f"/sessions/{session_id}/artifact", headers={"Authorization": f"Bearer {token_a}"})
        print("artifact status", artifact.status_code)
        if artifact.status_code != 200:
            sys.exit(1)
        print("ARTIFACT_OK")

        quality = client.post(f"/sessions/{session_id}/quality", headers={"Authorization": f"Bearer {token_a}"})
        print("quality status", quality.status_code)
        if quality.status_code != 200:
            sys.exit(1)
        print("QUALITY_OK")

        review = client.post(f"/sessions/{session_id}/review", headers={"Authorization": f"Bearer {token_a}"})
        print("review status", review.status_code)
        if review.status_code != 200:
            sys.exit(1)
        print("REVIEW_OK")

        seal = client.post(f"/sessions/{session_id}/seal", headers={"Authorization": f"Bearer {token_a}"})
        print("seal status", seal.status_code)
        if seal.status_code != 200:
            sys.exit(1)
        print("SEAL_OK")

        routing = client.post(f"/sessions/{session_id}/routing", headers={"Authorization": f"Bearer {token_a}"})
        print("routing status", routing.status_code)
        print("routing body", routing.text)
        if routing.status_code != 200:
            sys.exit(1)
        rtbody = routing.json()
        assert rtbody["kind"] == "ROUTING_REQUESTED"
        shortlist = rtbody["dealer_shortlist"]
        # Brand-matched: only Honda location
        assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in shortlist
        assert "cccccccc-cccc-cccc-cccc-cccccccccccc" not in shortlist
        print("ROUTING_BRAND_MATCH_OK")

        get_routing = client.get(f"/sessions/{session_id}/routing", headers={"Authorization": f"Bearer {token_a}"})
        print("get routing status", get_routing.status_code)
        print("get routing body", get_routing.text)
        if get_routing.status_code != 200:
            sys.exit(1)
        grbody = get_routing.json()
        assert grbody["outcome"] == "ROUTED"
        assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in grbody["candidates"]
        assert "cccccccc-cccc-cccc-cccc-cccccccccccc" not in grbody["candidates"]
        print("GET_ROUTING_OK")

        # --- Force empty shortlist for HUMAN_REVIEW ---
        print("=== FORCING EMPTY CAPACITY FOR HUMAN_REVIEW ===")
        import psycopg
        with psycopg.connect(os.environ["APP_DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE faos.location_capacity SET capacity = 0 WHERE tenant_id = %s",
                    ("11111111-1111-1111-1111-111111111111",),
                )
            conn.commit()
        print("Capacity zeroed")

        # New session for the empty case
        resp2 = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        if resp2.status_code != 200:
            print("second create failed", resp2.text)
            sys.exit(1)
        session_id2 = resp2.json()["session_id"]

        # Minimal path: just routing is enough for the outcome, but to keep parity we can skip the others
        routing2 = client.post(f"/sessions/{session_id2}/routing", headers={"Authorization": f"Bearer {token_a}"})
        print("routing2 status", routing2.status_code)
        print("routing2 body", routing2.text)
        if routing2.status_code != 200:
            sys.exit(1)
        rtbody2 = routing2.json()
        assert rtbody2["kind"] == "ROUTING_REQUESTED"
        assert rtbody2["dealer_shortlist"] == []
        print("ROUTING_EMPTY_OK")

        get_routing2 = client.get(f"/sessions/{session_id2}/routing", headers={"Authorization": f"Bearer {token_a}"})
        print("get routing2 status", get_routing2.status_code)
        print("get routing2 body", get_routing2.text)
        if get_routing2.status_code != 200:
            sys.exit(1)
        grbody2 = get_routing2.json()
        assert grbody2["outcome"] == "HUMAN_REVIEW"
        assert grbody2["candidates"] == []
        assert grbody2["selected_location_id"] is None
        print("GET_HUMAN_REVIEW_OK")

        lst = client.get("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        print("list status", lst.status_code)
        if lst.status_code != 200:
            sys.exit(1)
        sessions = lst.json()["sessions"]
        assert any(s["session_id"] == session_id for s in sessions)
        assert any(s["session_id"] == session_id2 for s in sessions)
        print("LIST_OK")

        get_a = client.get(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token_a}"})
        if get_a.status_code != 200:
            sys.exit(1)

        events = client.get(f"/sessions/{session_id}/events", headers={"Authorization": f"Bearer {token_a}"})
        print("events status", events.status_code)
        if events.status_code != 200:
            sys.exit(1)
        elist = events.json()["events"]
        assert len(elist) >= 8
        kinds = [e["kind"] for e in elist]
        assert "ROUTING_REQUESTED" in kinds
        print("EVENTS_OK")

        # Expired reservation must not consume capacity
        print("=== EXPIRED RESERVATION DOES NOT BLOCK CAPACITY ===")
        import psycopg
        with psycopg.connect(os.environ["APP_DATABASE_URL"], autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO faos.capacity_reservations
                        (tenant_id, reservation_id, location_id, request_digest, status, expires_at)
                    VALUES (%s, %s, %s, %s, 'ACTIVE', now() - interval '1 hour')
                """, (
                    "11111111-1111-1111-1111-111111111111",
                    str(uuid4()),
                    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "expired-test-" + str(uuid4()),
                ))
        # Restore capacity for the test
        with psycopg.connect(os.environ["APP_DATABASE_URL"], autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE faos.location_capacity
                    SET capacity = 2
                    WHERE location_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
                """)
        resp3 = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        if resp3.status_code != 200:
            sys.exit(1)
        session_id3 = resp3.json()["session_id"]
        client.post(f"/sessions/{session_id3}/vehicle", headers={"Authorization": f"Bearer {token_a}"})
        routing3 = client.post(f"/sessions/{session_id3}/routing", headers={"Authorization": f"Bearer {token_a}"})
        print("routing3 status", routing3.status_code)
        print("routing3 body", routing3.text)
        if routing3.status_code != 200:
            sys.exit(1)
        rtbody3 = routing3.json()
        assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in rtbody3["dealer_shortlist"]
        print("EXPIRED_RESERVATION_IGNORED_OK")

        print("=== ALL PROOFS PASSED INCLUDING HUMAN_REVIEW ===")
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

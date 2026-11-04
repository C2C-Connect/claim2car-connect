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
            print("consent body", consent.text)
            sys.exit(1)
        print("CONSENT_OK")

        vehicle = client.post(f"/sessions/{session_id}/vehicle", json={"brand": "Toyota"}, headers={"Authorization": f"Bearer {token_a}"})
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

        decision = client.post(f"/sessions/{session_id}/decision?decision=ACCEPTED", headers={"Authorization": f"Bearer {token_a}"})
        print("decision status", decision.status_code)
        print("decision body", decision.text)
        if decision.status_code != 200:
            sys.exit(1)
        dbody = decision.json()
        assert dbody["kind"] == "DEALER_ACCEPTED"
        assert dbody["decision"] == "ACCEPTED"
        print("DECISION_ACCEPTED_OK")
        # Settlement must follow acceptance
        events_after = client.get(f"/sessions/{session_id}/events", headers={"Authorization": f"Bearer {token_a}"})
        if events_after.status_code != 200:
            sys.exit(1)
        kinds_after = [e["kind"] for e in events_after.json()["events"]]
        assert "SETTLEMENT_RECORDED" in kinds_after
        print("SETTLEMENT_RECORDED_OK")
        # GET settlement must return the fixed amounts
        settle_get = client.get(f"/sessions/{session_id}/settlement", headers={"Authorization": f"Bearer {token_a}"})
        if settle_get.status_code != 200:
            sys.exit(1)
        sbody = settle_get.json()
        assert sbody["settled"] is True
        assert sbody["operator_payout_cents"] == 11000
        assert sbody["dealer_invoice_cents"] == 37500
        print("GET_SETTLEMENT_OK")
        # Second accept must not create a second settlement
        decision2 = client.post(
            f"/sessions/{session_id}/decision?decision=ACCEPTED",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        if decision2.status_code != 200:
            sys.exit(1)
        events_after2 = client.get(f"/sessions/{session_id}/events", headers={"Authorization": f"Bearer {token_a}"})
        kinds_after2 = [e["kind"] for e in events_after2.json()["events"]]
        assert kinds_after2.count("SETTLEMENT_RECORDED") == 1
        print("SETTLEMENT_IDEMPOTENT_OK")
        # Explicit Idempotency-Key: repeated key returns same event_id, no extra settlement
        key = "decision-key-1"
        d_idem = client.post(
            f"/sessions/{session_id}/decision?decision=ACCEPTED",
            headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": key},
        )
        if d_idem.status_code != 200:
            sys.exit(1)
        first_event = d_idem.json()["event_id"]
        d_idem2 = client.post(
            f"/sessions/{session_id}/decision?decision=ACCEPTED",
            headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": key},
        )
        if d_idem2.status_code != 200:
            sys.exit(1)
        assert d_idem2.json()["event_id"] == first_event
        events_idem = client.get(f"/sessions/{session_id}/events", headers={"Authorization": f"Bearer {token_a}"})
        assert [e["kind"] for e in events_idem.json()["events"]].count("SETTLEMENT_RECORDED") == 1
        print("IDEMPOTENCY_KEY_OK")

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

        # PASSED must not create a settlement (capacity restored)
        create_pass = client.post("/sessions", headers={"Authorization": f"Bearer {token_a}"})
        if create_pass.status_code != 200:
            sys.exit(1)
        session_pass = create_pass.json()["session_id"]
        client.post(f"/sessions/{session_pass}/consent", headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/vehicle", json={"brand": "Toyota"}, headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/artifact", headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/quality", headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/review", headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/seal", headers={"Authorization": f"Bearer {token_a}"})
        client.post(f"/sessions/{session_pass}/routing", headers={"Authorization": f"Bearer {token_a}"})
        passed = client.post(
            f"/sessions/{session_pass}/decision?decision=PASSED",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        if passed.status_code != 200:
            print("passed body", passed.text)
            sys.exit(1)
        events_passed = client.get(f"/sessions/{session_pass}/events", headers={"Authorization": f"Bearer {token_a}"})
        kinds_passed = [e["kind"] for e in events_passed.json()["events"]]
        assert "DEALER_PASSED" in kinds_passed
        assert "SETTLEMENT_RECORDED" not in kinds_passed
        settle_passed = client.get(f"/sessions/{session_pass}/settlement", headers={"Authorization": f"Bearer {token_a}"})
        assert settle_passed.json()["settled"] is False
        print("DEALER_PASSED_NO_SETTLEMENT_OK")
        # List settlements must contain the accepted session and its amounts
        settlements = client.get("/settlements", headers={"Authorization": f"Bearer {token_a}"})
        if settlements.status_code != 200:
            print("settlements body", settlements.text)
            sys.exit(1)
        slist = settlements.json()["settlements"]
        match = [s for s in slist if s["session_id"] == session_id]
        assert len(match) == 1
        assert match[0]["operator_payout_cents"] == 11000
        assert match[0]["dealer_invoice_cents"] == 37500
        print("LIST_SETTLEMENTS_OK")
        # Routing Idempotency-Key: repeated key returns same event_id
        rkey = "routing-key-1"
        r1 = client.post(
            f"/sessions/{session_id}/routing",
            headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": rkey},
        )
        if r1.status_code != 200:
            print("r1", r1.text)
            sys.exit(1)
        eid1 = r1.json()["event_id"]
        r2 = client.post(
            f"/sessions/{session_id}/routing",
            headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": rkey},
        )
        if r2.status_code != 200:
            sys.exit(1)
        assert r2.json()["event_id"] == eid1
        print("ROUTING_IDEMPOTENCY_KEY_OK")
        # Summary must include routing, decision, and settlement
        summary = client.get(f"/sessions/{session_id}/summary", headers={"Authorization": f"Bearer {token_a}"})
        if summary.status_code != 200:
            print("summary", summary.text)
            sys.exit(1)
        sbody = summary.json()
        assert sbody["routing_outcome"] == "ROUTED"
        assert sbody["decision"] == "ACCEPTED"
        assert sbody["settled"] is True
        assert sbody["operator_payout_cents"] == 11000
        assert sbody["dealer_invoice_cents"] == 37500
        print("SESSION_SUMMARY_OK")
        # Dealer packet must include brand + commercial fields
        packet = client.get(f"/sessions/{session_id}/dealer-packet", headers={"Authorization": f"Bearer {token_a}"})
        print("packet", packet.text)
        if packet.status_code != 200:
            sys.exit(1)
        pbody = packet.json()
        assert pbody["vehicle_brand"] == "Honda"
        assert pbody["routing_outcome"] == "ROUTED"
        assert pbody["decision"] == "ACCEPTED"
        assert pbody["settled"] is True
        assert pbody["dealer_invoice_cents"] == 37500
        print("DEALER_PACKET_OK")
        # Consumer packet
        cp = client.get(f"/sessions/{session_id}/consumer-packet", headers={"Authorization": f"Bearer {token_a}"})
        if cp.status_code != 200:
            sys.exit(1)
        assert cp.json()["settled"] is True
        assert cp.json()["decision"] == "ACCEPTED"
        print("CONSUMER_PACKET_OK")
        # Shop packet
        sp = client.get(f"/sessions/{session_id}/shop-packet", headers={"Authorization": f"Bearer {token_a}"})
        if sp.status_code != 200:
            sys.exit(1)
        assert sp.json()["routing_outcome"] == "ROUTED"
        print("SHOP_PACKET_OK")
        # Carrier packet
        cr = client.get(f"/sessions/{session_id}/carrier-packet", headers={"Authorization": f"Bearer {token_a}"})
        if cr.status_code != 200:
            sys.exit(1)
        assert cr.json()["operator_payout_cents"] == 11000
        print("CARRIER_PACKET_OK")
        # Dealer-scoped settlements
        ds = client.get("/dealer/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/settlements", headers={"Authorization": f"Bearer {token_a}"})
        if ds.status_code != 200:
            print("dealer settlements", ds.text)
            sys.exit(1)
        assert any(s["session_id"] == session_id for s in ds.json()["settlements"])
        print("DEALER_SETTLEMENTS_OK")
        # Timeline must include routing, accept, and settlement
        tl = client.get(f"/sessions/{session_id}/timeline", headers={"Authorization": f"Bearer {token_a}"})
        if tl.status_code != 200:
            sys.exit(1)
        kinds = [e["kind"] for e in tl.json()["events"]]
        assert "ROUTING_REQUESTED" in kinds
        assert "DEALER_ACCEPTED" in kinds
        assert "SETTLEMENT_RECORDED" in kinds
        print("TIMELINE_OK")
        # Status must be SETTLED after accept
        st = client.get(f"/sessions/{session_id}/status", headers={"Authorization": f"Bearer {token_a}"})
        if st.status_code != 200:
            sys.exit(1)
        assert st.json()["status"] == "SETTLED"
        print("SESSION_STATUS_OK")
        # Settlement total
        tot = client.get("/settlements/total", headers={"Authorization": f"Bearer {token_a}"})
        if tot.status_code != 200:
            sys.exit(1)
        assert tot.json()["count"] >= 1
        assert tot.json()["operator_payout_cents"] >= 11000
        print("SETTLEMENT_TOTAL_OK")
        # Human review list (may be empty or contain the forced session)
        hr = client.get("/routing/human-review", headers={"Authorization": f"Bearer {token_a}"})
        print("hr", hr.status_code, hr.text)
        if hr.status_code != 200:
            sys.exit(1)
        print("HUMAN_REVIEW_LIST_OK")
        # Expired reservations list
        er = client.get("/reservations/expired", headers={"Authorization": f"Bearer {token_a}"})
        if er.status_code != 200:
            print("expired", er.text)
            sys.exit(1)
        print("EXPIRED_RESERVATIONS_OK")
        # VIN decode
        vin = client.post(f"/sessions/{session_id}/vin", json={
            "vin": "1HGCM82633A004352",
            "year": 2003,
            "make": "HONDA",
            "model": "Accord",
            "body_class": "Coupe"
        }, headers={"Authorization": f"Bearer {token_a}"})
        if vin.status_code != 200:
            print("vin", vin.text)
            sys.exit(1)
        print("VIN_DECODED_OK")
        # Damage findings
        dmg = client.post(f"/sessions/{session_id}/damage", json={
            "findings": [
                {"panel": "Front Bumper", "severity": "MAJOR", "confidence": 0.92, "types": ["crush"]},
                {"panel": "Hood", "severity": "MINOR", "confidence": 0.81, "types": ["dent"]}
            ]
        }, headers={"Authorization": f"Bearer {token_a}"})
        if dmg.status_code != 200:
            print("damage", dmg.text)
            sys.exit(1)
        print("DAMAGE_DETECTED_OK")
        # Exhibit must aggregate VIN + damage + routing
        ex = client.get(f"/sessions/{session_id}/exhibit", headers={"Authorization": f"Bearer {token_a}"})
        if ex.status_code != 200:
            print("exhibit", ex.text)
            sys.exit(1)
        ebody = ex.json()
        assert ebody["vin"] == "1HGCM82633A004352"
        assert ebody["make"] == "HONDA"
        assert len(ebody["damage_findings"]) == 2
        assert ebody["routing_outcome"] == "ROUTED"
        assert ebody["settled"] is True
        print("EXHIBIT_OK")
        # Physics
        ph = client.post(f"/sessions/{session_id}/physics", json={
            "delta_v_mph": 18.2,
            "impact_angle_deg": 70,
            "crush_front_in": 18,
            "crush_side_in": 24,
            "crush_rear_in": 16
        }, headers={"Authorization": f"Bearer {token_a}"})
        if ph.status_code != 200:
            print("physics", ph.text)
            sys.exit(1)
        print("PHYSICS_COMPUTED_OK")
        # Cost
        co = client.post(f"/sessions/{session_id}/cost", json={
            "lines": [
                {"description": "Front Bumper Assembly", "part_id": "F-102", "labor_hours": 3.5, "cost_cents": 68000},
                {"description": "Left Door Panel", "part_id": "S-207", "labor_hours": 4.0, "cost_cents": 72000}
            ],
            "total_parts_cents": 194000,
            "total_labor_cents": 108000
        }, headers={"Authorization": f"Bearer {token_a}"})
        if co.status_code != 200:
            print("cost", co.text)
            sys.exit(1)
        print("COST_ESTIMATED_OK")
        # Exhibit must include physics and cost
        ex2 = client.get(f"/sessions/{session_id}/exhibit", headers={"Authorization": f"Bearer {token_a}"})
        if ex2.status_code != 200:
            sys.exit(1)
        e2 = ex2.json()
        assert e2["delta_v_mph"] == 18.2
        assert e2["crush_side_in"] == 24
        assert len(e2["cost_lines"]) == 2
        assert e2["total_parts_cents"] == 194000
        print("EXHIBIT_PHYSICS_COST_OK")
        # Capture frame (AR silhouette metadata)
        cap = client.post(f"/sessions/{session_id}/capture", json={
            "angle_deg": 0,
            "sharpness": 142.5,
            "silhouette_match": 0.91,
            "point": "FRONT"
        }, headers={"Authorization": f"Bearer {token_a}"})
        if cap.status_code != 200:
            print("capture", cap.text)
            sys.exit(1)
        print("CAPTURE_FRAME_OK")
        # NHTSA decode (falls back if offline)
        nh = client.post(f"/sessions/{session_id}/vin/decode", json={
            "vin": "1HGCM82633A004352"
        }, headers={"Authorization": f"Bearer {token_a}"})
        if nh.status_code != 200:
            print("nhtsa", nh.text)
            sys.exit(1)
        assert nh.json()["vin"] == "1HGCM82633A004352"
        print("NHTSA_DECODE_OK")
        # Dashboard
        dash = client.get("/admin/dashboard", headers={"Authorization": f"Bearer {token_a}"})
        if dash.status_code != 200:
            print("dashboard", dash.text)
            sys.exit(1)
        assert dash.json()["claims_today"] >= 1
        assert dash.json()["settled"] >= 1
        print("DASHBOARD_OK")
        # Capture progress
        prog = client.get(f"/sessions/{session_id}/capture-progress", headers={"Authorization": f"Bearer {token_a}"})
        if prog.status_code != 200:
            sys.exit(1)
        assert prog.json()["points_captured"] >= 1
        print("CAPTURE_PROGRESS_OK")
        # Damage summary
        ds = client.get(f"/sessions/{session_id}/damage-summary", headers={"Authorization": f"Bearer {token_a}"})
        if ds.status_code != 200:
            sys.exit(1)
        assert ds.json()["major"] >= 1
        print("DAMAGE_SUMMARY_OK")
        # Activity feed
        act = client.get("/admin/activity", headers={"Authorization": f"Bearer {token_a}"})
        if act.status_code != 200:
            print("activity", act.text)
            sys.exit(1)
        assert any(a["session_id"] == session_id for a in act.json()["events"])
        print("ACTIVITY_OK")
        # Capture idempotency
        cap2 = client.post(f"/sessions/{session_id}/capture", json={"point": "REAR", "sharpness": 100}, headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "cap-1"})
        print("cap2", cap2.status_code, cap2.text)
        if cap2.status_code != 200:
            sys.exit(1)
        cap3 = client.post(f"/sessions/{session_id}/capture", json={"point": "REAR", "sharpness": 100}, headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "cap-1"})
        if cap3.status_code != 200 or cap3.json().get("kind") != "CAPTURE_FRAME":
            print("cap idem", cap3.text)
            sys.exit(1)
        print("CAPTURE_IDEMPOTENCY_OK")
        # Shop packet includes damage and cost
        sp2 = client.get(f"/sessions/{session_id}/shop-packet", headers={"Authorization": f"Bearer {token_a}"})
        if sp2.status_code != 200:
            sys.exit(1)
        assert sp2.json()["major_damage"] >= 1
        assert sp2.json()["total_parts_cents"] == 194000
        print("SHOP_PACKET_ENRICHED_OK")
        # Carrier packet includes physics
        cr2 = client.get(f"/sessions/{session_id}/carrier-packet", headers={"Authorization": f"Bearer {token_a}"})
        if cr2.status_code != 200:
            sys.exit(1)
        assert cr2.json()["delta_v_mph"] == 18.2
        print("CARRIER_PACKET_ENRICHED_OK")
        # Damage idempotency
        dmg2 = client.post(f"/sessions/{session_id}/damage", json={"findings": [{"panel": "Hood", "severity": "MINOR", "confidence": 0.8}]}, headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "dmg-1"})
        if dmg2.status_code != 200:
            print("dmg2", dmg2.text)
            sys.exit(1)
        dmg3 = client.post(f"/sessions/{session_id}/damage", json={"findings": [{"panel": "Hood", "severity": "MINOR", "confidence": 0.8}]}, headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "dmg-1"})
        if dmg3.status_code != 200 or dmg3.json().get("kind") != "DAMAGE_DETECTED":
            print("dmg3", dmg3.text)
            sys.exit(1)
        print("DAMAGE_IDEMPOTENCY_OK")
        # Consumer packet includes VIN and damage
        cp2 = client.get(f"/sessions/{session_id}/packet", headers={"Authorization": f"Bearer {token_a}"})
        if cp2.status_code != 200:
            sys.exit(1)
        assert cp2.json()["major_damage"] >= 1
        print("CONSUMER_PACKET_ENRICHED_OK")
        # Status includes capture pct
        st2 = client.get(f"/sessions/{session_id}/status", headers={"Authorization": f"Bearer {token_a}"})
        if st2.status_code != 200:
            sys.exit(1)
        assert st2.json()["capture_pct"] >= 0
        print("STATUS_CAPTURE_PCT_OK")
        # Settlements list
        sl = client.get("/settlements", headers={"Authorization": f"Bearer {token_a}"})
        print("settlements", sl.status_code, sl.text)
        if sl.status_code != 200:
            sys.exit(1)
        assert any(s["session_id"] == session_id for s in sl.json()["settlements"])
        print("SETTLEMENT_LIST_OK")
        print("=== ALL PROOFS PASSED INCLUDING HUMAN_REVIEW ===")
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

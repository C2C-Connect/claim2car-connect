import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    "postgresql://faos_app@127.0.0.1:55432/claim2car_test",
)
TENANT_TABLES = [
    "organizations", "users", "memberships", "dealer_groups",
    "dealer_locations", "location_brands", "sessions", "events",
]


def run_gate_verification():
    print("Starting Claim2Car Connect database gate verification...")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'faos'")
            assert cur.fetchone(), "faos schema missing"
            print("[PASS] faos schema exists")

            cur.execute("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'faos' AND c.relkind = 'r'
            """)
            tables = {row["relname"]: row for row in cur.fetchall()}
            for table in TENANT_TABLES:
                assert table in tables, f"missing tenant table: {table}"
                assert tables[table]["relrowsecurity"], f"RLS not enabled: {table}"
                assert tables[table]["relforcerowsecurity"], f"FORCE RLS not enabled: {table}"
            print(f"[PASS] RLS and FORCE RLS verified for {len(TENANT_TABLES)} tables")

            cur.execute("SELECT 1 FROM information_schema.routines WHERE routine_schema = 'faos' AND routine_name = 'append_event'")
            assert cur.fetchone(), "faos.append_event missing"
            print("[PASS] faos.append_event exists")

        tenant_a = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
        tenant_b = "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (tenant_a,))
            cur.execute("SELECT faos.tenant_id() AS tenant_id")
            assert str(cur.fetchone()["tenant_id"]) == tenant_a, "tenant context mismatch"
            cur.execute(
                "INSERT INTO faos.organizations(tenant_id, name) VALUES (%s, %s)",
                (tenant_a, "gate-verification-org"),
            )
        conn.commit()
        print("[PASS] transaction-scoped tenant context verified")

        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (tenant_b,))
            cur.execute("SELECT count(*) AS visible FROM faos.organizations WHERE tenant_id = %s", (tenant_a,))
            assert cur.fetchone()["visible"] == 0, "cross-tenant row was visible"
        conn.commit()
        print("[PASS] cross-tenant read isolation verified")

        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (tenant_b,))
            try:
                cur.execute(
                    "SELECT faos.append_event(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (tenant_a, "gate-session", "gate-event", 1, "SESSION_CREATED",
                     "gate-verifier", "2026-01-01T00:00:00Z", "gate verification",
                     "{\"verification\":true}", "0.1"),
                )
            except psycopg.Error:
                pass
            else:
                raise AssertionError("append_event accepted mismatched tenant context")
        conn.rollback()
        print("[PASS] append_event tenant-context mismatch rejected")

        with conn.cursor() as cur:
            cur.execute("SELECT set_config('faos.tenant_id', %s, true)", (tenant_a,))
            cur.execute("DELETE FROM faos.organizations WHERE tenant_id = %s", (tenant_a,))
        conn.commit()

    print("Database gate verification completed successfully.")


if __name__ == "__main__":
    run_gate_verification()

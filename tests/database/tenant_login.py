"""Tenant-bound PostgreSQL login fixtures for legacy and authority schemas."""
import os
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


class TenantLogin:
    """Provision one test login bound to exactly one tenant.

    Pre-cutover schemas use the legacy faos_app login. Authority schemas get
    a unique login role mapped to the requested tenant in the private registry.
    """

    def __init__(self, tenant, *, memberships=("faos_app",), organization_name="synthetic tenant fixture"):
        self.tenant = str(tenant)
        self.admin_url = os.getenv(
            "MIGRATION_TEST_ADMIN_URL",
            "postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test",
        )
        self.app_url = os.getenv(
            "APP_DATABASE_URL",
            "postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test",
        )
        self.authority = False
        self.role_name = None
        self.password = None
        with psycopg.connect(self.admin_url, autocommit=True, connect_timeout=5) as admin:
            self.authority = admin.execute(
                "SELECT to_regclass('faos.tenant_login_bindings') IS NOT NULL"
            ).fetchone()[0]
            admin.execute(
                "INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s) "
                "ON CONFLICT (tenant_id) DO NOTHING",
                (self.tenant, organization_name),
            )
            if self.authority:
                self.role_name = "c2c_test_" + uuid.uuid4().hex[:20]
                self.password = uuid.uuid4().hex
                admin.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(self.role_name), sql.Literal(self.password))
                )
                for membership in memberships:
                    admin.execute(
                        sql.SQL("GRANT {} TO {}").format(
                            sql.Identifier(membership), sql.Identifier(self.role_name)
                        )
                    )
                admin.execute(
                    "INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id,enabled) "
                    "SELECT oid,rolname,%s,true FROM pg_roles WHERE rolname=%s",
                    (self.tenant, self.role_name),
                )
                binding = admin.execute(
                    "SELECT tenant_id::text,enabled FROM faos.tenant_login_bindings "
                    "WHERE role_name=%s",
                    (self.role_name,),
                ).fetchone()
                if binding != (self.tenant, True):
                    raise RuntimeError("TEST_LOGIN_TENANT_BINDING_FAILED")
                self.url = make_conninfo(
                    self.app_url, user=self.role_name, password=self.password
                )
            else:
                self.url = self.app_url

    def connect(self, *, autocommit=True):
        return psycopg.connect(self.url, autocommit=autocommit, connect_timeout=5)

    def close(self):
        if not self.authority or not self.role_name:
            return
        with psycopg.connect(self.admin_url, autocommit=True, connect_timeout=5) as admin:
            admin.execute(
                "DELETE FROM faos.tenant_login_bindings WHERE role_name=%s",
                (self.role_name,),
            )
            admin.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(self.role_name))
            )
        self.role_name = None

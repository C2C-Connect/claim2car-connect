"""PostgreSQL integration tests for the independent CLR identity root."""
import hashlib
import time
import unittest
import uuid

from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.identity import ActorBinding, Credential, CredentialResolver
from database.capture_sessions import CaptureSessionStore
from database.collision_lifecycle import (
    CollisionLifecycleConflict,
    CollisionLifecycleNotFound,
    CollisionLifecycleStore,
)


class CollisionLifecycleIntegration(unittest.TestCase):
    def setUp(self):
        import test_tenant_authority_integration as fixtures
        self.f = fixtures.TenantAuthorityIntegration()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.tokens = ["G" * 43, "H" * 43]
        credentials = []
        dsns = {}
        for index, role in enumerate(self.f.roles):
            password = uuid.uuid4().hex
            self.f.admin.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
            )
            dsns[role] = make_conninfo(
                self.f.admin.info.dsn, dbname=self.f.db, user=role, password=password
            )
            credentials.append(Credential(
                hashlib.sha256(self.tokens[index].encode()).hexdigest(),
                ActorBinding("clr-operator-" + str(index), uuid.UUID(self.f.tenants[index]), role),
                int(time.time()) + 3600,
            ))
        self.store = CollisionLifecycleStore(
            CaptureSessionStore(CredentialResolver(credentials), dsns)
        )

    def auth(self, index=0):
        return "Bearer " + self.tokens[index]

    def test_collision_identity_is_independent_and_idempotent(self):
        collision_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        first = self.store.create(self.auth(), collision_id=collision_id, request_id=request_id)
        retry = self.store.create(self.auth(), collision_id=collision_id, request_id=request_id)
        self.assertTrue(first.created)
        self.assertFalse(retry.created)
        self.assertEqual(first.collision_id, collision_id)
        self.assertEqual(first.state, "OPEN")
        self.assertEqual(retry.collision_id, collision_id)
        self.assertEqual(self.store.get(self.auth(), collision_id).collision_id, collision_id)
        self.assertEqual(self.f.seed.execute(
            "SELECT count(*) FROM faos.collision_lifecycle_records "
            "WHERE tenant_id=%s AND collision_id=%s",
            (self.f.tenants[0], collision_id),
        ).fetchone()[0], 1)

    def test_collision_creation_writes_initial_event_and_outbox_atomically(self):
        collision_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.store.create(self.auth(), collision_id=collision_id, request_id=request_id)
        self.assertEqual(self.f.seed.execute(
            "SELECT event_type,sequence FROM faos.collision_events "
            "WHERE tenant_id=%s AND collision_id=%s",
            (self.f.tenants[0], collision_id),
        ).fetchone(), ("collision_registered", 1))
        self.assertEqual(self.f.seed.execute(
            "SELECT count(*) FROM faos.collision_outbox "
            "WHERE tenant_id=%s AND collision_id=%s",
            (self.f.tenants[0], collision_id),
        ).fetchone()[0], 1)

    def test_idempotency_conflict_does_not_create_second_collision(self):
        request_id = str(uuid.uuid4())
        original = str(uuid.uuid4())
        self.store.create(self.auth(), collision_id=original, request_id=request_id)
        with self.assertRaisesRegex(CollisionLifecycleConflict, "COLLISION_RECORD_NOT_ACCEPTED"):
            self.store.create(self.auth(), collision_id=str(uuid.uuid4()), request_id=request_id)
        self.assertEqual(self.f.seed.execute(
            "SELECT count(*) FROM faos.collision_lifecycle_records WHERE tenant_id=%s",
            (self.f.tenants[0],),
        ).fetchone()[0], 1)

    def test_tenant_boundary_hides_other_tenant_collision(self):
        collision_id = str(uuid.uuid4())
        self.store.create(self.auth(0), collision_id=collision_id, request_id=str(uuid.uuid4()))
        with self.assertRaises(CollisionLifecycleNotFound):
            self.store.get(self.auth(1), collision_id)


if __name__ == "__main__":
    unittest.main()

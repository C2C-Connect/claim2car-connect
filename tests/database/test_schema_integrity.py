"""PostgreSQL tenant-key integrity tests using separately bound identities."""
import unittest
import uuid
import psycopg
from tenant_login import TenantLogin


class SchemaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.own, self.other = str(uuid.uuid4()), str(uuid.uuid4())
        self.own_login = TenantLogin(self.own, organization_name='synthetic constraint fixture')
        self.other_login = TenantLogin(self.other, organization_name='synthetic constraint fixture')
        self.addCleanup(self.own_login.close)
        self.addCleanup(self.other_login.close)
        self.conn = self.own_login.connect(autocommit=False)
        self.other_conn = self.other_login.connect(autocommit=False)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.other_conn.close)
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.other_conn.rollback)

    def connection(self, tenant):
        return self.conn if tenant == self.own else self.other_conn

    def context(self, tenant):
        conn = self.connection(tenant)
        conn.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))

    def user(self, tenant, user, subject):
        self.context(tenant)
        self.connection(tenant).execute(
            'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
            (tenant, user, subject),
        )

    def reject(self, exception, sqlstate, statement, values):
        with self.assertRaises(exception) as caught:
            with self.conn.transaction():
                self.conn.execute(statement, values)
        self.assertEqual(caught.exception.sqlstate, sqlstate)

    def test_membership_cannot_reference_other_tenant_user(self):
        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        self.user(self.other, user, 'other-user')
        self.context(self.own)
        statement = 'INSERT INTO faos.memberships(tenant_id,user_id,membership_id,role_name) VALUES (%s,%s,%s,%s)'
        values = (self.own, user, membership, 'synthetic-member')
        self.reject(psycopg.errors.ForeignKeyViolation, '23503', statement, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 0)
        self.user(self.own, user, 'own-user')
        self.assertEqual(self.conn.execute(statement, values).rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT user_id::text FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchall(), [(user,)])

    def test_location_cannot_reference_other_tenant_group(self):
        group, location = str(uuid.uuid4()), str(uuid.uuid4())
        group_sql = 'INSERT INTO faos.dealer_groups(tenant_id,group_id,name) VALUES (%s,%s,%s)'
        self.context(self.other)
        self.other_conn.execute(group_sql, (self.other, group, 'other-group'))
        self.context(self.own)
        statement = 'INSERT INTO faos.dealer_locations(tenant_id,location_id,group_id,name) VALUES (%s,%s,%s,%s)'
        values = (self.own, location, group, 'synthetic-location')
        self.reject(psycopg.errors.ForeignKeyViolation, '23503', statement, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.dealer_locations WHERE location_id=%s', (location,)).fetchone()[0], 0)
        self.conn.execute(group_sql, (self.own, group, 'own-group'))
        self.assertEqual(self.conn.execute(statement, values).rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT group_id::text,enabled FROM faos.dealer_locations WHERE location_id=%s', (location,)).fetchall(), [(group, False)])

    def test_external_subject_unique_per_tenant_not_globally(self):
        first, second = str(uuid.uuid4()), str(uuid.uuid4())
        self.user(self.own, first, 'shared-subject')
        self.user(self.other, second, 'shared-subject')
        self.context(self.own)
        statement = 'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)'
        self.reject(psycopg.errors.UniqueViolation, '23505', statement, (self.own, str(uuid.uuid4()), 'shared-subject'))
        self.assertEqual(self.conn.execute('SELECT user_id::text FROM faos.users WHERE external_subject=%s', ('shared-subject',)).fetchall(), [(first,)])
        self.context(self.other)
        self.assertEqual(self.other_conn.execute('SELECT user_id::text FROM faos.users WHERE external_subject=%s', ('shared-subject',)).fetchall(), [(second,)])

    def test_membership_key_unique_within_tenant(self):
        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        for tenant in (self.own, self.other):
            self.user(tenant, user, 'synthetic-user')
        statement = 'INSERT INTO faos.memberships(tenant_id,user_id,membership_id,role_name) VALUES (%s,%s,%s,%s)'
        values = (self.own, user, membership, 'synthetic-member')
        self.context(self.own)
        self.conn.execute(statement, values)
        self.reject(psycopg.errors.UniqueViolation, '23505', statement, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 1)
        self.context(self.other)
        self.other_conn.execute(statement, (self.other, user, membership, 'synthetic-member'))
        self.assertEqual(self.other_conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()

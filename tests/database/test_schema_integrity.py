"""PostgreSQL tenant-key integrity tests; not complete authorization acceptance."""
import os
import unittest
import uuid
import psycopg

class SchemaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.getenv('APP_DATABASE_URL', 'postgresql://faos_app:synthetic-app-only@127.0.0.1:55432/claim2car_test'))
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        role = self.conn.execute('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        self.assertEqual(role, ('faos_app', False, False))
        self.own, self.other = str(uuid.uuid4()), str(uuid.uuid4())
        for tenant in (self.own, self.other):
            self.context(tenant)
            self.conn.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)', (tenant, 'synthetic constraint fixture'))

    def context(self, tenant):
        self.conn.execute("SELECT set_config('faos.tenant_id',%s,true)", (tenant,))

    def user(self, tenant, user, subject):
        self.context(tenant)
        self.conn.execute('INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)', (tenant, user, subject))

    def reject(self, exception, sqlstate, sql, values):
        with self.assertRaises(exception) as caught:
            with self.conn.transaction():
                self.conn.execute(sql, values)
        self.assertEqual(caught.exception.sqlstate, sqlstate)

    def test_membership_cannot_reference_other_tenant_user(self):
        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        self.user(self.other, user, 'other-user')
        self.context(self.own)
        sql = 'INSERT INTO faos.memberships(tenant_id,user_id,membership_id,role_name) VALUES (%s,%s,%s,%s)'
        values = (self.own, user, membership, 'synthetic-member')
        self.reject(psycopg.errors.ForeignKeyViolation, '23503', sql, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 0)
        self.user(self.own, user, 'own-user')
        self.assertEqual(self.conn.execute(sql, values).rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT user_id::text FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchall(), [(user,)])

    def test_location_cannot_reference_other_tenant_group(self):
        group, location = str(uuid.uuid4()), str(uuid.uuid4())
        group_sql = 'INSERT INTO faos.dealer_groups(tenant_id,group_id,name) VALUES (%s,%s,%s)'
        self.context(self.other)
        self.conn.execute(group_sql, (self.other, group, 'other-group'))
        self.context(self.own)
        sql = 'INSERT INTO faos.dealer_locations(tenant_id,location_id,group_id,name) VALUES (%s,%s,%s,%s)'
        values = (self.own, location, group, 'synthetic-location')
        self.reject(psycopg.errors.ForeignKeyViolation, '23503', sql, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.dealer_locations WHERE location_id=%s', (location,)).fetchone()[0], 0)
        self.conn.execute(group_sql, (self.own, group, 'own-group'))
        self.assertEqual(self.conn.execute(sql, values).rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT group_id::text,enabled FROM faos.dealer_locations WHERE location_id=%s', (location,)).fetchall(), [(group, False)])

    def test_external_subject_unique_per_tenant_not_globally(self):
        first, second = str(uuid.uuid4()), str(uuid.uuid4())
        self.user(self.own, first, 'shared-subject')
        self.user(self.other, second, 'shared-subject')
        self.context(self.own)
        sql = 'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)'
        self.reject(psycopg.errors.UniqueViolation, '23505', sql, (self.own, str(uuid.uuid4()), 'shared-subject'))
        self.assertEqual(self.conn.execute('SELECT user_id::text FROM faos.users WHERE external_subject=%s', ('shared-subject',)).fetchall(), [(first,)])
        self.context(self.other)
        self.assertEqual(self.conn.execute('SELECT user_id::text FROM faos.users WHERE external_subject=%s', ('shared-subject',)).fetchall(), [(second,)])

    def test_membership_key_unique_within_tenant(self):
        user, membership = str(uuid.uuid4()), str(uuid.uuid4())
        for tenant in (self.own, self.other):
            self.user(tenant, user, 'synthetic-user')
        sql = 'INSERT INTO faos.memberships(tenant_id,user_id,membership_id,role_name) VALUES (%s,%s,%s,%s)'
        self.context(self.own)
        values = (self.own, user, membership, 'synthetic-member')
        self.conn.execute(sql, values)
        self.reject(psycopg.errors.UniqueViolation, '23505', sql, values)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 1)
        self.context(self.other)
        self.assertEqual(self.conn.execute(sql, (self.other, user, membership, 'synthetic-member')).rowcount, 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM faos.memberships WHERE membership_id=%s', (membership,)).fetchone()[0], 1)

if __name__ == '__main__':
    unittest.main()

"""Tenant/RLS integration tests for persisted Sandbox checkout-link intent."""
import hashlib
import json
import os
from pathlib import Path
import unittest
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from database.journal import tenant_transaction
from database.migrate import apply
from database.authority_migrate import migration_plan


class SquareSandboxPaymentIntentIntegration(unittest.TestCase):
    def setUp(self):
        admin_url=os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        config=conninfo_to_dict(admin_url)
        if any(config.get(k)!=v for k,v in {'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':'postgres'}.items()):
            raise ValueError('EXPLICIT_SYNTHETIC_ADMIN_TARGET_REQUIRED')
        self.admin=psycopg.connect(admin_url,autocommit=True,connect_timeout=5)
        self.addCleanup(self.admin.close)
        self.db='square_payment_intents_'+uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE DATABASE {} OWNER faos_migrator TEMPLATE template0').format(sql.Identifier(self.db)))
        self.addCleanup(self.drop_database)
        root=Path(__file__).resolve().parents[2]
        with psycopg.connect(make_conninfo(admin_url,dbname=self.db,user='faos_migrator',password='synthetic-migrator-only'),autocommit=True,connect_timeout=5) as migrator:
            apply(migrator,migration_plan(root))
        self.seed=psycopg.connect(make_conninfo(admin_url,dbname=self.db),autocommit=True,connect_timeout=5)
        self.addCleanup(self.seed.close)
        self.tenant=str(uuid.uuid4())
        self.session='square-payment-session'
        self.seed.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',(self.tenant,'sandbox payment integration'))
        self.seed.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',(self.tenant,self.session))
        self.role='square_payment_login_'+uuid.uuid4().hex
        self.password=uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}').format(sql.Identifier(self.role),sql.Literal(self.password)))
        self.addCleanup(self.drop_role)
        self.admin.execute(sql.SQL('GRANT faos_app TO {}').format(sql.Identifier(self.role)))
        self.seed.execute('INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id) SELECT oid,rolname,%s FROM pg_roles WHERE rolname=%s',(self.tenant,self.role))
        self.conn=psycopg.connect(make_conninfo(admin_url,dbname=self.db,user=self.role,password=self.password),autocommit=True,connect_timeout=5)
        self.addCleanup(self.conn.close)
        self.entry_id='payment-obligation-1'
        self.entry_key='payment-obligation-key'
        self.acceptance='shop-acceptance-1'
        self.partner='shop-1'
        self._append_shop_obligation()

    def drop_role(self):
        self.admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(self.role)))
    def drop_database(self):
        self.admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.db)))

    def _append_shop_obligation(self):
        lines=[
            {'account_code':'AR:SHOP:shop-1','direction':'DEBIT','amount_cents':27500},
            {'account_code':'REV:REPAIR_SHOP_ACCEPTANCE','direction':'CREDIT','amount_cents':27500},
        ]
        line_tuples=[(x['account_code'],x['direction'],x['amount_cents']) for x in lines]
        previous='0'*64
        payload=(f"1|{self.entry_id}|{self.entry_key}|{self.tenant}|{self.session}|OBLIGATION_BOOKED|"
                 f"REPAIR_SHOP_ACCEPTANCE_FEE|{self.partner}|{self.acceptance}|27500|None|{line_tuples}|{previous}")
        entry_hash=hashlib.sha256(payload.encode()).hexdigest()
        with tenant_transaction(self.conn,self.tenant):
            result=self.conn.execute('SELECT faos.append_financial_entry(%s::uuid,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text,%s::bigint,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text,%s::jsonb)',
                (self.tenant,self.entry_id,1,self.entry_key,self.session,'OBLIGATION_BOOKED','REPAIR_SHOP_ACCEPTANCE_FEE',
                 self.partner,self.acceptance,27500,'USD_CENTS','operator-1','2026-11-21T00:00:00Z',
                 'verified shop acceptance',None,previous,entry_hash,json.dumps(lines,separators=(',',':')))).fetchone()[0]
        self.assertEqual(result,'ACCEPTED')

    def register(self,*,tenant=None,intent_id=None,link='link-1',order='order-1',url='https://sandbox.square.link/u/test',key='c2c-shop-fee-test',actor='operator-1'):
        return self.conn.execute('SELECT faos.register_square_sandbox_payment_intent(%s::uuid,%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
            (tenant or self.tenant,intent_id or str(uuid.uuid4()),self.entry_id,link,order,url,key,actor)).fetchone()[0]

    def test_create_and_retry_are_idempotent_and_tenant_visible(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
            self.assertEqual(self.register(intent_id=str(uuid.uuid4())),'DUPLICATE')
        rows=self.conn.execute('SELECT obligation_entry_id,provider_link_id,provider_order_id,amount_cents,currency,status FROM faos.square_sandbox_payment_intents').fetchall()
        self.assertEqual(rows,[(self.entry_id,'link-1','order-1',27500,'USD','LINK_CREATED')])

    def test_idempotency_conflict_and_one_link_per_obligation(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
            with self.assertRaises(psycopg.errors.RaiseException) as conflict:
                self.register(link='different-link',order='different-order',key='c2c-shop-fee-test')
            self.assertEqual(conflict.exception.diag.message_primary,'SQUARE_PAYMENT_IDEMPOTENCY_CONFLICT')
            with self.assertRaises(psycopg.errors.RaiseException) as second:
                self.register(link='second-link',order='second-order',key='new-key')
            self.assertEqual(second.exception.diag.message_primary,'SQUARE_PAYMENT_INTENT_ALREADY_EXISTS')

    def test_checkout_url_and_obligation_guards(self):
        with tenant_transaction(self.conn,self.tenant):
            with self.assertRaises(psycopg.errors.RaiseException) as bad_url:
                self.register(url='https://evil.example/checkout')
            self.assertEqual(bad_url.exception.diag.message_primary,'INVALID_SQUARE_SANDBOX_PAYMENT_INTENT')
            with self.assertRaises(psycopg.errors.RaiseException) as bad_obligation:
                self.conn.execute('SELECT faos.register_square_sandbox_payment_intent(%s::uuid,%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                    (self.tenant,str(uuid.uuid4()),'not-a-ledger-entry','l','o','https://sandbox.square.link/u/test','k','operator-1'))
            self.assertEqual(bad_obligation.exception.diag.message_primary,'SHOP_ACCEPTANCE_OBLIGATION_NOT_ELIGIBLE')

    def test_application_cannot_direct_insert_or_cross_tenant(self):
        with tenant_transaction(self.conn,self.tenant):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.conn.execute('INSERT INTO faos.square_sandbox_payment_intents(tenant_id,payment_intent_id,obligation_entry_id,session_id,acceptance_id,partner_org_id,provider,provider_link_id,provider_order_id,checkout_url,idempotency_key,amount_cents,currency,status,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (self.tenant,str(uuid.uuid4()),self.entry_id,self.session,self.acceptance,self.partner,'SQUARE_SANDBOX','l','o','https://sandbox.square.link/u/test','k',27500,'USD','LINK_CREATED','operator-1'))
            with self.assertRaises(psycopg.errors.RaiseException) as mismatch:
                self.register(tenant=str(uuid.uuid4()),intent_id=str(uuid.uuid4()),actor='operator-1')
            self.assertEqual(mismatch.exception.diag.message_primary,'TENANT_CONTEXT_MISMATCH')

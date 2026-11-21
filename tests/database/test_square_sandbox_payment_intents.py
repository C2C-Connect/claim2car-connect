"""Tenant/RLS integration tests for persisted Sandbox checkout-link intent."""
import hashlib
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
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
        self.seed.execute('DELETE FROM faos.tenant_login_bindings WHERE role_name=%s',(self.role,))
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

    def register(self,*,conn=None,tenant=None,intent_id=None,link='link-1',order='order-1',url='https://sandbox.square.link/u/test',key='c2c-shop-fee-test',actor='operator-1'):
        conn=conn or self.conn
        return conn.execute('SELECT faos.register_square_sandbox_payment_intent(%s::uuid,%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
            (tenant or self.tenant,intent_id or str(uuid.uuid4()),self.entry_id,link,order,url,key,actor)).fetchone()[0]

    def test_create_and_retry_are_idempotent_and_tenant_visible(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
            self.assertEqual(self.register(intent_id=str(uuid.uuid4())),'DUPLICATE')
            rows=self.conn.execute('SELECT i.obligation_entry_id,i.provider_link_id,i.provider_order_id,i.amount_cents,i.currency,COALESCE(r.status,i.status) FROM faos.square_sandbox_payment_intents i LEFT JOIN faos.square_sandbox_payment_reconciliations r ON r.tenant_id=i.tenant_id AND r.payment_intent_id=i.payment_intent_id').fetchall()
            self.assertEqual(rows,[(self.entry_id,'link-1','order-1',27500,'USD','LINK_CREATED')])

    def test_concurrent_retries_share_one_payment_intent(self):
        second=psycopg.connect(make_conninfo(
            os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test'),
            dbname=self.db,user=self.role,password=self.password),autocommit=True,connect_timeout=5)
        self.addCleanup(second.close)
        def attempt(conn,intent):
            with tenant_transaction(conn,self.tenant):
                return self.register(conn=conn,intent_id=intent,key='same-concurrent-key')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda args: attempt(*args),[(self.conn,str(uuid.uuid4())),(second,str(uuid.uuid4()))]))
        self.assertCountEqual(results,['CREATED','DUPLICATE'])
        self.assertEqual(self.seed.execute('SELECT count(*) FROM faos.square_sandbox_payment_intents WHERE tenant_id=%s',(self.tenant,)).fetchone()[0],1)

    def test_idempotency_conflict_and_one_link_per_obligation(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
            with self.assertRaises(psycopg.errors.RaiseException) as conflict:
                with self.conn.transaction():
                    self.register(link='different-link',order='different-order',key='c2c-shop-fee-test')
            self.assertEqual(conflict.exception.diag.message_primary,'SQUARE_PAYMENT_IDEMPOTENCY_CONFLICT')
            with self.assertRaises(psycopg.errors.RaiseException) as second:
                with self.conn.transaction():
                    self.register(link='second-link',order='second-order',key='new-key')
            self.assertEqual(second.exception.diag.message_primary,'SQUARE_PAYMENT_INTENT_ALREADY_EXISTS')

    def test_checkout_url_and_obligation_guards(self):
        with tenant_transaction(self.conn,self.tenant):
            with self.assertRaises(psycopg.errors.RaiseException) as bad_url:
                with self.conn.transaction():
                    self.register(url='https://evil.example/checkout')
            self.assertEqual(bad_url.exception.diag.message_primary,'INVALID_SQUARE_SANDBOX_PAYMENT_INTENT')
            with self.assertRaises(psycopg.errors.RaiseException) as bad_obligation:
                with self.conn.transaction():
                    self.conn.execute('SELECT faos.register_square_sandbox_payment_intent(%s::uuid,%s::uuid,%s::text,%s::text,%s::text,%s::text,%s::text,%s::text)',
                        (self.tenant,str(uuid.uuid4()),'not-a-ledger-entry','l','o','https://sandbox.square.link/u/test','k','operator-1'))
            self.assertEqual(bad_obligation.exception.diag.message_primary,'SHOP_ACCEPTANCE_OBLIGATION_NOT_ELIGIBLE')

    def test_application_cannot_direct_insert_or_cross_tenant(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.conn.transaction():
                self.conn.execute('INSERT INTO faos.square_sandbox_payment_intents(tenant_id,payment_intent_id,obligation_entry_id,session_id,acceptance_id,partner_org_id,provider,provider_link_id,provider_order_id,checkout_url,idempotency_key,amount_cents,currency,status,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (self.tenant,str(uuid.uuid4()),self.entry_id,self.session,self.acceptance,self.partner,'SQUARE_SANDBOX','l','o','https://sandbox.square.link/u/test','k',27500,'USD','LINK_CREATED','operator-1'))
        with tenant_transaction(self.conn,self.tenant):
            with self.assertRaises(psycopg.errors.RaiseException) as mismatch:
                with self.conn.transaction():
                    self.register(tenant=str(uuid.uuid4()),intent_id=str(uuid.uuid4()),actor='operator-1')
            self.assertEqual(mismatch.exception.diag.message_primary,'TENANT_CONTEXT_MISMATCH')

    def webhook(self,event_id,status,*,order='order-1',payment='payment-1',amount=27500,currency='USD',created=None,body=None):
        created=created or datetime.now(timezone.utc)
        raw=body if body is not None else (f'{event_id}|{status}|{payment}|{order}|{amount}|{currency}|{created.isoformat()}').encode()
        digest=hashlib.sha256(raw).hexdigest()
        with tenant_transaction(self.conn,self.tenant):
            return self.conn.execute(
                'SELECT faos.reconcile_square_sandbox_webhook(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (event_id,'payment.updated',payment,order,status,amount,currency,created.isoformat(),digest),
            ).fetchone()[0]

    def test_verified_webhook_authorizes_and_completes_intent_idempotently(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
        created=datetime.now(timezone.utc)+timedelta(seconds=1)
        self.assertEqual(self.webhook('event-approved','APPROVED',created=created),'RECONCILED')
        row=self.conn.execute(
            'SELECT COALESCE(r.status,i.status),r.provider_payment_id FROM faos.square_sandbox_payment_intents i '
            'LEFT JOIN faos.square_sandbox_payment_reconciliations r ON r.tenant_id=i.tenant_id AND r.payment_intent_id=i.payment_intent_id',
        ).fetchone()
        self.assertEqual(row,('AUTHORIZED','payment-1'))
        paid_at=created+timedelta(seconds=2)
        self.assertEqual(self.webhook('event-completed','COMPLETED',created=paid_at),'RECONCILED')
        self.assertEqual(self.webhook('event-completed','COMPLETED',created=paid_at),'DUPLICATE')
        row=self.conn.execute(
            'SELECT COALESCE(r.status,i.status),r.provider_payment_id FROM faos.square_sandbox_payment_intents i '
            'LEFT JOIN faos.square_sandbox_payment_reconciliations r ON r.tenant_id=i.tenant_id AND r.payment_intent_id=i.payment_intent_id',
        ).fetchone()
        self.assertEqual(row,('PAID','payment-1'))
        receipt=self.seed.execute(
            'SELECT reconciliation_status FROM faos.square_sandbox_webhook_receipts WHERE provider_event_id=%s',
            ('event-completed',),
        ).fetchone()
        self.assertEqual(receipt,('RECONCILED',))

    def test_webhook_amount_mismatch_and_unmatched_order_are_recorded_without_payment(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
        self.assertEqual(self.webhook('event-wrong-amount','COMPLETED',amount=26000),'AMOUNT_MISMATCH')
        self.assertEqual(self.webhook('event-unmatched','COMPLETED',order='unknown-order'),'UNMATCHED_ORDER')
        status=self.conn.execute(
            'SELECT COALESCE(r.status,i.status) FROM faos.square_sandbox_payment_intents i '
            'LEFT JOIN faos.square_sandbox_payment_reconciliations r ON r.tenant_id=i.tenant_id AND r.payment_intent_id=i.payment_intent_id',
        ).fetchone()[0]
        self.assertEqual(status,'LINK_CREATED')
        states=self.seed.execute(
            'SELECT provider_event_id,reconciliation_status FROM faos.square_sandbox_webhook_receipts '
            'WHERE provider_event_id IN (%s,%s) ORDER BY provider_event_id',
            ('event-unmatched','event-wrong-amount'),
        ).fetchall()
        self.assertEqual(states,[('event-unmatched','UNMATCHED_ORDER'),('event-wrong-amount','AMOUNT_MISMATCH')])

    def test_webhook_payment_id_conflict_and_stale_event_cannot_regress_paid_state(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
        paid_at=datetime.now(timezone.utc)+timedelta(seconds=3)
        self.assertEqual(self.webhook('event-paid','COMPLETED',created=paid_at),'RECONCILED')
        self.assertEqual(self.webhook('event-other-payment','COMPLETED',payment='payment-2',created=paid_at+timedelta(seconds=1)),'PAYMENT_ID_CONFLICT')
        self.assertEqual(self.webhook('event-old-approval','APPROVED',created=paid_at-timedelta(seconds=1)),'STALE_EVENT')
        row=self.conn.execute(
            'SELECT COALESCE(r.status,i.status),r.provider_payment_id FROM faos.square_sandbox_payment_intents i '
            'LEFT JOIN faos.square_sandbox_payment_reconciliations r ON r.tenant_id=i.tenant_id AND r.payment_intent_id=i.payment_intent_id',
        ).fetchone()
        self.assertEqual(row,('PAID','payment-1'))

    def test_event_id_reuse_with_different_payload_is_rejected(self):
        with tenant_transaction(self.conn,self.tenant):
            self.assertEqual(self.register(),'CREATED')
        timestamp=datetime.now(timezone.utc)
        self.webhook('event-conflict','APPROVED',created=timestamp,body=b'first-payload')
        with self.assertRaises(psycopg.errors.RaiseException) as conflict:
            with self.conn.transaction():
                self.webhook('event-conflict','COMPLETED',created=timestamp,body=b'different-payload')
        self.assertEqual(conflict.exception.diag.message_primary,'SQUARE_WEBHOOK_EVENT_ID_CONFLICT')

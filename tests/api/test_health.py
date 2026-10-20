"""ASGI/HTTP unit tests with mocked database I/O; live SQL has separate CI stages."""
import os
import unittest
from unittest.mock import MagicMock, patch
import psycopg
from fastapi.testclient import TestClient
from app.main import Settings, create_app, probe_database

class HealthTests(unittest.TestCase):
    def request(self,path,settings=None,method='get'):
        with TestClient(create_app(settings if settings is not None else Settings())) as client:
            return getattr(client,method)(path)

    def test_liveness_never_connects_to_database(self):
        with patch('app.main.psycopg.connect',side_effect=AssertionError('UNEXPECTED_DATABASE_IO')) as connect:
            response=self.request('/health/live')
        connect.assert_not_called()
        self.assertEqual((response.status_code,response.json()),(200,{'status':'alive'}))
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_missing_configuration_fails_readiness_without_fallback(self):
        with patch.dict(os.environ,{},clear=True),patch('app.main.psycopg.connect') as connect:
            with TestClient(create_app()) as client:
                response=client.get('/health/ready')
        connect.assert_not_called()
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'status':'not_ready','scope':'infrastructure-only'})

    def test_valid_probe_reports_infrastructure_only(self):
        with patch('app.main.probe_database',return_value=True):
            response=self.request('/health/ready',Settings('synthetic-config'))
        self.assertEqual((response.status_code,response.json()),(200,{'status':'ready','scope':'infrastructure-only'}))
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_unavailable_database_fails_closed_without_leaking_details(self):
        secret='synthetic-password-must-not-appear'
        with patch('app.main.probe_database',side_effect=psycopg.OperationalError(secret)):
            response=self.request('/health/ready',Settings('postgresql://synthetic:'+secret+'@invalid/synthetic'))
        self.assertEqual(response.status_code,503)
        self.assertNotIn(secret,response.text)

    def test_unexpected_probe_exception_also_fails_closed(self):
        with patch('app.main.probe_database',side_effect=RuntimeError('internal detail')):
            response=self.request('/health/ready',Settings('synthetic-config'))
        self.assertEqual(response.status_code,503)
        self.assertNotIn('internal detail',response.text)

    def test_false_or_truthy_non_boolean_probe_is_not_accepted(self):
        for value in (False,None,1,'ready'):
            with self.subTest(value=value),patch('app.main.probe_database',return_value=value):
                self.assertEqual(self.request('/health/ready',Settings('synthetic-config')).status_code,503)

    def test_request_cannot_supply_database_or_tenant_authority(self):
        with patch('app.main.probe_database',return_value=True) as probe:
            response=self.request('/health/ready?database_url=attacker&tenant_id=attacker',Settings('configured-target'))
        self.assertEqual(response.status_code,200)
        probe.assert_called_once_with('configured-target')

    def test_only_read_only_health_routes_are_exposed(self):
        for path,method,expected in [('/packets','post',404),('/health/live','post',405),('/docs','get',404),('/openapi.json','get',404)]:
            with self.subTest(path=path,method=method):
                self.assertEqual(self.request(path,method=method).status_code,expected)

    def test_settings_repr_redacts_database_url(self):
        self.assertNotIn('synthetic-secret',repr(Settings('synthetic-secret')))

    def test_app_factory_does_not_connect_at_startup(self):
        with patch('app.main.psycopg.connect') as connect:
            with TestClient(create_app(Settings('synthetic-config'))):
                pass
        connect.assert_not_called()

    def test_probe_checks_all_prerequisites_with_read_only_timeouts(self):
        conn=MagicMock()
        conn.__enter__.return_value=conn
        with patch('app.main.psycopg.connect',return_value=conn) as connect:
            for row in ((True,True,True,True),(False,True,True,True),(True,False,True,True),(True,True,False,True),(True,True,True,False),None):
                with self.subTest(row=row):
                    conn.execute.return_value.fetchone.return_value=row
                    self.assertEqual(probe_database('configured-target'),row==(True,True,True,True))
        self.assertEqual(connect.call_args.kwargs,{'autocommit':True,'connect_timeout':3,'options':'-c statement_timeout=2000 -c default_transaction_read_only=on'})
        self.assertEqual(conn.__exit__.call_count,6)

if __name__=='__main__':
    unittest.main()

"""Loopback Uvicorn + real PostgreSQL composition. Synthetic disposable fixture only."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import httpx
from test_capture_sessions_integration import CaptureSessionIntegration

ROOT=Path(__file__).resolve().parents[2]
VIN='1HGCM82633A004352'
OTHER='1M8GDM9AXKP042788'

class IntakeHttpPostgresIntegration(unittest.TestCase):
    def setUp(self):
        self.base=CaptureSessionIntegration()
        self.addCleanup(self.base.doCleanups)
        self.base.setUp()
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config=Path(self.directory.name)/'runtime.json'
        value={'health_database_url':self.base.dsns[self.base.f.roles[0]],'dsn_by_role':self.base.dsns,
               'credentials':[{'actor_id':c.binding.actor_id,'tenant_id':str(c.binding.tenant_id),
                               'database_role':c.binding.database_role,'token_sha256':c.token_sha256,
                               'expires_at':c.expires_at,'enabled':c.enabled} for c in self.base.credentials]}
        self.config.write_text(json.dumps(value))
        self.config.chmod(0o600)
        self.process=None
        self.addCleanup(self.stop_server)
        self.start_server()
        self.addCleanup(lambda:self.client.close())
        self.headers={'Authorization':self.base.auth()}
        self.path='/v1/capture-sessions/'+self.base.key+'/draft'
        self.body={'request_id':str(uuid.uuid4()),'expected_revision':1,'vin':VIN}
        r=self.client.post('/v1/capture-sessions',headers=self.headers,json={'session_id':self.base.key})
        self.assertEqual(r.status_code,201)

    def stop_server(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill();self.process.wait(timeout=5)
            self.process=None

    def start_server(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env={**os.environ,'C2C_CAPTURE_CONFIG_FILE':str(self.config)}
        self.process=subprocess.Popen([sys.executable,'-m','uvicorn','app.intake_api:create_intake_app','--factory',
                                       '--host','127.0.0.1','--port',str(port),'--no-access-log'],
                                      cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.client=httpx.Client(base_url='http://127.0.0.1:'+str(port),timeout=5,trust_env=False)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if self.process.poll() is not None:break
            try:
                if self.client.get('/health/live').status_code==200:return
            except httpx.HTTPError:pass
            time.sleep(0.05)
        self.client.close()
        self.fail('INTAKE_TEST_SERVER_NOT_READY')

    def put(self,**changes):
        return self.client.put(self.path,headers=self.headers,json={**self.body,**changes})

    def event_count(self):
        return self.base.f.seed.execute('SELECT count(*) FROM faos.events WHERE tenant_id=%s AND session_id=%s',
                                        (self.base.f.tenants[0],self.base.key)).fetchone()[0]

    def test_save_and_fresh_http_client_readback(self):
        self.assertEqual(self.client.get(self.path,headers=self.headers).json()['revision'],1)
        r=self.put();self.assertEqual(r.status_code,200)
        self.assertEqual((r.json()['revision'],r.json()['vin']),(2,VIN))
        self.assertEqual(r.headers['cache-control'],'no-store')
        with httpx.Client(base_url=str(self.client.base_url),timeout=5,trust_env=False) as fresh:
            r=fresh.get(self.path,headers=self.headers)
            self.assertEqual((r.status_code,r.json()['vin']),(200,VIN))
        self.assertEqual(self.event_count(),2)

    def test_http_retry_returns_original_receipt(self):
        self.assertEqual(self.put().status_code,200)
        retry=self.put();self.assertEqual(retry.status_code,200)
        self.assertTrue(retry.json()['replayed'])
        self.assertEqual(self.event_count(),2)

    def test_conflicts_do_not_overwrite_saved_vin(self):
        self.assertEqual(self.put().status_code,200)
        for body in ({'vin':OTHER},{'request_id':str(uuid.uuid4()),'vin':OTHER}):
            r=self.put(**body)
            self.assertEqual((r.status_code,r.json()),(409,{'detail':'INTAKE_DRAFT_CONFLICT'}))
        self.assertEqual(self.client.get(self.path,headers=self.headers).json()['vin'],VIN)
        self.assertEqual(self.event_count(),2)

    def test_other_tenant_cannot_read_or_write(self):
        headers={'Authorization':self.base.auth(1)}
        self.assertEqual(self.client.get(self.path,headers=headers).status_code,404)
        self.assertEqual(self.client.put(self.path,headers=headers,json=self.body).status_code,404)
        self.assertEqual(self.event_count(),1)

    def test_missing_or_unknown_credentials_denied(self):
        for headers in ({},{'Authorization':'Bearer '+'Z'*43}):
            for r in (self.client.get(self.path,headers=headers),self.client.put(self.path,headers=headers,json=self.body)):
                self.assertEqual(r.status_code,401)
                self.assertEqual(r.headers['www-authenticate'],'Bearer')
                self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual(self.event_count(),1)

    def test_invalid_identity_fields_and_vin_not_persisted(self):
        for changes in ({'tenant_id':'untrusted-private-input'},{'expected_revision':True},{'vin':'1HGCM82643A004352'}):
            r=self.put(**changes)
            self.assertEqual((r.status_code,r.json()),(422,{'detail':'INVALID_INTAKE_REQUEST'}))
            self.assertNotIn('untrusted-private-input',r.text)
        self.assertEqual(self.event_count(),1)

    def test_uvicorn_restart_preserves_saved_state(self):
        self.assertEqual(self.put().status_code,200)
        self.client.close();self.stop_server();self.start_server()
        r=self.client.get(self.path,headers=self.headers)
        self.assertEqual((r.status_code,r.json()['revision'],r.json()['vin']),(200,2,VIN))
        self.assertEqual(self.event_count(),2)

if __name__=='__main__':unittest.main()

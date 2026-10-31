"""Session start contract test. Does not require live database."""
from uuid import UUID
from fastapi.testclient import TestClient
from app.main import create_app
from app.sessions import get_resolver
from app.identity import CredentialResolver, Credential, ActorBinding
import hashlib
import time

def test_session_start_requires_auth():
    app = create_app()
    client = TestClient(app)
    response = client.post('/sessions')
    assert response.status_code == 401

def test_session_start_returns_tenant_bound_id():
    token = 'test-token-for-session-start-aaaaaaaaaaaaaaaaaaaaaaaa'
    digest = hashlib.sha256(token.encode()).hexdigest()
    binding = ActorBinding(actor_id='operator-1', tenant_id=UUID('11111111-1111-1111-1111-111111111111'), database_role='tenant_a_role')
    cred = Credential(token_sha256=digest, binding=binding, expires_at=int(time.time()) + 3600)
    resolver = CredentialResolver([cred])

    app = create_app()
    app.dependency_overrides[get_resolver] = lambda: resolver
    client = TestClient(app)
    response = client.post('/sessions', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    body = response.json()
    assert body['tenant_id'] == '11111111-1111-1111-1111-111111111111'
    assert len(body['session_id']) > 0

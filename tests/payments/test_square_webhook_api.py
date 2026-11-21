import base64
import hashlib
import hmac
import json
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.payments.square_sandbox import SquareSandboxConfig
from app.payments.square_webhook_api import create_square_webhook_router


KEY="test-webhook-key"
URL="https://c2c.example.test/webhooks/square"
CONFIG=SquareSandboxConfig("sandbox-token","sandbox-location",KEY,URL,"sandbox")


class FakeConnection:
    def __init__(self,outcome="RECONCILED"):
        self.outcome=outcome
        self.calls=[]
        self.raise_code=None
    def execute(self,query,params):
        self.calls.append((query,params))
        if self.raise_code:
            exc=RuntimeError(self.raise_code)
            exc.diag=type('Diag',(),{'message_primary':self.raise_code})()
            raise exc
        return SimpleNamespace(fetchone=lambda:(self.outcome,))


@contextmanager
def connection_factory(url,connect_timeout=3):
    yield connection


def make_body(*,event_id="evt-1",status="COMPLETED",amount=27500):
    return json.dumps({
        "event_id":event_id,
        "type":"payment.updated",
        "created_at":"2026-11-21T18:30:00Z",
        "data":{"object":{"payment":{
            "id":"payment-1","order_id":"order-1","status":status,
            "amount_money":{"amount":amount,"currency":"USD"},
        }}},
    },separators=(",",":")).encode()


def signature(body):
    return base64.b64encode(hmac.new(KEY.encode(),URL.encode()+body,hashlib.sha256).digest()).decode()


def client(config_factory=lambda:CONFIG,db_url="postgresql://synthetic"):
    app=FastAPI()
    app.include_router(create_square_webhook_router(database_url=db_url,config_factory=config_factory,connection_factory=connection_factory))
    return TestClient(app)


def test_verified_webhook_calls_reconciliation_and_returns_outcome():
    global connection
    connection=FakeConnection("RECONCILED")
    body=make_body()
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":signature(body)})
    assert response.status_code==200
    assert response.json()=={"status":"RECONCILED"}
    assert len(connection.calls)==1
    assert "reconcile_square_sandbox_webhook" in connection.calls[0][0]
    assert connection.calls[0][1][0]=="evt-1"
    assert connection.calls[0][1][-1]==hashlib.sha256(body).hexdigest()


def test_invalid_signature_never_connects_to_database():
    global connection
    connection=FakeConnection()
    body=make_body()
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":"bad"})
    assert response.status_code==401
    assert response.json()=={"detail":"INVALID_WEBHOOK_SIGNATURE"}
    assert connection.calls==[]


def test_signed_amount_mismatch_is_durably_reconciled_as_mismatch():
    global connection
    connection=FakeConnection("AMOUNT_MISMATCH")
    body=make_body(amount=100)
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":signature(body)})
    assert response.status_code==200
    assert response.json()=={"status":"AMOUNT_MISMATCH"}
    assert len(connection.calls)==1


def test_nonpositive_amount_rejected_before_database():
    global connection
    connection=FakeConnection()
    body=make_body(amount=-1)
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":signature(body)})
    assert response.status_code==400
    assert response.json()=={"detail":"INVALID_PAYMENT_EVENT"}
    assert connection.calls==[]


def test_database_failure_returns_retryable_unavailable():
    global connection
    connection=FakeConnection("ERROR")
    response=client().post("/webhooks/square",content=make_body(),headers={"x-square-hmacsha256-signature":signature(make_body())})
    assert response.status_code==503
    assert response.json()=={"detail":"PAYMENT_RECONCILIATION_UNAVAILABLE"}


def test_webhook_event_id_conflict_returns_nonretryable_conflict():
    global connection
    connection=FakeConnection()
    connection.raise_code="SQUARE_WEBHOOK_EVENT_ID_CONFLICT"
    body=make_body()
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":signature(body)})
    assert response.status_code==409
    assert response.json()=={"detail":"WEBHOOK_EVENT_ID_CONFLICT"}


def test_body_too_large_is_rejected():
    global connection
    connection=FakeConnection()
    body=b"x"*65537
    response=client().post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":"irrelevant"})
    assert response.status_code==413
    assert connection.calls==[]


def test_invalid_configuration_fails_closed():
    global connection
    connection=FakeConnection()
    bad_config=lambda:SquareSandboxConfig("token","loc","key","http://not-https","sandbox")
    body=make_body()
    response=client(config_factory=bad_config).post("/webhooks/square",content=body,headers={"x-square-hmacsha256-signature":signature(body)})
    assert response.status_code==503
    assert connection.calls==[]

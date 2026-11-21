"""Public Square Sandbox webhook endpoint: signature verification before persistence."""
from __future__ import annotations

import json
from datetime import datetime
from os import environ

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.payments.square_sandbox import (
    SquareSandboxConfig,
    SquareSandboxError,
    verify_and_parse_square_payment_event,
)
from database.square_sandbox_webhooks import (
    SquareWebhookReceiptError,
    reconcile_verified_event,
)


def create_square_webhook_router(*, database_url=None, config_factory=SquareSandboxConfig.from_environment,
                                connection_factory=psycopg.connect):
    router = APIRouter()

    @router.post("/webhooks/square", include_in_schema=False)
    async def square_webhook(request: Request):
        signature = request.headers.get("x-square-hmacsha256-signature", "")
        raw_body = await request.body()
        if len(raw_body) > 65536:
            return JSONResponse({"detail":"WEBHOOK_BODY_TOO_LARGE"},status_code=413)
        try:
            config = config_factory()
            config.validate_webhook()
            if config.environment != "sandbox":
                return JSONResponse({"detail":"SQUARE_SANDBOX_ONLY"},status_code=503)
            event = verify_and_parse_square_payment_event(
                raw_body, signature, config, square_environment="Sandbox", allow_amount_mismatch=True,
            )
            try:
                envelope = json.loads(raw_body)
                timestamp = datetime.fromisoformat(envelope["created_at"].replace("Z","+00:00"))
            except (ValueError,TypeError,KeyError,AttributeError):
                return JSONResponse({"detail":"INVALID_SQUARE_WEBHOOK_TIMESTAMP"},status_code=400)
            db_url = database_url or environ.get("APP_DATABASE_URL","")
            if not db_url:
                return JSONResponse({"detail":"PAYMENT_RECONCILIATION_UNAVAILABLE"},status_code=503)
            with connection_factory(db_url,connect_timeout=3) as conn:
                outcome = reconcile_verified_event(conn,event,event_created_at=timestamp,raw_body=raw_body)
            return JSONResponse({"status":outcome},status_code=200,headers={"Cache-Control":"no-store"})
        except SquareSandboxError as exc:
            if exc.code == "SQUARE_SANDBOX_WEBHOOK_SIGNATURE_INVALID":
                return JSONResponse({"detail":"INVALID_WEBHOOK_SIGNATURE"},status_code=401)
            if exc.code in {"SQUARE_SANDBOX_PAYMENT_EVENT_INVALID","SQUARE_SANDBOX_PAYMENT_EVENT_UNSUPPORTED",
                            "SQUARE_SANDBOX_PAYMENT_AMOUNT_MISMATCH","SQUARE_SANDBOX_PAYMENT_CURRENCY_UNSUPPORTED",
                            "SQUARE_SANDBOX_PAYMENT_STATUS_UNSUPPORTED"}:
                return JSONResponse({"detail":"INVALID_PAYMENT_EVENT"},status_code=400)
            return JSONResponse({"detail":"PAYMENT_WEBHOOK_CONFIGURATION_UNAVAILABLE"},status_code=503)
        except SquareWebhookReceiptError as exc:
            if exc.code == "SQUARE_WEBHOOK_EVENT_ID_CONFLICT":
                return JSONResponse({"detail":"WEBHOOK_EVENT_ID_CONFLICT"},status_code=409)
            return JSONResponse({"detail":"PAYMENT_RECONCILIATION_UNAVAILABLE"},status_code=503)
        except Exception:
            return JSONResponse({"detail":"PAYMENT_RECONCILIATION_UNAVAILABLE"},status_code=503)

    return router

"""CIECA-aligned carrier message model (Slice 7; plan v1.3 D-11 candidate spec).

Defines the outbound message envelope and types for the carrier-facing
integration. The collision industry exchanges claims, FNOL, assignments,
estimates, attachments, dispositions, and status through CIECA BMS (XML)
and its emerging JSON API, sharing one data dictionary. This module models
our side of that boundary: a versioned, validated message contract whose
types mirror the CIECA message categories, so the eventual field-level
mapping to the CIECA schema is a translation, not a redesign.

Honesty: field-level CIECA mapping requires CIECA membership access to the
standard and is explicitly NOT claimed here. What IS claimed: a validated,
versioned message contract with CIECA-aligned categories, built only from
sealed, integrity-verified, attributed decisions — and a builder that
structurally refuses to emit compensation or incentive language.

Delivery is outbox-only (Slice 6); no live sends occur from this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.capture_workflow import CaptureWorkflow
from app.dispatch_routing import AcceptanceRecord, DispatchPlan
from app.outbox import OutboxMessage
from app.review_pipeline import ReviewDecisionRecord, SealRecord

CARRIER_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "carrier-message-model.json"
CARRIER_SCHEMA_VERSION = "0.1"
CARRIER_MODEL_VERSION = "carrier-message-v1"

CLAIM_STATUS = "CLAIM_STATUS"
ASSIGNMENT = "ASSIGNMENT"
ATTACHMENT = "ATTACHMENT"
DISPOSITION = "DISPOSITION"
ESTIMATE = "ESTIMATE"

# Language that must never appear in a carrier message (eradication
# alignment): the platform pays nothing to accident-involved persons.
BANNED_TERMS = (
    "$80", "80 dollar", "eighty dollar", "$60", "60 dollar", "sixty dollar",
    "incentive", "compensation", "payout to driver", "cash payment to",
)


class CarrierMessageError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def load_carrier_contract() -> dict:
    value = json.loads(CARRIER_CONTRACT_PATH.read_text(encoding="utf-8"))
    if (
        type(value) is not dict
        or value.get("schema_version") != CARRIER_SCHEMA_VERSION
        or value.get("model_version") != CARRIER_MODEL_VERSION
        or type(value.get("message_types")) is not dict
        or not value["message_types"]
        or type(value.get("envelope_required")) is not list
        or not value["envelope_required"]
    ):
        raise CarrierMessageError("INVALID_CARRIER_CONTRACT")
    for name, spec in value["message_types"].items():
        if type(spec) is not dict or "required_payload" not in spec or "optional_payload" not in spec:
            raise CarrierMessageError("INVALID_CARRIER_CONTRACT")
    return value


def assert_no_compensation_language(text: str) -> None:
    lowered = str(text).lower()
    for term in BANNED_TERMS:
        if term in lowered:
            raise CarrierMessageError("COMPENSATION_LANGUAGE_FORBIDDEN", term)


@dataclass(frozen=True)
class CarrierMessage:
    message_id: str
    message_type: str
    schema_version: str
    model_version: str
    created_at: str
    session_id: str
    source_event_id: str
    payload: dict

    def to_json(self) -> str:
        assert_no_compensation_language(json.dumps(self.payload))
        return json.dumps(
            {
                "message_id": self.message_id,
                "message_type": self.message_type,
                "schema_version": self.schema_version,
                "model_version": self.model_version,
                "created_at": self.created_at,
                "session_id": self.session_id,
                "source_event_id": self.source_event_id,
                "payload": self.payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def build_carrier_message(
    message_type: str,
    *,
    session_id: str,
    source_event_id: str,
    payload: dict,
    created_at: Optional[str] = None,
) -> CarrierMessage:
    contract = load_carrier_contract()
    spec = contract["message_types"].get(message_type)
    if spec is None:
        raise CarrierMessageError("UNKNOWN_MESSAGE_TYPE", message_type)
    if not isinstance(session_id, str) or not session_id.strip():
        raise CarrierMessageError("INVALID_SESSION")
    if not isinstance(source_event_id, str) or not source_event_id.strip():
        raise CarrierMessageError("INVALID_SOURCE_EVENT")
    if type(payload) is not dict:
        raise CarrierMessageError("INVALID_PAYLOAD")
    missing = [k for k in spec["required_payload"] if k not in payload]
    if missing:
        raise CarrierMessageError("MISSING_REQUIRED_PAYLOAD", ",".join(missing))
    allowed = set(spec["required_payload"]) | set(spec["optional_payload"])
    unexpected = [k for k in payload if k not in allowed]
    if unexpected:
        raise CarrierMessageError("UNEXPECTED_PAYLOAD_FIELD", ",".join(unexpected))
    message = CarrierMessage(
        message_id=str(uuid4()),
        message_type=message_type,
        schema_version=CARRIER_SCHEMA_VERSION,
        model_version=CARRIER_MODEL_VERSION,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        source_event_id=source_event_id,
        payload=payload,
    )
    message.to_json()  # validates serializability + banned-language scan
    return message


# --- typed builders from landed domain objects ---------------------------------

def build_claim_status(workflow: CaptureWorkflow, created_at: Optional[str] = None) -> CarrierMessage:
    """Status message from the frozen machine's current state."""
    if not isinstance(workflow, CaptureWorkflow):
        raise CarrierMessageError("INVALID_SESSION")
    if not workflow.history:
        raise CarrierMessageError("EMPTY_HISTORY")
    vin = None
    for event in workflow.history:
        if event.kind == "VEHICLE_RECORDED":
            vin = json.loads(event.payload_json).get("vin")
    return build_carrier_message(
        CLAIM_STATUS,
        session_id=workflow.session_id,
        source_event_id=workflow.history[-1].event_id,
        payload={"status": workflow.state, "session_id": workflow.session_id, **({"vin": vin} if vin else {})},
        created_at=created_at,
    )


def build_attachment(workflow: CaptureWorkflow, seal: SealRecord, created_at: Optional[str] = None) -> CarrierMessage:
    """Attachment reference: the sealed evidence manifest for the claim file."""
    if workflow.state not in ("sealed", "reviewed"):
        raise CarrierMessageError("ATTACHMENT_ORDER_VIOLATION", f"state={workflow.state}")
    if not isinstance(seal, SealRecord) or seal.session_id != workflow.session_id:
        raise CarrierMessageError("INVALID_SEAL")
    artifact_count = len(workflow.manifest_entries())
    return build_carrier_message(
        ATTACHMENT,
        session_id=workflow.session_id,
        source_event_id=seal.event_id,
        payload={
            "manifest_digest": seal.manifest_digest,
            "shot_list_version": seal.shot_list_version,
            "artifact_count": artifact_count,
        },
        created_at=created_at,
    )


def build_disposition(
    workflow: CaptureWorkflow, decision: ReviewDecisionRecord, created_at: Optional[str] = None
) -> CarrierMessage:
    """Disposition message from the attributed reviewer decision."""
    if workflow.state != "reviewed":
        raise CarrierMessageError("DISPOSITION_ORDER_VIOLATION", f"state={workflow.state}")
    if not isinstance(decision, ReviewDecisionRecord) or decision.session_id != workflow.session_id:
        raise CarrierMessageError("INVALID_DECISION")
    return build_carrier_message(
        DISPOSITION,
        session_id=workflow.session_id,
        source_event_id=decision.event_id,
        payload={
            "disposition": decision.disposition,
            "actor": decision.actor,
            "occurred_at": decision.occurred_at,
            "reason": decision.reason,
            "artifact_ids": list(decision.artifact_ids),
        },
        created_at=created_at,
    )


def build_assignment(
    workflow: CaptureWorkflow, plan: DispatchPlan, created_at: Optional[str] = None
) -> CarrierMessage:
    """Assignment message: the recorded acceptance and planned tow dispatch."""
    if workflow.state != "reviewed":
        raise CarrierMessageError("ASSIGNMENT_ORDER_VIOLATION", f"state={workflow.state}")
    if not isinstance(plan, DispatchPlan):
        raise CarrierMessageError("INVALID_DISPATCH_PLAN")
    if plan.acceptance.party_type not in ("shop", "dealer"):
        raise CarrierMessageError("INVALID_PARTY_TYPE")
    return build_carrier_message(
        ASSIGNMENT,
        session_id=workflow.session_id,
        source_event_id=decision_event_id(workflow),
        payload={
            "party_type": plan.acceptance.party_type,
            "party_id": plan.acceptance.party_id,
            "accepted_at": plan.acceptance.accepted_at,
            "location_label": plan.acceptance.location_label,
            "dispatch_total_minutes": plan.total_cost_minutes,
        },
        created_at=created_at,
    )


def decision_event_id(workflow: CaptureWorkflow) -> str:
    for event in reversed(workflow.history):
        if event.kind == "REVIEW_RECORDED":
            return event.event_id
    raise CarrierMessageError("REVIEW_EVENT_NOT_FOUND")

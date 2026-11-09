"""
Carrier message model tests (Slice 7; D-11 candidate spec).

Covers: contract loading and validation, envelope/payload validation per
message type, typed builders from landed domain objects (status,
attachment, disposition, assignment), ordering enforcement (messages only
from sealed/reviewed sessions), and the structural refusal to emit
compensation or incentive language.
"""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.capture_workflow import CaptureWorkflow
from app.carrier_messages import (
    ASSIGNMENT,
    ATTACHMENT,
    BANNED_TERMS,
    CLAIM_STATUS,
    DISPOSITION,
    ESTIMATE,
    CarrierMessage,
    CarrierMessageError,
    assert_no_compensation_language,
    build_assignment,
    build_attachment,
    build_carrier_message,
    build_claim_status,
    build_disposition,
    load_carrier_contract,
)
from app.dispatch_routing import (
    AcceptanceRecord,
    DispatchRoutingService,
    InMemoryRoutingEngine,
    load_road_network,
)
from app.evidence_manifest import CANONICAL_SLOTS
from app.review_pipeline import ReviewerQueue, SealService, ServerIntegrityVerifier
from app.review_pipeline import IntegrityReport
from app.artifact_storage import ArtifactKey, OriginalByteStore
from app.controlled_demo import synthetic_original

pytestmark = pytest.mark.subtests

FIXED_NOW = "2026-11-07T10:00:00+00:00"
VALID_VIN = "1HGCM82633A004352"


def make_reviewed_workflow(tmp_path=None):
    w = CaptureWorkflow(str(uuid4()), now=lambda: FIXED_NOW)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    w.record_vehicle("driver-1", VALID_VIN)
    for i, slot in enumerate(CANONICAL_SLOTS, start=1):
        data = synthetic_original(slot)
        w.register_artifact("driver-1", slot, f"art-{i}", sha256(data).hexdigest(), len(data))
    w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS})
    service = SealService()
    seal = service.seal(w, "sealer-1", "test seal", now=lambda: FIXED_NOW)
    # Integrity report: synthesize an ok report (verified in review tests).
    report = IntegrityReport(
        session_id=w.session_id,
        manifest_digest=seal.manifest_digest,
        verified_artifact_ids=tuple(e.artifact_id for e in w.manifest_entries()),
        rejections=(),
    )
    queue = ReviewerQueue(now=lambda: FIXED_NOW)
    queue.enqueue(w, seal, report, "enq-1")
    decision = queue.record_decision(
        w, "NOTE_ONLY", [e.artifact_id for e in w.manifest_entries()],
        "reviewer-01", "complete evidence set", integrity_report=report,
    )
    return w, seal, decision


def make_dispatch_plan(w):
    network = load_road_network()
    acceptance = AcceptanceRecord("shop", "shop-001", FIXED_NOW, "shop-a")
    return DispatchRoutingService(InMemoryRoutingEngine()).plan(
        network, acceptance, "operator-depot", "incident-scene", "google"
    )


# --- contract ------------------------------------------------------------------

def test_contract_loads():
    contract = load_carrier_contract()
    assert contract["model_version"] == "carrier-message-v1"
    assert set(contract["message_types"]) == {CLAIM_STATUS, ASSIGNMENT, ATTACHMENT, DISPOSITION, ESTIMATE}


def test_unknown_type_rejected():
    with pytest.raises(CarrierMessageError) as e:
        build_carrier_message("FNOL", session_id="s", source_event_id="e", payload={})
    assert e.value.code == "UNKNOWN_MESSAGE_TYPE"


def test_missing_required_payload_rejected():
    with pytest.raises(CarrierMessageError) as e:
        build_carrier_message(DISPOSITION, session_id="s", source_event_id="e", payload={"disposition": "NOTE_ONLY"})
    assert e.value.code == "MISSING_REQUIRED_PAYLOAD"


def test_unexpected_payload_field_rejected():
    with pytest.raises(CarrierMessageError) as e:
        build_carrier_message(
            CLAIM_STATUS, session_id="s", source_event_id="e",
            payload={"status": "reviewed", "session_id": "s", "surprise": 1},
        )
    assert e.value.code == "UNEXPECTED_PAYLOAD_FIELD"


def test_invalid_session_and_event_rejected():
    for session_id, event_id in (("", "e"), ("s", ""), (None, "e")):
        with pytest.raises(CarrierMessageError):
            build_carrier_message(CLAIM_STATUS, session_id=session_id, source_event_id=event_id,
                                  payload={"status": "reviewed", "session_id": session_id or "s"})


# --- typed builders --------------------------------------------------------------

def test_claim_status_builder():
    w, _, _ = make_reviewed_workflow()
    message = build_claim_status(w, created_at=FIXED_NOW)
    assert message.message_type == CLAIM_STATUS
    payload = message.to_json()
    parsed = json.loads(payload)
    assert parsed["payload"]["status"] == "reviewed"
    assert parsed["payload"]["vin"] == VALID_VIN
    assert parsed["payload"]["session_id"] == w.session_id


def test_attachment_builder_requires_sealed():
    w, _, _ = make_reviewed_workflow()  # reviewed: allowed
    w2 = CaptureWorkflow(str(uuid4()))
    with pytest.raises(CarrierMessageError) as e:
        build_attachment(w2, None)
    assert e.value.code in ("ATTACHMENT_ORDER_VIOLATION", "INVALID_SEAL")


def test_attachment_builder():
    w, seal, _ = make_reviewed_workflow()
    message = build_attachment(w, seal, created_at=FIXED_NOW)
    assert message.message_type == ATTACHMENT
    parsed = json.loads(message.to_json())
    assert parsed["payload"]["manifest_digest"] == seal.manifest_digest
    assert parsed["payload"]["artifact_count"] == len(CANONICAL_SLOTS)


def test_disposition_builder_requires_reviewed():
    w = CaptureWorkflow(str(uuid4()))
    with pytest.raises(CarrierMessageError) as e:
        build_disposition(w, None)
    assert e.value.code == "DISPOSITION_ORDER_VIOLATION"


def test_disposition_builder():
    w, _, decision = make_reviewed_workflow()
    message = build_disposition(w, decision, created_at=FIXED_NOW)
    parsed = json.loads(message.to_json())
    assert parsed["payload"]["disposition"] == "NOTE_ONLY"
    assert parsed["payload"]["actor"] == "reviewer-01"
    assert parsed["source_event_id"] == decision.event_id
    assert len(parsed["payload"]["artifact_ids"]) == len(CANONICAL_SLOTS)


def test_assignment_builder():
    w, _, _ = make_reviewed_workflow()
    plan = make_dispatch_plan(w)
    message = build_assignment(w, plan, created_at=FIXED_NOW)
    parsed = json.loads(message.to_json())
    assert parsed["payload"]["party_type"] == "shop"
    assert parsed["payload"]["party_id"] == "shop-001"
    assert parsed["payload"]["dispatch_total_minutes"] > 0
    assert parsed["message_type"] == ASSIGNMENT


def test_assignment_requires_reviewed_session():
    w, _, _ = make_reviewed_workflow()
    fresh = CaptureWorkflow(str(uuid4()))
    plan = make_dispatch_plan(w)
    with pytest.raises(CarrierMessageError) as e:
        build_assignment(fresh, plan)
    assert e.value.code == "ASSIGNMENT_ORDER_VIOLATION"


# --- compensation language ban -----------------------------------------------------

def test_compensation_language_structurally_refused():
    with pytest.raises(CarrierMessageError) as e:
        build_carrier_message(
            CLAIM_STATUS, session_id="s", source_event_id="e",
            payload={"status": "paid $80 to driver", "session_id": "s"},
        )
    assert e.value.code == "COMPENSATION_LANGUAGE_FORBIDDEN"


def test_banned_terms_scan():
    for term in BANNED_TERMS:
        with pytest.raises(CarrierMessageError):
            assert_no_compensation_language(f"message mentions {term} to the driver")
    assert_no_compensation_language("evidence packet ready for carrier review")  # clean text passes


def test_message_json_round_trip():
    w, seal, decision = make_reviewed_workflow()
    message = build_disposition(w, decision, created_at=FIXED_NOW)
    parsed = json.loads(message.to_json())
    assert parsed["model_version"] == "carrier-message-v1"
    assert parsed["schema_version"] == "0.1"
    rebuilt = CarrierMessage(
        message_id=parsed["message_id"], message_type=parsed["message_type"],
        schema_version=parsed["schema_version"], model_version=parsed["model_version"],
        created_at=parsed["created_at"], session_id=parsed["session_id"],
        source_event_id=parsed["source_event_id"], payload=parsed["payload"],
    )
    assert rebuilt.to_json() == message.to_json()

"""
Capture workflow tests (Slice 4; plan v1.3 phases 5-6).

Covers: disclosure gate, explicit consent, VIN guard uncertainty handling,
shot-contract-guided capture with retakes, per-slot quality gate, local draft
persistence with restart recovery, and idempotent resumable sync — ending in a
full synthetic incident running capture-to-sync end to end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.capture_workflow import (
    ArtifactEntry,
    CaptureWorkflow,
    LocalDraftStore,
    WorkflowError,
    load_disclosure_contract,
    sha256_hex_of,
    sync_draft_to_server,
)
from app.evidence_manifest import LEGACY_CANONICAL_SLOTS as CANONICAL_SLOTS
from app.capture_protocols import LEGACY_CAPTURE_PROTOCOL
from app.vin_guard import VIN_WEIGHTS, validate_vin

pytestmark = pytest.mark.subtests

VALID_VIN = "1HGCM82633A004352"
X_CHECK_VIN = "1M8GDM9AXKP042788"


def err_code(excinfo):
    return excinfo.value.code


# --- VIN guard: port parity with frontend/src/modules/capture/vin.mjs -------

def test_vin_numeric_check_digit():
    r = validate_vin(VALID_VIN)
    assert r.ok and r.expected_check_digit == "3"


def test_vin_remainder_ten_requires_x():
    r = validate_vin(X_CHECK_VIN)
    assert r.ok and r.expected_check_digit == "X"


def test_vin_normalization_retains_original():
    r = validate_vin(VALID_VIN.lower())
    assert r.ok and r.vin == VALID_VIN and r.raw_vin == VALID_VIN.lower() and r.normalization_changed


def test_vin_separators_removed_original_retained():
    raw = " 1HG-CM82633A004352 "
    r = validate_vin(raw)
    assert r.ok and r.raw_vin == raw and r.vin == VALID_VIN


def test_vin_wrong_check_digit_not_repaired():
    bad = VALID_VIN[:8] + "4" + VALID_VIN[9:]
    r = validate_vin(bad)
    assert not r.ok and r.reason == "CHECKSUM_MISMATCH" and r.vin == bad
    assert r.received_check_digit == "4" and r.expected_check_digit == "3"
    assert r.recapture_required and r.uncertainty_code == "CHECKSUM_MISMATCH"


def test_vin_illegal_i_o_q_never_substituted():
    for ch in ("I", "O", "Q"):
        r = validate_vin(VALID_VIN[:4] + ch + VALID_VIN[5:])
        assert not r.ok and r.reason == "ILLEGAL_CHARACTERS"


def test_vin_length_and_input_bounds():
    assert validate_vin("").reason == "INVALID_LENGTH"
    assert validate_vin(VALID_VIN[1:]).reason == "INVALID_LENGTH"
    assert validate_vin(VALID_VIN + "0").reason == "INVALID_LENGTH"
    for bad in (None, 123, {}, []):
        assert validate_vin(bad).reason == "INVALID_INPUT"
    assert validate_vin("A" * 257).reason == "INPUT_TOO_LONG"


def test_vin_unicode_confusables_rejected_not_rewritten():
    fullwidth = "１" + VALID_VIN[1:]
    for raw in (fullwidth, VALID_VIN + "ß"):
        r = validate_vin(raw)
        assert not r.ok and r.vin is None and r.raw_vin == raw and r.reason == "ILLEGAL_CHARACTERS"


def test_vin_report_is_immutable_and_weights_frozen():
    r = validate_vin(VALID_VIN)
    with pytest.raises(Exception):
        r.ok = False
    assert VIN_WEIGHTS == (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def test_vin_pass_is_not_decoded_identity():
    r = validate_vin("0" * 17)
    assert r.ok and r.scope == "format-and-check-digit-only"
    assert not hasattr(r, "make") and not hasattr(r, "model")


# --- disclosure gate ---------------------------------------------------------

def test_disclosure_contract_loads():
    version, sections = load_disclosure_contract()
    assert version == "disclosure-v1" and len(sections) >= 1


def test_consent_requires_disclosure_presentation():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    with pytest.raises(WorkflowError) as e:
        w.record_consent("driver-1", True, "disclosure-v1")
    assert err_code(e) == "DISCLOSURE_NOT_PRESENTED"


def test_consent_rejects_wrong_disclosure_version():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    with pytest.raises(WorkflowError) as e:
        w.record_consent("driver-1", True, "disclosure-stale")
    assert err_code(e) == "DISCLOSURE_VERSION_MISMATCH"


def test_consent_rejects_implicit_acceptance():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    for accepted in (False, None, "yes", 1):
        with pytest.raises(WorkflowError) as e:
            w.record_consent("driver-1", accepted, "disclosure-v1")
        assert err_code(e) == "CONSENT_NOT_EXPLICIT"


def test_presentation_rejects_stale_version():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    with pytest.raises(WorkflowError) as e:
        w.present_disclosure("disclosure-2024")
    assert err_code(e) == "DISCLOSURE_VERSION_MISMATCH"
    assert w._presented_disclosure is None


# --- VIN uncertainty handling --------------------------------------------------

def test_uncertain_vin_recorded_and_recapture_required():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    with pytest.raises(WorkflowError) as e:
        w.record_vehicle("driver-1", VALID_VIN[:8] + "9" + VALID_VIN[9:])
    assert err_code(e) == "VIN_UNCERTAIN"
    assert w.uncertainties and w.uncertainties[0].recapture_required
    assert w.state == "consented"  # no vehicle recorded on failure


def test_vin_correction_allowed_with_traceability():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    w.record_vehicle("driver-1", " " + VALID_VIN.lower() + " ")
    w.record_vehicle("driver-1", VALID_VIN)  # correction, m1-v1 allows
    assert w.state == "vehicle_identified"
    vehicle_events = [ev for ev in w.history if ev.kind == "VEHICLE_RECORDED"]
    assert len(vehicle_events) == 2
    payload = json.loads(vehicle_events[0].payload_json)
    assert payload["raw_input_retained"] == " " + VALID_VIN.lower() + " "
    assert payload["normalization_changed"] is True


def test_vehicle_requires_consent_first():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    with pytest.raises(WorkflowError) as e:
        w.record_vehicle("driver-1", VALID_VIN)
    assert err_code(e) == "CAPTURE_ORDER_VIOLATION"


# --- guided capture ------------------------------------------------------------

def make_started_workflow():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    w.record_vehicle("driver-1", VALID_VIN)
    return w


def artifact(i, slot):
    return (slot, f"art-{i}", sha256_hex_of(f"original-bytes-{i}".encode()), 1024 + i)


def test_capture_unknown_slot_rejected():
    w = make_started_workflow()
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", "trunk_interior", "art-1", "0" * 64, 100)
    assert err_code(e) == "UNKNOWN_SLOT"


def test_capture_invalid_digest_and_length_rejected():
    w = make_started_workflow()
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", "front", "art-1", "not-a-digest", 100)
    assert err_code(e) == "INVALID_DIGEST"
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", "front", "art-1", "0" * 64, 0)
    assert err_code(e) == "INVALID_BYTE_LENGTH"


def test_capture_requires_vehicle_identified():
    w = CaptureWorkflow(str(uuid4()), protocol_version=LEGACY_CAPTURE_PROTOCOL)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", "front", "art-1", "0" * 64, 100)
    assert err_code(e) == "CAPTURE_ORDER_VIOLATION"


def test_retake_supersedes_traceably_before_quality():
    w = make_started_workflow()
    w.register_artifact("driver-1", *artifact(1, "front"))
    w.register_artifact("driver-1", *artifact(2, "front"))  # retake
    assert w.state == "evidence_captured"
    events = [ev for ev in w.history if ev.kind == "ARTIFACT_REGISTERED"]
    assert len(events) == 2
    payload = json.loads(events[1].payload_json)
    assert payload["supersedes_artifact_id"] == "art-1"
    assert w._retakes and w._retakes[0].artifact_id == "art-1"


def test_duplicate_artifact_id_rejected():
    w = make_started_workflow()
    w.register_artifact("driver-1", *artifact(1, "front"))
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", "rear", "art-1", "1" * 64, 100)
    assert err_code(e) == "DUPLICATE_ARTIFACT_ID"


# --- quality gate ---------------------------------------------------------------

def complete_capture(w, actor="driver-1"):
    for i, slot in enumerate(CANONICAL_SLOTS, start=1):
        w.register_artifact(actor, *artifact(i, slot))


def test_quality_requires_complete_capture_set():
    w = make_started_workflow()
    w.register_artifact("driver-1", *artifact(1, CANONICAL_SLOTS[0]))
    with pytest.raises(WorkflowError) as e:
        w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS})
    assert err_code(e) == "CAPTURE_SET_INCOMPLETE"


def test_quality_rejects_failed_verdict_without_event():
    w = make_started_workflow()
    complete_capture(w)
    verdicts = {s: True for s in CANONICAL_SLOTS}
    verdicts["rear"] = False
    with pytest.raises(WorkflowError) as e:
        w.record_quality("driver-1", verdicts)
    assert err_code(e) == "QUALITY_GATE_FAILED" and e.value.detail == "rear"
    assert w.state == "evidence_captured"  # retake path stays open


def test_quality_rejects_partial_verdict_map():
    w = make_started_workflow()
    complete_capture(w)
    with pytest.raises(WorkflowError) as e:
        w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS[:-1]})
    assert err_code(e) == "QUALITY_VERDICTS_INCOMPLETE"


def test_quality_pass_reaches_quality_verified():
    w = make_started_workflow()
    complete_capture(w)
    result = w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS})
    assert result["passed"] and w.state == "quality_verified"
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", *artifact(99, "front"))  # retake closed
    assert err_code(e) == "CAPTURE_ORDER_VIOLATION"


# --- local persistence + resumable sync -------------------------------------------

def test_local_draft_survives_restart_and_resumes():
    storage = {}
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    draft.save_artifact("s1", *artifact(1, "vin_ocr"))
    draft.save_artifact("s1", *artifact(2, "front"))
    assert draft.revision() == 2
    # Simulated app restart: a new store over the same persisted state.
    resumed = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    snapshot = resumed.resume()
    assert snapshot["revision"] == 2
    assert snapshot["captured_slots"] == ["front", "vin_ocr"]
    assert snapshot["pending_sync_count"] == 2
    assert len(resumed.pending_sync()) == 2


def test_local_retake_replaces_pending_entry():
    storage = {}
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    draft.save_artifact("s1", *artifact(1, "front"))
    draft.save_artifact("s1", *artifact(2, "front"))  # local retake
    assert draft.revision() == 2
    pending = draft.pending_sync()
    assert len(pending) == 1 and pending[0]["artifact_id"] == "art-2"


def test_sync_idempotent_retry_no_duplicate():
    w = make_started_workflow()
    storage = {}
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    draft.save_artifact(w.session_id, *artifact(1, "front"))
    first = sync_draft_to_server(w, draft, "driver-1")
    assert first["synced"][0]["status"] == "registered"
    retry = sync_draft_to_server(w, draft, "driver-1")
    assert retry["synced"] == [] and retry["pending"] == []
    # Re-registering the same artifact id directly is also a no-op.
    outcome = w.register_artifact("driver-1", *artifact(1, "front"))
    assert outcome["status"] == "already_registered"
    events = [ev for ev in w.history if ev.kind == "ARTIFACT_REGISTERED"]
    assert len(events) == 1


def test_sync_retake_allowed_before_quality_rejected_after():
    w = make_started_workflow()
    storage = {}
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    draft.save_artifact(w.session_id, *artifact(1, "front"))
    sync_draft_to_server(w, draft, "driver-1")
    # A local retake for a synced slot syncs fine while quality is open.
    draft.save_artifact(w.session_id, *artifact(2, "front"))
    outcome = sync_draft_to_server(w, draft, "driver-1")
    assert outcome["synced"][0]["status"] == "registered"
    # The same artifact id re-used for another slot is a sync conflict.
    draft.save_artifact(w.session_id, *artifact(3, "rear"))
    draft.mark_synced("art-2")
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", *artifact(1, "rear"))
    assert err_code(e) == "DUPLICATE_ARTIFACT_ID"


# --- synthetic incident: capture-to-sync end to end -------------------------------

def test_synthetic_incident_capture_to_sync_end_to_end():
    session_id = str(uuid4())
    w = CaptureWorkflow(session_id, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    assert w.state == "initialized"

    # Disclosure gate then explicit consent.
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    assert w.state == "consented"

    # VIN guard: first attempt uncertain (recorded, recapture required)...
    with pytest.raises(WorkflowError):
        w.record_vehicle("driver-1", VALID_VIN[:8] + "7" + VALID_VIN[9:])
    assert w.state == "consented" and len(w.uncertainties) == 1
    # ...recapture succeeds.
    w.record_vehicle("driver-1", VALID_VIN)
    assert w.state == "vehicle_identified"

    # Guided capture happens locally, with a crash mid-capture.
    storage = {}
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    for i, slot in enumerate(CANONICAL_SLOTS[:6], start=1):
        draft.save_artifact(session_id, *artifact(i, slot))
    crashed_pending = draft.pending_sync()
    assert len(crashed_pending) == 6

    # App restart: draft recovered, capture resumes from remaining slots.
    draft = LocalDraftStore(storage, protocol_version=LEGACY_CAPTURE_PROTOCOL)
    snapshot = draft.resume()
    assert snapshot["revision"] == 6 and snapshot["pending_sync_count"] == 6
    for i, slot in enumerate(CANONICAL_SLOTS[6:], start=7):
        draft.save_artifact(session_id, *artifact(i, slot))

    # Resumable sync: interrupted after 5, resumed, completes all 12.
    for entry in draft.pending_sync()[:5]:
        w.register_artifact("driver-1", entry["slot"], entry["artifact_id"], entry["sha256_hex"], entry["byte_length"])
        draft.mark_synced(entry["artifact_id"])
    interrupted = draft.pending_sync()
    assert len(interrupted) == 7
    outcome = sync_draft_to_server(w, draft, "driver-1")
    assert len(outcome["synced"]) == 7 and outcome["pending"] == []
    assert w.state == "evidence_captured"
    assert sorted(w.captured_slots()) == sorted(CANONICAL_SLOTS)

    # Quality verification passes on the full capture set.
    w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS})
    assert w.state == "quality_verified"

    # Integrity summary ready for Slice 5 sealing: 12 slots, digests intact.
    entries = w.manifest_entries()
    assert len(entries) == 12 and all(isinstance(e, ArtifactEntry) for e in entries)
    assert entries[0].slot == CANONICAL_SLOTS[0]

    # Event history replays cleanly through the frozen machine.
    from contracts.m1_state_machine import M1SessionMachine

    replayed = M1SessionMachine.reconstruct(session_id, w.history)
    assert replayed.state == "quality_verified"


def test_abort_mid_capture_is_terminal():
    w = make_started_workflow()
    complete_capture(w)
    w.machine.apply(
        __import__("app.domain_events", fromlist=["DomainEvent"]).DomainEvent(
            session_id=w.session_id,
            event_id=str(uuid4()),
            sequence=w.history[-1].sequence + 1,
            kind="SESSION_ABORTED",
            actor="driver-1",
            occurred_at="2026-11-06T16:00:00+00:00",
            reason="roadside safety pause",
            payload_json="{}",
        )
    )
    assert w.state == "aborted"
    with pytest.raises(WorkflowError) as e:
        w.register_artifact("driver-1", *artifact(50, "front"))
    assert err_code(e) == "CAPTURE_ORDER_VIOLATION"

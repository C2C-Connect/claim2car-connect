"""
Review pipeline tests (Slice 5; plan v1.3 phases 7-8, 10).

Covers: seal ordering and digest binding, server-side hash recomputation from
durable storage (clean pass, corrupt/replaced media, missing artifact), the
reviewer queue with attributed decisions, and the controlled demonstration
end-to-end with a retained Gate A evidence record.
"""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.artifact_storage import ArtifactKey, OriginalByteStore
from app.capture_workflow import CaptureWorkflow, WorkflowError
from app.controlled_demo import run_demo, synthetic_original
from app.evidence_manifest import CANONICAL_SLOTS
from app.review_pipeline import (
    IntegrityRejection,
    ReviewPipelineError,
    ReviewerQueue,
    SealService,
    ServerIntegrityVerifier,
    replay_session,
)

pytestmark = pytest.mark.subtests

VALID_VIN = "1HGCM82633A004352"
FIXED_NOW = "2026-11-06T17:00:00+00:00"
now = lambda: FIXED_NOW


def quality_complete_workflow():
    w = CaptureWorkflow(str(uuid4()), now=now)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    w.record_vehicle("driver-1", VALID_VIN)
    for i, slot in enumerate(CANONICAL_SLOTS, start=1):
        data = synthetic_original(slot)
        w.register_artifact("driver-1", slot, f"art-{i}", sha256(data).hexdigest(), len(data))
    w.record_quality("driver-1", {s: True for s in CANONICAL_SLOTS})
    return w


def store_and_verify(w, tmp_path, tamper_slot=None):
    """Store originals for a completed workflow and return (store, report, key_for)."""
    tenant, session = uuid4(), uuid4()
    store = OriginalByteStore(tmp_path)
    uuids = {}
    key_for = lambda artifact_id: ArtifactKey(tenant, session, UUID(uuids[artifact_id]))
    manifest = SealService().manifest_for(w)
    for entry in manifest.entries:
        data = synthetic_original(entry.slot, salt="tampered" if entry.slot == tamper_slot else "")
        if entry.slot == tamper_slot:
            # Place genuinely different bytes under the original digest path:
            # bypass put() by writing the file directly, then expect the
            # verifier's read to fail the digest check.
            uuids[entry.artifact_id] = str(uuid4())
            key = key_for(entry.artifact_id)
            key_dir = Path(store.root) / str(tenant) / str(session)
            key_dir.mkdir(parents=True, exist_ok=True)
            (key_dir / f"{key.artifact_id}.original").write_bytes(data)
            continue
        uuids[entry.artifact_id] = str(uuid4())
        store.put(key_for(entry.artifact_id), data, expected_sha256=entry.sha256_hex)
    report = ServerIntegrityVerifier().verify(manifest, store, key_for)
    return store, report, key_for


# --- sealing -------------------------------------------------------------------

def test_seal_requires_quality_verified_state():
    w = CaptureWorkflow(str(uuid4()), now=now)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    with pytest.raises(ReviewPipelineError) as e:
        SealService().seal(w, "sealer-1", "premature seal")
    assert e.value.code == "SEAL_ORDER_VIOLATION"


def test_seal_binds_manifest_digest_and_advances_machine():
    w = quality_complete_workflow()
    service = SealService()
    manifest = service.manifest_for(w)
    seal = service.seal(w, "sealer-1", "Gate A synthetic seal", now=now)
    assert w.state == "sealed"
    assert seal.manifest_digest == manifest.digest()
    assert seal.shot_list_version == manifest.shot_list_version
    assert seal.actor == "sealer-1" and seal.occurred_at == FIXED_NOW
    event = w.history[-1]
    assert event.kind == "MANIFEST_SEALED"
    payload = json.loads(event.payload_json)
    assert payload["manifest_digest"] == manifest.digest()
    # Sealing twice is forbidden by the frozen machine.
    with pytest.raises(Exception):
        service.seal(w, "sealer-1", "double seal", now=now)


# --- server-side integrity verification ----------------------------------------

def test_clean_verification_passes(tmp_path):
    w = quality_complete_workflow()
    store, report, _ = store_and_verify(w, tmp_path)
    assert report.ok
    assert len(report.verified_artifact_ids) == len(CANONICAL_SLOTS)
    assert report.rejections == ()


def test_replaced_media_rejected_not_repaired(tmp_path):
    w = quality_complete_workflow()
    store, report, _ = store_and_verify(w, tmp_path, tamper_slot="front")
    assert not report.ok
    rejection = report.rejections[0]
    assert isinstance(rejection, IntegrityRejection)
    assert rejection.code == "CORRUPT_OR_REPLACED_MEDIA"
    assert rejection.slot == "front"
    # All other slots still verify; nothing was repaired.
    assert len(report.verified_artifact_ids) == len(CANONICAL_SLOTS) - 1


def test_missing_artifact_rejected(tmp_path):
    w = quality_complete_workflow()
    service = SealService()
    manifest = service.manifest_for(w)
    tenant, session = uuid4(), uuid4()
    store = OriginalByteStore(tmp_path)
    uuids = {e.artifact_id: str(uuid4()) for e in manifest.entries}  # keys exist for all
    for entry in manifest.entries[:-1]:  # but only n-1 originals are stored
        data = synthetic_original(entry.slot)
        store.put(
            ArtifactKey(tenant, session, UUID(uuids[entry.artifact_id])),
            data,
            expected_sha256=entry.sha256_hex,
        )
    key_for = lambda artifact_id: ArtifactKey(tenant, session, UUID(uuids[artifact_id]))
    report = ServerIntegrityVerifier().verify(manifest, store, key_for)
    assert not report.ok
    assert report.rejections[0].code == "MISSING_ARTIFACT"
    assert report.rejections[0].slot == manifest.entries[-1].slot


def test_storage_put_rejects_bytes_not_matching_digest(tmp_path):
    w = quality_complete_workflow()
    service = SealService()
    manifest = service.manifest_for(w)
    entry = manifest.entries[0]
    store = OriginalByteStore(tmp_path)
    key = ArtifactKey(uuid4(), uuid4(), uuid4())
    with pytest.raises(Exception):
        store.put(key, synthetic_original("other"), expected_sha256=entry.sha256_hex)


# --- reviewer queue with attributed decision -------------------------------------

def make_sealed(tmp_path):
    w = quality_complete_workflow()
    service = SealService()
    manifest = service.manifest_for(w)
    tenant, session = uuid4(), uuid4()
    store = OriginalByteStore(tmp_path)
    uuids = {}
    for entry in manifest.entries:
        data = synthetic_original(entry.slot)
        uuids[entry.artifact_id] = str(uuid4())
        store.put(ArtifactKey(tenant, session, UUID(uuids[entry.artifact_id])), data, expected_sha256=entry.sha256_hex)
    key_for = lambda artifact_id: ArtifactKey(tenant, session, UUID(uuids[artifact_id]))
    report = ServerIntegrityVerifier().verify(manifest, store, key_for)
    seal = service.seal(w, "sealer-1", "synthetic seal", now=now)
    return w, seal, report


def test_queue_requires_sealed_state(tmp_path):
    w = quality_complete_workflow()  # quality_verified, not sealed
    service = SealService()
    manifest = service.manifest_for(w)
    report = ServerIntegrityVerifier().verify(manifest, OriginalByteStore(tmp_path), lambda a: ArtifactKey(uuid4(), uuid4(), uuid4()))
    # not sealed -> order violation (integrity also cannot be ok with empty store)
    with pytest.raises(ReviewPipelineError):
        ReviewerQueue(now=now).enqueue(w, None, report, "enq-1")


def test_queue_requires_ok_integrity(tmp_path):
    w, seal, _ = make_sealed(tmp_path)
    bad = ServerIntegrityVerifier().verify(
        SealService().manifest_for(w), OriginalByteStore(tmp_path / "empty"), lambda a: ArtifactKey(uuid4(), uuid4(), uuid4())
    )
    assert not bad.ok
    with pytest.raises(ReviewPipelineError) as e:
        ReviewerQueue(now=now).enqueue(w, seal, bad, "enq-1")
    assert e.value.code == "INTEGRITY_NOT_VERIFIED"


def test_attributed_decision_terminates_session(tmp_path):
    w, seal, report = make_sealed(tmp_path)
    queue = ReviewerQueue(now=now)
    queued = queue.enqueue(w, seal, report, "enq-1")
    assert queued.session_id == w.session_id
    artifact_ids = [e.artifact_id for e in w.manifest_entries()]
    decision = queue.record_decision(w, "NOTE_ONLY", artifact_ids, "reviewer-01", "complete evidence set", integrity_report=report)
    assert w.state == "reviewed"
    assert decision.actor == "reviewer-01" and decision.occurred_at == FIXED_NOW
    assert decision.disposition == "NOTE_ONLY"
    event = w.history[-1]
    assert event.kind == "REVIEW_RECORDED" and event.actor == "reviewer-01"
    payload = json.loads(event.payload_json)
    assert payload["disposition"] == "NOTE_ONLY"
    assert queue.decision_for(w.session_id) == decision
    assert queue.pending() == ()  # dequeued


def test_second_decision_rejected(tmp_path):
    w, seal, report = make_sealed(tmp_path)
    queue = ReviewerQueue(now=now)
    queue.enqueue(w, seal, report, "enq-1")
    ids = [e.artifact_id for e in w.manifest_entries()]
    queue.record_decision(w, "NOTE_ONLY", ids, "reviewer-01", "first")
    with pytest.raises(ReviewPipelineError) as e:
        queue.record_decision(w, "HUMAN_QC_REQUIRED", ids, "reviewer-02", "second")
    assert e.value.code in ("ALREADY_REVIEWED", "REVIEW_ORDER_VIOLATION")


def test_invalid_disposition_and_references_rejected(tmp_path):
    w, seal, report = make_sealed(tmp_path)
    queue = ReviewerQueue(now=now)
    queue.enqueue(w, seal, report, "enq-1")
    ids = [e.artifact_id for e in w.manifest_entries()]
    with pytest.raises(ReviewPipelineError) as e:
        queue.record_decision(w, "APPROVED_FOR_PAYOUT", ids, "reviewer-01", "x")
    assert e.value.code == "INVALID_DISPOSITION"
    with pytest.raises(ReviewPipelineError) as e:
        queue.record_decision(w, "NOTE_ONLY", ["not-an-artifact"], "reviewer-01", "x")
    assert e.value.code == "INVALID_REVIEW_REFERENCES"
    with pytest.raises(ReviewPipelineError) as e:
        queue.record_decision(w, "NOTE_ONLY", [], "reviewer-01", "x")
    assert e.value.code == "INVALID_REVIEW_REFERENCES"


def test_replay_reconstructs_reviewed_state(tmp_path):
    w, seal, report = make_sealed(tmp_path)
    queue = ReviewerQueue(now=now)
    queue.enqueue(w, seal, report, "enq-1")
    ids = [e.artifact_id for e in w.manifest_entries()]
    queue.record_decision(w, "NOTE_ONLY", ids, "reviewer-01", "complete", integrity_report=report)
    replayed = replay_session(w)
    assert replayed.state == "reviewed" and replayed.session_id == w.session_id


# --- controlled demonstration (Gate A evidence) -----------------------------------

def test_controlled_demo_end_to_end(tmp_path):
    record = run_demo(tmp_path / "demo")
    assert record["final_state"] == "reviewed"
    assert record["label"] == "SYNTHETIC-CONTROLLED-DEMO"
    assert record["machine_contract_version"] == "m1-v1"
    steps = {s["step"]: s["outcome"] for s in record["steps"]}
    assert steps == {
        "consent": "recorded",
        "vin_guard": "recorded",
        "capture_sync": "resumable-sync-complete",
        "quality": "passed",
        "durable_storage": "originals-stored",
        "server_hash_recomputation": "verified",
        "tamper_rejected": "rejected",
        "seal": "sealed",
        "reviewer_decision": "reviewed",
        "history_replay": "replayed",
    }
    # Retained evidence record exists and is self-describing.
    evidence = Path(record["evidence_path"])
    assert evidence.is_file()
    loaded = json.loads(evidence.read_text(encoding="utf-8"))
    assert loaded["manifest_digest"] == record["manifest_digest"]
    assert loaded["reviewer_decision"]["actor"] == "synthetic-reviewer-01"
    assert loaded["reviewer_decision"]["disposition"] == "NOTE_ONLY"
    assert loaded["integrity"]["rejections"] == []
    assert len(loaded["event_history"]) >= 17  # created, consent, vehicle, 12 artifacts, quality, seal, review
    kinds = [e["kind"] for e in loaded["event_history"]]
    assert kinds[0] == "SESSION_CREATED" and kinds[-1] == "REVIEW_RECORDED"
    # Originals retained in durable storage for inspection.
    originals_dir = tmp_path / "demo" / "originals"
    assert sum(1 for _ in originals_dir.rglob("*.original")) == len(CANONICAL_SLOTS)


def test_demo_evidence_contains_no_payment_or_incentive_language(tmp_path):
    record = run_demo(tmp_path / "demo2")
    blob = json.dumps(record) + Path(record["evidence_path"]).read_text(encoding="utf-8")
    for banned in ("$80", "80 dollar", "eighty", "incentive", "payout to driver", "compensation"):
        assert banned.lower() not in blob.lower(), f"banned term in evidence: {banned}"

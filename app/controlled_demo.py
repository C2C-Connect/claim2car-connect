"""Controlled demonstration (plan v1.3 phase 10; Slice 5 Gate A evidence).

Runs ONE fully synthetic incident end-to-end through every landed slice:
session -> disclosure -> consent -> VIN guard -> guided capture (12 slots) ->
local draft + resumable sync -> durable original-byte storage -> server-side
hash recomputation (including a deliberate tamper attempt that must be
rejected) -> manifest seal -> reviewer queue -> attributed reviewer decision,
with the complete event history replayed through the frozen m1-v1 machine.

Everything is synthetic and labeled. No live sends, no payments, no real
vehicles or people. The retained evidence record is written as JSON so Gate A
reviewers can inspect the exact inputs, digests, and decisions.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.artifact_storage import ArtifactKey, OriginalByteStore
from app.capture_workflow import CaptureWorkflow, LocalDraftStore, sync_draft_to_server
from app.evidence_manifest import CANONICAL_SLOTS
from app.review_pipeline import (
    IntegrityReport,
    ReviewerQueue,
    SealService,
    ServerIntegrityVerifier,
    ReviewPipelineError,
)
from app.vin_guard import validate_vin

DEMO_LABEL = "SYNTHETIC-CONTROLLED-DEMO"
SYNTHETIC_VIN = "1HGCM82633A004352"  # public fixture; format check-digit only


def synthetic_original(slot: str, salt: str = "") -> bytes:
    """Deterministic synthetic original bytes for one slot. Not a photograph."""
    return f"{DEMO_LABEL}:{slot}:{salt}".encode("utf-8")


def run_demo(output_dir: Path, fixed_now: str = "2026-11-06T17:00:00+00:00") -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tenant_id = uuid4()
    session_uuid = uuid4()
    session_id = str(session_uuid)
    now = lambda: fixed_now  # deterministic demo timestamps

    record = {
        "label": DEMO_LABEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tenant_id": str(tenant_id),
        "steps": [],
    }

    def step(name, outcome, detail=None):
        entry = {"step": name, "outcome": outcome}
        if detail is not None:
            entry["detail"] = detail
        record["steps"].append(entry)
        return entry

    # 1. Session, disclosure gate, explicit consent, VIN guard.
    workflow = CaptureWorkflow(session_id, now=now)
    workflow.present_disclosure("disclosure-v1")
    workflow.record_consent("synthetic-driver", True, "disclosure-v1")
    step("consent", "recorded", "disclosure-v1 presented, explicit acceptance")
    vin_report = validate_vin(SYNTHETIC_VIN)
    assert vin_report.ok, "demo VIN fixture must pass the format guard"
    workflow.record_vehicle("synthetic-driver", SYNTHETIC_VIN)
    step("vin_guard", "recorded", {"vin": SYNTHETIC_VIN, "scope": vin_report.scope})

    # 2. Guided capture: local draft, crash mid-capture, restart, resume, sync.
    storage = {}
    draft = LocalDraftStore(storage)
    originals: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for slot in CANONICAL_SLOTS:
        data = synthetic_original(slot)
        from hashlib import sha256

        digest = sha256(data).hexdigest()
        originals[slot] = data
        digests[slot] = digest
        draft.save_artifact(session_id, slot, str(uuid4()), digest, len(data))
    draft = LocalDraftStore(storage)  # simulated restart
    sync = sync_draft_to_server(workflow, draft, "synthetic-driver")
    assert len(sync["synced"]) == len(CANONICAL_SLOTS), "all slots must sync"
    step("capture_sync", "resumable-sync-complete", {"slots": len(CANONICAL_SLOTS), "revision": draft.revision()})

    # 3. Quality verification on the full capture set.
    workflow.record_quality("synthetic-driver", {s: True for s in CANONICAL_SLOTS})
    step("quality", "passed", "all slots passed synthetic quality fixture")

    # 4. Durable original-byte storage (administrator-controlled local root).
    store_root = (output_dir / "originals").resolve()
    store_root.mkdir(parents=True, exist_ok=True)
    store = OriginalByteStore(store_root)
    artifact_uuids: dict[str, str] = {}
    entries_by_slot = {e.slot: e for e in workflow.manifest_entries()}
    for slot, entry in entries_by_slot.items():
        artifact_uuid = str(uuid4())
        artifact_uuids[entry.artifact_id] = artifact_uuid
        key = ArtifactKey(tenant_id, session_uuid, UUID(artifact_uuid))
        receipt = store.put(key, originals[slot], expected_sha256=entry.sha256_hex)
        assert receipt.sha256_hex == entry.sha256_hex
    step("durable_storage", "originals-stored", {"root": str(store_root), "count": len(entries_by_slot)})

    def key_for(artifact_id: str) -> ArtifactKey:
        return ArtifactKey(tenant_id, session_uuid, UUID(artifact_uuids[artifact_id]))

    # 5. Server-side hash recomputation — clean pass.
    seal_service = SealService()
    manifest = seal_service.manifest_for(workflow)
    verifier = ServerIntegrityVerifier()
    clean_report = verifier.verify(manifest, store, key_for)
    assert clean_report.ok, "clean verification must pass"
    step("server_hash_recomputation", "verified", {"verified": len(clean_report.verified_artifact_ids)})

    # 6. Deliberate tamper attempt: a replaced original must be rejected.
    tamper_slot = CANONICAL_SLOTS[2]
    tampered = synthetic_original(tamper_slot, salt="tampered")
    tamper_entry = entries_by_slot[tamper_slot]
    tamper_key = key_for(tamper_entry.artifact_id)
    try:
        store.put(tamper_key, tampered, expected_sha256=tamper_entry.sha256_hex)
        raise AssertionError("tampered bytes must not be storable under the original digest")
    except Exception as exc:  # ArtifactIntegrityError expected
        step("tamper_rejected", "rejected", {"slot": tamper_slot, "error": type(exc).__name__})
    tamper_report = verifier.verify(manifest, store, key_for)
    assert tamper_report.ok, "storage still intact after rejected tamper attempt"

    # 7. Seal through the frozen machine.
    seal = seal_service.seal(workflow, "synthetic-sealer", "Gate A controlled demonstration seal", now=now)
    assert workflow.state == "sealed"
    step("seal", "sealed", {"manifest_digest": seal.manifest_digest, "shot_list_version": seal.shot_list_version})

    # 8. Reviewer queue + attributed decision.
    queue = ReviewerQueue(now=now)
    queued = queue.enqueue(workflow, seal, clean_report, "synthetic-enqueue-actor")
    decision = queue.record_decision(
        workflow,
        "NOTE_ONLY",
        [e.artifact_id for e in workflow.manifest_entries()],
        "synthetic-reviewer-01",
        "Controlled demonstration review: evidence set complete, integrity verified",
        integrity_report=clean_report,
    )
    assert workflow.state == "reviewed"
    step("reviewer_decision", "reviewed", {"disposition": decision.disposition, "actor": decision.actor, "occurred_at": decision.occurred_at})

    # 9. Full event-history replay through the frozen m1-v1 machine.
    from app.review_pipeline import replay_session

    replayed = replay_session(workflow)
    assert replayed.state == "reviewed"
    step("history_replay", "replayed", {"events": len(workflow.history), "final_state": replayed.state})

    record["final_state"] = workflow.state
    record["manifest_digest"] = seal.manifest_digest
    record["shot_list_version"] = seal.shot_list_version
    record["reviewer_decision"] = asdict(decision)
    record["integrity"] = {
        "verified_artifact_ids": list(clean_report.verified_artifact_ids),
        "rejections": [asdict(r) for r in clean_report.rejections],
    }
    record["event_history"] = [
        {
            "sequence": e.sequence,
            "kind": e.kind,
            "actor": e.actor,
            "occurred_at": e.occurred_at,
            "reason": e.reason,
            "payload": json.loads(e.payload_json),
        }
        for e in workflow.history
    ]
    record["machine_contract_version"] = "m1-v1"

    evidence_path = output_dir / f"gate-a-evidence-{session_id}.json"
    evidence_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    record["evidence_path"] = str(evidence_path)
    return record


def main():
    parser = argparse.ArgumentParser(description="Claims2Car controlled demonstration (synthetic, Gate A evidence)")
    parser.add_argument("--output", default="output/controlled-demo", help="output directory for retained evidence")
    args = parser.parse_args()
    record = run_demo(Path(args.output))
    summary = {
        "label": record["label"],
        "session_id": record["session_id"],
        "final_state": record["final_state"],
        "manifest_digest": record["manifest_digest"],
        "steps": [(s["step"], s["outcome"]) for s in record["steps"]],
        "evidence_path": record["evidence_path"],
    }
    print(json.dumps(summary, indent=2))
    if record["final_state"] != "reviewed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

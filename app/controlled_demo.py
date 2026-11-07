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
from app.carrier_messages import ATTACHMENT, ASSIGNMENT, DISPOSITION, build_attachment, build_assignment, build_disposition
from app.dispatch_routing import AcceptanceRecord, DispatchRoutingService, InMemoryRoutingEngine, load_road_network
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

    # 0. Transactional outbox attached: every applied event mirrors a message.
    from app.outbox import OutboxRelay, OutboxStore

    outbox = OutboxStore()
    carrier_messages = []

    # 1. Session, disclosure gate, explicit consent, VIN guard.
    workflow = CaptureWorkflow(session_id, now=now, outbox=outbox)
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

    # 3. Pre-inference quality gate (Slice 8 InputGuard pattern) + recorded verdicts.
    from app.quality_gate import HeuristicQualityGate

    def synthetic_pixels(slot: str, size: int = 24) -> list[list[int]]:
        """Deterministic synthetic grayscale fixture per slot. Not a photograph."""
        seed = sum(slot.encode("utf-8")) % 97
        return [[((x * 31 + y * 17 + seed) % 200) + 20 for x in range(size)] for y in range(size)]

    gate = HeuristicQualityGate()
    gate_verdicts = gate.evaluate_all(
        {s: (f"demo-{s}", synthetic_pixels(s)) for s in CANONICAL_SLOTS}
    )
    assert all(v.passed for v in gate_verdicts), "synthetic fixtures must pass the reference gate"
    step("quality_gate", "evaluated", {
        "gate_version": gate.gate_version,
        "checks": sorted({c.name for v in gate_verdicts for c in v.checks}),
        "verdicts": HeuristicQualityGate.passed_verdicts(gate_verdicts),
    })
    workflow.record_quality(
        "synthetic-driver",
        HeuristicQualityGate.passed_verdicts(gate_verdicts),
        gate=HeuristicQualityGate.gate_metadata(gate_verdicts),
    )
    step("quality", "passed", "all slots passed the on-device quality gate (recorded with gate metadata)")

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

    # 8a. Confidence triage (Slice 9): the recorded gate margins order the
    # human review queue. Ordering only — every session stays human-reviewed.
    from app.learning_loop import DriftMonitor, SessionConfidenceScorer, TriagePolicy

    triage = SessionConfidenceScorer().score_workflow(workflow)
    queue_band = TriagePolicy().route(triage)
    step("review_triage", "routed", {
        "confidence": triage.confidence,
        "band": queue_band,
        "weakest_slot": triage.weakest_slot,
        "weakest_check": triage.weakest_check,
        "policy_version": triage.policy_version,
    })
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

    # 8b. Reviewer-decision dataset row (Slice 8: labeled data from the
    # attributed decision — the seed of the self-learning loop).
    from app.reviewer_dataset import ReviewerDataset, ReviewerDatasetBuilder

    dataset_row = ReviewerDatasetBuilder(decision).build(workflow, seal)
    dataset = ReviewerDataset([dataset_row])
    (output_dir / "reviewer-dataset.json").write_text(
        json.dumps(dataset.export(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    step("reviewer_dataset", "labeled", {
        "dataset_version": dataset_row.schema_version,
        "row_count": len(dataset),
        "slots": len(dataset_row.slots),
        "vehicle_reference": dataset_row.vehicle_reference,
    })

    # 8c. Drift monitoring (Slice 9): the quality gate is the predictor, the
    # reviewer disposition the outcome. The monitor measures agreement and
    # flags drift for humans; it never adjusts anything itself.
    drift = DriftMonitor()
    drift.observe(True, decision.disposition == "NOTE_ONLY")
    drift_report = drift.report()
    step("drift_monitor", "measured", {
        "observations": drift_report["observations"],
        "baseline_agreement": drift_report["baseline_agreement"],
        "drift_flagged": drift_report["drift_flagged"],
        "monitor_version": drift_report["monitor_version"],
    })

    # 9. Full event-history replay through the frozen m1-v1 machine.
    from app.review_pipeline import replay_session

    replayed = replay_session(workflow)
    assert replayed.state == "reviewed"
    step("history_replay", "replayed", {"events": len(workflow.history), "final_state": replayed.state})

    # 10. Acceptance-gated tow dispatch + navigation handoff (product contract
    # §7: acceptance precedes tow dispatch — enforced by DispatchRoutingService).
    network = load_road_network()
    acceptance = AcceptanceRecord(
        party_type="shop",
        party_id="synthetic-shop-001",
        accepted_at=fixed_now,
        location_label="shop-a",
    )
    dispatch_service = DispatchRoutingService(InMemoryRoutingEngine())
    plan = dispatch_service.plan(network, acceptance, "operator-depot", "incident-scene", "google")
    step(
        "tow_dispatch",
        "planned",
        {
            "acceptance_party": "synthetic-shop-001",
            "leg_1_minutes": plan.leg_to_incident.total_cost_minutes,
            "leg_2_minutes": plan.leg_to_receiving_party.total_cost_minutes,
            "total_minutes": plan.total_cost_minutes,
            "navigation_handoffs": [h.uri for h in plan.handoffs],
        },
    )

    # 11. Carrier messages (CIECA-aligned model, D-11 candidate spec).
    attachment_message = build_attachment(workflow, seal, created_at=fixed_now)
    disposition_message = build_disposition(workflow, decision, created_at=fixed_now)
    assignment_message = build_assignment(workflow, plan, created_at=fixed_now)
    carrier_messages.extend([attachment_message, disposition_message, assignment_message])
    step(
        "carrier_messages",
        "formatted",
        {
            "attachment_digest": attachment_message.payload["manifest_digest"],
            "disposition": disposition_message.payload["disposition"],
            "assignment_party": assignment_message.payload["party_type"],
        },
    )

    # 12. Outbox relay: internal carrier formatter consumer delivers
    # exactly-once per consumer; messages formatted, nothing sent live.
    relay = OutboxRelay(outbox)
    delivered_kinds = []

    def carrier_formatter(message):
        delivered_kinds.append(message.kind)
        if message.kind == "MANIFEST_SEALED":
            carrier_messages.append(build_attachment(workflow, seal, created_at=fixed_now))
        elif message.kind == "REVIEW_RECORDED":
            carrier_messages.append(build_disposition(workflow, decision, created_at=fixed_now))

    relay.register_consumer("MANIFEST_SEALED", carrier_formatter)
    relay.register_consumer("REVIEW_RECORDED", carrier_formatter)
    drain = relay.drain()
    assert set(delivered_kinds) >= {"MANIFEST_SEALED", "REVIEW_RECORDED"}
    undelivered = len(outbox.pending())
    step(
        "outbox_relay",
        "drained",
        {
            "delivered_count": len(drain.delivered),
            "pending_without_consumer": undelivered,  # events with no consumer stay pending, never lost
        },
    )

    record["final_state"] = workflow.state
    record["manifest_digest"] = seal.manifest_digest
    record["shot_list_version"] = seal.shot_list_version
    record["reviewer_decision"] = asdict(decision)
    record["dispatch_plan"] = {
        "acceptance": asdict(plan.acceptance),
        "leg_to_incident": list(plan.leg_to_incident.node_path),
        "leg_to_receiving_party": list(plan.leg_to_receiving_party.node_path),
        "total_cost_minutes": plan.total_cost_minutes,
        "navigation_handoffs": [{"provider": h.provider, "uri": h.uri} for h in plan.handoffs],
    }
    record["carrier_messages"] = [
        {"message_type": m.message_type, "message_id": m.message_id, "payload": m.payload}
        for m in carrier_messages
    ]
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

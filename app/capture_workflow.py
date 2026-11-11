"""M1 capture-to-intake workflow (plan v1.3 phases 5-6; five-slice Slice 4).

Vertical slice wiring the frozen m1-v1 session state machine (Slice 2) into a
runnable capture flow: versioned disclosure gate -> explicit consent record ->
VIN guard with uncertainty handling -> guided capture against the frozen shot
contract -> per-slot quality verification -> local draft persistence with
resumable, idempotent sync.

Scope honesty (plan v1.3 §6.1/§6.2): this module processes synthetic events
and metadata only. It stores no images, performs no vehicle decoding, makes
no authenticity or ownership claims, and does not seal or review — sealing
and review are Slice 5. Original bytes live client-side; the server tracks
slot -> artifact_id -> sha256 integrity metadata.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from app.domain_events import DomainEvent, canonical_event_payload
from app.evidence_manifest import LEGACY_CANONICAL_SLOTS
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, require_implemented_protocol
from app.telemetry import workflow_span
from app.vin_guard import validate_vin
from contracts.m1_state_machine import M1SessionMachine

REQUIRED_SLOTS = tuple(LEGACY_CANONICAL_SLOTS)  # legacy 12-v1 compatibility alias
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
DISCLOSURE_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "disclosure-v1.json"
DISCLOSURE_SCHEMA_VERSION = "0.1"


class WorkflowError(ValueError):
    """Stable-code workflow violations. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def load_disclosure_contract():
    value = json.loads(DISCLOSURE_CONTRACT_PATH.read_text(encoding="utf-8"))
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "disclosure_version", "requires_explicit_acceptance", "sections"}
        or value["schema_version"] != DISCLOSURE_SCHEMA_VERSION
        or not isinstance(value["disclosure_version"], str)
        or not value["disclosure_version"].strip()
        or value["requires_explicit_acceptance"] is not True
        or type(value["sections"]) is not list
        or not value["sections"]
        or not all(isinstance(s, str) and s.strip() for s in value["sections"])
    ):
        raise ValueError("INVALID_DISCLOSURE_CONTRACT")
    return value["disclosure_version"], tuple(value["sections"])


@dataclass(frozen=True)
class ArtifactEntry:
    slot: str
    artifact_id: str
    sha256_hex: str
    byte_length: int
    registered_at: str


@dataclass(frozen=True)
class UncertaintyRecord:
    code: str
    reason: str
    recapture_required: bool
    recorded_at: str


class CaptureWorkflow:
    """Server-side ordering authority for one capture session (M1 phases 5-6).

    All state changes flow through the frozen m1-v1 machine; this class adds
    the disclosure gate, VIN uncertainty handling, shot-contract validation,
    quality gating, and idempotent sync semantics on top.
    """

    def __init__(self, session_id: str, now: Optional[Callable[[], str]] = None, outbox=None, protocol_version: str = DEFAULT_CAPTURE_PROTOCOL):
        if not isinstance(session_id, str) or not session_id.strip():
            raise WorkflowError("INVALID_SESSION")
        self.session_id = session_id
        self.protocol = require_implemented_protocol(protocol_version)
        self.protocol_version = self.protocol.version
        self.required_slots = self.protocol.slots
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat())
        self.outbox = outbox  # optional app.outbox.OutboxStore; set via attach_outbox
        self.machine = M1SessionMachine(session_id)
        self.disclosure_version, _ = load_disclosure_contract()
        self._presented_disclosure: Optional[str] = None
        self._artifacts: dict[str, ArtifactEntry] = {}
        self._artifact_ids: set[str] = set()
        self._retakes: list[ArtifactEntry] = []
        self._synced: set[str] = set()
        self.uncertainties: list[UncertaintyRecord] = []
        self._emit("SESSION_CREATED", "system", "capture session initialized", {"session_id": session_id, "capture_protocol_version": self.protocol_version})

    # --- event plumbing -------------------------------------------------

    def _emit(self, kind: str, actor: str, reason: str, payload: dict) -> None:
        event = DomainEvent(
            session_id=self.session_id,
            event_id=str(uuid4()),
            sequence=self.machine.history[-1].sequence + 1 if self.machine.history else 1,
            kind=kind,
            actor=actor,
            occurred_at=self._now(),
            reason=reason,
            payload_json=canonical_event_payload(payload),
        )
        with workflow_span("capture.emit", kind=kind, session_id=self.session_id):
            self.machine.apply(event)
        # Transactional outbox pairing: the message is recorded only after the
        # state machine accepted the event — a rejected transition never
        # produces an outbound message.
        if self.outbox is not None:
            self.outbox.append_for_event(event)

    def mirror_outbox(self, event) -> None:
        """Mirror an externally applied event (seal, review) into the outbox.

        Any code path that applies a DomainEvent to this workflow's machine
        must call this, keeping the transactional pairing complete."""
        if self.outbox is not None:
            self.outbox.append_for_event(event)

    @property
    def state(self):
        return self.machine.state

    @property
    def history(self):
        return self.machine.history

    def _require_state(self, *states):
        if self.state not in states:
            raise WorkflowError("CAPTURE_ORDER_VIOLATION", f"state={self.state}")

    # --- disclosure gate -------------------------------------------------

    def present_disclosure(self, disclosure_version: str) -> None:
        """Record that the current disclosure was shown to the participant."""
        if not isinstance(disclosure_version, str) or disclosure_version != self.disclosure_version:
            raise WorkflowError("DISCLOSURE_VERSION_MISMATCH", f"expected={self.disclosure_version}")
        if self.state != "initialized":
            raise WorkflowError("CAPTURE_ORDER_VIOLATION", f"state={self.state}")
        self._presented_disclosure = disclosure_version

    # --- consent ----------------------------------------------------------

    def record_consent(self, actor: str, accepted: bool, disclosure_version: str) -> None:
        if not isinstance(actor, str) or not actor.strip():
            raise WorkflowError("INVALID_ACTOR")
        if self._presented_disclosure is None:
            raise WorkflowError("DISCLOSURE_NOT_PRESENTED")
        if disclosure_version != self._presented_disclosure:
            raise WorkflowError("DISCLOSURE_VERSION_MISMATCH")
        if accepted is not True:
            raise WorkflowError("CONSENT_NOT_EXPLICIT")
        self._require_state("initialized")
        self._emit(
            "CONSENT_RECORDED",
            actor,
            "affirmative consent after disclosure",
            {"disclosure_version": disclosure_version, "accepted": True},
        )

    # --- vehicle identification -------------------------------------------

    def record_vehicle(self, actor: str, vin_input) -> None:
        """VIN guard with uncertainty handling: failures are recorded and
        require recapture; nothing is repaired. A valid VIN may be corrected
        (re-recorded) before capture begins, per m1-v1 retake semantics."""
        if not isinstance(actor, str) or not actor.strip():
            raise WorkflowError("INVALID_ACTOR")
        self._require_state("consented", "vehicle_identified")
        report = validate_vin(vin_input)
        if not report.ok:
            self.uncertainties.append(
                UncertaintyRecord(
                    code=report.uncertainty_code or "VIN_UNCERTAIN",
                    reason=report.reason or "UNKNOWN",
                    recapture_required=True,
                    recorded_at=self._now(),
                )
            )
            raise WorkflowError("VIN_UNCERTAIN", report.reason or "UNKNOWN")
        self._emit(
            "VEHICLE_RECORDED",
            actor,
            "VIN format and check digit verified",
            {
                "vin": report.vin,
                "raw_input_retained": report.raw_vin,
                "normalization_changed": report.normalization_changed,
                "scope": report.scope,
            },
        )

    # --- guided capture ----------------------------------------------------

    def register_artifact(self, actor: str, slot: str, artifact_id: str, sha256_hex: str, byte_length: int) -> dict:
        """Register (or idempotently re-sync) one original's integrity metadata."""
        if not isinstance(actor, str) or not actor.strip():
            raise WorkflowError("INVALID_ACTOR")
        if slot not in self.required_slots:
            raise WorkflowError("UNKNOWN_SLOT", slot)
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise WorkflowError("INVALID_ARTIFACT_ID")
        if not isinstance(sha256_hex, str) or SHA256_PATTERN.fullmatch(sha256_hex) is None:
            raise WorkflowError("INVALID_DIGEST")
        if type(byte_length) is not int or byte_length <= 0:
            raise WorkflowError("INVALID_BYTE_LENGTH")
        if artifact_id in self._artifact_ids:
            current = self._artifacts.get(slot)
            if current is not None and current.artifact_id == artifact_id:
                # Idempotent re-sync: retrying the same original for the same
                # slot is a no-op. The same id for a different slot is a conflict.
                return {"status": "already_registered", "artifact_id": artifact_id, "slot": slot}
            raise WorkflowError("DUPLICATE_ARTIFACT_ID", artifact_id)
        self._require_state("vehicle_identified", "evidence_captured")
        previous = self._artifacts.get(slot)
        payload = {
            "slot": slot,
            "artifact_id": artifact_id,
            "sha256_hex": sha256_hex,
            "byte_length": byte_length,
        }
        if previous is not None:
            # Traceable retake: the superseded original stays in history.
            payload["supersedes_artifact_id"] = previous.artifact_id
        self._emit("ARTIFACT_REGISTERED", actor, f"original registered for slot {slot}", payload)
        if previous is not None:
            self._retakes.append(previous)
        entry = ArtifactEntry(slot, artifact_id, sha256_hex, byte_length, self._now())
        self._artifacts[slot] = entry
        self._artifact_ids.add(artifact_id)
        self._synced.add(artifact_id)
        return {"status": "registered", "artifact_id": artifact_id, "slot": slot}

    def captured_slots(self):
        return tuple(sorted(self._artifacts))

    def pending_slots(self):
        return tuple(s for s in self.required_slots if s not in self._artifacts)

    # --- quality -----------------------------------------------------------

    def record_quality(self, actor: str, verdicts: dict, gate: dict | None = None) -> dict:
        if not isinstance(actor, str) or not actor.strip():
            raise WorkflowError("INVALID_ACTOR")
        if self.pending_slots():
            raise WorkflowError("CAPTURE_SET_INCOMPLETE", ",".join(self.pending_slots()))
        if type(verdicts) is not dict or set(verdicts) != set(self.required_slots):
            raise WorkflowError("QUALITY_VERDICTS_INCOMPLETE", "one verdict per required slot")
        if not all(v is True or v is False for v in verdicts.values()):
            raise WorkflowError("INVALID_QUALITY_VERDICT")
        if gate is not None and (type(gate) is not dict or not isinstance(gate.get("gate_version"), str)
                                 or not gate["gate_version"].strip()):
            raise WorkflowError("INVALID_GATE_METADATA")
        failed = sorted(s for s, v in verdicts.items() if v is not True)
        if failed:
            raise WorkflowError("QUALITY_GATE_FAILED", ",".join(failed))
        self._require_state("evidence_captured")
        payload = {"verdicts": {s: True for s in self.required_slots}, "failed_slots": []}
        if gate is not None:
            payload["gate"] = gate
        self._emit(
            "QUALITY_RECORDED",
            actor,
            "all slots passed quality verification",
            payload,
        )
        return {"passed": True, "state": self.state}

    # --- integrity summary (for Slice 5 sealing) ----------------------------

    def manifest_entries(self):
        if self.pending_slots():
            raise WorkflowError("CAPTURE_SET_INCOMPLETE")
        return tuple(self._artifacts[s] for s in self.required_slots)


class LocalDraftStore:
    """Client-side draft persistence + resumable sync bookkeeping (phase 6).

    The storage argument is an injectable mutable mapping (persisted JSON in
    production, plain dict in tests) so restart/recovery is exercised by
    constructing a second store over the same storage.
    """

    def __init__(self, storage, protocol_version: str = DEFAULT_CAPTURE_PROTOCOL):
        self.storage = storage
        self.protocol = require_implemented_protocol(protocol_version)
        self.protocol_version = self.protocol.version

    def _load(self):
        return self.storage.get("draft", {"revision": 0, "entries": {}, "synced": []})

    def _save(self, data):
        self.storage["draft"] = data

    def save_artifact(self, session_id: str, slot: str, artifact_id: str, sha256_hex: str, byte_length: int) -> int:
        if not isinstance(session_id, str) or not session_id.strip():
            raise WorkflowError("INVALID_SESSION")
        if slot not in self.protocol.slots:
            raise WorkflowError("UNKNOWN_SLOT", slot)
        data = self._load()
        entries = data["entries"]
        if slot in entries:
            # Local retake replaces the slot's pending original; the replaced
            # entry is dropped from the local queue (server keeps its history).
            del entries[slot]
        entries[slot] = {
            "artifact_id": artifact_id,
            "sha256_hex": sha256_hex,
            "byte_length": byte_length,
        }
        data["revision"] += 1
        data["session_id"] = session_id
        data["capture_protocol_version"] = self.protocol_version
        self._save(data)
        return data["revision"]

    def revision(self) -> int:
        return self._load()["revision"]

    def pending_sync(self):
        data = self._load()
        synced = set(data["synced"])
        return [
            {"slot": slot, **entry}
            for slot, entry in data["entries"].items()
            if entry["artifact_id"] not in synced
        ]

    def mark_synced(self, artifact_id: str) -> None:
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise WorkflowError("INVALID_ARTIFACT_ID")
        data = self._load()
        if artifact_id not in {e["artifact_id"] for e in data["entries"].values()}:
            raise WorkflowError("UNKNOWN_ARTIFACT", artifact_id)
        if artifact_id not in data["synced"]:
            data["synced"].append(artifact_id)
            self._save(data)

    def resume(self):
        """Restart recovery snapshot: what is captured and what still needs sync."""
        data = self._load()
        return {
            "session_id": data.get("session_id"),
            "capture_protocol_version": data.get("capture_protocol_version", self.protocol_version),
            "revision": data["revision"],
            "captured_slots": sorted(data["entries"]),
            "pending_sync_count": len(self.pending_sync()),
        }


def sync_draft_to_server(workflow: CaptureWorkflow, draft: LocalDraftStore, actor: str) -> dict:
    """Resumable, idempotent sync: push pending originals one at a time.

    Re-running after an interruption resumes from the first unsynced entry;
    re-syncing an already-registered artifact is a no-op (idempotency), and a
    conflicting replacement for an already-synced slot is rejected.
    """
    if not isinstance(workflow, CaptureWorkflow) or not isinstance(draft, LocalDraftStore):
        raise WorkflowError("INVALID_SYNC_TARGET")
    results = []
    with workflow_span("capture.sync", session_id=workflow.session_id):
        if workflow.protocol_version != draft.protocol_version:
        raise WorkflowError("CAPTURE_PROTOCOL_VERSION_MISMATCH")
    for entry in draft.pending_sync():
            outcome = workflow.register_artifact(
                actor,
                entry["slot"],
                entry["artifact_id"],
                entry["sha256_hex"],
                entry["byte_length"],
            )
            draft.mark_synced(entry["artifact_id"])
            results.append({"slot": entry["slot"], **outcome})
    return {"synced": results, "pending": draft.pending_sync()}


def sha256_hex_of(data: bytes) -> str:
    if type(data) is not bytes or not data:
        raise WorkflowError("INVALID_ORIGINAL_BYTES")
    return sha256(data).hexdigest()

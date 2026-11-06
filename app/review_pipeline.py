"""Seal, server-side integrity verification, and reviewer decision (Slice 5).

Plan v1.3 phases 7-8 and 10: after a capture set passes quality (Slice 4),
this module (1) seals the manifest through the frozen m1-v1 machine, (2)
re-computes every content hash server-side from the durable original-byte
store — corrupt or replaced media is rejected, never repaired — and (3) runs
a reviewer queue where each decision is attributed to an authenticated actor
with a timestamp and reason, terminating the session.

Scope honesty: synthetic events and local durable storage only. No notary,
no post-quantum signing (SPEC_DECISIONS pending), no live distribution, no
payout logic. "Sealed" here means manifest-digest binding under the frozen
state machine — durable trusted sealing remains a separately reviewed
capability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID, uuid4

from app.artifact_storage import (
    ArtifactIntegrityError,
    ArtifactKey,
    ArtifactNotFound,
    ArtifactStorageUnavailable,
    OriginalByteStore,
)
from app.capture_workflow import ArtifactEntry, CaptureWorkflow, WorkflowError
from app.domain_events import DomainEvent
from app.evidence_manifest import Manifest, ManifestEntry, build_manifest
from contracts.m1_state_machine import M1SessionMachine

REVIEW_DISPOSITIONS = frozenset({"NOTE_ONLY", "HUMAN_QC_REQUIRED"})


class ReviewPipelineError(ValueError):
    """Stable-code pipeline violations. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# --- sealing (phase 8) --------------------------------------------------------

@dataclass(frozen=True)
class SealRecord:
    session_id: str
    manifest_digest: str
    shot_list_version: str
    event_id: str
    sequence: int
    actor: str
    occurred_at: str
    reason: str


class SealService:
    """Seals a quality-verified capture set into the frozen m1-v1 machine."""

    def seal(self, workflow: CaptureWorkflow, actor: str, reason: str, now: Optional[Callable[[], str]] = None) -> SealRecord:
        if not isinstance(workflow, CaptureWorkflow):
            raise ReviewPipelineError("INVALID_SESSION")
        if not isinstance(actor, str) or not actor.strip():
            raise ReviewPipelineError("INVALID_ACTOR")
        if not isinstance(reason, str) or not reason.strip():
            raise ReviewPipelineError("INVALID_REASON")
        if workflow.state != "quality_verified":
            raise ReviewPipelineError("SEAL_ORDER_VIOLATION", f"state={workflow.state}")
        try:
            manifest = self.manifest_for(workflow)
        except WorkflowError as exc:
            raise ReviewPipelineError(exc.code, exc.detail) from None
        occurred_at = (now or _now_iso)()
        event = DomainEvent(
            session_id=workflow.session_id,
            event_id=str(uuid4()),
            sequence=workflow.history[-1].sequence + 1,
            kind="MANIFEST_SEALED",
            actor=actor,
            occurred_at=occurred_at,
            reason=reason,
            payload_json=json.dumps(
                {
                    "schema_version": "0.1",
                    "shot_list_version": manifest.shot_list_version,
                    "manifest_digest": manifest.digest(),
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
        workflow.machine.apply(event)
        return SealRecord(
            session_id=workflow.session_id,
            manifest_digest=manifest.digest(),
            shot_list_version=manifest.shot_list_version,
            event_id=event.event_id,
            sequence=event.sequence,
            actor=actor,
            occurred_at=occurred_at,
            reason=reason,
        )

    def manifest_for(self, workflow: CaptureWorkflow) -> Manifest:
        entries = workflow.manifest_entries()
        return build_manifest(
            workflow.session_id,
            tuple(ManifestEntry(e.artifact_id, e.slot, e.sha256_hex) for e in entries),
        )


# --- server-side integrity verification (phase 8) -------------------------------

@dataclass(frozen=True)
class IntegrityRejection:
    artifact_id: str
    slot: str
    code: str  # MISSING_ARTIFACT | CORRUPT_OR_REPLACED_MEDIA | STORAGE_UNAVAILABLE
    detail: str


@dataclass(frozen=True)
class IntegrityReport:
    session_id: str
    manifest_digest: str
    verified_artifact_ids: tuple[str, ...]
    rejections: tuple[IntegrityRejection, ...]

    @property
    def ok(self) -> bool:
        return not self.rejections


class ServerIntegrityVerifier:
    """Re-computes content hashes from the durable original-byte store.

    The manifest digest binds slot -> artifact_id -> sha256; this verifier
    proves those digests still match the stored originals. Tampered, replaced,
    or missing media is rejected with a stable code — nothing is repaired.
    """

    def verify(
        self,
        manifest: Manifest,
        store: OriginalByteStore,
        key_for: Callable[[str], ArtifactKey],
    ) -> IntegrityReport:
        if not isinstance(manifest, Manifest) or not isinstance(store, OriginalByteStore):
            raise ReviewPipelineError("INVALID_VERIFICATION_INPUT")
        verified = []
        rejections = []
        for entry in manifest.entries:
            try:
                key = key_for(entry.artifact_id)
                stored = store.get(key, expected_sha256=entry.sha256_hex)
                if not stored:
                    raise ArtifactIntegrityError("INVALID_STORED_ARTIFACT")
                verified.append(entry.artifact_id)
            except ArtifactNotFound:
                rejections.append(IntegrityRejection(entry.artifact_id, entry.slot, "MISSING_ARTIFACT", "original not found in durable store"))
            except ArtifactIntegrityError as exc:
                rejections.append(IntegrityRejection(entry.artifact_id, entry.slot, "CORRUPT_OR_REPLACED_MEDIA", str(exc)))
            except ArtifactStorageUnavailable as exc:
                rejections.append(IntegrityRejection(entry.artifact_id, entry.slot, "STORAGE_UNAVAILABLE", str(exc)))
        return IntegrityReport(
            session_id=manifest.session_id,
            manifest_digest=manifest.digest(),
            verified_artifact_ids=tuple(sorted(verified)),
            rejections=tuple(rejections),
        )


# --- reviewer queue with attributed decision (phase 10) --------------------------

@dataclass(frozen=True)
class QueuedReview:
    session_id: str
    manifest_digest: str
    integrity_report: IntegrityReport
    enqueued_at: str
    actor: str


@dataclass(frozen=True)
class ReviewDecisionRecord:
    session_id: str
    disposition: str
    artifact_ids: tuple[str, ...]
    actor: str
    occurred_at: str
    reason: str
    event_id: str
    sequence: int


class ReviewerQueue:
    """Sealed, integrity-verified sessions await an attributed human decision."""

    def __init__(self, now: Optional[Callable[[], str]] = None):
        self._queue: list[QueuedReview] = []
        self._decisions: dict[str, ReviewDecisionRecord] = {}
        self._now = now or _now_iso

    def enqueue(self, workflow: CaptureWorkflow, seal: SealRecord, integrity_report: IntegrityReport, actor: str) -> QueuedReview:
        if not isinstance(workflow, CaptureWorkflow) or not isinstance(seal, SealRecord):
            raise ReviewPipelineError("INVALID_QUEUE_INPUT")
        if not isinstance(actor, str) or not actor.strip():
            raise ReviewPipelineError("INVALID_ACTOR")
        if workflow.state != "sealed":
            raise ReviewPipelineError("QUEUE_ORDER_VIOLATION", f"state={workflow.state}")
        if seal.session_id != workflow.session_id:
            raise ReviewPipelineError("SEAL_SESSION_MISMATCH")
        if not isinstance(integrity_report, IntegrityReport) or not integrity_report.ok:
            raise ReviewPipelineError("INTEGRITY_NOT_VERIFIED", ",".join(r.code for r in integrity_report.rejections))
        if workflow.session_id in self._decisions:
            raise ReviewPipelineError("ALREADY_REVIEWED")
        queued = QueuedReview(workflow.session_id, seal.manifest_digest, integrity_report, self._now(), actor)
        self._queue.append(queued)
        return queued

    def pending(self):
        return tuple(self._queue)

    def record_decision(
        self,
        workflow: CaptureWorkflow,
        disposition: str,
        artifact_ids,
        actor: str,
        reason: str,
        integrity_report: Optional[IntegrityReport] = None,
    ) -> ReviewDecisionRecord:
        if not isinstance(workflow, CaptureWorkflow):
            raise ReviewPipelineError("INVALID_SESSION")
        if disposition not in REVIEW_DISPOSITIONS:
            raise ReviewPipelineError("INVALID_DISPOSITION", disposition)
        if not isinstance(actor, str) or not actor.strip():
            raise ReviewPipelineError("INVALID_ACTOR")
        if not isinstance(reason, str) or not reason.strip():
            raise ReviewPipelineError("INVALID_REASON")
        if workflow.state != "sealed":
            raise ReviewPipelineError("REVIEW_ORDER_VIOLATION", f"state={workflow.state}")
        if workflow.session_id in self._decisions:
            raise ReviewPipelineError("ALREADY_REVIEWED")
        known = {e.artifact_id for e in workflow.manifest_entries()}
        if (not isinstance(artifact_ids, (list, tuple))
                or not artifact_ids
                or any(a not in known for a in artifact_ids)
                or len(set(artifact_ids)) != len(artifact_ids)):
            raise ReviewPipelineError("INVALID_REVIEW_REFERENCES")
        if integrity_report is not None:
            if not isinstance(integrity_report, IntegrityReport) or not integrity_report.ok:
                raise ReviewPipelineError("INTEGRITY_NOT_VERIFIED")
        occurred_at = self._now()
        event = DomainEvent(
            session_id=workflow.session_id,
            event_id=str(uuid4()),
            sequence=workflow.history[-1].sequence + 1,
            kind="REVIEW_RECORDED",
            actor=actor,
            occurred_at=occurred_at,
            reason=reason,
            payload_json=json.dumps(
                {"disposition": disposition, "artifact_ids": list(artifact_ids)},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
        workflow.machine.apply(event)
        record = ReviewDecisionRecord(
            session_id=workflow.session_id,
            disposition=disposition,
            artifact_ids=tuple(artifact_ids),
            actor=actor,
            occurred_at=occurred_at,
            reason=reason,
            event_id=event.event_id,
            sequence=event.sequence,
        )
        self._decisions[workflow.session_id] = record
        self._queue = [q for q in self._queue if q.session_id != workflow.session_id]
        return record

    def decision_for(self, session_id: str) -> Optional[ReviewDecisionRecord]:
        return self._decisions.get(session_id)


# --- reconstruction helper ---------------------------------------------------

def replay_session(workflow: CaptureWorkflow) -> M1SessionMachine:
    """Rebuild final state from the retained event history (restart recovery)."""
    return M1SessionMachine.reconstruct(workflow.session_id, workflow.history)

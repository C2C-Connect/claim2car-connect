"""Reviewer-decision dataset schema — the seed of the self-learning loop (Slice 8).

Tier 2 item 7 of the recalibration brief: attributed reviewer decisions
become labeled data. This module defines the versioned row contract
(``reviewer-decision-dataset-v1``) and the builder that turns a reviewed,
sealed, integrity-verified session into one immutable dataset row.

Rules carried over from the platform's non-negotiables:
- Rows are built ONLY from terminal reviewed sessions with an attributed
  human decision; nothing is inferred, automated, or fabricated.
- Compensation/incentive language is refused structurally (same banned
  terms as the carrier message model).
- Rows are immutable once appended; a session contributes at most one row.
- Exporting real-tenant data for training is a counsel-gated action; this
  module only builds and validate rows. No data leaves the system here.

The dataset is the labeled set against which any future model (CV damage
localization, triage) must beat the baseline before adoption.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from app.carrier_messages import BANNED_TERMS
from app.evidence_manifest import CANONICAL_SLOTS

DATASET_VERSION = "reviewer-decision-dataset-v1"


class ReviewerDatasetError(ValueError):
    """Stable-code dataset failures. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _refuse_banned_terms(text: str) -> None:
    lowered = text.lower()
    for term in BANNED_TERMS:
        if term in lowered:
            raise ReviewerDatasetError("BANNED_TERMS_REFUSED", term)


@dataclass(frozen=True)
class SlotLabel:
    slot: str
    artifact_id: str
    sha256_hex: str
    quality_passed: bool
    gate_version: str


@dataclass(frozen=True)
class DatasetRow:
    session_id: str
    manifest_digest: str
    shot_list_version: str
    vehicle_reference: str | None
    disposition: str
    actor: str
    occurred_at: str
    reason: str
    event_id: str
    sequence: int
    slots: tuple[SlotLabel, ...]
    schema_version: str = DATASET_VERSION


def _vehicle_reference(workflow) -> str | None:
    for event in workflow.history:
        if event.kind == "VEHICLE_RECORDED":
            payload = json.loads(event.payload_json)
            vin = payload.get("vin")
            if isinstance(vin, str) and vin.strip():
                return vin
    return None


def _quality_by_artifact(workflow) -> dict[str, dict]:
    """Per-artifact quality verdicts + gate version from QUALITY_RECORDED."""
    by_artifact: dict[str, dict] = {}
    artifacts = {e.artifact_id: e for e in workflow.manifest_entries()}
    for event in workflow.history:
        if event.kind != "QUALITY_RECORDED":
            continue
        payload = json.loads(event.payload_json)
        gate_version = (payload.get("gate") or {}).get("gate_version", "unattributed-fixture")
        verdicts = payload.get("verdicts") or {}
        for slot, passed in verdicts.items():
            entry = artifacts.get(_artifact_for_slot(workflow, slot))
            if entry is not None:
                by_artifact[entry.artifact_id] = {
                    "quality_passed": passed is True,
                    "gate_version": gate_version,
                }
    return by_artifact


def _artifact_for_slot(workflow, slot: str):
    for entry in workflow.manifest_entries():
        if entry.slot == slot:
            return entry.artifact_id
    return None


class ReviewerDatasetBuilder:
    """Builds one validated dataset row from a terminal reviewed session."""

    def __init__(self, decision, quality_verdicts=None):
        """decision: ReviewDecisionRecord; quality_verdicts optional explicit
        {slot: bool} when the caller keeps the gate output separately."""
        self._decision = decision
        self._explicit_quality = dict(quality_verdicts or {})

    def build(self, workflow, seal) -> DatasetRow:
        from app.review_pipeline import ReviewDecisionRecord, SealRecord

        if workflow.state != "reviewed":
            raise ReviewerDatasetError("SESSION_NOT_REVIEWED", f"state={workflow.state}")
        if not isinstance(self._decision, ReviewDecisionRecord):
            raise ReviewerDatasetError("INVALID_DECISION")
        if not isinstance(seal, SealRecord):
            raise ReviewerDatasetError("INVALID_SEAL")
        if self._decision.session_id != workflow.session_id:
            raise ReviewerDatasetError("DECISION_SESSION_MISMATCH")
        if seal.session_id != workflow.session_id:
            raise ReviewerDatasetError("SEAL_SESSION_MISMATCH")
        _refuse_banned_terms(self._decision.reason)
        if not self._decision.actor.strip():
            raise ReviewerDatasetError("INVALID_ACTOR")

        entries = workflow.manifest_entries()
        if {e.slot for e in entries} != set(CANONICAL_SLOTS):
            raise ReviewerDatasetError("SLOT_SET_INCOMPLETE")
        quality = _quality_by_artifact(workflow)
        slots = []
        for entry in entries:
            q = quality.get(entry.artifact_id)
            if q is None:
                # Fall back to explicitly supplied gate verdicts.
                explicit = self._explicit_quality.get(entry.slot)
                if explicit is None:
                    raise ReviewerDatasetError("QUALITY_NOT_RECORDED", entry.slot)
                q = {"quality_passed": explicit is True, "gate_version": "unattributed-fixture"}
            slots.append(SlotLabel(
                slot=entry.slot,
                artifact_id=entry.artifact_id,
                sha256_hex=entry.sha256_hex,
                quality_passed=q["quality_passed"],
                gate_version=q["gate_version"],
            ))
        return DatasetRow(
            session_id=workflow.session_id,
            manifest_digest=seal.manifest_digest,
            shot_list_version=seal.shot_list_version,
            vehicle_reference=_vehicle_reference(workflow),
            disposition=self._decision.disposition,
            actor=self._decision.actor,
            occurred_at=self._decision.occurred_at,
            reason=self._decision.reason,
            event_id=self._decision.event_id,
            sequence=self._decision.sequence,
            slots=tuple(slots),
        )


class ReviewerDataset:
    """Append-only store of validated rows; one row per session."""

    def __init__(self, rows: Iterable[DatasetRow] = ()):
        self._rows: dict[str, DatasetRow] = {}
        for row in rows:
            self.append(row)

    def append(self, row: DatasetRow) -> DatasetRow:
        if not isinstance(row, DatasetRow):
            raise ReviewerDatasetError("INVALID_ROW")
        if row.schema_version != DATASET_VERSION:
            raise ReviewerDatasetError("SCHEMA_VERSION_MISMATCH", row.schema_version)
        if row.session_id in self._rows:
            raise ReviewerDatasetError("SESSION_ALREADY_PRESENT", row.session_id)
        self._rows[row.session_id] = row
        return row

    def rows(self) -> tuple[DatasetRow, ...]:
        return tuple(self._rows.values())

    def __len__(self) -> int:
        return len(self._rows)

    def export(self) -> dict:
        """Versioned JSON-serializable export. No data leaves the system."""
        return {
            "dataset_version": DATASET_VERSION,
            "row_count": len(self._rows),
            "rows": [
                {
                    **{k: v for k, v in row.__dict__.items() if k != "slots"},
                    "slots": [s.__dict__ for s in row.slots],
                }
                for row in self._rows.values()
            ],
        }

    @classmethod
    def load(cls, payload: dict) -> "ReviewerDataset":
        """Rebuild from an export; validates version, shape, and uniqueness."""
        if not isinstance(payload, dict) or payload.get("dataset_version") != DATASET_VERSION:
            raise ReviewerDatasetError("INVALID_DATASET_EXPORT")
        rows = []
        for raw in payload.get("rows", []):
            if not isinstance(raw, dict):
                raise ReviewerDatasetError("INVALID_ROW")
            slots = tuple(
                SlotLabel(
                    slot=s["slot"], artifact_id=s["artifact_id"], sha256_hex=s["sha256_hex"],
                    quality_passed=s["quality_passed"], gate_version=s["gate_version"],
                ) for s in raw.get("slots", [])
            )
            rows.append(DatasetRow(
                session_id=raw["session_id"], manifest_digest=raw["manifest_digest"],
                shot_list_version=raw["shot_list_version"], vehicle_reference=raw.get("vehicle_reference"),
                disposition=raw["disposition"], actor=raw["actor"], occurred_at=raw["occurred_at"],
                reason=raw["reason"], event_id=raw["event_id"], sequence=raw["sequence"], slots=slots,
            ))
        return cls(rows)

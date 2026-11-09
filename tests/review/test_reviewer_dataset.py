"""Reviewer-decision dataset tests (Slice 8): labeled data from attributed decisions."""
from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

import pytest

from app.capture_workflow import CaptureWorkflow
from app.evidence_manifest import CANONICAL_SLOTS
from app.quality_gate import GATE_VERSION, HeuristicQualityGate
from app.review_pipeline import ReviewerQueue, SealService
from app.reviewer_dataset import (
    DATASET_VERSION,
    DatasetRow,
    ReviewerDataset,
    ReviewerDatasetBuilder,
    ReviewerDatasetError,
)
from tests.review.test_review_pipeline import quality_complete_workflow, store_and_verify

pytestmark = pytest.mark.subtests

FIXED_NOW = "2026-11-06T17:00:00+00:00"
now = lambda: FIXED_NOW

GATE_META = {"gate_version": GATE_VERSION, "checks": {}}


def reviewed_session(tmp_path):
    """Full pipeline through an attributed reviewer decision."""
    w = quality_complete_workflow()
    seal = SealService().seal(w, "sealer-1", "synthetic seal")
    store, report, _ = store_and_verify(w, tmp_path)
    queue = ReviewerQueue(now=now)
    queue.enqueue(w, seal, report, "queue-actor")
    decision = queue.record_decision(
        w, "NOTE_ONLY", [e.artifact_id for e in w.manifest_entries()],
        "synthetic-reviewer-01", "clear guided-capture set", report,
    )
    return w, seal, decision


class TestRowBuilding:
    def test_row_binds_decision_manifest_and_slots(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        row = ReviewerDatasetBuilder(decision).build(w, seal)
        assert row.session_id == w.session_id
        assert row.manifest_digest == seal.manifest_digest
        assert row.disposition == "NOTE_ONLY"
        assert row.actor == "synthetic-reviewer-01"
        assert {s.slot for s in row.slots} == set(CANONICAL_SLOTS)
        assert row.schema_version == DATASET_VERSION

    def test_slot_labels_carry_digest_and_gate_version(self, tmp_path):
        w = quality_complete_workflow()
        w.record_quality  # already recorded by fixture with no gate metadata
        seal = SealService().seal(w, "sealer-1", "s")
        store, report, _ = store_and_verify(w, tmp_path)
        queue = ReviewerQueue(now=now)
        queue.enqueue(w, seal, report, "q")
        decision = queue.record_decision(
            w, "NOTE_ONLY", [e.artifact_id for e in w.manifest_entries()],
            "synthetic-reviewer-01", "ok", report)
        row = ReviewerDatasetBuilder(decision).build(w, seal)
        entries = {e.slot: e for e in w.manifest_entries()}
        for label in row.slots:
            assert label.sha256_hex == entries[label.slot].sha256_hex
            assert label.quality_passed is True
            assert label.gate_version == "unattributed-fixture"

    def test_vehicle_reference_from_vin_event(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        row = ReviewerDatasetBuilder(decision).build(w, seal)
        assert row.vehicle_reference == "1HGCM82633A004352"

    def test_requires_terminal_reviewed_state(self):
        w = quality_complete_workflow()
        with pytest.raises(ReviewerDatasetError, match="SESSION_NOT_REVIEWED"):
            ReviewerDatasetBuilder(None).build(w, None)

    def test_requires_matching_seal_and_decision(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        other, other_seal, _ = reviewed_session(tmp_path)
        with pytest.raises(ReviewerDatasetError, match="DECISION_SESSION_MISMATCH"):
            ReviewerDatasetBuilder(decision).build(other, other_seal)
        with pytest.raises(ReviewerDatasetError, match="SEAL_SESSION_MISMATCH"):
            ReviewerDatasetBuilder(decision).build(w, other_seal)

    def test_banned_compensation_language_refused(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        from dataclasses import replace
        poisoned = replace(decision, reason="operator paid $80 for this capture")
        with pytest.raises(ReviewerDatasetError, match="BANNED_TERMS_REFUSED"):
            ReviewerDatasetBuilder(poisoned).build(w, seal)


class TestDatasetStore:
    def test_append_and_export_roundtrip(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        dataset = ReviewerDataset()
        dataset.append(ReviewerDatasetBuilder(decision).build(w, seal))
        assert len(dataset) == 1
        payload = dataset.export()
        assert payload["dataset_version"] == DATASET_VERSION
        loaded = ReviewerDataset.load(payload)
        assert loaded.rows() == dataset.rows()

    def test_one_row_per_session(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        row = ReviewerDatasetBuilder(decision).build(w, seal)
        dataset = ReviewerDataset([row])
        with pytest.raises(ReviewerDatasetError, match="SESSION_ALREADY_PRESENT"):
            dataset.append(row)

    def test_schema_version_mismatch_rejected(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        row = ReviewerDatasetBuilder(decision).build(w, seal)
        bad = DatasetRow(**{**row.__dict__, "schema_version": "other-v9"})
        with pytest.raises(ReviewerDatasetError, match="SCHEMA_VERSION_MISMATCH"):
            ReviewerDataset([bad])

    def test_load_rejects_foreign_version(self):
        with pytest.raises(ReviewerDatasetError, match="INVALID_DATASET_EXPORT"):
            ReviewerDataset.load({"dataset_version": "not-ours", "rows": []})

    def test_export_contains_no_payment_language(self, tmp_path):
        w, seal, decision = reviewed_session(tmp_path)
        dataset = ReviewerDataset([ReviewerDatasetBuilder(decision).build(w, seal)])
        import json
        blob = json.dumps(dataset.export()).lower()
        for term in ("$80", "cash", "incentive", "compensat"):
            assert term not in blob

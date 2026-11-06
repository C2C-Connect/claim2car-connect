"""
M1 state-machine contract tests (Slice 2).

Positive path: full capture-to-review lifecycle.
Negative cases: every forbidden transition, consent-gating, sequence integrity,
cross-session rejection, terminal-state lockdown, and abort semantics per the
plan v1.3 technical verification matrix.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.domain_events import DomainEvent
from contracts.m1_state_machine import (
    ABORTED,
    CONTRACT_VERSION,
    CONSENTED,
    EVIDENCE_CAPTURED,
    INITIALIZED,
    M1SessionMachine,
    M1_STATES,
    REVIEWED,
    SEALED,
    TERMINAL_STATES,
    TRANSITIONS,
    TransitionError,
    VEHICLE_IDENTIFIED,
)

pytestmark = pytest.mark.subtests


def make_event(session_id, kind, sequence, actor="operator-1", reason="contract test"):
    return DomainEvent(
        session_id=session_id,
        event_id=str(uuid.uuid4()),
        sequence=sequence,
        kind=kind,
        actor=actor,
        occurred_at="2026-11-06T15:00:00+00:00",
        reason=reason,
        payload_json="{}",
    )


def happy_path_events(session_id):
    return [
        make_event(session_id, "SESSION_CREATED", 1, reason="session start"),
        make_event(session_id, "CONSENT_RECORDED", 2, reason="affirmative consent v1"),
        make_event(session_id, "VEHICLE_RECORDED", 3, reason="VIN decode ok"),
        make_event(session_id, "ARTIFACT_REGISTERED", 4, reason="slot 1 original"),
        make_event(session_id, "QUALITY_RECORDED", 5, reason="gates passed"),
        make_event(session_id, "MANIFEST_SEALED", 6, reason="server seal"),
        make_event(session_id, "REVIEW_RECORDED", 7, actor="reviewer-1", reason="accepted"),
    ]


class TestPositivePath:
    def test_full_lifecycle(self):
        sid = "session-contract-1"
        m = M1SessionMachine(sid)
        for event in happy_path_events(sid):
            m.apply(event)
        assert m.state == REVIEWED

    def test_state_sequence(self):
        sid = "session-contract-2"
        m = M1SessionMachine(sid)
        expected = [INITIALIZED, CONSENTED, VEHICLE_IDENTIFIED, EVIDENCE_CAPTURED, "quality_verified", SEALED, REVIEWED]
        for event, want in zip(happy_path_events(sid), expected):
            assert m.apply(event) == want

    def test_restart_reconstruction(self):
        sid = "session-contract-3"
        m1 = M1SessionMachine(sid)
        for event in happy_path_events(sid):
            m1.apply(event)
        m2 = M1SessionMachine.reconstruct(sid, m1.history)
        assert m2.state == m1.state == REVIEWED

    def test_retake_before_quality(self):
        sid = "session-contract-4"
        m = M1SessionMachine(sid)
        for event in happy_path_events(sid)[:4]:
            m.apply(event)
        m.apply(make_event(sid, "ARTIFACT_REGISTERED", 5, reason="slot 1 retake"))
        assert m.state == EVIDENCE_CAPTURED

    def test_abort_is_valid_from_any_non_terminal_state(self):
        for events_count in range(1, 7):  # INITIALIZED through SEALED
            sid = f"session-abort-{events_count}"
            m = M1SessionMachine(sid)
            for event in happy_path_events(sid)[:events_count]:
                m.apply(event)
            m.apply(make_event(sid, "SESSION_ABORTED", events_count + 1, reason="scene safety"))
            assert m.state == ABORTED
            with pytest.raises(TransitionError) as exc:
                m.apply(make_event(sid, "QUALITY_RECORDED", events_count + 2))
            assert exc.value.code == "TERMINAL_STATE_REACHED"

    def test_abort_before_creation_is_forbidden(self):
        m = M1SessionMachine("session-abort-none")
        with pytest.raises(TransitionError):
            m.apply(make_event("session-abort-none", "SESSION_ABORTED", 1))


class TestConsentGate:
    def test_vehicle_without_consent_is_forbidden(self):
        sid = "session-consent-1"
        m = M1SessionMachine(sid)
        m.apply(make_event(sid, "SESSION_CREATED", 1))
        with pytest.raises(TransitionError) as exc:
            m.apply(make_event(sid, "VEHICLE_RECORDED", 2))
        assert exc.value.code == "FORBIDDEN_TRANSITION"

    def test_capture_without_consent_is_forbidden(self):
        sid = "session-consent-2"
        m = M1SessionMachine(sid)
        m.apply(make_event(sid, "SESSION_CREATED", 1))
        with pytest.raises(TransitionError):
            m.apply(make_event(sid, "ARTIFACT_REGISTERED", 2))


class TestOrdering:
    @pytest.mark.parametrize("skip", [2, 3, 4, 5])
    def test_skipping_ahead_is_forbidden(self, skip):
        sid = f"session-skip-{skip}"
        events = happy_path_events(sid)
        m = M1SessionMachine(sid)
        for event in events[:1]:  # only SESSION_CREATED
            m.apply(event)
        with pytest.raises(TransitionError):
            m.apply(events[skip])

    def test_seal_requires_quality(self):
        sid = "session-seal-1"
        m = M1SessionMachine(sid)
        for event in happy_path_events(sid)[:4]:  # up to ARTIFACT_REGISTERED
            m.apply(event)
        with pytest.raises(TransitionError):
            m.apply(make_event(sid, "MANIFEST_SEALED", 5))

    def test_review_requires_seal(self):
        sid = "session-review-1"
        m = M1SessionMachine(sid)
        for event in happy_path_events(sid)[:5]:
            m.apply(event)
        with pytest.raises(TransitionError):
            m.apply(make_event(sid, "REVIEW_RECORDED", 6))

    def test_duplicate_creation_is_forbidden(self):
        sid = "session-dup-1"
        m = M1SessionMachine(sid)
        m.apply(make_event(sid, "SESSION_CREATED", 1))
        with pytest.raises(TransitionError):
            m.apply(make_event(sid, "SESSION_CREATED", 2))


class TestIntegrity:
    def test_sequence_gap_rejected(self):
        sid = "session-seq-1"
        m = M1SessionMachine(sid)
        m.apply(make_event(sid, "SESSION_CREATED", 1))
        with pytest.raises(TransitionError) as exc:
            m.apply(make_event(sid, "CONSENT_RECORDED", 3))
        assert exc.value.code == "SEQUENCE_CONFLICT"

    def test_cross_session_event_rejected(self):
        sid = "session-a"
        other = make_event("session-b", "CONSENT_RECORDED", 2)
        m = M1SessionMachine(sid)
        m.apply(make_event(sid, "SESSION_CREATED", 1))
        with pytest.raises(TransitionError) as exc:
            m.apply(other)
        assert exc.value.code == "CROSS_SESSION_EVENT"

    def test_invalid_session_id_rejected(self):
        with pytest.raises(TransitionError):
            M1SessionMachine("   ")

    def test_terminal_reviewed_accepts_nothing(self):
        sid = "session-term-1"
        m = M1SessionMachine(sid)
        for event in happy_path_events(sid):
            m.apply(event)
        for kind in ("CONSENT_RECORDED", "ARTIFACT_REGISTERED", "MANIFEST_SEALED"):
            with pytest.raises(TransitionError) as exc:
                m.apply(make_event(sid, kind, 8))
            assert exc.value.code == "TERMINAL_STATE_REACHED"


class TestContractSurface:
    def test_contract_version_frozen(self):
        assert CONTRACT_VERSION == "m1-v1"

    def test_matrix_covers_only_known_states(self):
        for (state, _event), target in TRANSITIONS.items():
            assert state is None or state in M1_STATES
            assert target in M1_STATES

    def test_every_state_reachable_and_terminal_set_stable(self):
        reachable = {target for target in TRANSITIONS.values()}
        assert reachable == M1_STATES
        assert TERMINAL_STATES == {REVIEWED, ABORTED}

    def test_machine_rejects_non_domain_event(self):
        m = M1SessionMachine("session-type")
        with pytest.raises(TransitionError):
            m.apply({"kind": "SESSION_CREATED"})

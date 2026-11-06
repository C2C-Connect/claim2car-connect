"""
M1 product contract — frozen session state machine (Gavel M1).

This module IS the contract. The transition matrix below is the single source
of truth for M1 session lifecycle ordering. Any change requires a CONTRACT
version bump, product-owner approval, and synchronized tests
(plan v1.3 §2.1, workstream C; five-slice plan Slice 2).

Design rules encoded here (plan v1.3 §2.1 and §9 verification matrix):
- Consent precedes vehicle identification; consent is never fabricated or
  inferred — no VEHICLE_RECORDED may follow a session that skipped
  CONSENT_RECORDED.
- Evidence (ARTIFACT_REGISTERED) precedes quality gates (QUALITY_RECORDED);
  quality precedes sealing (MANIFEST_SEALED); sealing precedes review
  (REVIEW_RECORDED).
- Abort is valid from any non-terminal state (roadside safety SOP: pause/abort
  without penalty) and is terminal.
- Transitions are server-owned: the machine consumes validated DomainEvents
  with monotonic sequence numbers and rejects wrong-session events.
"""

from __future__ import annotations

from app.domain_events import DomainEvent

CONTRACT_VERSION = "m1-v1"

# --- States ---
INITIALIZED = "initialized"            # SESSION_CREATED
CONSENTED = "consented"                # CONSENT_RECORDED
VEHICLE_IDENTIFIED = "vehicle_identified"  # VEHICLE_RECORDED
EVIDENCE_CAPTURED = "evidence_captured"    # ARTIFACT_REGISTERED
QUALITY_VERIFIED = "quality_verified"      # QUALITY_RECORDED
SEALED = "sealed"                          # MANIFEST_SEALED
REVIEWED = "reviewed"                      # REVIEW_RECORDED (terminal)
ABORTED = "aborted"                        # SESSION_ABORTED (terminal)

M1_STATES = frozenset(
    {
        INITIALIZED,
        CONSENTED,
        VEHICLE_IDENTIFIED,
        EVIDENCE_CAPTURED,
        QUALITY_VERIFIED,
        SEALED,
        REVIEWED,
        ABORTED,
    }
)

TERMINAL_STATES = frozenset({REVIEWED, ABORTED})

# --- Events (extend DomainEvent.KINDS with the abort kind) ---
SESSION_ABORTED = "SESSION_ABORTED"

M1_EVENTS = frozenset(
    {
        "SESSION_CREATED",
        "CONSENT_RECORDED",
        "VEHICLE_RECORDED",
        "ARTIFACT_REGISTERED",
        "QUALITY_RECORDED",
        "MANIFEST_SEALED",
        "REVIEW_RECORDED",
        SESSION_ABORTED,
    }
)

# --- Frozen transition matrix: (current_state, event) -> next_state ---
TRANSITIONS = {
    (None, "SESSION_CREATED"): INITIALIZED,
    (INITIALIZED, "CONSENT_RECORDED"): CONSENTED,
    (INITIALIZED, SESSION_ABORTED): ABORTED,
    (CONSENTED, "VEHICLE_RECORDED"): VEHICLE_IDENTIFIED,
    (CONSENTED, SESSION_ABORTED): ABORTED,
    (VEHICLE_IDENTIFIED, "ARTIFACT_REGISTERED"): EVIDENCE_CAPTURED,
    (VEHICLE_IDENTIFIED, SESSION_ABORTED): ABORTED,
    (EVIDENCE_CAPTURED, "QUALITY_RECORDED"): QUALITY_VERIFIED,
    (EVIDENCE_CAPTURED, SESSION_ABORTED): ABORTED,
    (QUALITY_VERIFIED, "MANIFEST_SEALED"): SEALED,
    (QUALITY_VERIFIED, SESSION_ABORTED): ABORTED,
    (SEALED, "REVIEW_RECORDED"): REVIEWED,
    (SEALED, SESSION_ABORTED): ABORTED,
}

# Retake semantics: a new required-slot original may be registered while
# quality is not yet verified (traceable revision, plan v1.3 §2.1).
TRANSITIONS[(EVIDENCE_CAPTURED, "ARTIFACT_REGISTERED")] = EVIDENCE_CAPTURED
TRANSITIONS[(VEHICLE_IDENTIFIED, "VEHICLE_RECORDED")] = VEHICLE_IDENTIFIED  # VIN correction w/ uncertainty handling


class TransitionError(ValueError):
    """Illegal or out-of-contract transition. Codes are stable API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code


class M1SessionMachine:
    """
    Server-side session lifecycle authority for Gavel M1.

    Consumes validated DomainEvents in strict sequence order and applies the
    frozen transition matrix. Reconstructs state after restart from the event
    history (tenant-scoped event history requirement, plan v1.3 §2.1).
    """

    def __init__(self, session_id: str):
        if not session_id or not session_id.strip():
            raise TransitionError("INVALID_SESSION")
        self.session_id = session_id
        self._state = None
        self._sequence = 0
        self._history = []

    @property
    def state(self):
        return self._state

    @property
    def history(self):
        return tuple(self._history)

    def apply(self, event: DomainEvent):
        if not isinstance(event, DomainEvent):
            raise TransitionError("INVALID_EVENT")
        event.validate()
        if event.session_id != self.session_id:
            raise TransitionError("CROSS_SESSION_EVENT")
        if event.sequence != self._sequence + 1:
            raise TransitionError("SEQUENCE_CONFLICT")
        if event.kind not in M1_EVENTS:
            raise TransitionError("UNSUPPORTED_EVENT_KIND")

        key = (self._state, event.kind)
        if key not in TRANSITIONS:
            if self._state in TERMINAL_STATES:
                raise TransitionError("TERMINAL_STATE_REACHED")
            raise TransitionError(
                "FORBIDDEN_TRANSITION", f"{self._state} + {event.kind}"
            )

        self._state = TRANSITIONS[key]
        self._sequence = event.sequence
        self._history.append(event)
        return self._state

    @classmethod
    def reconstruct(cls, session_id: str, events):
        """Rebuild session state from an ordered event history (restart recovery)."""
        machine = cls(session_id)
        for event in events:
            machine.apply(event)
        return machine

    def assert_alive(self):
        """Workflow pause/abort is valid; a terminal session accepts no work."""
        if self._state in TERMINAL_STATES:
            raise TransitionError("TERMINAL_STATE_REACHED")

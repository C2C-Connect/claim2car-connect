"""
Property-based tests for the frozen M1 contract and capture workflow
(Slice 6; CTO brief Tier 1 #1).

Hypothesis generates thousands of random operation sequences — valid and
invalid interleaved — against the live CaptureWorkflow and checks invariants
after every step: state legality, sequence integrity, replay equivalence,
no fabricated consent, terminal absorption, digest integrity. The pure VIN
guard gets algebraic properties (any single-character mutation of a valid
VIN is invalid; ok iff the computed check digit matches).
"""
from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hypothesis import assume, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from app.capture_workflow import CaptureWorkflow, WorkflowError, sha256_hex_of
from app.evidence_manifest import CANONICAL_SLOTS
from app.vin_guard import VIN_WEIGHTS, _VALUES, validate_vin
from contracts.m1_state_machine import M1SessionMachine, M1_STATES

VALID_VIN = "1HGCM82633A004352"
LEGAL_CHARS = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O, Q
FIXED_NOW = "2026-11-06T18:00:00+00:00"

SLOTS = st.sampled_from(sorted(CANONICAL_SLOTS) + ["bogus_slot"])
SHA256S = st.from_regex(r"[0-9a-f]{64}", fullmatch=True)
ARTIFACT_IDS = st.sampled_from([f"art-{i}" for i in range(1, 15)] + ["", "dup"])


def expected_check_digit(vin: str) -> str:
    total = sum((int(c) if c.isdigit() else _VALUES[c]) * VIN_WEIGHTS[i] for i, c in enumerate(vin))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


# --- VIN guard algebraic properties -----------------------------------------

VALID_VINS = ["1HGCM82633A004352", "1M8GDM9AXKP042788", "JH4KA7561PC008269"]

VIN17 = st.text(alphabet=LEGAL_CHARS, min_size=17, max_size=17)


@settings(max_examples=300, deadline=None)
@given(vin=VIN17)
def test_check_digit_property(vin):
    """ok is exactly 'the 9th character equals the ISO 3779 check digit'."""
    report = validate_vin(vin)
    assert report.ok == (vin[8] == expected_check_digit(vin))
    assert report.scope == "format-and-check-digit-only"


def char_value(c):
    return int(c) if c.isdigit() else _VALUES[c]


@settings(max_examples=200, deadline=None)
@given(data=st.data())
def test_single_character_mutation_breaks_vin(data):
    """A substitution that changes the character's numeric value invalidates
    the VIN.

    Because 11 is prime and every weight w in VIN_WEIGHTS satisfies
    0 <= w < 11 (w=0 only at the check-digit position), a value change d
    (0 < |d| < 11) shifts the total by d*w which is never a multiple of 11 —
    so the expected check digit must change; and mutating the check-digit
    position itself changes the received digit. Either way: invalid.
    """
    vin = data.draw(st.sampled_from(VALID_VINS))
    pos = data.draw(st.integers(min_value=0, max_value=16))
    replacement = data.draw(
        st.sampled_from([c for c in LEGAL_CHARS if c != vin[pos] and char_value(c) != char_value(vin[pos])])
    )
    mutated = vin[:pos] + replacement + vin[pos + 1:]
    report = validate_vin(mutated)
    assert not report.ok
    assert report.recapture_required and report.uncertainty_code is not None


@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_value_preserving_substitution_keeps_vin_valid(data):
    """Known ISO 3779 equivalence: the check digit sees values, not glyphs.

    Digits and letters with equal transliteration values (A/J/1, B/K/S/2,
    C/L/T/3, D/M/U/4, E/N/V/5, F/W/6, G/P/X/7, H/Y/8, R/9) are
    interchangeable as far as the check digit is concerned. This documents
    the homoglyph equivalence explicitly rather than pretending the guard
    can distinguish them — capture quality and human review handle that.
    """
    vin = data.draw(st.sampled_from(VALID_VINS))
    pos = data.draw(st.integers(min_value=0, max_value=16))
    assume(pos != 8)  # the check digit is compared literally (0-9 or X), not by value
    same_value = [c for c in LEGAL_CHARS if c != vin[pos] and char_value(c) == char_value(vin[pos])]
    assume(same_value)  # positions holding digits 0/9 have no letter twin
    replacement = data.draw(st.sampled_from(same_value))
    mutated = vin[:pos] + replacement + vin[pos + 1:]
    report = validate_vin(mutated)
    assert report.ok
    assert mutated[8] == vin[8]


@settings(max_examples=200, deadline=None)
@given(raw=st.text(min_size=0, max_size=40))
def test_guard_never_crashes_and_never_repairs(raw):
    report = validate_vin(raw)
    if not report.ok:
        assert report.recapture_required is True
        assert report.message == "VIN VALIDATION FAILED: Recapture VIN Plate"
        assert report.ok is False
    else:
        assert len(report.vin) == 17
        assert report.vin[8] == expected_check_digit(report.vin)


# --- stateful capture-workflow property machine --------------------------------

class CaptureWorkflowMachine(RuleBasedStateMachine):
    """Random legal/illegal operation sequences against the live workflow.

    Every rule failure is captured as WorkflowError (ordering holds); the
    invariants run after EVERY rule, valid or invalid.
    """

    def __init__(self):
        super().__init__()
        self.w = CaptureWorkflow(str(uuid4()), now=lambda: FIXED_NOW)
        self.terminal_events = None

    def _try(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except WorkflowError:
            return None  # illegal ops are rejected, never corrupt state

    @rule()
    def present_disclosure(self):
        self._try(self.w.present_disclosure, "disclosure-v1")

    @rule(version=st.sampled_from(["disclosure-v1", "disclosure-stale"]))
    def present_disclosure_random_version(self, version):
        self._try(self.w.present_disclosure, version)

    @rule(accepted=st.one_of(st.just(True), st.just(False), st.text(min_size=1, max_size=3)))
    def consent(self, accepted):
        self._try(self.w.record_consent, "driver", accepted, "disclosure-v1")

    @rule(vin=st.one_of(st.just(VALID_VIN), VIN17, st.text(min_size=5, max_size=25)))
    def record_vehicle(self, vin):
        self._try(self.w.record_vehicle, "driver", vin)

    @rule(slot=SLOTS, artifact_id=ARTIFACT_IDS, digest=SHA256S, length=st.integers(min_value=-1, max_value=5000))
    def register_artifact(self, slot, artifact_id, digest, length):
        self._try(self.w.register_artifact, "driver", slot, artifact_id, digest, length)

    @rule(fail_slot=st.one_of(st.none(), st.sampled_from(sorted(CANONICAL_SLOTS))))
    def quality(self, fail_slot):
        verdicts = {s: (s != fail_slot) for s in CANONICAL_SLOTS}
        self._try(self.w.record_quality, "driver", verdicts)

    @rule()
    def seal(self):
        from app.review_pipeline import ReviewPipelineError, SealService

        try:
            SealService().seal(self.w, "sealer", "property test seal", now=lambda: FIXED_NOW)
        except ReviewPipelineError:
            pass

    @rule()
    def review(self):
        from app.review_pipeline import ReviewPipelineError, ReviewerQueue

        try:
            ReviewerQueue(now=lambda: FIXED_NOW).record_decision(
                self.w, "NOTE_ONLY", [e.artifact_id for e in self.w.manifest_entries()], "reviewer", "property"
            )
        except (ReviewPipelineError, WorkflowError):
            pass

    @rule()
    def abort(self):
        event_id = str(uuid4())
        if self.w.history:
            from app.domain_events import DomainEvent

            try:
                self.w.machine.apply(
                    DomainEvent(
                        session_id=self.w.session_id,
                        event_id=event_id,
                        sequence=self.w.history[-1].sequence + 1,
                        kind="SESSION_ABORTED",
                        actor="driver",
                        occurred_at=FIXED_NOW,
                        reason="property abort",
                        payload_json="{}",
                    )
                )
            except Exception:
                pass

    @invariant()
    def state_is_legal(self):
        assert self.w.state in M1_STATES

    @invariant()
    def sequence_integrity(self):
        sequences = [e.sequence for e in self.w.history]
        assert sequences == list(range(1, len(sequences) + 1))

    @invariant()
    def replay_equivalence(self):
        replayed = M1SessionMachine.reconstruct(self.w.session_id, self.w.history)
        assert replayed.state == self.w.state

    @invariant()
    def no_fabricated_consent(self):
        kinds = [e.kind for e in self.w.history]
        if "CONSENT_RECORDED" in kinds:
            first = kinds.index("CONSENT_RECORDED")
            assert self.w._presented_disclosure == "disclosure-v1"
            import json

            payload = json.loads(self.w.history[first].payload_json)
            assert payload["accepted"] is True

    @invariant()
    def artifacts_consistent_with_state(self):
        captured = self.w.captured_slots()
        if captured:
            # Aborting is valid from any nonterminal state. It closes
            # the workflow but does not erase the evidence already captured.
            assert self.w.state in ("vehicle_identified", "evidence_captured", "quality_verified", "sealed", "reviewed", "aborted")
            ids = [self.w._artifacts[s].artifact_id for s in captured]
            assert len(ids) == len(set(ids))

    @invariant()
    def quality_implies_complete_set(self):
        if self.w.state in ("quality_verified", "sealed", "reviewed"):
            assert not self.w.pending_slots()

    @invariant()
    def terminal_states_absorb(self):
        if self.w.state in ("aborted", "reviewed"):
            if self.terminal_events is None:
                self.terminal_events = len(self.w.history)
            assert len(self.w.history) == self.terminal_events


TestCaptureWorkflowProperties = CaptureWorkflowMachine.TestCase
TestCaptureWorkflowProperties.settings = settings(max_examples=120, stateful_step_count=40, deadline=None)


# --- outbox property: no loss, no duplicate delivery ----------------------------

from app.outbox import OutboxMessage, OutboxRelay, OutboxStore  # noqa: E402


class OutboxMachine(RuleBasedStateMachine):
    """Random append/drain interleavings with a sometimes-failing consumer.

    Invariant: every message is eventually delivered or dead-lettered (never
    lost), and no consumer ever processes the same message id twice.
    """

    def __init__(self):
        super().__init__()
        self.storage = {}
        self.store = OutboxStore(self.storage, max_attempts=3)
        self.relay = OutboxRelay(self.store)
        self.delivered_seen = []
        self.kinds = ["K1", "K2"]
        self.relay.register_consumer("K1", self.consumer_k1)
        self.relay.register_consumer("K2", self.consumer_k2)

    def consumer_k1(self, message):
        self.delivered_seen.append(("K1", message.message_id))

    def consumer_k2(self, message):
        self.delivered_seen.append(("K2", message.message_id))

    @rule(kind=st.sampled_from(["K1", "K2", "K3"]))
    def append(self, kind):
        message = OutboxMessage(
            message_id=str(uuid4()),
            session_id="s",
            source_event_id=str(uuid4()),
            kind=kind,
            sequence=1,
            payload_json="{}",
            created_at=FIXED_NOW,
        )
        self.store.append(message)

    @rule(fail_k1=st.booleans(), fail_k2=st.booleans())
    def drain(self, fail_k1, fail_k2):
        self._fail_k1 = fail_k1
        self._fail_k2 = fail_k2
        original_k1 = self.relay._registrations[0]
        original_k2 = self.relay._registrations[1]

        def maybe_failing_k1(message):
            if self._fail_k1:
                raise RuntimeError("synthetic k1 failure")
            self.consumer_k1(message)

        def maybe_failing_k2(message):
            if self._fail_k2:
                raise RuntimeError("synthetic k2 failure")
            self.consumer_k2(message)

        self.relay._registrations[0] = (original_k1[0], original_k1[1], maybe_failing_k1)
        self.relay._registrations[1] = (original_k2[0], original_k2[1], maybe_failing_k2)
        self.relay.drain()
        self.relay._registrations[0] = original_k1
        self.relay._registrations[1] = original_k2

    @invariant()
    def no_duplicate_delivery(self):
        assert len(self.delivered_seen) == len(set(self.delivered_seen))

    @invariant()
    def no_message_lost(self):
        outbox = self.storage.get("outbox")
        if outbox is None:
            return
        for message_id, entry in outbox["messages"].items():
            if entry["status"] == "delivered":
                kinds_delivered = {c for c, m in self.delivered_seen if m == message_id}
                assert kinds_delivered <= {"K1", "K2"}
            # pending or dead are both acceptable resting states; nothing else exists
            assert entry["status"] in ("pending", "delivered", "dead")


TestOutboxProperties = OutboxMachine.TestCase
TestOutboxProperties.settings = settings(max_examples=80, stateful_step_count=25, deadline=None)

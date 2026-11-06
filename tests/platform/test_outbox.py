"""
Transactional outbox tests (Slice 6): lifecycle, exactly-once delivery per
consumer, bounded retries with dead-lettering, transactional pairing with
the state machine, and crash-resume safety.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

from app.capture_workflow import CaptureWorkflow
from app.outbox import (
    OutboxError,
    OutboxMessage,
    OutboxRelay,
    OutboxStore,
    attach_outbox,
)
from app.domain_events import DomainEvent

FIXED_NOW = "2026-11-06T18:00:00+00:00"
pytestmark = pytest.mark.subtests


def make_message(kind="K1", message_id=None):
    return OutboxMessage(
        message_id=message_id or str(uuid4()),
        session_id="s1",
        source_event_id=str(uuid4()),
        kind=kind,
        sequence=1,
        payload_json='{"a":1}',
        created_at=FIXED_NOW,
    )


def test_append_and_pending_lifecycle():
    store = OutboxStore()
    m = store.append(make_message())
    assert store.pending() == (m,)
    assert store.status(m.message_id) == "pending"
    store.mark_delivered(m.message_id)
    assert store.pending() == () and store.status(m.message_id) == "delivered"


def test_duplicate_message_id_rejected():
    store = OutboxStore()
    m = make_message()
    store.append(m)
    with pytest.raises(OutboxError) as e:
        store.append(m)
    assert e.value.code == "DUPLICATE_MESSAGE_ID"


def test_unknown_message_operations_rejected():
    store = OutboxStore()
    with pytest.raises(OutboxError):
        store.mark_delivered("missing")
    with pytest.raises(OutboxError):
        store.record_failure("missing", "x")


def test_relay_delivers_exactly_once_across_re_drains():
    store = OutboxStore()
    relay = OutboxRelay(store)
    seen = []
    relay.register_consumer("K1", seen.append)
    m = store.append(make_message())
    first = relay.drain()
    assert first.delivered == (m.message_id,)
    second = relay.drain()
    assert second.delivered == () and second.skipped_duplicate == ()  # not even pending
    assert seen == [m]
    assert store.status(m.message_id) == "delivered"


def test_relay_routes_by_kind():
    store = OutboxStore()
    relay = OutboxRelay(store)
    k1, k2 = [], []
    relay.register_consumer("K1", k1.append)
    relay.register_consumer("K2", k2.append)
    m1 = store.append(make_message("K1"))
    m2 = store.append(make_message("K2"))
    relay.drain()
    assert [m.message_id for m in k1] == [m1.message_id]
    assert [m.message_id for m in k2] == [m2.message_id]
    assert store.status(m1.message_id) == "delivered" and store.status(m2.message_id) == "delivered"


def test_unregistered_kind_stays_pending():
    store = OutboxStore()
    relay = OutboxRelay(store)
    relay.register_consumer("K1", lambda m: None)
    m = store.append(make_message("K3"))
    result = relay.drain()
    assert result.delivered == () and store.status(m.message_id) == "pending"


def test_failing_consumer_retries_then_success():
    store = OutboxStore()
    relay = OutboxRelay(store)
    attempts = []

    def flaky(message):
        attempts.append(message.message_id)
        if len(attempts) < 3:
            raise RuntimeError("transient")
        return None

    relay.register_consumer("K1", flaky)
    m = store.append(make_message())
    relay.drain()  # fail 1
    relay.drain()  # fail 2
    assert store.status(m.message_id) == "pending" and store.attempts(m.message_id) == 2
    relay.drain()  # success
    assert store.status(m.message_id) == "delivered"
    assert len(attempts) == 3


def test_dead_letter_after_max_attempts():
    store = OutboxStore(max_attempts=2)
    relay = OutboxRelay(store)
    def always_fails(message):
        raise RuntimeError("permanent")
    relay.register_consumer("K1", always_fails)
    m = store.append(make_message())
    relay.drain()
    assert store.attempts(m.message_id) == 1 and store.status(m.message_id) == "pending"
    relay.drain()
    assert store.attempts(m.message_id) == 2 and store.status(m.message_id) == "dead"
    third = relay.drain()
    assert third.delivered == ()  # dead messages are never retried
    assert store.dead_lettered() == (m,)
    # Dead-lettered message retains its payload for inspection.
    assert m.payload() == {"a": 1}


def test_crash_resume_delivers_remaining_without_duplicates():
    store = OutboxStore()
    delivered = []
    m1, m2 = store.append(make_message("K1")), store.append(make_message("K1"))
    # Simulated crash mid-batch: only the first message was processed before
    # the process died; the store still shows both as pending.
    relay = OutboxRelay(store)
    relay.register_consumer("K1", delivered.append)
    relay._processed[1] = set()  # fresh relay: no memory of the crash
    relay.drain()
    assert {m.message_id for m in delivered} == {m1.message_id, m2.message_id}
    assert len(delivered) == 2  # no duplicates across the crash boundary


def test_transactional_pairing_with_state_machine():
    """Every applied domain event is mirrored into the outbox; a rejected
    transition produces no outbox row."""
    outbox = OutboxStore()
    w = CaptureWorkflow(str(uuid4()), now=lambda: FIXED_NOW, outbox=outbox)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    kinds = [m.kind for m in outbox.pending()]
    assert kinds == ["SESSION_CREATED", "CONSENT_RECORDED"]
    # An ordering violation raises and must NOT append an outbox message.
    from app.capture_workflow import WorkflowError

    with pytest.raises(WorkflowError):
        w.record_vehicle("driver-1", "not-a-vin")
    assert len(outbox.pending()) == 2
    w.record_vehicle("driver-1", "1HGCM82633A004352")
    assert [m.kind for m in outbox.pending()][-1] == "VEHICLE_RECORDED"


def test_relay_feeds_from_workflow_outbox():
    outbox = OutboxStore()
    w = CaptureWorkflow(str(uuid4()), now=lambda: FIXED_NOW, outbox=outbox)
    w.present_disclosure("disclosure-v1")
    w.record_consent("driver-1", True, "disclosure-v1")
    audit_log = []
    relay = OutboxRelay(outbox)
    relay.register_consumer("CONSENT_RECORDED", audit_log.append)
    result = relay.drain()
    assert result.delivered == (audit_log[0].message_id,)
    assert audit_log[0].payload() == {"disclosure_version": "disclosure-v1", "accepted": True}
    # SESSION_CREATED has no consumer: stays pending, never lost.
    assert outbox.status(result.delivered[0]) == "delivered"
    assert any(m.kind == "SESSION_CREATED" for m in outbox.pending())

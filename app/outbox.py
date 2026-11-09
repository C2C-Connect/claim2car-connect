"""Transactional outbox (Slice 6; CTO brief Tier 1 #4).

Solves the dual-write problem for the distribution workstream (plan v1.3
§3.2): a domain event and its outbound message are recorded together — if
the state machine rejects the event, no outbox row is ever written — and a
relay delivers each message to each interested consumer exactly once per
consumer, with bounded retries and an inspectable dead-letter list. Nothing
is silently dropped: a message ends up delivered or dead-lettered, never
lost.

Production mapping: store rows in the same database transaction as the
domain event; the relay runs as a background worker. This module keeps the
semantics identical with an injectable persistence mapping (dict here,
Postgres later).

Live sends remain gated: consumers registered today are internal formatters
and auditors only. No external delivery happens without counsel sign-off.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

from app.domain_events import DomainEvent
from app.telemetry import workflow_span

MAX_DELIVERY_ATTEMPTS = 5
STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_DEAD = "dead"


class OutboxError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class OutboxMessage:
    message_id: str
    session_id: str
    source_event_id: str
    kind: str  # domain event kind; consumers subscribe by kind
    sequence: int
    payload_json: str
    created_at: str

    @classmethod
    def from_event(cls, event: DomainEvent) -> "OutboxMessage":
        if not isinstance(event, DomainEvent):
            raise OutboxError("INVALID_EVENT")
        return cls(
            message_id=str(uuid4()),
            session_id=event.session_id,
            source_event_id=event.event_id,
            kind=event.kind,
            sequence=event.sequence,
            payload_json=event.payload_json,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def payload(self):
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class DrainResult:
    delivered: tuple[str, ...] = ()
    skipped_duplicate: tuple[str, ...] = ()
    retried: tuple[str, ...] = ()
    dead_lettered: tuple[str, ...] = ()


class OutboxStore:
    """Append-only outbox with delivery bookkeeping. Injectable persistence."""

    def __init__(self, storage=None, max_attempts: int = MAX_DELIVERY_ATTEMPTS):
        self.storage = storage if storage is not None else {}
        self.max_attempts = max(1, int(max_attempts))

    def _load(self) -> dict:
        return self.storage.setdefault("outbox", {"messages": {}, "order": []})

    def append(self, message: OutboxMessage) -> OutboxMessage:
        if not isinstance(message, OutboxMessage):
            raise OutboxError("INVALID_MESSAGE")
        data = self._load()
        if message.message_id in data["messages"]:
            raise OutboxError("DUPLICATE_MESSAGE_ID", message.message_id)
        data["messages"][message.message_id] = {
            "message": message,
            "status": STATUS_PENDING,
            "attempts": 0,
            "last_error": None,
        }
        data["order"].append(message.message_id)
        return message

    def append_for_event(self, event: DomainEvent) -> OutboxMessage:
        """Record the outbound counterpart of an applied domain event."""
        return self.append(OutboxMessage.from_event(event))

    def pending(self) -> tuple[OutboxMessage, ...]:
        data = self._load()
        return tuple(
            data["messages"][mid]["message"]
            for mid in data["order"]
            if data["messages"][mid]["status"] == STATUS_PENDING
        )

    def get(self, message_id: str) -> Optional[OutboxMessage]:
        entry = self._load()["messages"].get(message_id)
        return entry["message"] if entry else None

    def status(self, message_id: str) -> Optional[str]:
        entry = self._load()["messages"].get(message_id)
        return entry["status"] if entry else None

    def attempts(self, message_id: str) -> int:
        entry = self._load()["messages"].get(message_id)
        return entry["attempts"] if entry else -1

    def mark_delivered(self, message_id: str) -> None:
        entry = self._load()["messages"].get(message_id)
        if entry is None:
            raise OutboxError("UNKNOWN_MESSAGE", message_id)
        entry["status"] = STATUS_DELIVERED

    def record_failure(self, message_id: str, error: str) -> str:
        """Record a failed attempt. Returns the resulting status."""
        entry = self._load()["messages"].get(message_id)
        if entry is None:
            raise OutboxError("UNKNOWN_MESSAGE", message_id)
        if entry["status"] != STATUS_PENDING:
            raise OutboxError("NOT_PENDING", message_id)
        entry["attempts"] += 1
        entry["last_error"] = str(error)[:500]
        if entry["attempts"] >= self.max_attempts:
            entry["status"] = STATUS_DEAD  # dead-lettered: retained, never retried
        return entry["status"]

    def dead_lettered(self) -> tuple[OutboxMessage, ...]:
        data = self._load()
        return tuple(
            e["message"] for e in data["messages"].values() if e["status"] == STATUS_DEAD
        )


class OutboxRelay:
    """Delivers pending messages to registered consumers, exactly once each.

    At-least-once delivery from the relay's perspective (a crash mid-batch is
    safe to re-run) combined with per-consumer dedupe by message id gives
    effectively-once processing per consumer. A consumer that keeps failing is
    dead-lettered by the store after max_attempts; delivery of other messages
    continues.
    """

    def __init__(self, store: OutboxStore):
        if not isinstance(store, OutboxStore):
            raise OutboxError("INVALID_STORE")
        self.store = store
        self._registrations: list[tuple[int, str, Callable[[OutboxMessage], None]]] = []
        self._processed: dict[int, set[str]] = {}
        self._next_consumer_id = 1

    def register_consumer(self, kind: str, handler: Callable[[OutboxMessage], None]) -> int:
        """Register a handler for one event kind. Returns the consumer id."""
        if not isinstance(kind, str) or not kind.strip():
            raise OutboxError("INVALID_KIND")
        if not callable(handler):
            raise OutboxError("INVALID_HANDLER")
        consumer_id = self._next_consumer_id
        self._next_consumer_id += 1
        self._registrations.append((consumer_id, kind, handler))
        self._processed[consumer_id] = set()
        return consumer_id

    def drain(self) -> DrainResult:
        """Deliver every pending message to every consumer registered for its
        kind. Safe to re-run; per-consumer dedupe prevents double processing."""
        delivered, skipped, retried, dead = [], [], [], []
        for message in self.store.pending():
            matching = [r for r in self._registrations if r[1] == message.kind]
            if not matching:
                # No consumer registered for this kind yet: the message stays
                # pending rather than being marked delivered and lost.
                continue
            for consumer_id, kind, handler in matching:
                if kind != message.kind:
                    continue
                if message.message_id in self._processed.get(consumer_id, ()):
                    skipped.append(message.message_id)
                    continue
                try:
                    with workflow_span("outbox.deliver", kind=message.kind, message_id=message.message_id):
                        handler(message)
                except Exception as exc:  # bounded retry, then dead-letter
                    status = self.store.record_failure(message.message_id, exc)
                    if status == STATUS_DEAD:
                        dead.append(message.message_id)
                    else:
                        retried.append(message.message_id)
                    continue
                self._processed.setdefault(consumer_id, set()).add(message.message_id)
                delivered.append(message.message_id)
                if self._all_consumers_satisfied(message):
                    self.store.mark_delivered(message.message_id)
        return DrainResult(
            delivered=tuple(delivered),
            skipped_duplicate=tuple(skipped),
            retried=tuple(retried),
            dead_lettered=tuple(dead),
        )

    def _all_consumers_satisfied(self, message: OutboxMessage) -> bool:
        for consumer_id, kind, _ in self._registrations:
            if kind == message.kind and message.message_id not in self._processed.get(consumer_id, ()):
                return False
        return True


def attach_outbox(workflow, outbox: OutboxStore) -> None:
    """Attach an outbox to an existing CaptureWorkflow.

    Prefer passing outbox= to the CaptureWorkflow constructor: events applied
    before attachment (including SESSION_CREATED) are not mirrored, so
    post-hoc attachment is only for retrofitting a session mid-flight."""
    from app.capture_workflow import CaptureWorkflow

    if not isinstance(workflow, CaptureWorkflow) or not isinstance(outbox, OutboxStore):
        raise OutboxError("INVALID_ATTACH")
    workflow.outbox = outbox

"""Synthetic event history validation; not persistence or evidence-state replay."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
import math
import re

VERSION = '0.1'
KINDS = frozenset({
    'SESSION_CREATED',
    'CONSENT_RECORDED',
    'VEHICLE_RECORDED',
    'ARTIFACT_REGISTERED',
    'QUALITY_RECORDED',
    'MANIFEST_SEALED',
    'REVIEW_RECORDED',
    'SESSION_ABORTED',
    'INCIDENT_INTAKE_CONSENT_RECORDED',
    'INCIDENT_INTAKE_RECORDED',
})
RFC3339_TIMESTAMP = re.compile(
    r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-5][0-9]:[0-5][0-9]'
    r'(?:\.[0-9]{1,6})?(?:Z|[+-](?:0[0-9]|1[0-9]|2[0-3]):[0-5][0-9])$'
)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _reject_nonfinite(_value):
    raise ValueError('NONFINITE_EVENT_NUMBER')


def _canonical_json(value):
    """Serialize the shared event JSON dialect used by Python and PostgreSQL.

    Object keys are sorted by Unicode code point (equivalent to UTF-8 byte
    order for valid strings). Decimal values are emitted in fixed notation,
    matching PostgreSQL jsonb numeric output rather than Python exponent form.
    """
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if type(value) is int:
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('NONFINITE_EVENT_NUMBER')
        value = Decimal(str(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('NONFINITE_EVENT_NUMBER')
        return format(value, 'f')
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(_canonical_json(item) for item in value) + ']'
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError('EVENT_OBJECT_KEYS_MUST_BE_STRINGS')
        return '{' + ','.join(
            json.dumps(key, ensure_ascii=False, separators=(',', ':')) + ':' + _canonical_json(value[key])
            for key in sorted(value)
        ) + '}'
    raise TypeError('UNSUPPORTED_EVENT_JSON_VALUE')


def canonical_event_payload(payload):
    """Return compact, deterministic JSON text for an event object."""
    if type(payload) is not dict:
        raise ValueError('EVENT_PAYLOAD_MUST_BE_OBJECT')
    return _canonical_json(payload)


@dataclass(frozen=True)
class DomainEvent:
    session_id: str
    event_id: str
    sequence: int
    kind: str
    actor: str
    occurred_at: str
    reason: str
    payload_json: str
    schema_version: str = VERSION

    def validate(self):
        if self.schema_version != VERSION:
            raise ValueError('UNSUPPORTED_SCHEMA')
        if not all(nonempty(v) for v in (self.session_id, self.event_id, self.actor, self.reason)):
            raise ValueError('MISSING_CONTEXT')
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError('INVALID_SEQUENCE')
        if not isinstance(self.kind, str) or self.kind not in KINDS:
            raise ValueError('INVALID_EVENT_KIND')
        if not isinstance(self.occurred_at, str) or not RFC3339_TIMESTAMP.fullmatch(self.occurred_at):
            raise ValueError('INVALID_TIMESTAMP')
        try:
            timestamp = self.occurred_at
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            parsed_timestamp = datetime.fromisoformat(timestamp)
            if parsed_timestamp.utcoffset() is None:
                raise ValueError
        except (ValueError, OverflowError):
            raise ValueError('INVALID_TIMESTAMP') from None
        if not isinstance(self.payload_json, str):
            raise ValueError('INVALID_PAYLOAD')
        try:
            payload = json.loads(
                self.payload_json,
                parse_float=Decimal,
                parse_constant=_reject_nonfinite,
            )
            if type(payload) is not dict:
                raise ValueError('NONCANONICAL_PAYLOAD')
            canonical = canonical_event_payload(payload)
        except (ValueError, TypeError, RecursionError):
            raise ValueError('INVALID_PAYLOAD') from None
        if canonical != self.payload_json:
            raise ValueError('NONCANONICAL_PAYLOAD')
        return self

    @property
    def payload(self):
        return json.loads(self.payload_json)


class EventJournal:
    """In-memory journal for validating synthetic event histories."""
    def __init__(self, session_id):
        if not nonempty(session_id):
            raise ValueError('INVALID_SESSION')
        self.session_id = session_id
        self._events = ()

    @property
    def events(self):
        return self._events

    def append(self, event):
        if not isinstance(event, DomainEvent):
            raise ValueError('INVALID_EVENT')
        event.validate()
        if event.session_id != self.session_id:
            raise ValueError('CROSS_SESSION_REFERENCE')
        for existing in self._events:
            if existing.event_id == event.event_id:
                if existing != event:
                    raise ValueError('CONFLICTING_EVENT_DUPLICATE')
                return 'DUPLICATE'
        if event.sequence != len(self._events) + 1:
            raise ValueError('SEQUENCE_CONFLICT')
        self._events = self._events + (event,)
        return 'ACCEPTED'

    @classmethod
    def replay(cls, session_id, events):
        journal = cls(session_id)
        for event in events:
            if journal.append(event) != 'ACCEPTED':
                raise ValueError('DUPLICATE_IN_HISTORY')
        return journal

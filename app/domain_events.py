from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json

@dataclass
class DomainEvent:
    session_id: str
    event_id: str
    sequence: int
    kind: str
    actor: str
    occurred_at: str
    reason: str
    payload_json: str
    schema_version: str = "0.1"

    def validate(self):
        if not self.session_id or not self.event_id:
            raise ValueError("INVALID_EVENT_IDENTIFIERS")
        json.loads(self.payload_json)

class EventJournal:
    @staticmethod
    def replay(session_id, events):
        return events

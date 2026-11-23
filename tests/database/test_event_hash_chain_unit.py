import copy
import unittest
from dataclasses import replace

from app.domain_events import DomainEvent
from database.event_hash_chain import event_hash, genesis_hash, verify_event_chain

TENANT = "12345678-1234-5678-1234-567812345678"
SESSION = "sess-α"
EVENT_1 = DomainEvent(
    session_id=SESSION,
    event_id="evt-1",
    sequence=1,
    kind="SESSION_CREATED",
    actor="operator-1",
    occurred_at="2026-11-23T12:34:56.123456Z",
    reason="created",
    payload_json='{"capture_protocol_version":"claims2car-16-v2","synthetic":true}',
    schema_version="0.1",
)
EXPECTED_GENESIS = "3caf4b5b5be75332e7483650e6450531bf17a203e7bb917483f93c3ef9236cff"
EXPECTED_EVENT_1 = "6be67e7eca3721355e15440ef7a7ae9477bc0acd8ca62879355ce58f8bef9dbd"


def row(event, previous_hash, entry_hash):
    return {
        "session_id": event.session_id, "event_id": event.event_id,
        "sequence": event.sequence, "kind": event.kind, "actor": event.actor,
        "occurred_at": event.occurred_at, "reason": event.reason,
        "payload_json": event.payload_json, "schema_version": event.schema_version,
        "previous_hash": previous_hash, "entry_hash": entry_hash,
        "hash_version": "event-hash-v1",
    }


class EventHashChainUnitTests(unittest.TestCase):
    def test_known_vector_genesis_and_event(self):
        genesis = genesis_hash(TENANT, SESSION)
        self.assertEqual(genesis, EXPECTED_GENESIS)
        self.assertEqual(event_hash(TENANT, EVENT_1, genesis), EXPECTED_EVENT_1)

    def test_valid_chain_verifies(self):
        record = row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)
        result = verify_event_chain(TENANT, SESSION, [record])
        self.assertTrue(result["valid"])
        self.assertEqual(result["chain_head"], EXPECTED_EVENT_1)
        self.assertEqual(result["event_count"], 1)

    def test_each_committed_field_is_bound(self):
        genesis = genesis_hash(TENANT, SESSION)
        base = event_hash(TENANT, EVENT_1, genesis)
        changes = (
            {"session_id": "different-session"}, {"event_id": "evt-other"},
            {"sequence": 2}, {"kind": "CONSENT_RECORDED"},
            {"actor": "operator-2"}, {"occurred_at": "2026-11-23T12:34:56.123455Z"},
            {"reason": "changed"},
            {"payload_json": '{"capture_protocol_version":"claims2car-16-v2","synthetic":false}'},
            {"schema_version": "0.2"},
        )
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(event_hash(TENANT, replace(EVENT_1, **change), genesis), base)

    def test_tenant_and_previous_hash_are_bound(self):
        self.assertNotEqual(event_hash(TENANT, EVENT_1, EXPECTED_GENESIS),
                            event_hash("22345678-1234-5678-1234-567812345678", EVENT_1, EXPECTED_GENESIS))
        self.assertNotEqual(event_hash(TENANT, EVENT_1, "0" * 64), EXPECTED_EVENT_1)

    def test_payload_tamper_fails(self):
        record = row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)
        record["payload_json"] = '{"capture_protocol_version":"claims2car-16-v2","synthetic":false}'
        result = verify_event_chain(TENANT, SESSION, [record])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "EVENT_HASH_MISMATCH")

    def test_previous_link_tamper_fails(self):
        result = verify_event_chain(TENANT, SESSION, [row(EVENT_1, "0" * 64, EXPECTED_EVENT_1)])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "PREVIOUS_HASH_MISMATCH")

    def test_sequence_gap_or_reorder_fails(self):
        record = row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)
        record["sequence"] = 2
        result = verify_event_chain(TENANT, SESSION, [record])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "EVENT_SEQUENCE_GAP_OR_REORDER")

    def test_session_binding_fails(self):
        record = row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)
        record["session_id"] = "another-session"
        result = verify_event_chain(TENANT, SESSION, [record])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "SESSION_BINDING_MISMATCH")

    def test_empty_chain_fails_closed(self):
        result = verify_event_chain(TENANT, SESSION, [])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "EMPTY_EVENT_CHAIN")

    def test_invalid_tenant_and_blank_session_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TENANT_ID"):
            genesis_hash("not-a-uuid", SESSION)
        with self.assertRaisesRegex(ValueError, "INVALID_SESSION_ID"):
            genesis_hash(TENANT, "   ")

    def test_missing_field_unsupported_version_and_bad_hash_fail(self):
        valid = row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)
        for mutate, expected in (
            (lambda r: r.pop("actor"), "MISSING_CONTEXT"),
            (lambda r: r.update(hash_version="future"), "UNSUPPORTED_EVENT_HASH_VERSION"),
            (lambda r: r.update(entry_hash="bad"), "INVALID_STORED_ENTRY_HASH"),
        ):
            with self.subTest(expected=expected):
                record = copy.deepcopy(valid)
                mutate(record)
                result = verify_event_chain(TENANT, SESSION, [record])
                self.assertFalse(result["valid"])
                self.assertEqual(result["reason"], expected)

    def test_verifier_does_not_claim_external_anchor(self):
        result = verify_event_chain(TENANT, SESSION, [row(EVENT_1, EXPECTED_GENESIS, EXPECTED_EVENT_1)])
        self.assertTrue(result["valid"])
        self.assertNotIn("externally_anchored", result)


if __name__ == "__main__":
    unittest.main()

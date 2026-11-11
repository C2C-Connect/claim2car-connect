from __future__ import annotations

from hashlib import sha256

import pytest

from app.capture_protocols import (
    DEFAULT_CAPTURE_PROTOCOL,
    LEGACY_CAPTURE_PROTOCOL,
    resolve_capture_protocol,
)
from app.damage_localization import DamageLocalizationError, DamageRegion, PhysicsInputAdapter, zone_for_slot
from app.evidence_manifest import ManifestEntry, build_manifest, verify_manifest
from app.capture_workflow import CaptureWorkflow, LocalDraftStore

EXPECTED_16 = (
    "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior", "03_rear_right_exterior",
    "04_rear_exterior", "05_rear_left_exterior", "06_left_side_exterior", "07_front_left_exterior",
    "08_wheel_front_left", "09_wheel_front_right", "10_wheel_rear_right", "11_wheel_rear_left",
    "12_cabin_front_airbags", "13_instrument_cluster_odometer", "14_physical_vin",
    "15_license_and_insurance_docs",
)


def _entries(slots):
    return tuple(
        ManifestEntry(f"artifact-{index}", slot, sha256(f"bytes-{index}".encode()).hexdigest())
        for index, slot in enumerate(slots, start=1)
    )


def test_registry_loads_exact_owner_approved_16_v1_contract():
    protocol = resolve_capture_protocol(DEFAULT_CAPTURE_PROTOCOL)
    assert protocol.version == "claims2car-16-v1"
    assert protocol.status == "implemented"
    assert protocol.slots == EXPECTED_16
    assert len(protocol.descriptions) == 16


def test_legacy_12_v1_remains_selectable_and_unchanged():
    protocol = resolve_capture_protocol(LEGACY_CAPTURE_PROTOCOL)
    assert protocol.version == "claims2car-12-v1"
    assert protocol.status == "implemented"
    assert protocol.slots == (
        "vin_ocr", "doc_ocr", "front", "front_left", "driver_side", "rear_left",
        "rear", "rear_right", "passenger_side", "front_right", "interior_front",
        "undercarriage_engine",
    )


def test_new_capture_workflow_defaults_to_16_v1_and_legacy_is_explicit():
    current = CaptureWorkflow("session-16")
    legacy = CaptureWorkflow("session-12", protocol_version=LEGACY_CAPTURE_PROTOCOL)
    assert current.protocol_version == DEFAULT_CAPTURE_PROTOCOL
    assert current.pending_slots() == EXPECTED_16
    assert legacy.protocol_version == LEGACY_CAPTURE_PROTOCOL
    assert len(legacy.pending_slots()) == 12


def test_local_draft_store_defaults_to_16_v1_and_rejects_legacy_slot_aliases():
    draft = LocalDraftStore({})
    assert draft.protocol_version == DEFAULT_CAPTURE_PROTOCOL
    with pytest.raises(Exception, match="UNKNOWN_SLOT"):
        draft.save_artifact("s", "front", "a", "a" * 64, 1)
    draft.save_artifact("s", EXPECTED_16[0], "b", "b" * 64, 1)
    assert draft.resume()["capture_protocol_version"] == DEFAULT_CAPTURE_PROTOCOL


def test_manifest_digest_and_verification_bind_exact_protocol_version():
    slots16 = EXPECTED_16
    slots12 = resolve_capture_protocol(LEGACY_CAPTURE_PROTOCOL).slots
    manifest16 = build_manifest("session-16", _entries(slots16), DEFAULT_CAPTURE_PROTOCOL)
    manifest12 = build_manifest("session-12", _entries(slots12), LEGACY_CAPTURE_PROTOCOL)
    assert manifest16.shot_list_version == DEFAULT_CAPTURE_PROTOCOL
    assert manifest12.shot_list_version == LEGACY_CAPTURE_PROTOCOL
    assert len(manifest16.entries) == 16 and len(manifest12.entries) == 12
    bytes16 = {entry.artifact_id: f"bytes-{index}".encode() for index, entry in enumerate(manifest16.entries, start=1)}
    assert verify_manifest("session-16", manifest16, manifest16.digest(), bytes16)
    assert not verify_manifest("session-16", manifest12, manifest12.digest(), bytes16)


@pytest.mark.parametrize(
    ("slot", "zone"),
    [
        ("00_front_exterior", "front"),
        ("01_front_right_exterior", "front"),
        ("02_right_side_exterior", "side"),
        ("03_rear_right_exterior", "rear"),
        ("04_rear_exterior", "rear"),
        ("05_rear_left_exterior", "rear"),
        ("06_left_side_exterior", "side"),
        ("07_front_left_exterior", "front"),
    ],
)
def test_16_v1_exterior_slots_map_to_physics_zones(slot, zone):
    assert zone_for_slot(slot, DEFAULT_CAPTURE_PROTOCOL) == zone
    region = DamageRegion(slot, 0.1, 0.1, 0.4, 0.4, "dent", 0.9,
                          protocol_version=DEFAULT_CAPTURE_PROTOCOL)
    assert PhysicsInputAdapter().to_impact_geometry(region).zone == zone


@pytest.mark.parametrize("slot", EXPECTED_16[8:])
def test_16_v1_wheel_cabin_odometer_vin_and_documents_are_not_crush_physics(slot):
    assert zone_for_slot(slot, DEFAULT_CAPTURE_PROTOCOL) is None
    region = DamageRegion(slot, 0.1, 0.1, 0.4, 0.4, "dent", 0.9,
                          protocol_version=DEFAULT_CAPTURE_PROTOCOL)
    with pytest.raises(DamageLocalizationError, match="NOT_AN_EXTERIOR_SLOT"):
        PhysicsInputAdapter().to_impact_geometry(region)

"""Versioned capture contracts. Historical protocol IDs never change meaning."""
from dataclasses import dataclass
import json
from pathlib import Path

DEFAULT_CAPTURE_PROTOCOL = "claims2car-16-v1"
FAOS_CAPTURE_PROTOCOL = "claims2car-16-v2"
LEGACY_CAPTURE_PROTOCOL = "claims2car-12-v1"
SUPPORTED_PROTOCOL_IDS = frozenset({DEFAULT_CAPTURE_PROTOCOL, FAOS_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL})
ROOT = Path(__file__).resolve().parents[1]

CANONICAL_PROTOCOL_SLOTS = {
    DEFAULT_CAPTURE_PROTOCOL: (
        "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior", "03_rear_right_exterior",
        "04_rear_exterior", "05_rear_left_exterior", "06_left_side_exterior", "07_front_left_exterior",
        "08_wheel_front_left", "09_wheel_front_right", "10_wheel_rear_right", "11_wheel_rear_left",
        "12_cabin_front_airbags", "13_instrument_cluster_odometer", "14_physical_vin",
        "15_license_and_insurance_docs",
    ),
    FAOS_CAPTURE_PROTOCOL: (
        "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior", "03_rear_right_exterior",
        "04_rear_exterior", "05_rear_left_exterior", "06_left_side_exterior", "07_front_left_exterior",
        "08_front_left_structural", "09_front_right_structural", "10_rear_right_structural", "11_rear_left_structural",
        "12_front_cabin_restraints", "13_rear_cabin_restraints",
        "14_instrument_cluster_telemetry", "15_vehicle_identity_vin",
    ),
    LEGACY_CAPTURE_PROTOCOL: (
        "vin_ocr", "doc_ocr", "front", "front_left", "driver_side", "rear_left",
        "rear", "rear_right", "passenger_side", "front_right", "interior_front", "undercarriage_engine",
    ),
}

@dataclass(frozen=True)
class CaptureProtocol:
    version: str
    status: str
    slots: tuple[str, ...]
    descriptions: dict


def validate_protocol_version(version):
    if not isinstance(version, str) or version not in SUPPORTED_PROTOCOL_IDS:
        raise ValueError("UNSUPPORTED_CAPTURE_PROTOCOL")
    return version


def _load(path, version, expected_count, required_keys):
    contract = json.loads(path.read_text(encoding="utf-8"))
    slots = contract.get("required_angles") if isinstance(contract, dict) else None
    if (
        type(contract) is not dict
        or set(contract) != required_keys
        or contract.get("schema_version") != "0.1"
        or contract.get("shot_list_version") != version
        or type(slots) is not list
        or len(slots) != expected_count
        or len(set(slots)) != expected_count
        or any(not isinstance(slot, str) or not slot for slot in slots)
        or tuple(slots) != CANONICAL_PROTOCOL_SLOTS[version]
    ):
        raise ValueError("INVALID_CAPTURE_PROTOCOL_CONTRACT")
    descriptions = contract.get("descriptions") or {slot: slot.replace("_", " ").title() for slot in slots}
    if (
        type(descriptions) is not dict
        or set(descriptions) != set(slots)
        or any(not isinstance(label, str) or not label.strip() for label in descriptions.values())
    ):
        raise ValueError("INVALID_CAPTURE_PROTOCOL_DESCRIPTIONS")
    return CaptureProtocol(version, "implemented", tuple(slots), descriptions)


def resolve_capture_protocol(version=DEFAULT_CAPTURE_PROTOCOL):
    validate_protocol_version(version)
    if version == DEFAULT_CAPTURE_PROTOCOL:
        return _load(ROOT / "contracts" / "shot-list-16-v1.json", version, 16,
                     {"schema_version", "shot_list_version", "required_angles", "descriptions"})
    if version == FAOS_CAPTURE_PROTOCOL:
        return _load(ROOT / "contracts" / "shot-list-16-v2.json", version, 16,
                     {"schema_version", "shot_list_version", "required_angles", "descriptions"})
    legacy = _load(ROOT / "contracts" / "shot-list.json", version, 12,
                   {"schema_version", "shot_list_version", "required_angles"})
    return CaptureProtocol(legacy.version, legacy.status, legacy.slots,
                           {slot: slot.replace("_", " ").title() for slot in legacy.slots})


def require_implemented_protocol(version=DEFAULT_CAPTURE_PROTOCOL):
    return resolve_capture_protocol(version)


def protocol_registry():
    versions = (DEFAULT_CAPTURE_PROTOCOL, FAOS_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL)
    protocols = []
    for version in versions:
        protocol = resolve_capture_protocol(version)
        protocols.append({
            "version": version,
            "status": protocol.status,
            "capture_enabled": True,
            "slot_count": len(protocol.slots),
            "required_slots": list(protocol.slots),
            "slot_descriptions": protocol.descriptions,
        })
    return {"default_protocol_version": DEFAULT_CAPTURE_PROTOCOL, "protocols": protocols}

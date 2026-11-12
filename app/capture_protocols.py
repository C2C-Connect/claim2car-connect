"""Versioned, immutable capture protocol registry."""
from dataclasses import dataclass
import json
from pathlib import Path

DEFAULT_CAPTURE_PROTOCOL = "claims2car-16-v1"
LEGACY_CAPTURE_PROTOCOL = "claims2car-12-v1"
SUPPORTED_PROTOCOL_IDS = frozenset({DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL})
CANONICAL_PROTOCOL_SLOTS = {
    DEFAULT_CAPTURE_PROTOCOL: (
        "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior",
        "03_rear_right_exterior", "04_rear_exterior", "05_rear_left_exterior",
        "06_left_side_exterior", "07_front_left_exterior", "08_wheel_front_left",
        "09_wheel_front_right", "10_wheel_rear_right", "11_wheel_rear_left",
        "12_cabin_front_airbags", "13_instrument_cluster_odometer", "14_physical_vin",
        "15_license_and_insurance_docs",
    ),
    LEGACY_CAPTURE_PROTOCOL: (
        "vin_ocr", "doc_ocr", "front", "front_left", "driver_side", "rear_left",
        "rear", "rear_right", "passenger_side", "front_right", "interior_front",
        "undercarriage_engine",
    ),
}
ROOT = Path(__file__).resolve().parents[1]


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


def _load(path, expected_version, expected_count, required_keys):
    value = json.loads(path.read_text(encoding="utf-8"))
    if (type(value) is not dict or set(value) != required_keys
            or value["schema_version"] != "0.1"
            or value["shot_list_version"] != expected_version
            or type(value["required_angles"]) is not list
            or len(value["required_angles"]) != expected_count
            or len(set(value["required_angles"])) != expected_count
            or any(not isinstance(slot, str) or not slot for slot in value["required_angles"])
            or tuple(value["required_angles"]) != CANONICAL_PROTOCOL_SLOTS[expected_version]):
        raise ValueError("INVALID_CAPTURE_PROTOCOL_CONTRACT")
    descriptions = value.get("descriptions")
    if descriptions is None:
        descriptions = {slot: slot.replace("_", " ").title() for slot in value["required_angles"]}
    if type(descriptions) is not dict or set(descriptions) != set(value["required_angles"]):
        raise ValueError("INVALID_CAPTURE_PROTOCOL_DESCRIPTIONS")
    if any(not isinstance(label, str) or not label.strip() for label in descriptions.values()):
        raise ValueError("INVALID_CAPTURE_PROTOCOL_DESCRIPTIONS")
    return CaptureProtocol(expected_version, "implemented", tuple(value["required_angles"]), descriptions)


def resolve_capture_protocol(version=DEFAULT_CAPTURE_PROTOCOL):
    validate_protocol_version(version)
    if version == DEFAULT_CAPTURE_PROTOCOL:
        return _load(ROOT / "contracts" / "shot-list-16-v1.json",
                     DEFAULT_CAPTURE_PROTOCOL, 16,
                     {"schema_version", "shot_list_version", "required_angles", "descriptions"})
    legacy = _load(ROOT / "contracts" / "shot-list.json",
                   LEGACY_CAPTURE_PROTOCOL, 12,
                   {"schema_version", "shot_list_version", "required_angles"})
    return CaptureProtocol(legacy.version, legacy.status, legacy.slots,
                           {slot: slot.replace("_", " ").title() for slot in legacy.slots})


def require_implemented_protocol(version=DEFAULT_CAPTURE_PROTOCOL):
    return resolve_capture_protocol(version)


def protocol_registry():
    return {
        "default_protocol_version": DEFAULT_CAPTURE_PROTOCOL,
        "protocols": [
            {"version": DEFAULT_CAPTURE_PROTOCOL, "status": "implemented", "capture_enabled": True,
             "slot_count": 16, "slots": list(resolve_capture_protocol(DEFAULT_CAPTURE_PROTOCOL).slots)},
            {"version": LEGACY_CAPTURE_PROTOCOL, "status": "implemented", "capture_enabled": True,
             "slot_count": 12, "slots": list(resolve_capture_protocol(LEGACY_CAPTURE_PROTOCOL).slots)},
        ],
    }

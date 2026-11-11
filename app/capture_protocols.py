"""Versioned capture protocol registry.

The approved 16-v1 default is reserved as the new-session default, but its
slot contract is intentionally unavailable until the authoritative 16 slots
and order are approved. The historical 12-v1 contract remains executable.
"""
from dataclasses import dataclass
import json
from pathlib import Path

DEFAULT_CAPTURE_PROTOCOL = "claims2car-16-v1"
LEGACY_CAPTURE_PROTOCOL = "claims2car-12-v1"
SUPPORTED_PROTOCOL_IDS = frozenset({DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL})


@dataclass(frozen=True)
class CaptureProtocol:
    version: str
    status: str
    slots: tuple[str, ...]


def validate_protocol_version(version):
    if not isinstance(version, str) or version not in SUPPORTED_PROTOCOL_IDS:
        raise ValueError("UNSUPPORTED_CAPTURE_PROTOCOL")
    return version


def resolve_capture_protocol(version):
    validate_protocol_version(version)
    if version == DEFAULT_CAPTURE_PROTOCOL:
        return CaptureProtocol(version, "definition_pending", ())
    path = Path(__file__).resolve().parents[1] / "contracts" / "shot-list.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {"schema_version", "shot_list_version", "required_angles"}
    if (type(value) is not dict or set(value) != expected
            or value["schema_version"] != "0.1"
            or value["shot_list_version"] != LEGACY_CAPTURE_PROTOCOL
            or type(value["required_angles"]) is not list
            or len(value["required_angles"]) != 12
            or len(set(value["required_angles"])) != 12
            or any(not isinstance(slot, str) or not slot for slot in value["required_angles"])):
        raise ValueError("INVALID_LEGACY_CAPTURE_PROTOCOL_CONTRACT")
    return CaptureProtocol(version, "implemented", tuple(value["required_angles"]))


def require_implemented_protocol(version):
    protocol = resolve_capture_protocol(version)
    if protocol.status != "implemented":
        raise ValueError("CAPTURE_PROTOCOL_DEFINITION_PENDING")
    return protocol

"""Consent-gated NHTSA vPIC decoder with explicit attribute provenance.

This adapter performs no work at import time and stores no raw VIN or raw
provider response. Callers must establish and re-check the owner's separate
vehicle-decoding consent before and after the external request. A successful
decode is vehicle-description data, not proof of ownership, physical condition,
curb mass, or eligibility for physics calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.vin_guard import validate_vin

VPIC_PROVIDER = "NHTSA_VPIC"
VPIC_API = "DecodeVinValuesExtended"
VPIC_ENDPOINT = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/"
MAX_RESPONSE_BYTES = 262_144
DEFAULT_TIMEOUT_SECONDS = 8.0

# Values are normalized only when the provider supplies them. No defaults are
# inferred from model year, make, model, or trim.
ATTRIBUTE_FIELDS = {
    "make": "Make",
    "model": "Model",
    "model_year": "ModelYear",
    "trim": "Trim",
    "series": "Series",
    "body_class": "BodyClass",
    "vehicle_type": "VehicleType",
    "drive_type": "DriveType",
    "engine_cylinders": "EngineCylinders",
    "displacement_l": "DisplacementL",
    "fuel_type_primary": "FuelTypePrimary",
    "gvwr": "GVWR",
    "curb_weight_lb": "CurbWeightLB",
}


class VpicDecodeError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VpicProfile:
    status: str
    provider: str
    provider_api: str
    requested_at: str
    response_sha256: str
    attributes: dict
    decode_error_code: str | None
    physics_input_eligibility: str = "NOT_ESTABLISHED"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "provider": self.provider,
            "provider_api": self.provider_api,
            "requested_at": self.requested_at,
            "response_sha256": self.response_sha256,
            "attributes": self.attributes,
            "decode_error_code": self.decode_error_code,
            "physics_input_eligibility": self.physics_input_eligibility,
        }


def _clean(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() in {
        "unknown", "not applicable", "not available", "n/a", "null",
    }:
        return None
    return value


def _attribute_value(name, raw):
    value = _clean(raw)
    if value is None:
        return None
    if name == "model_year":
        if not value.isdigit() or len(value) != 4:
            return None
        year = int(value)
        return year if 1886 <= year <= datetime.now(timezone.utc).year + 2 else None
    if name == "engine_cylinders":
        try:
            number = int(value)
        except ValueError:
            return None
        return number if 0 < number <= 16 else None
    if name == "displacement_l":
        try:
            number = float(value)
        except ValueError:
            return None
        return number if 0 < number <= 20 else None
    if name in ("gvwr", "curb_weight_lb"):
        # Preserve the provider's unit and value. Never relabel GVWR as curb
        # mass or promote either value into a physics input in this adapter.
        try:
            number = float(value.replace(",", ""))
        except ValueError:
            return None
        return number if 0 < number <= 100_000 else None
    return value[:200]


def parse_vpic_payload(requested_vin: str, payload: dict, *, requested_at: str | None = None) -> VpicProfile:
    validation = validate_vin(requested_vin)
    if not validation.ok or validation.normalization_changed or validation.vin != requested_vin:
        raise VpicDecodeError("VIN_VALIDATION_FAILED")
    if type(payload) is not dict or len(json.dumps(payload, separators=(",", ":"))) > MAX_RESPONSE_BYTES:
        raise VpicDecodeError("INVALID_PROVIDER_RESPONSE")
    rows = payload.get("Results")
    if payload.get("Count") != 1 or not isinstance(rows, list) or len(rows) != 1 or type(rows[0]) is not dict:
        raise VpicDecodeError("INVALID_PROVIDER_RESPONSE")
    row = rows[0]
    returned_vin = _clean(row.get("VIN"))
    if returned_vin is None or returned_vin.upper() != validation.vin:
        raise VpicDecodeError("PROVIDER_VIN_MISMATCH")
    error_code = _clean(row.get("ErrorCode"))
    if error_code != "0":
        raise VpicDecodeError("PROVIDER_DECODE_UNRESOLVED")
    if _clean(row.get("SuggestedVIN")):
        raise VpicDecodeError("PROVIDER_SUGGESTED_VIN_REQUIRES_REVIEW")

    attributes = {}
    for name, provider_field in ATTRIBUTE_FIELDS.items():
        value = _attribute_value(name, row.get(provider_field))
        attributes[name] = {
            "value": value,
            "status": "REPORTED" if value is not None else "UNAVAILABLE",
            "source": VPIC_PROVIDER,
            "source_field": provider_field,
            "unit": "lb" if name == "curb_weight_lb" else ("provider_reported" if name == "gvwr" else None),
        }
    required = ("make", "model", "model_year")
    status = "DECODED" if all(attributes[key]["value"] is not None for key in required) else "PARTIAL"
    # The provider response contains the raw VIN. Hash a redacted copy so
    # the retained digest cannot be used as an offline VIN-guessing oracle.
    redacted_payload = dict(payload)
    redacted_payload["Results"] = [
        {key: value for key, value in row.items() if key not in ("VIN", "SuggestedVIN")}
    ]
    canonical = json.dumps(redacted_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    timestamp = requested_at or datetime.now(timezone.utc).isoformat()
    return VpicProfile(
        status=status,
        provider=VPIC_PROVIDER,
        provider_api=VPIC_API,
        requested_at=timestamp,
        response_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        attributes=attributes,
        decode_error_code=error_code,
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VpicClient:
    """Fixed-host, bounded NHTSA transport. No credentials or caller URL."""

    def __init__(self, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                 fetcher: Callable | None = None):
        if not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 30:
            raise ValueError("INVALID_VPIC_TIMEOUT")
        self.timeout_seconds = float(timeout_seconds)
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str, timeout: float):
        opener = build_opener(_NoRedirect())
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read(MAX_RESPONSE_BYTES + 1)

    def decode(self, vin: str, *, requested_at: str | None = None) -> VpicProfile:
        requested_at = requested_at or datetime.now(timezone.utc).isoformat()
        validation = validate_vin(vin)
        if not validation.ok or validation.normalization_changed or validation.vin != vin:
            raise VpicDecodeError("VIN_VALIDATION_FAILED")
        url = VPIC_ENDPOINT + validation.vin + "?format=json"
        try:
            status, content_type, body = self._fetcher(url, self.timeout_seconds)
        except HTTPError as error:
            raise VpicDecodeError("PROVIDER_HTTP_ERROR") from error
        except (URLError, TimeoutError, OSError):
            raise VpicDecodeError("PROVIDER_UNAVAILABLE") from None
        if status != 200:
            raise VpicDecodeError("PROVIDER_HTTP_ERROR")
        if not isinstance(content_type, str) or "application/json" not in content_type.lower():
            raise VpicDecodeError("INVALID_PROVIDER_CONTENT_TYPE")
        if not isinstance(body, (bytes, bytearray)) or not body or len(body) > MAX_RESPONSE_BYTES:
            raise VpicDecodeError("PROVIDER_RESPONSE_SIZE_INVALID")
        try:
            payload = json.loads(bytes(body).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise VpicDecodeError("INVALID_PROVIDER_RESPONSE") from None
        return parse_vpic_payload(vin, payload, requested_at=requested_at)

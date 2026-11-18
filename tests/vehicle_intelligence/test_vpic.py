from __future__ import annotations

import hashlib
import json
import pytest

from backend.app.vehicle_intelligence.vpic import (
    VPIC_ENDPOINT,
    VpicClient,
    VpicDecodeError,
    parse_vpic_payload,
)

VIN = "1HGCM82633A004352"


def provider_row(**overrides):
    row = {
        "VIN": VIN,
        "ErrorCode": "0",
        "SuggestedVIN": "",
        "Make": "HONDA",
        "Model": "Accord",
        "ModelYear": "2003",
        "Trim": "EX",
        "Series": "",
        "BodyClass": "Sedan",
        "VehicleType": "PASSENGER CAR",
        "DriveType": "4x2",
        "EngineCylinders": "4",
        "DisplacementL": "2.4",
        "FuelTypePrimary": "Gasoline",
        "GVWR": "CLASS 1: 6,000 lb or less",
        "CurbWeightLB": "",
    }
    row.update(overrides)
    return row


def payload(**overrides):
    return {"Count": 1, "Results": [provider_row(**overrides)]}


def test_valid_response_is_source_attributed_and_never_physics_ready():
    profile = parse_vpic_payload(VIN, payload(), requested_at="2026-11-18T12:00:00+00:00")
    assert profile.status == "DECODED"
    assert profile.provider == "NHTSA_VPIC"
    assert profile.provider_api == "DecodeVinValuesExtended"
    assert profile.attributes["make"]["value"] == "HONDA"
    assert profile.attributes["model_year"]["value"] == 2003
    assert profile.attributes["make"]["source"] == "NHTSA_VPIC"
    assert profile.attributes["curb_weight_lb"]["status"] == "UNAVAILABLE"
    assert profile.attributes["gvwr"]["value"] == "CLASS 1: 6,000 lb or less"
    assert profile.physics_input_eligibility == "NOT_ESTABLISHED"
    assert "vin" not in profile.to_dict()
    assert len(profile.response_sha256) == 64
    redacted = {
        "Count": 1,
        "Results": [{key: value for key, value in provider_row().items()
                     if key not in ("VIN", "SuggestedVIN")}],
    }
    canonical = json.dumps(redacted, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert profile.response_sha256 == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_missing_fields_are_unknown_not_filled_from_defaults():
    profile = parse_vpic_payload(VIN, payload(Make="", Model="", ModelYear=""))
    assert profile.status == "PARTIAL"
    assert profile.attributes["make"]["value"] is None
    assert profile.attributes["model"]["value"] is None
    assert profile.attributes["model_year"]["value"] is None
    assert profile.attributes["curb_weight_lb"]["value"] is None


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"VIN": "1M8GDM9AXKP042788"}, "PROVIDER_VIN_MISMATCH"),
        ({"ErrorCode": "7"}, "PROVIDER_DECODE_UNRESOLVED"),
        ({"SuggestedVIN": "1HGCM82633A004353"}, "PROVIDER_SUGGESTED_VIN_REQUIRES_REVIEW"),
    ],
)
def test_provider_identity_or_decode_errors_fail_closed(changes, code):
    with pytest.raises(VpicDecodeError, match=code):
        parse_vpic_payload(VIN, payload(**changes))


def test_invalid_vin_is_rejected_before_transport():
    calls = []
    client = VpicClient(fetcher=lambda *args: calls.append(args))
    with pytest.raises(VpicDecodeError, match="VIN_VALIDATION_FAILED"):
        client.decode("not-a-vin")
    assert calls == []


def test_transport_uses_only_fixed_nhtsa_endpoint_and_bounded_timeout():
    calls = []

    def fetch(url, timeout):
        calls.append((url, timeout))
        return 200, "application/json; charset=utf-8", json.dumps(payload()).encode()

    profile = VpicClient(timeout_seconds=4, fetcher=fetch).decode(VIN)
    assert profile.status == "DECODED"
    assert calls == [(VPIC_ENDPOINT + VIN + "?format=json", 4.0)]


@pytest.mark.parametrize(
    ("status", "content_type", "body", "code"),
    [
        (503, "application/json", b"{}", "PROVIDER_HTTP_ERROR"),
        (200, "text/html", b"{}", "INVALID_PROVIDER_CONTENT_TYPE"),
        (200, "application/json", b"x" * 262145, "PROVIDER_RESPONSE_SIZE_INVALID"),
        (200, "application/json", b"{", "INVALID_PROVIDER_RESPONSE"),
    ],
)
def test_transport_rejects_invalid_provider_responses(status, content_type, body, code):
    client = VpicClient(fetcher=lambda *_: (status, content_type, body))
    with pytest.raises(VpicDecodeError, match=code):
        client.decode(VIN)


def test_provider_unavailable_is_explicit():
    def unavailable(*_):
        raise TimeoutError()
    with pytest.raises(VpicDecodeError, match="PROVIDER_UNAVAILABLE"):
        VpicClient(fetcher=unavailable).decode(VIN)


def test_provider_profile_contains_no_raw_provider_row():
    profile = parse_vpic_payload(VIN, payload())
    serialized = json.dumps(profile.to_dict())
    assert VIN not in serialized
    assert "rawResult" not in serialized

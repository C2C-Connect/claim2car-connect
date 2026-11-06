"""Server-side VIN format and check-digit guard (plan v1.3 phase 5).

Python port of frontend/src/modules/capture/vin.mjs — identical semantics,
weights, failure codes and messages, so client and server reject the same
inputs. Not a vehicle decoder or authenticity proof: a passing check digit
asserts format only. Failures return the exact recapture message and an
uncertainty record; nothing is ever repaired or transliterated.
"""
from dataclasses import dataclass
from typing import Optional

VIN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
_VALUES = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
MESSAGE = "VIN VALIDATION FAILED: Recapture VIN Plate"
SCOPE = "format-and-check-digit-only"


@dataclass(frozen=True)
class VinReport:
    """Immutable result. `ok` asserts format only — never decoded identity."""
    ok: bool
    reason: Optional[str]
    message: Optional[str]
    scope: str
    raw_vin: Optional[str]
    vin: Optional[str]
    normalization_changed: bool
    expected_check_digit: Optional[str]
    received_check_digit: Optional[str]
    # Uncertainty handling (plan v1.3 phase 5): a failure is recorded as an
    # explicit uncertainty, never silently repaired or retried server-side.
    uncertainty_code: Optional[str]
    recapture_required: bool


def _fail(reason, raw_vin, vin, expected_check_digit=None):
    return VinReport(
        ok=False,
        reason=reason,
        message=MESSAGE,
        scope=SCOPE,
        raw_vin=raw_vin,
        vin=vin,
        normalization_changed=raw_vin is not None and vin is not None and raw_vin != vin,
        expected_check_digit=expected_check_digit,
        received_check_digit=vin[8] if isinstance(vin, str) and len(vin) == 17 else None,
        uncertainty_code=reason,
        recapture_required=True,
    )


def validate_vin(input_value):
    """Validate VIN format + ISO 3779 check digit. No repair, no decode."""
    if not isinstance(input_value, str):
        return _fail("INVALID_INPUT", None, None)
    raw = input_value if len(input_value) <= 256 else None
    if len(input_value) > 256:
        return _fail("INPUT_TOO_LONG", None, None)
    # Unicode lookalikes are rejected, never transliterated to ASCII.
    if any(ord(ch) > 127 for ch in input_value):
        return _fail("ILLEGAL_CHARACTERS", raw, None)
    vin = "".join(ch for ch in input_value if ch.isalnum()).upper()
    if len(vin) != 17:
        return _fail("INVALID_LENGTH", raw, vin if len(vin) == 17 else vin)
    if not all(ch.isdigit() or ch in _VALUES for ch in vin):
        return _fail("ILLEGAL_CHARACTERS", raw, vin)
    total = sum(
        (int(ch) if ch.isdigit() else _VALUES[ch]) * VIN_WEIGHTS[i]
        for i, ch in enumerate(vin)
    )
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    if vin[8] != expected:
        return _fail("CHECKSUM_MISMATCH", raw, vin, expected)
    return VinReport(
        ok=True,
        reason=None,
        message=None,
        scope=SCOPE,
        raw_vin=raw,
        vin=vin,
        normalization_changed=raw != vin,
        expected_check_digit=expected,
        received_check_digit=vin[8],
        uncertainty_code=None,
        recapture_required=False,
    )

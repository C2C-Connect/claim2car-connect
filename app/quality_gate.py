"""On-device pre-inference capture quality gate (InputGuard pattern; Slice 8).

Published 2026 work on pre-inference quality gating (blur, exposure, and
artifact checks run before any downstream model) reports 79.9–88.0% fewer
erroneous downstream AI decisions at under 35 ms and under 4.8 MB on
mid-range devices. This module lands that *pattern* behind our existing
QUALITY_RECORDED contract:

- ``HeuristicQualityGate`` is the pure-Python reference gate (runs
  everywhere, including CI, with zero dependencies). It is deterministic
  and never repairs or retries anything — verdicts only.
- ``OnnxQualityGate`` is the deployment seam for a real on-device runtime
  (ONNX Runtime Mobile on the capture device; LiteRT for the Android
  shell). It implements the same interface and is selected when a model
  is configured; the heuristic gate remains the fallback and the parity
  reference.

The gate NEVER auto-repairs, never re-captures, and never decides
anything downstream: it produces per-slot verdicts that the operator sees
and that ``CaptureWorkflow.record_quality`` records. Failed slots are the
operator's retake decision, per the frozen m1-v1 retake semantics.

All thresholds are provisional constants (documented in SPEC_DECISIONS)
pending calibration against real device captures.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GATE_VERSION = "quality-gate-v1"

# Provisional thresholds (calibration against real captures pending).
BLUR_VARIANCE_MIN = 10.0        # variance of Laplacian response below this = blurry
CLIPPED_FRACTION_MAX = 0.10     # fraction of near-black/near-white pixels above this = bad exposure
UNIFORM_FRACTION_MAX = 0.60     # single value covering more than this = occluded/flat frame
FLAT_DYNAMIC_RANGE_MIN = 16     # max-min grayscale spread below this = flat frame


class QualityGateError(ValueError):
    """Stable-code gate failures. Codes are API surface."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    metric: float
    threshold: float
    detail: str = ""


@dataclass(frozen=True)
class SlotVerdict:
    slot: str
    artifact_id: str
    passed: bool
    checks: tuple[CheckResult, ...]
    gate_version: str = GATE_VERSION


def _validate_pixels(pixels) -> None:
    if (not isinstance(pixels, (list, tuple)) or not pixels
            or not all(isinstance(r, (list, tuple)) and r for r in pixels)):
        raise QualityGateError("INVALID_PIXELS", "nonempty 2D grayscale grid required")
    width = len(pixels[0])
    if any(len(r) != width for r in pixels):
        raise QualityGateError("INVALID_PIXELS", "rows must share one width")
    flat = [v for r in pixels for v in r]
    if not all(isinstance(v, int) and 0 <= v <= 255 for v in flat):
        raise QualityGateError("INVALID_PIXELS", "values must be ints 0-255")


def _laplacian_variance(pixels) -> float:
    """Variance of the 4-neighbour Laplacian response (blur metric)."""
    height, width = len(pixels), len(pixels[0])
    if height < 3 or width < 3:
        return 0.0
    responses = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            responses.append(
                pixels[y][x - 1] + pixels[y][x + 1]
                + pixels[y - 1][x] + pixels[y + 1][x]
                - 4 * pixels[y][x]
            )
    if not responses:
        return 0.0
    mean = sum(responses) / len(responses)
    return sum((r - mean) ** 2 for r in responses) / len(responses)


def _clipped_fraction(pixels) -> float:
    flat = [v for r in pixels for v in r]
    clipped = sum(1 for v in flat if v <= 8 or v >= 247)
    return clipped / len(flat)


def _uniform_fraction(pixels) -> float:
    """Fraction of the frame covered by the single most common value."""
    counts: dict[int, int] = {}
    for r in pixels:
        for v in r:
            counts[v] = counts.get(v, 0) + 1
    total = sum(counts.values())
    return max(counts.values()) / total if total else 0.0


def _dynamic_range(pixels) -> int:
    flat = [v for r in pixels for v in r]
    return max(flat) - min(flat)


class HeuristicQualityGate:
    """Reference pre-inference gate: blur, exposure, occlusion, flatness.

    Deterministic, dependency-free, synthetic-safe. The same verdict shape
    is produced by the ONNX runtime backend when one is deployed.
    """

    gate_version = GATE_VERSION

    def evaluate(self, slot: str, artifact_id: str, pixels) -> SlotVerdict:
        if not isinstance(slot, str) or not slot.strip():
            raise QualityGateError("INVALID_SLOT")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise QualityGateError("INVALID_ARTIFACT_ID")
        _validate_pixels(pixels)
        blur = _laplacian_variance(pixels)
        clipped = _clipped_fraction(pixels)
        uniform = _uniform_fraction(pixels)
        dynamic = _dynamic_range(pixels)
        checks = (
            CheckResult("blur", blur >= BLUR_VARIANCE_MIN, round(blur, 4), BLUR_VARIANCE_MIN,
                        "variance of Laplacian response"),
            CheckResult("exposure", clipped <= CLIPPED_FRACTION_MAX, round(clipped, 4), CLIPPED_FRACTION_MAX,
                        "fraction of clipped (near-black/near-white) pixels"),
            CheckResult("occlusion", uniform <= UNIFORM_FRACTION_MAX, round(uniform, 4), UNIFORM_FRACTION_MAX,
                        "fraction of frame covered by the modal value"),
            CheckResult("flatness", dynamic >= FLAT_DYNAMIC_RANGE_MIN, float(dynamic), float(FLAT_DYNAMIC_RANGE_MIN),
                        "grayscale dynamic range"),
        )
        return SlotVerdict(slot, artifact_id, all(c.passed for c in checks), checks)

    def evaluate_all(self, artifacts) -> tuple[SlotVerdict, ...]:
        """artifacts: mapping slot -> (artifact_id, pixels). One verdict per slot."""
        if not isinstance(artifacts, dict) or not artifacts:
            raise QualityGateError("INVALID_ARTIFACT_SET")
        return tuple(self.evaluate(slot, aid, pixels) for slot, (aid, pixels) in artifacts.items())

    @staticmethod
    def passed_verdicts(verdicts) -> dict:
        """Workflow-compatible {slot: bool} mapping from gate verdicts."""
        return {v.slot: v.passed for v in verdicts}

    @staticmethod
    def gate_metadata(verdicts) -> dict:
        """Structured summary embedded in the QUALITY_RECORDED payload."""
        return {
            "gate_version": GATE_VERSION,
            "checks": {
                v.slot: {c.name: {"passed": c.passed, "metric": c.metric, "threshold": c.threshold}
                         for c in v.checks}
                for v in verdicts
            },
        }


class OnnxQualityGate:
    """Deployment seam for a trained on-device gate model (ONNX Runtime).

    The device runtime (ONNX Runtime Mobile or LiteRT on the capture
    shell) executes the trained model; this class is the server-side
    parity reference and integration seam. It requires ``onnxruntime``
    and a model file, neither of which ships with the repository. The
    heuristic gate stays the default until a model is calibrated against
    real captures and beats it on our own labeled set (same adoption rule
    as CV damage localization).
    """

    gate_version = GATE_VERSION + "+onnx"

    def __init__(self, model_path: str):
        try:
            import onnxruntime  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only with the dep absent
            raise QualityGateError("ONNX_RUNTIME_UNAVAILABLE",
                                   "onnxruntime is not installed; the heuristic gate is the reference") from exc
        from pathlib import Path

        path = Path(model_path)
        if not path.is_file():
            raise QualityGateError("ONNX_MODEL_NOT_FOUND", str(path))
        self._model_path = str(path)

    def evaluate(self, slot: str, artifact_id: str, pixels) -> SlotVerdict:  # pragma: no cover
        raise QualityGateError("ONNX_EVALUATION_NOT_IMPLEMENTED",
                               "wire to the calibrated model's input/output contract before use")


def load_gate(model_path: str | None = None):
    """Factory: ONNX backend when a model is configured, heuristic otherwise."""
    if model_path:
        return OnnxQualityGate(model_path)
    return HeuristicQualityGate()

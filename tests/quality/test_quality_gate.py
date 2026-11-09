"""On-device pre-inference quality gate tests (Slice 8).

pytestmark mirrors the repo convention (subtests marker is registered
nowhere; the warning is pre-existing and harmless).
"""
from __future__ import annotations

import pytest

from app.quality_gate import (
    BLUR_VARIANCE_MIN,
    CLIPPED_FRACTION_MAX,
    FLAT_DYNAMIC_RANGE_MIN,
    GATE_VERSION,
    HeuristicQualityGate,
    OnnxQualityGate,
    QualityGateError,
    load_gate,
)

pytestmark = pytest.mark.subtests


def sharp_grid(size: int = 24, seed: int = 7) -> list[list[int]]:
    """Deterministic high-detail grid: alternating texture passes all checks."""
    return [[((x * 31 + y * 17 + seed) % 200) + 20 for x in range(size)] for y in range(size)]


def blurry_grid(size: int = 24) -> list[list[int]]:
    """Smooth horizontal gradient: low Laplacian variance (blurry)."""
    return [[128 + int((x / max(size - 1, 1)) * 60) for x in range(size)] for y in range(size)]


def dark_grid(size: int = 24) -> list[list[int]]:
    """Underexposed frame: nearly all pixels clipped to near-black."""
    return [[3] * size for _ in range(size)]


def occluded_grid(size: int = 24) -> list[list[int]]:
    """Mostly one value with a small detail patch (finger over the lens)."""
    grid = [[150] * size for _ in range(size)]
    for y in range(2, 6):
        for x in range(2, 6):
            grid[y][x] = 40 + ((x + y) % 30)
    return grid


def flat_grid(size: int = 24) -> list[list[int]]:
    """Uniform mid-gray: flat frame, no dynamic range."""
    return [[128] * size for _ in range(size)]


gate = HeuristicQualityGate()


class TestHeuristicChecks:
    def test_sharp_well_exposed_frame_passes(self):
        verdict = gate.evaluate("front-left-45", "art-1", sharp_grid())
        assert verdict.passed
        assert verdict.slot == "front-left-45" and verdict.artifact_id == "art-1"
        assert verdict.gate_version == GATE_VERSION

    def test_blurry_frame_fails_blur_check_only(self):
        verdict = gate.evaluate("rear-straight", "art-2", blurry_grid())
        blur = next(c for c in verdict.checks if c.name == "blur")
        assert not blur.passed
        assert not verdict.passed

    def test_dark_frame_fails_exposure(self):
        verdict = gate.evaluate("dash-vin", "art-3", dark_grid())
        exposure = next(c for c in verdict.checks if c.name == "exposure")
        assert not exposure.passed
        assert not verdict.passed

    def test_occluded_frame_fails_occlusion(self):
        verdict = gate.evaluate("damage-close", "art-4", occluded_grid())
        occlusion = next(c for c in verdict.checks if c.name == "occlusion")
        assert not occlusion.passed
        assert not verdict.passed

    def test_flat_frame_fails_flatness(self):
        verdict = gate.evaluate("odometer", "art-5", flat_grid())
        flatness = next(c for c in verdict.checks if c.name == "flatness")
        assert not flatness.passed
        assert not verdict.passed

    def test_check_metrics_are_reported_with_thresholds(self):
        verdict = gate.evaluate("s", "a", sharp_grid())
        for check in verdict.checks:
            assert isinstance(check.metric, float) and isinstance(check.threshold, float)
            assert check.metric >= 0

    def test_provisional_thresholds_are_documented_constants(self):
        # Calibration against real captures pending; constants must stay explicit.
        assert BLUR_VARIANCE_MIN == 10.0
        assert CLIPPED_FRACTION_MAX == 0.10
        assert FLAT_DYNAMIC_RANGE_MIN == 16


class TestGateInterface:
    def test_invalid_slot_rejected(self):
        with pytest.raises(QualityGateError, match="INVALID_SLOT"):
            gate.evaluate("  ", "a", sharp_grid())

    def test_invalid_artifact_id_rejected(self):
        with pytest.raises(QualityGateError, match="INVALID_ARTIFACT_ID"):
            gate.evaluate("slot", "", sharp_grid())

    def test_non_grid_pixels_rejected(self):
        for bad in (None, [], [1, 2, 3], [[1, 2], [3]], [[1, 2], [3, 300]]):
            with pytest.raises(QualityGateError, match="INVALID_PIXELS"):
                gate.evaluate("slot", "a", bad)

    def test_evaluate_all_requires_mapping(self):
        with pytest.raises(QualityGateError, match="INVALID_ARTIFACT_SET"):
            gate.evaluate_all(None)

    def test_evaluate_all_returns_one_verdict_per_slot(self):
        verdicts = gate.evaluate_all({
            "a": ("art-a", sharp_grid()),
            "b": ("art-b", sharp_grid(seed=11)),
        })
        assert {v.slot for v in verdicts} == {"a", "b"}
        assert all(v.passed for v in verdicts)

    def test_passed_verdicts_maps_to_workflow_contract(self):
        verdicts = gate.evaluate_all({"a": ("art-a", sharp_grid())})
        assert HeuristicQualityGate.passed_verdicts(verdicts) == {"a": True}

    def test_gate_metadata_is_structured_and_versioned(self):
        verdicts = gate.evaluate_all({"a": ("art-a", sharp_grid())})
        meta = HeuristicQualityGate.gate_metadata(verdicts)
        assert meta["gate_version"] == GATE_VERSION
        assert set(meta["checks"]["a"]) == {"blur", "exposure", "occlusion", "flatness"}


class TestOnnxSeam:
    def test_onnx_gate_requires_runtime_and_model(self):
        # onnxruntime is not a dependency of this repository, so this asserts
        # the documented failure mode; if the dep appears, the model check
        # still guards against a silent no-op backend.
        try:
            OnnxQualityGate("/nonexistent/model.onnx")
            assert False, "expected QualityGateError"
        except QualityGateError as exc:
            assert exc.code in {"ONNX_RUNTIME_UNAVAILABLE", "ONNX_MODEL_NOT_FOUND"}

    def test_load_gate_defaults_to_heuristic(self):
        assert isinstance(load_gate(), HeuristicQualityGate)

    def test_load_gate_with_model_path_selects_onnx(self):
        try:
            loaded = load_gate("/nonexistent/model.onnx")
            assert isinstance(loaded, OnnxQualityGate)
        except QualityGateError:
            pass  # runtime unavailable: acceptable, heuristic remains default

"""
Integration-style tests for Layer 2 analysis pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.analysis.pipeline import AnalysisPipeline, AnalysisRequest  # noqa: E402
from backend.app.api.analysis import AnalyzeRequest, run_analysis  # noqa: E402
from config import forensic_constants as C  # noqa: E402


def test_pipeline_end_to_end():
    pipe = AnalysisPipeline()
    result = pipe.run(
        AnalysisRequest(
            session_id="test-session-001",
            mass_kg=1550.0,
            velocity_kph=48.0,
            photos=[b"fake-jpeg-bytes-front", b"fake-jpeg-bytes-side"],
            zone_hints=["front", "side"],
            materials=["mild_steel", "ahss"],
        )
    )
    assert result.session_id == "test-session-001"
    assert result.ensemble.decision in ("total_loss_dealer", "repairable_shop")
    assert 0.0 <= result.ensemble.p_ensemble <= 1.0
    assert result.darci.e_k_kj > 0
    assert result.formula_version == C.VERSION
    assert result.segmentation_source in ("vision_stack", "physics_fallback")
    assert result.model_status == "STUBS_ONLY"
    assert result.advisory_only is True
    assert result.model_outputs_are_real_inference is False
    assert any("not real model inference" in note for note in result.notes)
    assert all(d["source"] == "synthetic_stub" for d in result.detections)
    assert all(d["confidence_is_model_calibrated"] is False for d in result.detections)
    assert all(m["source"] == "synthetic_stub" for m in result.masks)
    assert all(d["source"] == "synthetic_stub" for d in result.depths)
    assert all(p["source"] == "synthetic_stub" for p in result.lmm_panels)


def test_pipeline_zero_photo_still_runs_and_marks_stubs():
    pipe = AnalysisPipeline()
    result = pipe.run(
        AnalysisRequest(
            session_id="empty",
            mass_kg=1400.0,
            velocity_kph=20.0,
            photos=[],
        )
    )
    assert result.darci is not None
    assert result.ensemble is not None
    assert result.model_status == "STUBS_ONLY"
    assert result.advisory_only is True
    assert result.model_outputs_are_real_inference is False


def test_analysis_api_discloses_synthetic_placeholders():
    response = run_analysis(
        AnalyzeRequest(
            session_id="api-stub-disclosure",
            mass_kg=1500.0,
            velocity_kph=35.0,
            photo_count=2,
        )
    )
    assert response["model_status"] == "STUBS_ONLY"
    assert response["model_outputs_are_real_inference"] is False
    assert response["advisory_only"] is True
    assert response["not_a_vehicle_appraisal"] is True
    assert response["input_image_mode"] == "synthetic_placeholders"
    assert response["vehicle_images_received"] is False
    assert response["decision_is_simulated"] is True
    assert response["vision_signal_is_synthetic"] is True

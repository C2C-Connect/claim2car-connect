"""
Integration-style tests for Layer 2 analysis pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.analysis.pipeline import AnalysisPipeline, AnalysisRequest  # noqa: E402
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


def test_pipeline_zero_photo_still_runs():
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

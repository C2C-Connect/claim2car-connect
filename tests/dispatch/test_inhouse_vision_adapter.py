from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from app.damage_localization import DamageAnnotation, DamageRegion
from backend.app.vision.adapters import (
    AdvisoryVisionAnalysis,
    GatedVisionPhysicsPipeline,
    LocalYoloTwoStageDetector,
    VisionAdapterError,
    compute_weight_provenance,
)


class InHouseVisionAdapterTests(unittest.TestCase):
    def test_weight_provenance_is_sha256_of_local_file(self):
        weights = Path(__file__).parents[1] / "fixtures" / "vision" / "weights-digest-fixture.txt"
        provenance = compute_weight_provenance("damage-test", "damage", weights)
        self.assertEqual(provenance.sha256_hex, hashlib.sha256(weights.read_bytes()).hexdigest())
        self.assertEqual(provenance.stage, "damage")

    def test_detector_normalizes_boxes_and_labels(self):
        detector = LocalYoloTwoStageDetector(
            inference_runner=lambda _slot, _img: [
                {"x1": 0.1, "y1": 0.2, "x2": 0.4, "y2": 0.6, "label": "major_dent", "confidence": 0.95},
                {"x1": 0.1, "y1": 0.2, "x2": 0.4, "y2": 0.6, "label": "dent", "confidence": 0.1},
            ]
        )
        detected = detector.detect("front_left", object())
        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0].damage_class, "structural_deformation")
        self.assertEqual((detected[0].x0, detected[0].y0, detected[0].x1, detected[0].y1), (0.1, 0.2, 0.4, 0.6))

    def test_candidate_stays_unpromoted_without_minimum_review_labels(self):
        region = DamageRegion(
            slot="front_left", x0=0.32, y0=0.32, x1=0.52, y1=0.52,
            damage_class="structural_deformation", confidence=1.0,
        )
        annotation = DamageAnnotation(
            session_id="session-1", slot="front_left", region=region, annotated_by="reviewer-1"
        )
        detector = LocalYoloTwoStageDetector(
            inference_runner=lambda _slot, _img: [
                {"x1": 0.32, "y1": 0.32, "x2": 0.52, "y2": 0.52, "label": "major_dent", "confidence": 0.95}
            ]
        )
        output = GatedVisionPhysicsPipeline(candidate_detector=detector).evaluate_and_extract_physics(
            session_id="session-1", slot="front_left", grid_fixture=[[90] * 36 for _ in range(36)],
            ground_truth_annotations=[annotation],
        )
        self.assertFalse(output.promoted_over_baseline)
        self.assertTrue(output.advisory_only)
        with self.assertRaises(VisionAdapterError):
            output.assert_advisory_boundary("trigger_live_dispatch")
        output.assert_advisory_boundary("store_human_review_summary")


if __name__ == "__main__":
    unittest.main()

from unittest import TestCase
from uuid import uuid4

from pydantic import ValidationError

from app.evidence_substantiation import EvidenceSubstantiationContract


def envelope():
    session_id, acquisition_id, artifact_id = uuid4(), uuid4(), uuid4()
    measurement_id, inference_id = uuid4(), uuid4()
    return {
        "contract_version": "1.0.0",
        "session_id": str(session_id),
        "acquisitions": [{
            "acquisition_id": str(acquisition_id),
            "artifact": {
                "artifact_id": str(artifact_id), "sha256": "a" * 64, "byte_length": 128,
                "mime_type": "image/jpeg", "role": "ORIGINAL",
            },
            "modality": "IMAGE", "captured_at_utc": "2026-11-26T12:00:00Z",
            "time_source": "DEVICE_CLOCK", "actor_id": "operator-1", "device_id": "tablet-1",
            "raw_unmodified": True, "sensor_metadata": {"orientation": "landscape"},
            "camera_calibration": {
                "camera_model": "qualified-camera-profile", "image_width_px": 4032, "image_height_px": 3024,
                "intrinsics_3x3": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "distortion_coefficients": [0.01, -0.02], "calibration_source": "device-capture-api",
                "source_api": "AVCameraCalibrationData", "calibration_error_px": 0.2,
            },
        }],
        "quality_assessments": [{
            "quality_id": str(uuid4()), "artifact_id": str(artifact_id),
            "metric": "LAPLACIAN_VARIANCE", "observed_value": 125.0, "comparator": "GTE",
            "threshold_policy_id": "image-quality-v1", "threshold_policy_version": "1.0.0",
            "threshold_values": [100.0], "result": "PASS", "method_version": "opencv-4.x",
            "advisory_only": True,
        }],
        "measurements": [{
            "measurement_id": str(measurement_id), "source_acquisition_ids": [str(acquisition_id)],
            "method_id": "test-distance-method", "method_version": "0.1.0", "value": 2.4,
            "unit": "m", "coordinate_frame": "vehicle-frame-v1",
            "uncertainty": {"kind": "BOUNDED_INTERVAL", "lower_bound": 2.3, "upper_bound": 2.5},
            "calibration_acquisition_ids": [], "limitations": ["synthetic fixture only"],
        }],
        "inferences": [{
            "inference_id": str(inference_id), "input_acquisition_ids": [str(acquisition_id)],
            "input_measurement_ids": [str(measurement_id)], "method_id": "test-inference",
            "method_version": "0.1.0", "proposition": "A bounded test proposition",
            "result": "inconclusive in synthetic fixture", "status": "INCONCLUSIVE",
            "confidence": None, "confidence_calibrated": False, "assumptions": [],
            "alternatives": ["alternative explanation"], "missing_inputs": [],
            "source_references": ["synthetic-fixture://reference"],
        }],
        "decisions": [{
            "decision_id": str(uuid4()), "input_inference_ids": [str(inference_id)],
            "action": "HUMAN_REVIEW", "reason_codes": ["INSUFFICIENT_TELEMETRY"],
            "decided_by": "reviewer-1", "decided_at_utc": "2026-11-26T12:05:00Z",
        }],
        "custody": {
            "event_chain_tip_sha256": "b" * 64, "event_chain_tip_sequence": 17,
            "hash_chain_version": "faos-chain-v1", "manifest_sha256": "c" * 64,
            "merkle_root_sha256": "d" * 64, "merkle_tree_version": "faos-merkle-v1",
            "merkle_leaf_count": 16, "hash_algorithm": "SHA-256",
            "serialization_version": "faos-event-v1", "storage_claim": "DURABLE_STORAGE",
            "certification_status": "NOT_CERTIFIED",
        },
    }


class EvidenceSubstantiationContractTests(TestCase):
    def assert_contract_error(self, data, message):
        with self.assertRaisesRegex(ValidationError, message):
            EvidenceSubstantiationContract.model_validate(data)

    def test_contract_accepts_distinct_layers_and_explicit_uncertainty(self):
        model = EvidenceSubstantiationContract.model_validate(envelope())
        self.assertEqual(model.contract_version, "1.0.0")
        self.assertTrue(model.acquisitions[0].raw_unmodified)
        self.assertTrue(model.quality_assessments[0].advisory_only)
        self.assertEqual(model.measurements[0].uncertainty.kind, "BOUNDED_INTERVAL")
        self.assertEqual(model.inferences[0].status, "INCONCLUSIVE")
        self.assertEqual(model.decisions[0].action, "HUMAN_REVIEW")
        self.assertEqual(model.custody.certification_status, "NOT_CERTIFIED")

    def test_original_artifact_cannot_claim_a_derivative_transformation(self):
        data = envelope()
        data["acquisitions"][0]["artifact"]["transformation_id"] = "rectify-v1"
        self.assert_contract_error(data, "ORIGINAL_MUST_NOT_HAVE_TRANSFORMATION")

    def test_derivative_requires_parent_and_transformation(self):
        data = envelope()
        artifact = data["acquisitions"][0]["artifact"]
        artifact["role"] = "DERIVATIVE"
        artifact["parent_artifact_id"] = None
        self.assert_contract_error(data, "DERIVATIVE_REQUIRES_PARENT_AND_TRANSFORMATION")

    def test_acquisition_time_must_be_explicit_utc(self):
        data = envelope()
        data["acquisitions"][0]["captured_at_utc"] = "2026-11-26T12:00:00-06:00"
        self.assert_contract_error(data, "CAPTURE_TIMESTAMP_MUST_BE_UTC")

    def test_measurement_must_reference_known_acquisition(self):
        data = envelope()
        data["measurements"][0]["source_acquisition_ids"] = [str(uuid4())]
        self.assert_contract_error(data, "MEASUREMENT_REFERENCES_UNKNOWN_ACQUISITION")

    def test_inference_cannot_publish_uncalibrated_probability(self):
        data = envelope()
        data["inferences"][0]["confidence"] = 0.67
        data["inferences"][0]["confidence_calibrated"] = False
        self.assert_contract_error(data, "UNCALIBRATED_CONFIDENCE_FORBIDDEN")

    def test_abstention_requires_a_missing_input_reason(self):
        data = envelope()
        data["inferences"][0]["status"] = "ABSTAINED"
        data["inferences"][0]["missing_inputs"] = []
        self.assert_contract_error(data, "ABSTENTION_REQUIRES_MISSING_INPUT_REASON")

    def test_decision_cannot_reference_unknown_inference(self):
        data = envelope()
        data["decisions"][0]["input_inference_ids"] = [str(uuid4())]
        self.assert_contract_error(data, "DECISION_REFERENCES_UNKNOWN_INFERENCE")

    def test_qualified_certification_requires_certifier_and_certificate_artifact(self):
        data = envelope()
        data["custody"]["certification_status"] = "CERTIFIED_BY_QUALIFIED_PERSON"
        data["custody"]["certification_basis"] = "FRE_902_14"
        self.assert_contract_error(data, "QUALIFIED_CERTIFICATION_REQUIRES_BASIS_CERTIFIER_AND_CERTIFICATE")

    def test_raw_original_must_remain_unmodified(self):
        data = envelope()
        data["acquisitions"][0]["raw_unmodified"] = False
        self.assert_contract_error(data, "ORIGINAL_ACQUISITION_MUST_BE_UNMODIFIED")

    def test_quality_assessment_must_reference_a_registered_original_or_derivative(self):
        data = envelope()
        data["quality_assessments"][0]["artifact_id"] = str(uuid4())
        self.assert_contract_error(data, "QUALITY_REFERENCES_UNKNOWN_ARTIFACT")

    def test_merkle_root_requires_tree_version_and_leaf_count(self):
        data = envelope()
        data["custody"]["merkle_leaf_count"] = None
        self.assert_contract_error(data, "MERKLE_ROOT_REQUIRES_TREE_VERSION_AND_LEAF_COUNT")

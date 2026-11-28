"""Versioned evidence-to-decision contract.

This module defines typed records and validation only. It does not claim that a
sensor is calibrated, a measurement is accurate, a model is validated, storage
is physically WORM, or a record is legally self-authenticating.
"""
from datetime import datetime, timezone
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool, StrictStr, root_validator, validator


SHA256 = r"^[0-9a-f]{64}$"


class ContractModel(BaseModel):
    class Config:
        extra = "forbid"
        allow_mutation = False
        allow_inf_nan = False


class ArtifactReference(ContractModel):
    artifact_id: UUID
    sha256: StrictStr = Field(pattern=SHA256)
    byte_length: int = Field(gt=0)
    mime_type: StrictStr = Field(min_length=1, max_length=128)
    role: Literal["ORIGINAL", "DERIVATIVE"] = "ORIGINAL"
    parent_artifact_id: UUID | None = None
    transformation_id: StrictStr | None = Field(default=None, max_length=128)

    @root_validator(skip_on_failure=True)
    def lineage_is_explicit(cls, values):
        role = values.get("role")
        parent = values.get("parent_artifact_id")
        transform = values.get("transformation_id")
        if role == "ORIGINAL" and (parent is not None or transform is not None):
            raise ValueError("ORIGINAL_MUST_NOT_HAVE_TRANSFORMATION")
        if role == "DERIVATIVE" and (parent is None or not transform):
            raise ValueError("DERIVATIVE_REQUIRES_PARENT_AND_TRANSFORMATION")
        return values


class CameraCalibration(ContractModel):
    camera_model: StrictStr = Field(min_length=1, max_length=128)
    image_width_px: int = Field(gt=0)
    image_height_px: int = Field(gt=0)
    intrinsics_3x3: tuple[float, ...] = Field(min_length=9, max_length=9)
    distortion_coefficients: tuple[float, ...] = ()
    calibration_source: StrictStr = Field(min_length=1, max_length=256)
    source_api: StrictStr | None = Field(default=None, max_length=128)
    calibration_error_px: float | None = Field(default=None, ge=0)

    @validator("intrinsics_3x3", "distortion_coefficients", each_item=True)
    def finite_calibration_values(cls, value):
        if not isfinite(value):
            raise ValueError("NON_FINITE_CALIBRATION_VALUE")
        return value


def _require_utc_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("INVALID_CAPTURE_TIMESTAMP") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("CAPTURE_TIMESTAMP_MUST_BE_UTC")
    return value


class AcquisitionRecord(ContractModel):
    acquisition_id: UUID
    artifact: ArtifactReference
    modality: Literal["IMAGE", "DEPTH_MAP", "LIDAR_POINT_CLOUD", "IMU", "AUDIO", "CAMERA_CALIBRATION", "VIN_IMAGE", "DOCUMENT"]
    captured_at_utc: StrictStr
    time_source: Literal["DEVICE_CLOCK", "SERVER_RECEIPT", "GPS_TIME", "EXTERNAL_TRUSTED_TIME"]
    actor_id: StrictStr = Field(min_length=1, max_length=128)
    device_id: StrictStr = Field(min_length=1, max_length=128)
    raw_unmodified: StrictBool
    sensor_metadata: dict = Field(default_factory=dict)
    camera_calibration: CameraCalibration | None = None

    @validator("captured_at_utc")
    def require_utc_timestamp(cls, value):
        return _require_utc_timestamp(value)

    @root_validator(skip_on_failure=True)
    def original_fidelity_is_explicit(cls, values):
        artifact = values.get("artifact")
        raw = values.get("raw_unmodified")
        if artifact and artifact.role == "ORIGINAL" and raw is not True:
            raise ValueError("ORIGINAL_ACQUISITION_MUST_BE_UNMODIFIED")
        if artifact and artifact.role == "DERIVATIVE" and raw is True:
            raise ValueError("DERIVATIVE_CANNOT_BE_DECLARED_ORIGINAL")
        return values


class Uncertainty(ContractModel):
    kind: Literal["STANDARD_UNCERTAINTY", "BOUNDED_INTERVAL", "QUALITATIVE_LIMITATION"]
    standard_uncertainty: float | None = Field(default=None, ge=0)
    lower_bound: float | None = None
    upper_bound: float | None = None
    coverage_probability: float | None = Field(default=None, gt=0, lt=1)
    limitation: StrictStr | None = Field(default=None, max_length=1000)

    @root_validator(skip_on_failure=True)
    def uncertainty_shape_matches_kind(cls, values):
        kind = values.get("kind")
        standard = values.get("standard_uncertainty")
        lower, upper = values.get("lower_bound"), values.get("upper_bound")
        limitation = values.get("limitation")
        if kind == "STANDARD_UNCERTAINTY" and (standard is None or lower is not None or upper is not None):
            raise ValueError("STANDARD_UNCERTAINTY_REQUIRES_ONLY_STANDARD_VALUE")
        if kind == "BOUNDED_INTERVAL" and (lower is None or upper is None or lower > upper or standard is not None):
            raise ValueError("INVALID_BOUNDED_INTERVAL")
        if kind == "QUALITATIVE_LIMITATION" and (not limitation or standard is not None or lower is not None or upper is not None):
            raise ValueError("QUALITATIVE_LIMITATION_REQUIRED")
        return values


class QualityAssessment(ContractModel):
    quality_id: UUID
    artifact_id: UUID
    metric: Literal["LAPLACIAN_VARIANCE", "LUMINANCE_MEAN", "MOTION_MAGNITUDE", "FRAMING_COMPLIANCE", "FOCUS_SCORE", "CUSTOM"]
    observed_value: float
    comparator: Literal["GTE", "LTE", "BETWEEN", "BOOLEAN"]
    threshold_policy_id: StrictStr = Field(min_length=1, max_length=128)
    threshold_policy_version: StrictStr = Field(min_length=1, max_length=64)
    threshold_values: list[float] = Field(default_factory=list)
    result: Literal["PASS", "WARN", "FAIL", "NOT_ASSESSABLE"]
    method_version: StrictStr = Field(min_length=1, max_length=64)
    advisory_only: StrictBool = True

    @validator("observed_value")
    def finite_quality_value(cls, value):
        if not isfinite(value):
            raise ValueError("NON_FINITE_QUALITY_VALUE")
        return value


class MeasurementRecord(ContractModel):
    measurement_id: UUID
    source_acquisition_ids: list[UUID] = Field(min_length=1)
    method_id: StrictStr = Field(min_length=1, max_length=128)
    method_version: StrictStr = Field(min_length=1, max_length=64)
    value: float
    unit: StrictStr = Field(min_length=1, max_length=32)
    coordinate_frame: StrictStr | None = Field(default=None, max_length=128)
    uncertainty: Uncertainty
    calibration_acquisition_ids: list[UUID] = Field(default_factory=list)
    limitations: list[StrictStr] = Field(default_factory=list)

    @validator("value")
    def finite_measurement(cls, value):
        if not isfinite(value):
            raise ValueError("NON_FINITE_MEASUREMENT")
        return value


class InferenceRecord(ContractModel):
    inference_id: UUID
    input_acquisition_ids: list[UUID] = Field(default_factory=list)
    input_measurement_ids: list[UUID] = Field(default_factory=list)
    method_id: StrictStr = Field(min_length=1, max_length=128)
    method_version: StrictStr = Field(min_length=1, max_length=64)
    proposition: StrictStr = Field(min_length=1, max_length=2000)
    result: StrictStr = Field(min_length=1, max_length=1000)
    status: Literal["PROVISIONAL", "SUPPORTED", "INCONCLUSIVE", "CONTRADICTED", "ABSTAINED"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_calibrated: StrictBool = False
    assumptions: list[StrictStr] = Field(default_factory=list)
    alternatives: list[StrictStr] = Field(default_factory=list)
    missing_inputs: list[StrictStr] = Field(default_factory=list)
    source_references: list[StrictStr] = Field(default_factory=list)
    vehicle_applicability: StrictStr | None = Field(default=None, max_length=512)
    source_revision: StrictStr | None = Field(default=None, max_length=128)
    effective_date: StrictStr | None = Field(default=None, max_length=32)

    @root_validator(skip_on_failure=True)
    def confidence_and_abstention_are_honest(cls, values):
        if values.get("confidence") is not None and values.get("confidence_calibrated") is not True:
            raise ValueError("UNCALIBRATED_CONFIDENCE_FORBIDDEN")
        if values.get("status") == "ABSTAINED" and not values.get("missing_inputs"):
            raise ValueError("ABSTENTION_REQUIRES_MISSING_INPUT_REASON")
        return values


class DecisionRecord(ContractModel):
    decision_id: UUID
    input_inference_ids: list[UUID] = Field(min_length=1)
    action: Literal["LOW_SEVERITY_TRIAGE", "HIGH_SEVERITY_TRIAGE", "HUMAN_REVIEW", "ABSTAIN", "NO_ACTION"]
    reason_codes: list[StrictStr] = Field(min_length=1)
    decided_by: StrictStr = Field(min_length=1, max_length=128)
    decided_at_utc: StrictStr

    @validator("decided_at_utc")
    def require_utc_decision_time(cls, value):
        return _require_utc_timestamp(value)


class CustodyAttestation(ContractModel):
    event_chain_tip_sha256: StrictStr = Field(pattern=SHA256)
    event_chain_tip_sequence: int = Field(gt=0)
    hash_chain_version: StrictStr = Field(min_length=1, max_length=64)
    manifest_sha256: StrictStr = Field(pattern=SHA256)
    merkle_root_sha256: StrictStr | None = Field(default=None, pattern=SHA256)
    merkle_tree_version: StrictStr | None = Field(default=None, max_length=64)
    merkle_leaf_count: int | None = Field(default=None, gt=0)
    hash_algorithm: Literal["SHA-256"] = "SHA-256"
    serialization_version: StrictStr = Field(min_length=1, max_length=64)
    storage_claim: Literal["DURABLE_STORAGE", "APPEND_ONLY_POLICY"] = "DURABLE_STORAGE"
    immutability_verification_ref: StrictStr | None = Field(default=None, max_length=512)
    certification_status: Literal["NOT_CERTIFIED", "PENDING_QUALIFIED_CERTIFIER", "CERTIFIED_BY_QUALIFIED_PERSON"] = "NOT_CERTIFIED"
    certification_basis: Literal["FRE_902_13", "FRE_902_14"] | None = None
    certifier_identity: StrictStr | None = Field(default=None, max_length=256)
    certificate_artifact_id: UUID | None = None
    certifier_qualification_reference: StrictStr | None = Field(default=None, max_length=512)
    certified_at_utc: StrictStr | None = Field(default=None, max_length=40)

    @root_validator(skip_on_failure=True)
    def certification_is_not_self_asserted(cls, values):
        merkle_parts = (values.get("merkle_root_sha256"), values.get("merkle_tree_version"), values.get("merkle_leaf_count"))
        if any(part is not None for part in merkle_parts) and not all(part is not None for part in merkle_parts):
            raise ValueError("MERKLE_ROOT_REQUIRES_TREE_VERSION_AND_LEAF_COUNT")
        if values.get("certification_status") == "CERTIFIED_BY_QUALIFIED_PERSON":
            required = (values.get("certification_basis"), values.get("certifier_identity"), values.get("certificate_artifact_id"), values.get("certifier_qualification_reference"), values.get("certified_at_utc"))
            if not all(required):
                raise ValueError("QUALIFIED_CERTIFICATION_REQUIRES_BASIS_CERTIFIER_AND_CERTIFICATE")
        return values


class EvidenceSubstantiationContract(ContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    session_id: UUID
    acquisitions: list[AcquisitionRecord] = Field(default_factory=list)
    quality_assessments: list[QualityAssessment] = Field(default_factory=list)
    measurements: list[MeasurementRecord] = Field(default_factory=list)
    inferences: list[InferenceRecord] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    custody: CustodyAttestation

    @root_validator(skip_on_failure=True)
    def references_resolve_and_layers_do_not_collapse(cls, values):
        acquisitions = {x.acquisition_id for x in values.get("acquisitions", [])}
        measurements = {x.measurement_id for x in values.get("measurements", [])}
        for quality in values.get("quality_assessments", []):
            if quality.artifact_id not in {a.artifact.artifact_id for a in values.get("acquisitions", [])}:
                raise ValueError("QUALITY_REFERENCES_UNKNOWN_ARTIFACT")
        inferences = {x.inference_id for x in values.get("inferences", [])}
        for item in values.get("measurements", []):
            if not set(item.source_acquisition_ids + item.calibration_acquisition_ids) <= acquisitions:
                raise ValueError("MEASUREMENT_REFERENCES_UNKNOWN_ACQUISITION")
        for item in values.get("inferences", []):
            if not set(item.input_acquisition_ids) <= acquisitions or not set(item.input_measurement_ids) <= measurements:
                raise ValueError("INFERENCE_REFERENCES_UNKNOWN_INPUT")
        for item in values.get("decisions", []):
            if not set(item.input_inference_ids) <= inferences:
                raise ValueError("DECISION_REFERENCES_UNKNOWN_INFERENCE")
        return values

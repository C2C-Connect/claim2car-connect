/** TypeScript mirror of app/evidence_substantiation.py (contract 1.0.0).
 * Raw media bytes are stored as immutable artifacts, never embedded in this JSON envelope.
 * This file is a compile-time contract; server Pydantic validation remains authoritative.
 */
export type UUID = string & { readonly __uuid: unique symbol };
export type Sha256 = string & { readonly __sha256: unique symbol };
export type UtcTimestamp = string & { readonly __utcTimestamp: unique symbol };

export interface ArtifactReference {
  artifact_id: UUID;
  sha256: Sha256;
  byte_length: number;
  mime_type: string;
  role: "ORIGINAL" | "DERIVATIVE";
  parent_artifact_id?: UUID | null;
  transformation_id?: string | null;
}

export interface CameraCalibration {
  camera_model: string;
  image_width_px: number;
  image_height_px: number;
  /** Row-major 3x3 intrinsic matrix. */
  intrinsics_3x3: [number, number, number, number, number, number, number, number, number];
  distortion_coefficients: number[];
  calibration_source: string;
  source_api?: string | null;
  calibration_error_px?: number | null;
}

export interface AcquisitionRecord {
  acquisition_id: UUID;
  artifact: ArtifactReference;
  modality: "IMAGE" | "DEPTH_MAP" | "LIDAR_POINT_CLOUD" | "IMU" | "AUDIO" | "CAMERA_CALIBRATION" | "VIN_IMAGE" | "DOCUMENT";
  captured_at_utc: UtcTimestamp;
  time_source: "DEVICE_CLOCK" | "SERVER_RECEIPT" | "GPS_TIME" | "EXTERNAL_TRUSTED_TIME";
  actor_id: string;
  device_id: string;
  raw_unmodified: boolean;
  sensor_metadata: Record<string, unknown>;
  camera_calibration?: CameraCalibration | null;
}

export type Uncertainty =
  | { kind: "STANDARD_UNCERTAINTY"; standard_uncertainty: number; lower_bound?: never; upper_bound?: never; limitation?: never; coverage_probability?: number }
  | { kind: "BOUNDED_INTERVAL"; lower_bound: number; upper_bound: number; standard_uncertainty?: never; limitation?: never; coverage_probability?: number }
  | { kind: "QUALITATIVE_LIMITATION"; limitation: string; standard_uncertainty?: never; lower_bound?: never; upper_bound?: never; coverage_probability?: never };

export interface QualityAssessment {
  quality_id: UUID;
  artifact_id: UUID;
  metric: "LAPLACIAN_VARIANCE" | "LUMINANCE_MEAN" | "MOTION_MAGNITUDE" | "FRAMING_COMPLIANCE" | "FOCUS_SCORE" | "CUSTOM";
  observed_value: number;
  comparator: "GTE" | "LTE" | "BETWEEN" | "BOOLEAN";
  threshold_policy_id: string;
  threshold_policy_version: string;
  threshold_values: number[];
  result: "PASS" | "WARN" | "FAIL" | "NOT_ASSESSABLE";
  method_version: string;
  advisory_only: true;
}

export interface MeasurementRecord {
  measurement_id: UUID;
  source_acquisition_ids: UUID[];
  method_id: string;
  method_version: string;
  value: number;
  unit: string;
  coordinate_frame?: string | null;
  uncertainty: Uncertainty;
  calibration_acquisition_ids: UUID[];
  limitations: string[];
}

export interface InferenceRecord {
  inference_id: UUID;
  input_acquisition_ids: UUID[];
  input_measurement_ids: UUID[];
  method_id: string;
  method_version: string;
  proposition: string;
  result: string;
  status: "PROVISIONAL" | "SUPPORTED" | "INCONCLUSIVE" | "CONTRADICTED" | "ABSTAINED";
  /** Present only when empirically calibrated for the declared task/population. */
  confidence?: number | null;
  confidence_calibrated: boolean;
  assumptions: string[];
  alternatives: string[];
  missing_inputs: string[];
  source_references: string[];
  vehicle_applicability?: string | null;
  source_revision?: string | null;
  effective_date?: string | null;
}

export interface DecisionRecord {
  decision_id: UUID;
  input_inference_ids: UUID[];
  action: "LOW_SEVERITY_TRIAGE" | "HIGH_SEVERITY_TRIAGE" | "HUMAN_REVIEW" | "ABSTAIN" | "NO_ACTION";
  reason_codes: string[];
  decided_by: string;
  decided_at_utc: UtcTimestamp;
}

export interface CustodyAttestation {
  event_chain_tip_sha256: Sha256;
  event_chain_tip_sequence: number;
  hash_chain_version: string;
  manifest_sha256: Sha256;
  merkle_root_sha256?: Sha256 | null;
  merkle_tree_version?: string | null;
  merkle_leaf_count?: number | null;
  hash_algorithm: "SHA-256";
  serialization_version: string;
  /** WORM_VERIFIED is allowed only after independent storage-control verification. */
  storage_claim: "DURABLE_STORAGE" | "APPEND_ONLY_POLICY";
  immutability_verification_ref?: string | null;
  certification_status: "NOT_CERTIFIED" | "PENDING_QUALIFIED_CERTIFIER" | "CERTIFIED_BY_QUALIFIED_PERSON";
  certification_basis?: "FRE_902_13" | "FRE_902_14" | null;
  certifier_identity?: string | null;
  certificate_artifact_id?: UUID | null;
  certifier_qualification_reference?: string | null;
  certified_at_utc?: UtcTimestamp | null;
}

export interface EvidenceSubstantiationContractV1 {
  contract_version: "1.0.0";
  session_id: UUID;
  acquisitions: AcquisitionRecord[];
  quality_assessments: QualityAssessment[];
  measurements: MeasurementRecord[];
  inferences: InferenceRecord[];
  decisions: DecisionRecord[];
  custody: CustodyAttestation;
}

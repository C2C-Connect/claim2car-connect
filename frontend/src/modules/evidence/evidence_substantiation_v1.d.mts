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
  manifest_sha256: Sha256;
  merkle_root_sha256?: Sha256 | null;
  hash_algorithm: "SHA-256";
  serialization_version: string;
  /** WORM_VERIFIED is allowed only after independent storage-control verification. */
  storage_claim: "DURABLE_STORAGE" | "APPEND_ONLY_POLICY" | "WORM_VERIFIED";
  certification_status: "NOT_CERTIFIED" | "PENDING_QUALIFIED_CERTIFIER" | "CERTIFIED_BY_QUALIFIED_PERSON";
  certification_basis?: "FRE_902_13" | "FRE_902_14" | null;
  certifier_identity?: string | null;
  certificate_artifact_id?: UUID | null;
}

export interface EvidenceSubstantiationContractV1 {
  contract_version: "1.0.0";
  session_id: UUID;
  acquisitions: AcquisitionRecord[];
  measurements: MeasurementRecord[];
  inferences: InferenceRecord[];
  decisions: DecisionRecord[];
  custody: CustodyAttestation;
}

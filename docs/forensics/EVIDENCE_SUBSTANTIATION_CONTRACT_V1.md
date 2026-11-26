# Evidence Measurement and Substantiation Contract v1.0.0

**Executable source:** `app/evidence_substantiation.py`  
**Frontend type mirror:** `frontend/src/modules/evidence/evidence_substantiation_v1.d.mts`  
**Executable invariants:** `tests/api/test_evidence_substantiation_contract.py`

The Pydantic models are the server-side authority. The TypeScript declarations are a compile-time mirror, not a substitute for server validation. Unknown fields are rejected. The contract is additive only through a new version; do not reinterpret a v1.0.0 field in place.

## Layer contract

| Layer | Record | Contract requirement |
|---|---|---|
| Acquisition | `AcquisitionRecord` | Original artifact reference, SHA-256, byte length, MIME type, actor/device, UTC capture time and time source. Original bytes are stored separately; an original must be declared unmodified and cannot carry a transformation. |
| Sensor metadata | `CameraCalibration` + acquisition metadata | Preserve supported camera model, image dimensions, intrinsics, distortion coefficients, calibration source/API and calibration error where actually supplied. Apple capture integration must retain `AVCameraCalibrationData` when the device/API exposes it. Absence is explicit; never synthesize calibration. LiDAR, IMU and audio payloads are separate original artifacts, not values silently inserted into image metadata. |
| Acquisition quality | `QualityAssessment` | Store observed metric, method version and versioned threshold policy. Quality results are advisory acquisition checks; they do not rewrite originals or certify measurement accuracy. No universal Laplacian/luminance threshold is declared by this contract. |
| Measurement | `MeasurementRecord` | Name every source acquisition, method/version, units, coordinate frame and uncertainty representation. Metric claims require calibration/reference inputs and disclosed limitations. A qualitative limitation is valid; fabricated numeric precision is not. |
| Inference | `InferenceRecord` | Link source acquisitions and measurements; preserve method/model version, proposition, result, assumptions, alternatives, missing inputs, source references and vehicle applicability. A confidence value is rejected unless explicitly marked calibrated. Abstention requires a reason. |
| Decision | `DecisionRecord` | Link one or more inference records, record actor/time/reasons, and permit human review or abstention. Decision policy is distinct from model output and does not itself authorize payment, dispatch or marketplace action. |
| Custody/certification | `CustodyAttestation` | Bind the event-chain tip/sequence/version and manifest digest. Merkle root is optional and must carry tree version and leaf count; it is not a substitute for the event chain, a signature or a trusted timestamp. Certification is `NOT_CERTIFIED` by default. FRE 902(13)/(14) status requires a named qualified certifier, basis, qualification reference, certificate artifact and time. |

## Non-negotiable invariants

1. Original media bytes are never rectified, cropped, annotated, recompressed or model-processed in place. Every derivative is a separate artifact with parent ID and transformation ID.
2. Timestamps are UTC values with an explicit time-source label. A device clock is not a trusted timestamp.
3. Sensor presence is not sensor qualification. Calibration metadata is preserved only when actually delivered by a supported acquisition path.
4. Pixel-to-metric, stand-off, point-cloud surface and other measurements must identify their method, coordinate frame, calibration/reference inputs and uncertainty. If these are absent, record a limitation or abstain.
5. CRASH3 coefficient sets and OEM procedures must be source- and vehicle-applicability-bound. The generic inference fields carry source/revision/applicability; no universal coefficient or material-yield threshold is encoded here.
6. A model vote is not a calibrated probability. Uncalibrated confidence is rejected; conflicting, missing or out-of-domain inputs should produce `INCONCLUSIVE` or `ABSTAINED` and human review.
7. `DURABLE_STORAGE` and `APPEND_ONLY_POLICY` are not claims of physical WORM. Do not claim WORM without separate control verification. This contract does not provide external notarization or legal admissibility.
8. FRE 902(13)/(14) fields record a certification process; the schema does not certify the system, qualify a person, or establish admissibility.

## M1 acceptance boundary

M1 may use acquisition and custody records for controlled intake, original preservation, consent/identity linkage, offline synchronization, server verification and reviewer retrieval. Image quality is an advisory capture gate. The measurement and inference structures are defined for lineage and research telemetry, but LiDAR volumetric crush measurement, CRASH3 outcome adjudication, structural-yield decisions and autonomous repair/total-loss decisions are **not M1 acceptance criteria**. They remain disabled/research-only until separately validated and accepted.

## Test mapping

- `test_contract_accepts_distinct_layers_and_explicit_uncertainty`: valid layer separation and bounded uncertainty.
- Original/derivative tests: byte-fidelity and transformation lineage.
- UTC test: time-source semantics.
- Measurement/inference/decision reference tests: no dangling provenance.
- Confidence/abstention tests: calibrated probability and explicit missing-prior requirements.
- Custody tests: Merkle structure completeness and qualified-certifier prerequisites.

These tests validate schema invariants only. They do not validate camera calibration, image-quality thresholds, metric accuracy, model performance, storage WORM controls or legal sufficiency.

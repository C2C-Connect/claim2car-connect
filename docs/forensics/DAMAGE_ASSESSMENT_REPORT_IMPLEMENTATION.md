# Evidence-linked damage assessment PDF — implementation status

**Status:** first report-rendering vertical slice implemented on PR #186; not yet production released.

## Implemented in this increment

- A typed damage assessment contract with unique finding and estimate-line IDs.
- Each finding references a manifest-bound image artifact and its immutable tenant/session-scoped storage key; a finding cannot exist without that source reference.
- Original image bytes are SHA-256 checked before rendering.
- Each finding renders a derived source preview and a separate annotated derivative with a red image-space bounding box. The original byte object is retrieved by immutable storage key and is not represented by the embedded preview.
- Every bounding box carries `slot_id`, normalized coordinates, camera-angle metadata and provenance, reviewer attribution, and a source-image reference (artifact ID, immutable storage key, SHA-256). Reports also show derived pixel bounds, source image dimensions, server-side artifact registration timestamp, and the capture protocol version.
- A confirmed finding requires reviewer identity and review time. The document service additionally requires that the finding reviewer match the reviewer bound to the sealed evidence dossier.
- Estimate line items include category, quantity/unit, unit rate, calculated amount, related finding, declared source name/reference, and effective date.
- Financial arithmetic uses integer cents and decimal quantity rounding. No estimate is fabricated when no sourced line items are supplied.
- The PDF and JSON carrier each receive a SHA-256 digest and are stored as separate immutable tenant/session-scoped objects. An append-only `DAMAGE_ASSESSMENT_REPORT_GENERATED` event binds both storage keys and digests to the sealed manifest, capture protocol version, reviewer event, report revision, finding IDs, estimate total and request digest. Both carriers can be retrieved after a fresh process start.

## Boundaries that remain explicit

- The PDF embeds a visual rendering of each source image plus a marked derivative. The original byte object remains authoritative in the evidence store and is identified by its verified digest; the PDF is not a substitute for retrieving the original bytes.
- The current contrast detector is a deterministic heuristic baseline, not a trained/validated vehicle damage model. It does not establish damage class, severity, depth, structural condition, hidden damage, causation, repairability, or roadworthiness.
- Bounding boxes are normalized image-space suspect regions, not physical vehicle measurements. The PDF and JSON carrier both state that a box is not a measured dimension, calibrated geometry, or structural-severity claim. Camera angles are reported only with their stated source; unknown angles remain unknown.
- A confirmed finding is a reviewer decision, not proof of collision causation.
- Estimate source fields are declarations supplied to the renderer, not independently authenticated source records. Source applicability, OEM procedure validation, labor-time validation, local rate validation, parts fitment, taxes, and shop approval still require their own integrations and checks. Camera-angle source labels are likewise reported as supplied and are not independently authenticated by the renderer.
- The legacy four-tier in-memory service explicitly refuses damage-assessment report versioning. The authenticated capture API is the only supported report-generation path: it stores the PDF and JSON carrier as separate immutable objects, records both storage keys and SHA-256 digests in the PostgreSQL event journal, supports idempotent retry and authenticated retrieval, survives fresh-runtime reconstruction, and deletes both report objects on owner consent withdrawal. Owner/shop/carrier report distribution, end-user UI integration and production deployment remain outstanding.

## Required next implementation increments

1. Add capture-device camera pose/orientation and calibration provenance; the current report accepts only explicit manual angle entry or `NOT_RECORDED`, never an angle inferred from a slot name.
2. Add per-finding multi-view correspondence, segmentation masks/polygons, calibrated measurement and reviewer annotation editing.
3. Integrate independently sourced parts/labor/paint/material/diagnostic/ADAS operations and vehicle-configuration applicability.
4. Add owner/shop/carrier delivery authorization, recipient-specific redaction and end-user report UI.
5. Replace the heuristic baseline only after trained model provenance, reviewer-labeled datasets, blind evaluation, calibration, and pre-registered acceptance thresholds.
6. Run production-grade end-to-end tests for restart recovery, consent withdrawal, tenant isolation, report revisions, request idempotency, tampering and PDF image extraction.

**Release rule:** a passing PDF-rendering test is a document-functionality result, not evidence of forensic accuracy. Do not market damage-detection accuracy or automated estimating accuracy until the independent validation gates are passed.

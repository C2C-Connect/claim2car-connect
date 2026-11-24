# Evidence-linked damage assessment PDF — implementation status

**Status:** first report-rendering vertical slice implemented on PR #186; not yet production released.

## Implemented in this increment

- A typed damage assessment contract with unique finding and estimate-line IDs.
- Each finding references an image artifact that is part of the report's evidence inventory.
- Original image bytes are SHA-256 checked before rendering.
- Each finding renders its source image and a separate annotated image with a red image-space bounding box.
- Reports show normalized bounding-box coordinates, derived pixel bounds, source image dimensions, capture slot, server-side artifact registration timestamp, image digest, and camera-angle values with an explicit provenance label.
- A confirmed finding requires reviewer identity and review time. The document service additionally requires that the finding reviewer match the reviewer bound to the sealed evidence dossier.
- Estimate line items include category, quantity/unit, unit rate, calculated amount, related finding, declared source name/reference, and effective date.
- Financial arithmetic uses integer cents and decimal quantity rounding. No estimate is fabricated when no sourced line items are supplied.
- Generated PDF bytes receive a SHA-256 digest, are stored in the tenant/session-scoped original-byte store, and are bound to an append-only `DAMAGE_ASSESSMENT_REPORT_GENERATED` event with manifest digest, reviewer event, report revision, finding IDs, estimate total and request digest.

## Boundaries that remain explicit

- The PDF embeds a visual rendering of each source image plus a marked derivative. The original byte object remains authoritative in the evidence store and is identified by its verified digest; the PDF is not a substitute for retrieving the original bytes.
- The current contrast detector is a deterministic heuristic baseline, not a trained/validated vehicle damage model. It does not establish damage class, severity, depth, structural condition, hidden damage, causation, repairability, or roadworthiness.
- Bounding boxes are normalized image-space regions, not physical vehicle measurements. Camera angles are reported only with their stated source; unknown angles remain unknown.
- A confirmed finding is a reviewer decision, not proof of collision causation.
- Estimate source fields are declarations supplied to the renderer, not independently authenticated source records. Source applicability, OEM procedure validation, labor-time validation, local rate validation, parts fitment, taxes, and shop approval still require their own integrations and checks. Camera-angle source labels are likewise reported as supplied and are not independently authenticated by the renderer.
- The four-tier dossier service still keeps its local version objects in process memory. The authenticated capture API now generates and returns the PDF, persists its bytes, records a chain-bound report event, supports idempotent retry and audited download, and deletes report bytes when owner capture consent is withdrawn. Owner/shop/carrier report distribution, end-user UI integration and production deployment remain outstanding.

## Required next implementation increments

1. Add capture-device camera pose/orientation and calibration provenance; the current report accepts only explicit manual angle entry or `NOT_RECORDED`, never an angle inferred from a slot name.
2. Add per-finding multi-view correspondence, segmentation masks/polygons, calibrated measurement and reviewer annotation editing.
3. Integrate independently sourced parts/labor/paint/material/diagnostic/ADAS operations and vehicle-configuration applicability.
4. Add owner/shop/carrier delivery authorization, recipient-specific redaction and end-user report UI.
5. Replace the heuristic baseline only after trained model provenance, reviewer-labeled datasets, blind evaluation, calibration, and pre-registered acceptance thresholds.
6. Run production-grade end-to-end tests for restart recovery, consent withdrawal, tenant isolation, report revisions, request idempotency, tampering and PDF image extraction.

**Release rule:** a passing PDF-rendering test is a document-functionality result, not evidence of forensic accuracy. Do not market damage-detection accuracy or automated estimating accuracy until the independent validation gates are passed.

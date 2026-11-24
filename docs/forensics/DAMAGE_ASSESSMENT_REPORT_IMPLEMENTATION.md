# Evidence-linked damage assessment PDF — implementation status

**Status:** first report-rendering vertical slice implemented on PR #186; not yet production released.

## Implemented in this increment

- A typed damage assessment contract with unique finding and estimate-line IDs.
- Each finding references an image artifact that is part of the report's evidence inventory.
- Original image bytes are SHA-256 checked before rendering.
- Each finding renders its source image and a separate annotated image with a red image-space bounding box.
- Reports show normalized bounding-box coordinates, derived pixel bounds, source image dimensions, capture slot, capture timestamp, image digest, and camera-angle values with an explicit provenance label.
- A confirmed finding requires reviewer identity and review time. The document service additionally requires that the finding reviewer match the reviewer bound to the sealed evidence dossier.
- Estimate line items include category, quantity/unit, unit rate, calculated amount, related finding, declared source name/reference, and effective date.
- Financial arithmetic uses integer cents and decimal quantity rounding. No estimate is fabricated when no sourced line items are supplied.
- Generated PDF bytes receive a SHA-256 digest and are versioned by the existing in-process dossier service.

## Boundaries that remain explicit

- The PDF embeds a visual rendering of each source image plus a marked derivative. The original byte object remains authoritative in the evidence store and is identified by its verified digest; the PDF is not a substitute for retrieving the original bytes.
- The current contrast detector is a deterministic heuristic baseline, not a trained/validated vehicle damage model. It does not establish damage class, severity, depth, structural condition, hidden damage, causation, repairability, or roadworthiness.
- Bounding boxes are normalized image-space regions, not physical vehicle measurements. Camera angles are reported only with their stated source; unknown angles remain unknown.
- A confirmed finding is a reviewer decision, not proof of collision causation.
- Estimate source fields are declarations supplied to the renderer, not independently authenticated source records. Source applicability, OEM procedure validation, labor-time validation, local rate validation, parts fitment, taxes, and shop approval still require their own integrations and checks. Camera-angle source labels are likewise reported as supplied and are not independently authenticated by the renderer.
- The current dossier service stores document versions in process memory. Durable report registry/storage, event-journal audit, authenticated report-generation/download routes, and end-user UI integration remain to be completed before production use.

## Required next implementation increments

1. Connect the report builder to tenant-authorized sealed-artifact retrieval and authenticated independent review.
2. Persist PDF artifacts and report revision metadata in durable storage with append-only journal binding and audited downloads.
3. Add the capture metadata contract for camera pose/orientation and calibration provenance; do not infer pose from slot names.
4. Add per-finding multi-view correspondence and reviewer annotation editing.
5. Integrate sourced parts/labor/paint/material/diagnostic/ADAS operations and vehicle-configuration applicability.
6. Replace the heuristic baseline only after trained model provenance, reviewer-labeled datasets, blind evaluation, calibration, and pre-registered acceptance thresholds.
7. Run end-to-end tests against original bytes, persisted reports, consent withdrawal, tenant isolation, report revisions, and PDF image extraction.

**Release rule:** a passing PDF-rendering test is a document-functionality result, not evidence of forensic accuracy. Do not market damage-detection accuracy or automated estimating accuracy until the independent validation gates are passed.

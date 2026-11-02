# Base44 capture residue

Source: Base44 export `claim2-car-6e2373a2`, file timestamps 2026-10-05, reviewed 2026-11-01. That tree is a prototype of about 1,300 files on the Base44 SDK. It is older than `acceptance/capture-core` and it is not a candidate to merge.

These four notes are non-binding. They do not change `contracts/shot-list.json`, the pilot amounts, or any total-loss threshold.

## 1. Pre-recovery baseline

`functions/ForensicIntakeAuditSpec.md.ts` asks for a walkaround before the winch or any other recovery contact, with time, GPS, and a hash of that baseline. The current 12-shot contract does not say this. It is a future capture gate, not a silent extra shot list.

The same spec also names plate, odometer, roof, and ADAS zones (bumper, windshield, mirrors) plus a license and an insurance card. Those are candidates for a later contract revision. They are not shots today. The spec's claim that intake was 80 percent done, and its confidence score that adds up to 100 percent, are not evidence.

## 2. Fields worth persisting from vPIC

`functions/vinDecoder.ts` asks to keep year, make, model, trim, body class, engine, drive, transmission, fuel, manufacturer, and plant, and to keep a null when vPIC does not return the field. The capture branch already parses make, model, model year, and body class and refuses a suggested VIN. It does not persist those fields on the draft. Extending the draft is a later slice. Inventing a vehicle when vPIC fails is already forbidden, including the demo library and the model fallback in `functions/nhtsaVehicleAPI.ts`.

## 3. Consent shape

`src/components/intake/ConsentSignaturePad.jsx` records an explicit act, a signature image, a consent type, and a timestamp, tied to an incident. PRODUCT-01 still requires consent version, the explicit act, the timestamp, and session linkage. The third-party IP lookup in that component is not part of the shape we keep.

## 4. Photo-quality words

`functions/photoQualityAssessment.ts` uses clarity, brightness, framing, and resolution, with accept, retake, or warning. That is vocabulary for PRODUCT-06. The implementation asks a model to score the photo. It is not the check. The unvalidated Laplacian starting point stays in `phase-c-d-capture.md`.

## Left in the export on purpose

Not carried forward: dashboard pages, model bridges, auctions, blockchain and IPFS, live card charges, salvage percentages, invented trade-in rates, unsourced parts prices, and any total-loss percentage. Those figures disagree with each other and with the product contract. Tow-company document types (business license, insurance certificate, W-9) can be an onboarding checklist later. They are not M1.

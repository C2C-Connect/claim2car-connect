# Claim2Car Connect — Product Acceptance Contract

**Document ID:** C2C-PROD-AC-001
**Version:** 1.0 — PROPOSED, pending owner adoption
**Scope:** The complete product workflow, from operator intake through dealer decision, settlement, and pilot readiness
**Governing doctrine:** SPECIFIED → IMPLEMENTED → TESTED → VALIDATED. BLOCKED is a legitimate status. No gate's status is ever upgraded to make a dashboard look better.

> Status at adoption: this contract becomes authoritative only when the owner approves and merges it.
> This is the product layer of a two-layer acceptance structure; the database-foundation gates are
> defined separately in `docs/acceptance/database-contract.md` (DB-01–14). The two frameworks are
> layered, not merged, and are mapped to each other in `docs/acceptance/baseline-and-milestone.md`.

## 1. Status vocabulary

* **SPECIFIED** — The requirement is written; no implementation exists.
* **IMPLEMENTED** — Code exists in the canonical repository; acceptance evidence is insufficient.
* **IMPLEMENTED — UNVERIFIED** — Code exists, but acceptance evidence is insufficient to award TESTED or VALIDATED.
* **TESTED** — Specific automated test evidence exists and is recorded.
* **VALIDATED** — The complete intended behavior has been demonstrated in its intended operating environment.
* **BLOCKED** — Verification cannot proceed; the blocker is recorded.

A gate can be partially implemented and still fail acceptance. A green CI run is evidence, not
acceptance.

As of 2026-10-28, no gate has been awarded TESTED or VALIDATED. The per-gate "starting assessment"
lines below are conservative owner-supplied proposals from the repository evidence review, not
awarded statuses; awarded statuses come only from the traceability matrix and gate runners.

## 2. The 14 product gates

Each gate records its requirement and its completion evidence. Formal status is tracked in the
work ledger and traceability matrix (`docs/acceptance/baseline-and-milestone.md`), not in this
contract.

### PRODUCT-01 — Identity, authorization, consent
**Starting assessment (2026-10-28 review):** Partial
**Requirement:** An authenticated operator flow with explicit consent and enforced tenant/actor boundaries. Actor, tenant, and role authority are derived from server-verified credentials; client-supplied identifiers are never trusted as authorization.
**Completion evidence:** Working authenticated operator flow, explicit consent, tenant/actor boundary tests.

### PRODUCT-02 — Capture session and lifecycle
**Starting assessment (2026-10-28 review):** Partial
**Requirement:** Sessions can be created, resumed, retrieved, and completed through the API and frontend, with valid state transitions only.
**Completion evidence:** API and frontend lifecycle, resume/readback, valid state transitions.

### PRODUCT-03 — Vehicle identity / VIN
**Starting assessment (2026-10-28 review):** In progress
**Requirement:** VIN validation and lookup with clear results or explicit failures; no fabricated vehicle identity.
**Completion evidence:** Validation, lookup failure handling, authorized save/readback, and the intended client interaction demonstrated and recorded at a specific revision.

### PRODUCT-04 — Evidence collection
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Real device capture with durable original-image storage, session association, and retrieval.
**Completion evidence:** Actual device capture, durable original-image storage, session association, retrieval.

### PRODUCT-05 — Integrity and provenance
**Starting assessment (2026-10-28 review):** Partial
**Requirement:** Manifest and artifact binding with reproducible verification and tamper detection.
**Completion evidence:** Manifest and artifact binding, reproducible verification, tamper tests.

### PRODUCT-06 — Evidence quality / completeness
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Defined quality rules with real-image test cases, retries, and a human-QC path.
**Completion evidence:** Tested checks, clear failure/retry path, human-review fallback.

### PRODUCT-07 — Opportunity eligibility
**Starting assessment (2026-10-28 review):** Partial
**Requirement:** Explicit eligibility rules with reproducible eligible/ineligible outcomes.
**Completion evidence:** Explicit rule set, required evidence, reproducible eligible/ineligible outcomes.

### PRODUCT-08 — Analysis and human adjudication
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Traceable observations, authorized reviewer, recorded decision and reason.
**Completion evidence:** Traceable observations, authorized reviewer, recorded decision/reason, immutable audit trail.

### PRODUCT-09 — Dealer matching and delivery
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Routing to the correct, authorized destination based on validated dealer information.
**Completion evidence:** Validated dealer directory, brands/services, geography, availability, routing rules.

### PRODUCT-10 — Accept / Pass / Expire
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Persisted state transitions with deadlines, duplicate-request handling, and terminal states; no silent recycling.
**Completion evidence:** Tested state machine, deadlines, duplicate requests, terminal states.

### PRODUCT-11 — Exactly-once settlement
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Idempotent invoice/payout records with retry safety and reconciliation. Unique internal invoice/payout records are distinct from exactly-once external payment effects: idempotent database records alone cannot establish exactly-once behavior across a payment provider. Provider-specific retry, uncertain-result, and reconciliation evidence is required before the broader guarantee is claimed. Live settlement remains outside milestone M1.
**Completion evidence:** Idempotent invoice/payout records, retry safety, reconciliation.

### PRODUCT-12 — Pass/Expire economics
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** Pass and Expire produce no charge, no payout, and no silent recycling.
**Completion evidence:** Automated tests proving no charge, payout, or silent recycling.

### PRODUCT-13 — Audit, security and recovery
**Starting assessment (2026-10-28 review):** Partial
**Requirement:** End-to-end audit, secrets/access review, backup restoration, incident and recovery tests.
**Completion evidence:** End-to-end audit, secrets/access review, backup restoration, incident and recovery tests.

### PRODUCT-14 — Integrated acceptance and pilot readiness
**Starting assessment (2026-10-28 review):** Not established
**Requirement:** The full workflow passes in approved staging and an operator can demonstrate it reliably.
**Completion evidence:** Full workflow passes in approved staging and the operator can demonstrate it reliably.

## 3. Evidence required for every gate

Each gate must record five pieces of evidence before it can be considered complete:

1. **Requirement** — What must happen, and what must never happen.
2. **Implementation** — Which canonical files, APIs, migrations, or UI components implement it.
3. **Tests** — Which named tests cover the normal case, failures, retries, authorization boundaries, and relevant concurrency.
4. **Validation** — What observed result proves it works in the intended environment.
5. **Decision** — Who reviewed the evidence and accepted the gate.

If any piece is missing, the gate remains partial or blocked. A proposed component remains a
proposal until the code and evidence exist in the canonical repository.

## 4. First-demo cutline (milestone M1)

The first product demonstration is deliberately narrow and is the first milestone toward
PRODUCT-14:

**Authorized test operator → consent → VIN → photos → durable save/resume → human review.**

M1 acceptance applies to its explicitly listed requirements. It does not validate entire product
gates whose broader requirements extend beyond M1, and it does not require full database
certification (a separately scoped milestone).

### M1 exit checklist (observable conditions)

1. Approved test identity is used, and tenant/actor access is enforced.
2. Consent is recorded with version, explicit action, timestamp, and session linkage.
3. VIN validation produces a clear result or an explicit failure, with no fabricated substitutes.
4. The defined photo checklist is captured; original bytes are stored durably, linked to the session,
   and their recorded integrity can be verified.
5. Closing and reopening the client preserves the draft; persisted state is read back.
6. An authorized human reviewer can see the evidence and record an attributed decision/reason;
   history is preserved.
7. Negative cases are tested and pass: unauthorized access, missing consent/evidence, interrupted
   saves, and conflicting retries.

Target device: unresolved decision — to be selected and recorded before M1 device verification.

In scope for M1:
- Synthetic or explicitly authorized test data and test identities only.
- Full audit trail displayed.
- Optional demonstration material: clearly labeled simulated dealer-routing and decision flow. This
  is demonstration material, not an M1 requirement.

Explicitly not implied by M1:
- Live dealer routing, dispatch, invoicing, payouts, or settlement.
- Driver-facing end-user sign-in beyond the approved test identity.
- Automated damage diagnosis, physics conclusions, or insurance integrations.

A demo can show a compelling, narrow workflow before all 14 product gates are complete. A live
operational pilot cannot quietly inherit that same incomplete status.

## 5. Settlement and pilot rules retained from the documented pilot brief

- Dealer acquisition fee: **flat $375**, due upon close of the qualified acquisition (plan v1.3, D-01 — supersedes the prior $375–$425 range and the earlier $175 figure). Not due merely for receiving a packet or expressing interest.
- Repair-shop fee: **flat $275** (owner decision 2026-11-06; supersedes the $250 auction floor).
- Operator payout: $110 amount carried forward; **trigger, eligibility, and ledger treatment remain an open decision** (plan v1.3, D-04) — no payout logic until approved. Separately confirmed: the shop's recorded acceptance of the vehicle authorizes tow dispatch to that shop, and the tow driver is then routed to deliver the vehicle there.
- Pass: $0, not recycled. Owner cash: none (permanently excluded per legal counsel). Expire: no charge or payout unless a separately approved business rule explicitly says otherwise.
- Payment-provider credentials and live financial integrations remain disabled until separately approved and validated.
- No live settlement is activated merely because a screen displays "Accepted."

## 6. Definition of product acceptance

The product is accepted for a given milestone only when every gate that milestone depends on is
VALIDATED with recorded evidence, the run is traceable to an exact source revision, and the
acceptance decision is recorded with the named reviewer. Demo-readiness and live-pilot readiness
are separate decisions with separate evidence requirements.

## 7. Post-adjudication distribution and guided routing (owner decision 2026-11-06)

Status: **Specified.** Not implemented. No live sends or navigation handoffs are
enabled until attorney review (docs/LEGAL_REVIEW.md) and the acceptance gates
for the owning milestone are passed.

### 7.1 Automatic multi-party distribution

On workflow completion (adjudication recorded and dossier generated), the
system automatically distributes the generated artifacts to the relevant
parties of the incident:

- Dealer packet dossier → the routed dealership (total-loss path).
- Shop repair packet → the accepting repair shop (repairable path).
- Owner PDF → the person involved in the accident (owner portal / provided channel).
- Insurance-carrier 7-page document → the carrier of record.

Requirements:

- Distribution is versioned, consent-gated, and auditable (recipient identity,
  artifact version, timestamp, channel recorded per send).
- Recipient authorization is verified server-side before any send; a missing or
  unauthorized recipient blocks that send rather than falling back to another party.
- Live external sends remain disabled behind an adapter until attorney review
  of consent, TCPA/SMS, and privacy obligations for every recipient channel.

### 7.2 Acceptance, dispatch, and guided navigation

When the receiving party accepts (plan v1.3 §4):

1. **Authorized acceptance** — explicit accept/reject by an authorized recipient
   user; actor, organization, timestamp, destination, accepted terms, and
   packet/evidence version are recorded.
2. **Commercial trigger** — shop acceptance of the vehicle creates the $275 fee
   obligation; dealer fee obligation arises on qualified-acquisition close.
   Payment lifecycle (authorized/collected/settled/failed/refunded/disputed) is
   recorded separately from dispatch; failed payment must not silently create
   duplicate dispatches or charges (dispatch gating on payment failure is an
   open decision, v1.3 D-12).
3. **Dispatch authorization** — shop acceptance authorizes tow routing to the
   accepted shop destination only, after validating acceptance and dispatch
   prerequisites. Dealer-destination dispatch semantics are open (v1.3 D-14).
4. **Operator assignment and navigation** — an eligible tow operator is
   assigned and receives step-by-step guided navigation (Google Maps or
   another approved provider, behind a maps adapter) to the accepted
   destination; the receiving party likewise receives guided navigation to
   their destination.
5. **Arrival and handoff** — en-route, arrival, handoff, recipient
   confirmation, exceptions, and completion are recorded with actor/time/
   location provenance per the approved privacy policy.

Requirements:

- The destination comes from the authorized acceptance record; client-side
  substitution is prevented absent a logged, authorized change.
- Address/geocoding confidence is validated with a correction/escalation path.
- Tow-appropriate routing constraints (height, weight, length, width, clearances,
  access limits) are investigated before provider selection (v1.3 D-13).
- Navigation handoff is recorded separately from actual arrival and physical
  handoff; a handoff is not proof of route followed or delivery completed.
- The maps provider sits behind an adapter; no provider is hard-wired into the
  core workflow.
- Location/destination sharing with any party is consent-gated and covered by
  the privacy review; no continuous location history beyond what is necessary
  and approved.

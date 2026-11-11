/**
 * Slice 2 Operator & Reviewer Workbench Controller
 * Tasks: S2-2A-03, S2-2B-01..18 (Operator), S2-2C-01..14 (Reviewer)
 * Target Runtime: Node 22 CI & React/Capacitor on Apple iPad Pro 11-inch M5
 */

export const DEFAULT_CAPTURE_PROTOCOL = "claims2car-16-v1";
export const LEGACY_CAPTURE_PROTOCOL = "claims2car-12-v1";
export const CAPTURE_PROTOCOL_SLOTS = Object.freeze({
  [DEFAULT_CAPTURE_PROTOCOL]: Object.freeze([
    "00_front_exterior", "01_front_right_exterior", "02_right_side_exterior", "03_rear_right_exterior",
    "04_rear_exterior", "05_rear_left_exterior", "06_left_side_exterior", "07_front_left_exterior",
    "08_wheel_front_left", "09_wheel_front_right", "10_wheel_rear_right", "11_wheel_rear_left",
    "12_cabin_front_airbags", "13_instrument_cluster_odometer", "14_physical_vin", "15_license_and_insurance_docs",
  ]),
  [LEGACY_CAPTURE_PROTOCOL]: Object.freeze([
    "front_center", "front_left", "left_side", "rear_left", "rear_center", "rear_right",
    "right_side", "front_right", "vin_plate", "odometer_cluster",
    "primary_impact_closeup", "undercarriage_or_wheel_well",
  ]),
});
export const CANONICAL_SLOTS = CAPTURE_PROTOCOL_SLOTS[DEFAULT_CAPTURE_PROTOCOL];
export const LEGACY_CANONICAL_SLOTS = CAPTURE_PROTOCOL_SLOTS[LEGACY_CAPTURE_PROTOCOL];

export const REVIEW_DISPOSITIONS = Object.freeze([
  "NOTE_ONLY", "REPAIRABLE_CANDIDATE", "TOTAL_LOSS_CANDIDATE",
  "REQUEST_RETAKE", "ESCALATE_SUPERVISOR",
]);

export class OperatorRoadsideController {
  constructor({ sessionId, tenantId, operatorId, protocolVersion = DEFAULT_CAPTURE_PROTOCOL, now = () => new Date().toISOString() }) {
    if (!sessionId || !tenantId || !operatorId) throw new Error("OPERATOR_CONTEXT_REQUIRED");
    if (!CAPTURE_PROTOCOL_SLOTS[protocolVersion]) throw new Error("UNSUPPORTED_CAPTURE_PROTOCOL");
    this.sessionId = sessionId;
    this.protocolVersion = protocolVersion;
    this.canonicalSlots = CAPTURE_PROTOCOL_SLOTS[protocolVersion];
    this.tenantId = tenantId;
    this.operatorId = operatorId;
    this.now = now;
    // awaiting_disclosure | awaiting_consent | awaiting_vin | capturing | paused_unsafe |
    // aborted_unsafe | consent_withdrawn | ready_to_seal | incomplete_skipped
    this.state = "awaiting_disclosure";
    this.disclosureVersion = null;
    this.consent = null;
    this.vehicle = null;
    this.slots = new Map();
    this.supersededArtifacts = [];
    this.safetyEvents = [];
    this.auditLog = [];
  }

  _recordEvent(kind, payload = {}) {
    const entry = {
      sequence: this.auditLog.length + 1, kind, actor: this.operatorId,
      tenantId: this.tenantId, occurredAt: this.now(), payload,
    };
    this.auditLog.push(entry);
    return entry;
  }

  presentDisclosure(disclosureVersion = "disclosure-v1") {
    this.disclosureVersion = disclosureVersion;
    this.state = "awaiting_consent";
    return this._recordEvent("DISCLOSURE_PRESENTED", { disclosureVersion });
  }

  recordConsent({ ownerActorId, accepted, scope = "m1-capture-and-human-review" }) {
    if (!this.disclosureVersion) throw new Error("DISCLOSURE_REQUIRED_BEFORE_CONSENT");
    if (!ownerActorId) throw new Error("OWNER_ACTOR_ID_REQUIRED");
    if (typeof accepted !== "boolean") throw new Error("CONSENT_BOOLEAN_REQUIRED");
    if (typeof scope !== "string" || !scope.trim()) throw new Error("CONSENT_SCOPE_REQUIRED");
    this.consent = {
      ownerActorId, accepted: Boolean(accepted), disclosureVersion: this.disclosureVersion,
      scope, recordedAt: this.now(), withdrawnAt: null,
    };
    this.state = accepted ? "awaiting_vin" : "consent_declined";
    return this._recordEvent("CONSENT_RECORDED", { ...this.consent });
  }

  withdrawConsent(ownerActorId, reason = "owner_requested_withdrawal") {
    if (!this.consent || this.consent.ownerActorId !== ownerActorId) {
      throw new Error("UNAUTHORIZED_CONSENT_WITHDRAWAL");
    }
    this.consent.withdrawnAt = this.now();
    this.consent.accepted = false;
    this.state = "consent_withdrawn";
    return this._recordEvent("CONSENT_WITHDRAWN", {
      ownerActorId, withdrawnAt: this.consent.withdrawnAt, reason,
      quarantineArtifactCount: this.slots.size,
    });
  }

  recordVehicleIdentification({ vin = null, unavailableReason = null }) {
    if (this.state !== "awaiting_vin" && this.state !== "capturing") {
      throw new Error(`INVALID_STATE_FOR_VIN:${this.state}`);
    }
    if (!vin && !unavailableReason) throw new Error("VIN_OR_UNAVAILABLE_REASON_REQUIRED");
    this.vehicle = {
      vin: vin ? String(vin).trim().toUpperCase() : null,
      unavailableReason: vin ? null : String(unavailableReason).trim(),
      recordedAt: this.now(),
    };
    this.state = "capturing";
    // Audit log never carries raw VIN; local draft keeps it on-device only.
    return this._recordEvent("VEHICLE_IDENTIFIED", {
      vinProvided: Boolean(this.vehicle.vin),
      unavailableReason: this.vehicle.unavailableReason,
      recordedAt: this.vehicle.recordedAt,
    });
  }

  captureSlot({ slot, artifactId, sha256Hex, byteLength, deviceContext = {} }) {
    if (this.state !== "capturing" && this.state !== "incomplete_skipped") {
      throw new Error(`CAPTURE_NOT_ACTIVE:${this.state}`);
    }
    if (!this.canonicalSlots.includes(slot)) throw new Error(`INVALID_CANONICAL_SLOT:${slot}`);
    if (typeof artifactId !== "string" || !artifactId.trim()
        || !/^[a-f0-9]{64}$/i.test(sha256Hex)
        || !Number.isSafeInteger(byteLength) || byteLength <= 0) {
      throw new Error("INVALID_ORIGINAL_ARTIFACT_METADATA");
    }
    const previous = this.slots.get(slot);
    if (previous && previous.status === "captured") {
      this.supersededArtifacts.push({
        ...previous, supersededBy: artifactId, supersededAt: this.now(),
      });
    }
    const record = {
      slot, status: "captured", artifactId, sha256Hex: sha256Hex.toLowerCase(), byteLength,
      capturedAt: this.now(), supersededArtifactId: previous?.artifactId ?? null,
      deviceContext: {
        hardwareModel: deviceContext.hardwareModel ?? "iPad_Pro_11_M5",
        osVersion: deviceContext.osVersion ?? "iPadOS_19",
        ...deviceContext,
      },
    };
    this.slots.set(slot, record);
    this._evaluateCaptureCompletion();
    return this._recordEvent(previous ? "ARTIFACT_SUPERSEDED" : "ARTIFACT_CAPTURED", record);
  }

  pauseForRoadsideSafety(reason = "active_traffic_or_emergency_response") {
    this.state = "paused_unsafe";
    const entry = { action: "pause", reason, occurredAt: this.now() };
    this.safetyEvents.push(entry);
    return this._recordEvent("ROADSIDE_SAFETY_PAUSED", entry);
  }

  resumeFromSafetyPause() {
    if (this.state !== "paused_unsafe") throw new Error(`CANNOT_RESUME_FROM_STATE:${this.state}`);
    this.state = this.vehicle ? "capturing" : "awaiting_vin";
    return this._recordEvent("ROADSIDE_SAFETY_RESUMED", { state: this.state });
  }

  skipUnsafeSlot(slot, hazardReason = "traffic_side_exposure_hazard") {
    if (this.state !== "capturing" && this.state !== "paused_unsafe") {
      throw new Error(`INVALID_STATE_FOR_SKIP:${this.state}`);
    }
    if (!this.canonicalSlots.includes(slot)) throw new Error(`INVALID_CANONICAL_SLOT:${slot}`);
    const skipRecord = { slot, status: "skipped_unsafe", hazardReason, skippedAt: this.now() };
    this.slots.set(slot, skipRecord);
    this.safetyEvents.push({ action: "skip_slot", slot, reason: hazardReason, occurredAt: this.now() });
    this._evaluateCaptureCompletion();
    return this._recordEvent("SLOT_SKIPPED_UNSAFE", skipRecord);
  }

  abortUnsafeScene(reason = "immediate_scene_clearance_ordered") {
    this.state = "aborted_unsafe";
    const entry = { action: "abort_scene", reason, occurredAt: this.now() };
    this.safetyEvents.push(entry);
    return this._recordEvent("SCENE_ABORTED_UNSAFE", entry);
  }

  _evaluateCaptureCompletion() {
    if (this.slots.size !== this.canonicalSlots.length) return;
    const allCaptured = Array.from(this.slots.values()).every((s) => s.status === "captured");
    this.state = allCaptured ? "ready_to_seal" : "incomplete_skipped";
  }

  exportDraftSnapshot() {
    return JSON.stringify({
      sessionId: this.sessionId, tenantId: this.tenantId, operatorId: this.operatorId, protocolVersion: this.protocolVersion,
      state: this.state, disclosureVersion: this.disclosureVersion, consent: this.consent,
      vehicle: this.vehicle, slots: Array.from(this.slots.entries()),
      supersededArtifacts: this.supersededArtifacts, safetyEvents: this.safetyEvents,
      auditLog: this.auditLog,
    });
  }

  static restoreFromDraftSnapshot(serializedSnapshot, now) {
    const d = JSON.parse(serializedSnapshot);
    const c = new OperatorRoadsideController({
      sessionId: d.sessionId, tenantId: d.tenantId, operatorId: d.operatorId, protocolVersion: d.protocolVersion ?? LEGACY_CAPTURE_PROTOCOL, now,
    });
    c.state = d.state;
    c.disclosureVersion = d.disclosureVersion;
    c.consent = d.consent;
    c.vehicle = d.vehicle;
    c.slots = new Map(d.slots);
    c.supersededArtifacts = d.supersededArtifacts ?? [];
    c.safetyEvents = d.safetyEvents ?? [];
    c.auditLog = d.auditLog ?? [];
    return c;
  }
}

export class ReviewerWorkbenchController {
  constructor({ reviewerId, tenantId, now = () => new Date().toISOString() }) {
    if (!reviewerId || !tenantId) throw new Error("REVIEWER_IDENTITY_AND_TENANT_REQUIRED");
    this.reviewerId = reviewerId;
    this.tenantId = tenantId;
    this.now = now;
    this.cases = new Map();
  }

  ingestSealedCase(caseEnvelope) {
    if (!caseEnvelope || typeof caseEnvelope.sessionId !== "string" || !caseEnvelope.sessionId.trim()) {
      throw new Error("SESSION_ID_REQUIRED");
    }
    if (caseEnvelope.tenantId !== this.tenantId) throw new Error("CROSS_TENANT_ACCESS_DENIED");
    const protocolVersion = caseEnvelope.captureProtocolVersion ?? LEGACY_CAPTURE_PROTOCOL;
    if (!CAPTURE_PROTOCOL_SLOTS[protocolVersion]) throw new Error("UNSUPPORTED_CAPTURE_PROTOCOL");
    if (!caseEnvelope.integrityVerified) throw new Error("UNVERIFIED_MANIFEST_CANNOT_ENTER_QUEUE");
    if (!Number.isFinite(caseEnvelope.confidence) || caseEnvelope.confidence < 0 || caseEnvelope.confidence > 1) {
      throw new Error("INVALID_REVIEW_CONFIDENCE");
    }
    const band = caseEnvelope.confidence < 0.5 ? "priority-review" : "standard-review";
    const record = {
      ...caseEnvelope, protocolVersion, canonicalSlots: CAPTURE_PROTOCOL_SLOTS[protocolVersion], band, lockedBy: null, lockedAt: null,
      status: "queued", decision: null, retakeSlots: [],
    };
    this.cases.set(caseEnvelope.sessionId, record);
    return record;
  }

  getOrderedQueue({ statusFilter = "queued" } = {}) {
    const matching = Array.from(this.cases.values()).filter(
      (c) => !statusFilter || c.status === statusFilter
    );
    return matching.sort((a, b) => {
      if (a.band !== b.band) return a.band === "priority-review" ? -1 : 1;
      return a.confidence - b.confidence;
    });
  }

  claimCase(sessionId) {
    const item = this._getAuthorizedCase(sessionId);
    if (item.lockedBy && item.lockedBy !== this.reviewerId) {
      throw new Error(`CASE_ALREADY_LOCKED_BY:${item.lockedBy}`);
    }
    item.lockedBy = this.reviewerId;
    item.lockedAt = this.now();
    item.status = "in_review";
    return item;
  }

  requestSlotRetake(sessionId, slotsToRetake, reasonCode) {
    const item = this._requireOwnedCase(sessionId);
    if (!Array.isArray(slotsToRetake) || slotsToRetake.length === 0) {
      throw new Error("RETAKE_SLOTS_REQUIRED");
    }
    if (!reasonCode || !String(reasonCode).trim()) throw new Error("RETAKE_REASON_REQUIRED");
    for (const slot of slotsToRetake) {
      if (!item.canonicalSlots.includes(slot)) throw new Error(`INVALID_RETAKE_SLOT:${slot}`);
    }
    item.status = "retake_requested";
    item.retakeSlots = [...slotsToRetake];
    item.decision = Object.freeze({
      disposition: "REQUEST_RETAKE", reviewerId: this.reviewerId,
      retakeSlots: Object.freeze([...slotsToRetake]), reasonCode, occurredAt: this.now(),
    });
    return item.decision;
  }

  recordDecision(sessionId, { disposition, reasonCode, notes, verifiedArtifactIds }) {
    const item = this._requireOwnedCase(sessionId);
    if (!REVIEW_DISPOSITIONS.includes(disposition)) throw new Error(`INVALID_DISPOSITION:${disposition}`);
    if (!reasonCode || !String(reasonCode).trim()) throw new Error("REASON_CODE_REQUIRED");
    if (!Array.isArray(verifiedArtifactIds) || verifiedArtifactIds.length === 0) {
      throw new Error("VERIFIED_ARTIFACT_IDS_REQUIRED");
    }
    if (verifiedArtifactIds.some((id) => typeof id !== "string" || !id.trim())
        || new Set(verifiedArtifactIds).size !== verifiedArtifactIds.length) {
      throw new Error("INVALID_VERIFIED_ARTIFACT_IDS");
    }
    const decision = Object.freeze({
      sessionId, tenantId: this.tenantId, disposition, reviewerId: this.reviewerId,
      reasonCode: String(reasonCode).trim(), notes: notes ? String(notes).trim() : "",
      verifiedArtifactIds: Object.freeze([...verifiedArtifactIds]), occurredAt: this.now(),
    });
    item.decision = decision;
    item.status = disposition === "ESCALATE_SUPERVISOR" ? "escalated" : "decided";
    return decision;
  }

  _getAuthorizedCase(sessionId) {
    const item = this.cases.get(sessionId);
    if (!item) throw new Error(`CASE_NOT_FOUND:${sessionId}`);
    if (item.tenantId !== this.tenantId) throw new Error("CROSS_TENANT_ACCESS_DENIED");
    return item;
  }

  _requireOwnedCase(sessionId) {
    const item = this._getAuthorizedCase(sessionId);
    if (item.lockedBy !== this.reviewerId) throw new Error("CASE_LOCK_OWNERSHIP_REQUIRED");
    if (item.status === "decided") throw new Error("IMMUTABLE_DECISION_ALREADY_RECORDED");
    return item;
  }
}

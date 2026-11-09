import assert from "node:assert/strict";
import {
  CANONICAL_SLOTS,
  OperatorRoadsideController,
  ReviewerWorkbenchController,
} from "../src/modules/capture/slice2_workbench_controller.mjs";

let tick = 0;
const now = () => `2026-11-08T18:00:${String(tick++).padStart(2, "0")}Z`;
const operator = new OperatorRoadsideController({
  sessionId: "session-s2", tenantId: "tenant-a", operatorId: "operator-a", now,
});
operator.presentDisclosure("disclosure-v1");
operator.recordConsent({ ownerActorId: "owner-a", accepted: true });
operator.recordVehicleIdentification({ vin: "1HGCM82633A004352" });
operator.pauseForRoadsideSafety("police_control");
assert.equal(operator.state, "paused_unsafe");
operator.skipUnsafeSlot("left_side", "traffic_side_hazard");
assert.equal(operator.slots.get("left_side").status, "skipped_unsafe");
operator.resumeFromSafetyPause();
operator.captureSlot({ slot: "front_center", artifactId: "a1", sha256Hex: "A".repeat(64), byteLength: 1024 });
operator.captureSlot({ slot: "front_center", artifactId: "a2", sha256Hex: "b".repeat(64), byteLength: 2048 });
assert.equal(operator.supersededArtifacts[0].artifactId, "a1");
const restored = OperatorRoadsideController.restoreFromDraftSnapshot(operator.exportDraftSnapshot(), now);
assert.equal(restored.slots.get("front_center").artifactId, "a2");
assert.equal(restored.auditLog.find((e) => e.kind === "VEHICLE_IDENTIFIED").payload.vin, undefined);

const reviewer = new ReviewerWorkbenchController({ reviewerId: "reviewer-a", tenantId: "tenant-a", now });
assert.throws(() => reviewer.ingestSealedCase({ sessionId: "cross", tenantId: "tenant-b", integrityVerified: true }), /CROSS_TENANT/);
assert.throws(() => reviewer.ingestSealedCase({ sessionId: "bad", tenantId: "tenant-a", integrityVerified: false }), /UNVERIFIED_MANIFEST/);
reviewer.ingestSealedCase({ sessionId: "priority", tenantId: "tenant-a", integrityVerified: true, confidence: 0.2 });
reviewer.ingestSealedCase({ sessionId: "standard", tenantId: "tenant-a", integrityVerified: true, confidence: 0.9 });
assert.equal(reviewer.getOrderedQueue()[0].sessionId, "priority");
reviewer.claimCase("priority");
assert.throws(() => reviewer.recordDecision("priority", { disposition: "AUTO_APPROVE", reasonCode: "x", verifiedArtifactIds: ["a"] }), /INVALID_DISPOSITION/);
const decision = reviewer.recordDecision("priority", {
  disposition: "NOTE_ONLY", reasonCode: "human_reviewed", notes: "Observed damage",
  verifiedArtifactIds: ["a2"],
});
assert.equal(decision.reviewerId, "reviewer-a");
assert.equal(CANONICAL_SLOTS.length, 12);
console.log(JSON.stringify({ suite: "slice2-workbench", assertions: 12, status: "passed" }));

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  CANONICAL_SLOTS,
  LEGACY_CANONICAL_SLOTS,
  LEGACY_CAPTURE_PROTOCOL,
  OperatorRoadsideController,
  ReviewerWorkbenchController,
} from "../src/modules/capture/slice2_workbench_controller.mjs";

let tick = 0;
const now = () => `2026-11-08T18:00:${String(tick++).padStart(2, "0")}Z`;
const operator = new OperatorRoadsideController({
  sessionId: "session-s2", tenantId: "tenant-a", operatorId: "operator-a", protocolVersion: LEGACY_CAPTURE_PROTOCOL, now,
});
operator.presentDisclosure("disclosure-v1");
assert.throws(() => operator.recordConsent({ ownerActorId: "owner-a", accepted: "false" }), /CONSENT_BOOLEAN/);
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
assert.throws(() => reviewer.ingestSealedCase({ sessionId: "bad-confidence", tenantId: "tenant-a", integrityVerified: true, confidence: 2 }), /INVALID_REVIEW_CONFIDENCE/);
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
assert.equal(CANONICAL_SLOTS.length, 16);
assert.equal(LEGACY_CANONICAL_SLOTS.length, 12);

const browserWorkbenchSource = readFileSync(new URL("../app/app.mjs", import.meta.url), "utf8");
const apiSlotBlock = browserWorkbenchSource.match(/const API_CAPTURE_SLOTS = \[([\s\S]*?)\n\];/);
assert.ok(apiSlotBlock, "browser workbench must declare its server API capture slots");
const apiSlots = Array.from(apiSlotBlock[1].matchAll(/\["([a-z0-9_]+)",\s*"[^"]+"\]/g), (match) => match[1]);
assert.deepEqual(apiSlots, CANONICAL_SLOTS, "browser upload slots must exactly match the server's ordered 16-view protocol");
assert.ok(browserWorkbenchSource.includes("/v1/claim-cases"), "workbench must create a persistent claim-case record");
assert.ok(browserWorkbenchSource.includes("capture_protocol_version:\"claims2car-16-v1\""), "new cases must bind the implemented 16-view protocol");
assert.ok(!browserWorkbenchSource.includes('api("/v1/capture-sessions",state.token'), "workbench must not create unlinked controlled-test sessions");

console.log(JSON.stringify({ suite: "slice2-workbench", assertions: 12, status: "passed" }));

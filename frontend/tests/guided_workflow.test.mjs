// Guided capture workflow controller assertions (Slice 4). Pure offline tests
// with an injected localStorage-shaped storage; no images, no network, no
// vehicle decoding. Mirrors backend capture_workflow semantics.
import assert from 'node:assert/strict';
import { createGuidedCapture, resumeGuidedCapture, DISCLOSURE_VERSION, WORKFLOW_STORAGE_KEY } from '../src/modules/capture/guided_workflow.mjs';
import { validateVin } from '../src/modules/capture/vin.mjs';

const SHOT_LIST = ['vin_ocr','doc_ocr','front','front_left','driver_side','rear_left','rear','rear_right','passenger_side','front_right','interior_front','undercarriage_engine'];
const VALID_VIN = '1HGCM82633A004352';
const records = [];
function test(id, action) {
  try { action(); records.push({ id, outcome: 'passed' }); }
  catch (error) { records.push({ id, outcome: 'failed', error_type: error.name }); }
}
function makeStorage() {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)), _map: map };
}
const digest = (n) => 'a'.repeat(63) + String(n);

function makeController(storage = makeStorage()) {
  return createGuidedCapture({ shotList: SHOT_LIST, storage, sessionId: 'session-slice4' });
}
function consented(controller) {
  controller.presentDisclosure(DISCLOSURE_VERSION);
  controller.recordConsent(true);
  controller.enterVin(VALID_VIN);
}

test('empty_or_missing_shot_list_rejected', () => {
  assert.throws(() => createGuidedCapture({ shotList: [], storage: makeStorage(), sessionId: 's' }), /INVALID_SHOT_LIST/);
  assert.throws(() => createGuidedCapture({ shotList: SHOT_LIST, storage: null, sessionId: 's' }), /STORAGE_REQUIRED/);
});

test('consent_requires_disclosure_presentation', () => {
  const c = makeController();
  assert.deepEqual(c.recordConsent(true), { ok: false, reason: 'DISCLOSURE_NOT_PRESENTED' });
});

test('stale_disclosure_version_rejected', () => {
  const c = makeController();
  assert.deepEqual(c.presentDisclosure('disclosure-2024'), { ok: false, reason: 'DISCLOSURE_VERSION_MISMATCH' });
});

test('implicit_consent_rejected', () => {
  const c = makeController();
  c.presentDisclosure(DISCLOSURE_VERSION);
  assert.deepEqual(c.recordConsent(false), { ok: false, reason: 'CONSENT_NOT_EXPLICIT' });
  assert.deepEqual(c.recordConsent('yes'), { ok: false, reason: 'CONSENT_NOT_EXPLICIT' });
});

test('vin_entry_requires_consent', () => {
  const c = makeController();
  assert.deepEqual(c.enterVin(VALID_VIN), { ok: false, reason: 'CAPTURE_ORDER_VIOLATION' });
});

test('uncertain_vin_recorded_not_repaired', () => {
  const c = makeController();
  c.presentDisclosure(DISCLOSURE_VERSION);
  c.recordConsent(true);
  const bad = VALID_VIN.slice(0, 8) + '4' + VALID_VIN.slice(9);
  const r = c.enterVin(bad);
  assert.equal(r.ok, false);
  assert.equal(r.reason, 'VIN_UNCERTAIN');
  assert.equal(r.uncertainty.recaptureRequired, true);
  assert.equal(c.snapshot().vin, null);
  assert.deepEqual(validateVin(bad).reason, 'CHECKSUM_MISMATCH');
  const ok = c.enterVin(VALID_VIN);
  assert.equal(ok.ok, true);
  assert.equal(c.snapshot().vinUncertainty, null);
});

test('capture_requires_vin', () => {
  const c = makeController();
  c.presentDisclosure(DISCLOSURE_VERSION);
  c.recordConsent(true);
  assert.deepEqual(c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 }), { ok: false, reason: 'CAPTURE_ORDER_VIOLATION' });
});

test('unknown_slot_rejected', () => {
  const c = makeController();
  consented(c);
  assert.deepEqual(c.recordCapture({ slot: 'trunk', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 }), { ok: false, reason: 'UNKNOWN_SLOT' });
});

test('invalid_digest_and_length_rejected', () => {
  const c = makeController();
  consented(c);
  assert.deepEqual(c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: 'zz', byteLength: 10 }), { ok: false, reason: 'INVALID_DIGEST' });
  assert.deepEqual(c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 0 }), { ok: false, reason: 'INVALID_BYTE_LENGTH' });
});

test('duplicate_artifact_id_rejected', () => {
  const c = makeController();
  consented(c);
  c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  assert.deepEqual(c.recordCapture({ slot: 'rear', artifactId: 'a1', sha256Hex: digest(2), byteLength: 10 }), { ok: false, reason: 'DUPLICATE_ARTIFACT_ID' });
});

test('local_retake_replaces_slot_entry', () => {
  const c = makeController();
  consented(c);
  c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  c.recordCapture({ slot: 'front', artifactId: 'a2', sha256Hex: digest(2), byteLength: 12 });
  const pending = c.pendingSync();
  assert.equal(pending.length, 1);
  assert.equal(pending[0].artifactId, 'a2');
});

test('pending_slots_tracks_progress', () => {
  const c = makeController();
  consented(c);
  c.recordCapture({ slot: 'vin_ocr', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  const snap = c.snapshot();
  assert.equal(snap.capturedSlots.length, 1);
  assert.equal(snap.pendingSlots.length, 11);
  assert.equal(snap.pendingSyncCount, 1);
});

test('mark_synced_clears_pending', () => {
  const c = makeController();
  consented(c);
  c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  assert.equal(c.markSynced('a1'), true);
  assert.equal(c.pendingSync().length, 0);
  assert.equal(c.markSynced('unknown'), false);
});

test('draft_survives_storage_restart', () => {
  const storage = makeStorage();
  const c = createGuidedCapture({ shotList: SHOT_LIST, storage, sessionId: 'session-slice4' });
  consented(c);
  c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  const revision = c.snapshot().revision;
  // App restart: raw draft recovered from the same storage.
  const recovered = resumeGuidedCapture({ storage });
  assert.equal(recovered.sessionId, 'session-slice4');
  assert.equal(recovered.slots.front.artifactId, 'a1');
  assert.equal(recovered.revision, revision);
  assert.equal(recovered.consented, true);
});

test('resume_without_storage_returns_null', () => {
  const storage = { getItem: () => null, setItem: () => {} };
  assert.equal(resumeGuidedCapture({ storage }), null);
  const corrupt = { getItem: () => '{not json', setItem: () => {} };
  assert.equal(resumeGuidedCapture({ storage: corrupt }), null);
});

test('abort_is_recorded', () => {
  const c = makeController();
  consented(c);
  c.abort();
  assert.equal(c.snapshot().aborted, true);
});

test('revision_monotonic_across_captures', () => {
  const c = makeController();
  consented(c);
  c.recordCapture({ slot: 'front', artifactId: 'a1', sha256Hex: digest(1), byteLength: 10 });
  const first = c.snapshot().revision;
  c.recordCapture({ slot: 'rear', artifactId: 'a2', sha256Hex: digest(2), byteLength: 10 });
  const second = c.snapshot().revision;
  assert.ok(second > first);
  assert.equal(c.pendingSync().length, 2);
});

test('storage_key_is_stable', () => {
  assert.equal(WORKFLOW_STORAGE_KEY, 'c2c.guided-capture.v1');
});

const failures = records.filter(r => r.outcome !== 'passed').length;
const successful = records.length > 0 && new Set(records.map(r => r.id)).size === records.length && failures === 0;
console.log(JSON.stringify({ classification: 'offline-guided-capture-controller-tests', commit: process.env.GITHUB_SHA ?? null, runtime: process.version, executed: records.length, failures, successful, tests: records }, null, 2));
process.exitCode = successful ? 0 : 1;

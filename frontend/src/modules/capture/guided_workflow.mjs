/**
 * Guided capture workflow controller (plan v1.3 phases 5-6; Slice 4).
 *
 * Client-side coordination for the M1 flow: disclosure gate -> consent ->
 * VIN entry (vin.mjs guard) -> shot-list-guided capture -> local draft
 * persistence -> resumable sync. Storage is injected (localStorage-shaped
 * {getItem,setItem}); the server-side ordering authority is
 * app/capture_workflow.py — this controller never fabricates consent,
 * quality verdicts, or state transitions.
 */
import { validateVin } from './vin.mjs';

export const DISCLOSURE_VERSION = 'disclosure-v1';
export const WORKFLOW_STORAGE_KEY = 'c2c.guided-capture.v1';

export function createGuidedCapture({ shotList, storage, sessionId, now = () => new Date().toISOString() }) {
  if (!Array.isArray(shotList) || shotList.length === 0) throw new Error('INVALID_SHOT_LIST');
  if (storage === null || storage === undefined) throw new Error('STORAGE_REQUIRED');
  if (typeof sessionId !== 'string' || !sessionId.trim()) throw new Error('INVALID_SESSION');

  const state = {
    sessionId,
    disclosurePresented: null,
    consented: false,
    vin: null,
    vinUncertainty: null,
    slots: {},        // slot -> { artifactId, sha256Hex, byteLength, capturedAt, synced }
    revision: 0,
    aborted: false,
  };

  function persist() {
    state.revision += 1;
    storage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify(state));
    return state.revision;
  }

  function presentDisclosure(version) {
    if (version !== DISCLOSURE_VERSION) {
      return { ok: false, reason: 'DISCLOSURE_VERSION_MISMATCH' };
    }
    if (state.consented) return { ok: false, reason: 'ALREADY_CONSENTED' };
    state.disclosurePresented = version;
    persist();
    return { ok: true };
  }

  function recordConsent(accepted) {
    if (state.disclosurePresented !== DISCLOSURE_VERSION) return { ok: false, reason: 'DISCLOSURE_NOT_PRESENTED' };
    if (accepted !== true) return { ok: false, reason: 'CONSENT_NOT_EXPLICIT' };
    state.consented = true;
    persist();
    return { ok: true };
  }

  function enterVin(input) {
    if (!state.consented) return { ok: false, reason: 'CAPTURE_ORDER_VIOLATION' };
    const report = validateVin(input);
    if (!report.ok) {
      // Uncertainty is recorded, never repaired; recapture is required.
      state.vinUncertainty = { code: report.reason, recaptureRequired: true, recordedAt: now() };
      persist();
      return { ok: false, reason: 'VIN_UNCERTAIN', message: report.message, uncertainty: state.vinUncertainty };
    }
    state.vin = report.vin;
    state.vinUncertainty = null;
    persist();
    return { ok: true, vin: report.vin, scope: report.scope };
  }

  function recordCapture({ slot, artifactId, sha256Hex, byteLength }) {
    if (!state.consented || state.vin === null) return { ok: false, reason: 'CAPTURE_ORDER_VIOLATION' };
    if (!shotList.includes(slot)) return { ok: false, reason: 'UNKNOWN_SLOT' };
    if (typeof artifactId !== 'string' || !artifactId.trim()) return { ok: false, reason: 'INVALID_ARTIFACT_ID' };
    if (typeof sha256Hex !== 'string' || !/^[0-9a-f]{64}$/.test(sha256Hex)) return { ok: false, reason: 'INVALID_DIGEST' };
    if (!Number.isInteger(byteLength) || byteLength <= 0) return { ok: false, reason: 'INVALID_BYTE_LENGTH' };
    if (Object.values(state.slots).some(s => s.artifactId === artifactId)) {
      return { ok: false, reason: 'DUPLICATE_ARTIFACT_ID' };
    }
    state.slots[slot] = { artifactId, sha256Hex, byteLength, capturedAt: now(), synced: false };
    persist();
    return { ok: true, slot };
  }

  function pendingSlots() {
    return shotList.filter(slot => !(slot in state.slots));
  }

  function pendingSync() {
    return Object.entries(state.slots)
      .filter(([, entry]) => !entry.synced)
      .map(([slot, entry]) => ({ slot, ...entry }));
  }

  function markSynced(artifactId) {
    for (const entry of Object.values(state.slots)) {
      if (entry.artifactId === artifactId) {
        entry.synced = true;
        persist();
        return true;
      }
    }
    return false;
  }

  function abort() {
    state.aborted = true;
    persist();
    return { ok: true };
  }

  function snapshot() {
    return {
      sessionId: state.sessionId,
      revision: state.revision,
      disclosurePresented: state.disclosurePresented,
      consented: state.consented,
      vin: state.vin,
      vinUncertainty: state.vinUncertainty,
      capturedSlots: Object.keys(state.slots).sort(),
      pendingSlots: pendingSlots(),
      pendingSyncCount: pendingSync().length,
      aborted: state.aborted,
    };
  }

  return { presentDisclosure, recordConsent, enterVin, recordCapture, pendingSlots, pendingSync, markSynced, abort, snapshot };
}

export function resumeGuidedCapture({ storage }) {
  const raw = storage.getItem(WORKFLOW_STORAGE_KEY);
  if (raw === null || raw === undefined) return null;
  let parsed;
  try { parsed = JSON.parse(raw); } catch { return null; }
  if (parsed === null || typeof parsed !== 'object') return null;
  return parsed; // caller rehydrates controller state from this snapshot
}

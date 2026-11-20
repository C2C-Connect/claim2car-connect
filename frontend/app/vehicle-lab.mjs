import { validateVin } from "../src/modules/capture/vin.mjs";

const $ = (id) => document.getElementById(id);
const API = "/api";
const MAX_EVIDENCE_BYTES = 25 * 1024 * 1024;
const state = { profile:null, vin:null, retrievedAt:null, photos:new Map(), qualities:new Map(), observations:[], stream:null, detector:null, scanFrame:null, captureToken:null, claimId:null, claimRequestId:null, sessionId:null, captureConsentRecorded:false, vehicleRecorded:false, sealed:false, manifestDigest:null, capturePaused:false, activeExceptions:new Map() };
const slots = [
  ["00_front_exterior","Front exterior"],
  ["01_front_right_exterior","Front-right 45°"],
  ["02_right_side_exterior","Right-side profile"],
  ["03_rear_right_exterior","Rear-right 45°"],
  ["04_rear_exterior","Rear exterior"],
  ["05_rear_left_exterior","Rear-left 45°"],
  ["06_left_side_exterior","Left-side profile"],
  ["07_front_left_exterior","Front-left 45°"],
  ["08_wheel_front_left","Front-left wheel assembly"],
  ["09_wheel_front_right","Front-right wheel assembly"],
  ["10_wheel_rear_right","Rear-right wheel assembly"],
  ["11_wheel_rear_left","Rear-left wheel assembly"],
  ["12_cabin_front_airbags","Front cabin / visible airbag indicators"],
  ["13_instrument_cluster_odometer","Instrument cluster / odometer"],
  ["14_physical_vin","Physical VIN plate"],
  ["15_license_and_insurance_docs","License / insurance documentation"]
];
const show = (id, yes=true) => { $(id).hidden = !yes; };
const setMessage = (value, error=false) => {
  $("vin-message").textContent = value;
  $("vin-message").classList.toggle("error", error);
};
const now = () => new Date().toLocaleString();
const uuid = () => crypto.randomUUID();
async function captureApi(path, token, options={}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", "Bearer " + token);
  headers.set("Cache-Control", "no-store");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  const response = await fetch(API + path, {...options, headers, cache:"no-store"});
  if (!response.ok) {
    let detail = "REQUEST_FAILED_" + response.status;
    try { const body = await response.json(); if (typeof body.detail === "string") detail = body.detail; } catch {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}
function bytesToBase64(bytes) {
  let binary = "";
  for (let offset=0; offset<bytes.length; offset+=0x8000) binary += String.fromCharCode(...bytes.subarray(offset, Math.min(offset+0x8000,bytes.length)));
  return btoa(binary);
}
async function sha256Hex(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2,"0")).join("");
}
function backendStatus(value, error=false) {
  $("backend-status").textContent = value;
  $("backend-status").classList.toggle("error", error);
}
$("create-claim-case").addEventListener("click", async () => {
  const token = $("capture-operator-token").value.trim();
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(token)) { backendStatus("Enter a valid operator credential.", true); return; }
  const button = $("create-claim-case"); button.disabled = true;
  try {
    // Keep identifiers stable across a retry after an ambiguous network failure.
    state.claimId ||= uuid();
    state.claimRequestId ||= uuid();
    const created = await captureApi("/v1/claim-cases", token, {
      method:"POST", body:JSON.stringify({claim_id:state.claimId,request_id:state.claimRequestId})
    });
    if (!created || created.scope !== "persistent-claim-case" || created.claim_id !== state.claimId || !created.capture_session_id) {
      throw new Error("PERSISTENT_CLAIM_CASE_RESPONSE_INVALID");
    }
    state.captureToken = token; state.sessionId = created.capture_session_id;
    $("capture-operator-token").value = "";
    button.textContent = "Persistent case created";
    button.disabled = true; $("capture-operator-token").disabled = true;
    $("claim-case-id").textContent = "CLAIM CASE  " + created.claim_id + "  ·  CAPTURE SESSION  " + created.capture_session_id;
    $("claim-case-id").hidden = false;
    $("owner-consent-panel").hidden = false;
    backendStatus("Persistent claim case created by the authenticated PostgreSQL authority · Awaiting owner consent.");
    try { await refreshEvidenceReadiness(); }
    catch (error) { backendStatus("Persistent case created, but server readiness is unavailable · " + error.message, true); }
  } catch (error) { backendStatus(error.message, true); button.disabled = false; }
});
$("record-capture-consent").addEventListener("click", async () => {
  const ownerToken = $("owner-capture-token").value.trim();
  if (!state.sessionId || !ownerToken || !$("owner-capture-consent").checked) {
    backendStatus("Owner token and explicit capture consent are required.", true); return;
  }
  const button = $("record-capture-consent"); button.disabled = true;
  try {
    await captureApi("/v1/capture-sessions/" + state.sessionId + "/consent", ownerToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),accepted:true,scope:"capture_review"})
    });
    $("owner-capture-token").value = ""; $("owner-capture-token").disabled = true;
    $("owner-capture-consent").disabled = true; state.captureConsentRecorded = true;
    backendStatus("Owner capture consent recorded by the server · VIN acquisition is enabled.");
  } catch (error) { backendStatus(error.message, true); button.disabled = false; }
});

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));

async function refreshEvidenceReadiness() {
  if (!state.captureToken || !state.sessionId) return;
  const readiness = await captureApi("/v1/capture-sessions/" + state.sessionId + "/evidence-readiness", state.captureToken);
  state.capturePaused = readiness.capture_paused === true;
  state.activeExceptions = new Map((readiness.active_capture_exceptions || []).map(item => [item.slot, item]));
  $("capture-paused-status").textContent = state.capturePaused ? "CAPTURE PAUSED · uploads blocked" : "Capture active";
  $("pause-capture").hidden = state.capturePaused;
  $("resume-capture").hidden = !state.capturePaused;
  // Successful transitions re-enable the opposite action; never leave the UI locked.
  $("pause-capture").disabled = !state.captureToken || !state.sessionId || state.capturePaused;
  $("resume-capture").disabled = !state.captureToken || !state.sessionId || !state.capturePaused;
  renderPhotoSlots();
  updateSealAvailability();
  return readiness;
}
function localizationStatus(localization) {
  if (localization?.analysis?.status === "COMPLETED") {
    const count = localization.analysis.observations?.length || 0;
    return "Contrast baseline: " + count + " candidate region(s) · heuristic, not AI";
  }
  if (localization?.status === "UNAVAILABLE") return "Contrast baseline unavailable · " + (localization.code || "unknown error");
  if (localization?.status === "NOT_APPLICABLE") return "Localization not applicable to this view";
  return "Localization not run";
}
function renderPhotoSlots() {
  const grid = $("photo-grid");
  grid.replaceChildren();
  for (const [slot,label] of slots) {
    const card = document.createElement("div");
    card.className = "lab-photo-card";
    const title = document.createElement("strong");
    title.textContent = label;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.capture = "environment";
    input.setAttribute("aria-label", "Photograph " + label);
    const stateText = document.createElement("div");
    stateText.className = "photo-state";
    stateText.textContent = "Not captured";
    const preview = document.createElement("img");
    preview.alt = label;
    preview.hidden = true;
    const quality = document.createElement("select");
    quality.setAttribute("aria-label", "Quality review for " + label);
    quality.disabled = true;
    quality.add(new Option("Quality review pending",""));
    quality.add(new Option("Usable","usable"));
    quality.add(new Option("Needs retake","retake"));
        quality.addEventListener("change", () => { state.qualities.set(slot, quality.value); updateSealAvailability(); });
    const exceptionControls = document.createElement("div");
    exceptionControls.className = "capture-exception-controls";
    const reason = document.createElement("select");
    reason.setAttribute("aria-label", "Capture exception reason for " + label);
    reason.add(new Option("Record exception reason", ""));
    for (const [code, text] of [["UNSAFE_TO_APPROACH","Unsafe to approach"],["ACCESS_RESTRICTED","Access restricted"],["VEHICLE_IN_MOTION","Vehicle in motion"],["WEATHER_HAZARD","Weather hazard"],["OWNER_DECLINED","Owner declined this view"],["EQUIPMENT_FAILURE","Equipment failure"],["OTHER","Other"]]) reason.add(new Option(text,code));
    const explanation = document.createElement("textarea");
    explanation.rows = 2; explanation.maxLength = 500;
    explanation.placeholder = "Explain why this view is unavailable (required)";
    explanation.setAttribute("aria-label", "Capture exception explanation for " + label);
    const recordException = document.createElement("button");
    recordException.type = "button"; recordException.className = "button quiet";
    recordException.textContent = "Record audited exception";
    const activeException = state.activeExceptions.get(slot);
    const exceptionStatus = document.createElement("div");
    exceptionStatus.className = "photo-state";
    exceptionStatus.textContent = activeException ? "OPEN EXCEPTION · " + activeException.reason_code + " · " + activeException.explanation : "No open exception";
    recordException.disabled = !state.captureToken || !state.sessionId || !state.captureConsentRecorded || state.capturePaused || Boolean(activeException) || state.sealed;
    recordException.addEventListener("click", async () => {
      if (!reason.value || !explanation.value.trim()) { exceptionStatus.textContent = "Select a reason and explain the exception."; return; }
      recordException.disabled = true;
      try {
        await captureApi("/v1/capture-sessions/" + state.sessionId + "/exceptions", state.captureToken, {
          method:"POST", body:JSON.stringify({request_id:uuid(),slot,reason_code:reason.value,explanation:explanation.value.trim()})
        });
        await refreshEvidenceReadiness();
        backendStatus("Audited exception recorded. The view remains required; exception records do not replace original evidence.");
      } catch (error) { exceptionStatus.textContent = "Exception not recorded · " + error.message; recordException.disabled = false; }
    });
    const resolution = document.createElement("select");
    resolution.setAttribute("aria-label", "Capture exception resolution for " + label);
    resolution.add(new Option("Resolution action", ""));
    for (const [code,text] of [["CAPTURED_AFTER_RETRY","Captured after retry"],["NO_LONGER_APPLICABLE","No longer applicable"]]) resolution.add(new Option(text,code));
    const resolutionNotes = document.createElement("textarea");
    resolutionNotes.rows = 2; resolutionNotes.maxLength = 500;
    resolutionNotes.placeholder = "Explain resolution (required)";
    resolutionNotes.setAttribute("aria-label", "Exception resolution explanation for " + label);
    const resolveException = document.createElement("button");
    resolveException.type = "button"; resolveException.className = "button quiet"; resolveException.textContent = "Resolve exception";
    resolveException.disabled = !activeException || !state.photos.get(slot)?.uploaded || state.capturePaused || state.sealed;
    resolveException.addEventListener("click", async () => {
      if (!resolution.value || !resolutionNotes.value.trim()) { exceptionStatus.textContent = "Select a resolution and explain it."; return; }
      resolveException.disabled = true;
      try {
        await captureApi("/v1/capture-sessions/" + state.sessionId + "/exceptions/resolve", state.captureToken, {
          method:"POST", body:JSON.stringify({request_id:uuid(),slot,resolution_code:resolution.value,explanation:resolutionNotes.value.trim()})
        });
        await refreshEvidenceReadiness();
        backendStatus("Exception resolution recorded. All 16 original views are still required before sealing.");
      } catch (error) { exceptionStatus.textContent = "Resolution not recorded · " + error.message; resolveException.disabled = false; }
    });
    exceptionControls.append(reason,explanation,recordException,exceptionStatus,resolution,resolutionNotes,resolveException);
    input.addEventListener("change", async () => {
      const file = input.files?.[0]; if (!file) return;
      if (!file.type.startsWith("image/") || file.size <= 0 || file.size > MAX_EVIDENCE_BYTES) {
        stateText.textContent = "Choose a non-empty image no larger than 25 MiB."; input.value = ""; return;
      }
      if (!state.captureToken || !state.sessionId || !state.captureConsentRecorded || !state.vehicleRecorded) {
        stateText.textContent = "Connect a session, record owner consent, and decode the vehicle before upload."; input.value = ""; return;
      }
      input.disabled = true; stateText.textContent = "Hashing and uploading original bytes…"; stateText.classList.remove("error");
      try {
        const buffer = await file.arrayBuffer(), digest = await sha256Hex(buffer), artifactId = uuid();
        const uploadResponse = await captureApi("/v1/capture-sessions/" + state.sessionId + "/artifacts", state.captureToken, {
          method:"POST", body:JSON.stringify({request_id:uuid(),artifact_id:artifactId,slot,payload_base64:bytesToBase64(new Uint8Array(buffer)),sha256:digest})
        });
        const localization = uploadResponse?.localization || null;
        const old = state.photos.get(slot); if (old?.url) URL.revokeObjectURL(old.url);
        const url = URL.createObjectURL(file);
        state.photos.set(slot,{file,url,label,artifactId,sha256:digest,uploaded:true,byteLength:file.size,localization});
        state.qualities.delete(slot); quality.disabled = false; quality.value = "";
        preview.src = url; preview.hidden = false;
        stateText.textContent = "Original uploaded · " + file.size.toLocaleString() + " bytes · SHA-256 verified" + (localization ? " · " + localizationStatus(localization) : "");
        updateReportAvailability(); syncPhotoSelect(); updateSealAvailability();
        await refreshEvidenceReadiness();
      } catch (error) {
        stateText.textContent = "Upload failed · " + error.message + " · Select the image again to retry.";
        stateText.classList.add("error"); input.value = "";
      } finally { input.disabled = false; }
    });
    const existingPhoto = state.photos.get(slot);
    if (existingPhoto?.uploaded) {
      quality.disabled = state.capturePaused;
      quality.value = state.qualities.get(slot) || "";
      preview.src = existingPhoto.url;
      preview.hidden = false;
      stateText.textContent = "Original uploaded · " + existingPhoto.byteLength.toLocaleString() + " bytes · SHA-256 verified" + (existingPhoto.localization ? " · " + localizationStatus(existingPhoto.localization) : "");
    }
    input.disabled = state.capturePaused || state.sealed;
    card.append(title,input,quality,exceptionControls,stateText,preview);
    grid.append(card);
  }
}
function syncPhotoSelect() {
  const select = $("damage-photo");
  const selected = select.value;
  select.replaceChildren(new Option("No linked photo selected",""));
  for (const [slot,label] of slots) if (state.photos.has(slot)) select.add(new Option(label,slot));
  if (state.photos.has(selected)) select.value = selected;
}
function updateSealAvailability() {
  const complete = !state.capturePaused && state.activeExceptions.size === 0 && slots.every(([slot]) => state.photos.get(slot)?.uploaded === true && state.qualities.get(slot) === "usable");
  $("seal-evidence").disabled = !complete || state.sealed || !state.sessionId || state.capturePaused || state.activeExceptions.size > 0;
}
$("pause-capture").addEventListener("click", async () => {
  if (!state.sessionId || !state.captureToken) return;
  const reason = $("capture-pause-reason").value.trim();
  if (!reason) { backendStatus("Enter a reason for pausing the capture session.", true); return; }
  $("pause-capture").disabled = true;
  try {
    await captureApi("/v1/capture-sessions/" + state.sessionId + "/pause", state.captureToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),reason})
    });
    await refreshEvidenceReadiness();
    backendStatus("Capture paused and audit event recorded. Uploads and evidence-finalization actions are blocked.");
  } catch (error) { backendStatus(error.message,true); $("pause-capture").disabled = false; }
});
$("resume-capture").addEventListener("click", async () => {
  if (!state.sessionId || !state.captureToken) return;
  const reason = $("capture-pause-reason").value.trim();
  if (!reason) { backendStatus("Enter a reason for resuming the capture session.", true); return; }
  $("resume-capture").disabled = true;
  try {
    await captureApi("/v1/capture-sessions/" + state.sessionId + "/resume", state.captureToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),reason})
    });
    await refreshEvidenceReadiness();
    backendStatus("Capture resumed and audit event recorded.");
  } catch (error) { backendStatus(error.message,true); $("resume-capture").disabled = false; }
});
$("seal-evidence").addEventListener("click", async () => {
  const button = $("seal-evidence"); button.disabled = true;
  try {
    const results = Object.fromEntries(slots.map(([slot]) => [slot, state.qualities.get(slot) === "usable"]));
    await captureApi("/v1/capture-sessions/" + state.sessionId + "/quality", state.captureToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),results})
    });
    const sealed = await captureApi("/v1/capture-sessions/" + state.sessionId + "/seal", state.captureToken, {
      method:"POST", body:JSON.stringify({request_id:uuid()})
    });
    state.sealed = true; state.manifestDigest = sealed.manifest_digest;
    $("seal-status").textContent = "Evidence sealed · Manifest SHA-256: " + sealed.manifest_digest;
    button.textContent = "Evidence sealed";
    backendStatus("All 16 original images uploaded, hash-verified, quality-reviewed, and sealed by the evidence service.");
  } catch (error) {
    $("seal-status").textContent = "Seal not completed · " + error.message;
    $("seal-status").classList.add("error"); updateSealAvailability();
  }
});
function updateReportAvailability() {
  show("report-panel", Boolean(state.profile));
}
function renderProfile() {
  const p = state.profile;
  $("vehicle-title").textContent = [p.modelYear,p.make,p.model].join(" ");
  $("decode-status").textContent = "DECODED";
  const attrs = [
    ["Model year",p.modelYear],["Make",p.make],["Model",p.model],["Body class",p.bodyClass],
    ["Trim",p.trim],["Series",p.series],["Drive type",p.driveType],["Engine cylinders",p.engineCylinders],
    ["Displacement (L)",p.displacementL],["Fuel type",p.fuelType],["Transmission",p.transmission],["Plant country",p.plantCountry],
    ["Curb weight (lb)",p.curbWeightStatus === "reported" ? p.curbWeightLb : null],
    ["Curb weight (kg)",p.curbWeightStatus === "reported" ? p.curbWeightKg.toFixed(1) : null],
    ["Curb weight status",p.curbWeightStatus]
  ];
  const grid = $("vehicle-attributes");
  grid.replaceChildren();
  for (const [label,value] of attrs) {
    const item = document.createElement("div");
    item.className = "attribute";
    const small = document.createElement("small");
    small.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value ?? "Not reported";
    item.append(small,strong);
    grid.append(item);
  }
  $("vehicle-provenance").textContent =
    "Source: NHTSA vPIC DecodeVinValuesExtended · Retrieved " + (state.retrievedAt ? new Date(state.retrievedAt).toLocaleString() : now()) +
    ". Parsed response is format-checked but the source is not independently authenticated. Missing fields remain missing. " +
    "VIN check digit status: " + p.checkDigitStatus + ". Vehicle identity decoding does not establish ownership, history, condition, roadworthiness, or safety.";
  renderPhotoSlots();
  updateReportAvailability();
  show("vehicle-panel");
  show("inspection-panel");
}
function resetVehicleEvidence() {
  for (const photo of state.photos.values()) if (photo.url) URL.revokeObjectURL(photo.url);
  state.photos.clear();
  state.qualities.clear();
  state.sealed = false;
  state.manifestDigest = null;
  $("seal-evidence").disabled = true;
  $("seal-status").textContent = "";
  state.observations = [];
  state.profile = null;
  state.retrievedAt = null;
  $("observation-list").replaceChildren();
  $("damage-notes").value = "";
  $("damage-photo").replaceChildren(new Option("No linked photo selected",""));
  show("vehicle-panel",false);
  show("inspection-panel",false);
  show("report-panel",false);
  show("report-preview",false);
  show("print-report",false);
}
async function decodeVin() {
  const raw = $("vin-entry").value.trim();
  const check = validateVin(raw);
  const mismatchOverride = check.reason === "CHECKSUM_MISMATCH";
  if ((!check.ok && !mismatchOverride) || check.normalizationChanged) {
    setMessage(check.reason === "CHECKSUM_MISMATCH" ? "The North American VIN check digit does not match. Recheck the physical VIN before continuing." : "Enter the exact 17-character VIN using permitted VIN characters, without spaces or punctuation.", true);
    return;
  }
  if (mismatchOverride) {
    show("checksum-override-row");
    setMessage("This server-authoritative capture route requires a VIN that passes its check-digit validation. The manual override is not accepted for a persisted vehicle profile.", true);
    return;
  }
  if (!$("decode-consent").checked) { setMessage("Explicit consent is required before sending the VIN to NHTSA vPIC.", true); return; }
  if (!state.captureToken || !state.sessionId || !state.captureConsentRecorded) {
    setMessage("Create an authenticated capture session and record owner capture consent before decoding or collecting evidence.", true); return;
  }
  if (state.vehicleRecorded && state.vin !== check.vin) { setMessage("This session is already bound to a different vehicle. Start a new capture session to change VIN.", true); return; }
  if (state.photos.size > 0) { setMessage("This session already contains uploaded evidence. Continue the current inspection; start a new session to restart it.", true); return; }
  const ownerToken = $("decode-owner-token").value.trim();
  if (!ownerToken) { setMessage("Re-enter the owner's token to record separate NHTSA vehicle-decoding consent.", true); return; }
  resetVehicleEvidence(); state.vin = check.vin; $("decode-vin").disabled = true;
  setMessage("Recording keyed vehicle reference and separate owner decode consent…");
  try {
    if (!state.vehicleRecorded) {
      await captureApi("/v1/capture-sessions/" + state.sessionId + "/vehicle-reference", state.captureToken, {
        method:"POST", body:JSON.stringify({request_id:uuid(),vin:check.vin})
      });
      state.vehicleRecorded = true;
    }
    const disclosure = await captureApi("/v1/vehicle-decode-disclosure", state.captureToken);
    await captureApi("/v1/capture-sessions/" + state.sessionId + "/vehicle-decode-consent", ownerToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),accepted:true,scope:"nhtsa_vpic_decode",disclosure_version:disclosure.disclosure_version})
    });
    $("decode-owner-token").value = "";
    const profile = await captureApi("/v1/capture-sessions/" + state.sessionId + "/vehicle-profile", state.captureToken, {
      method:"POST", body:JSON.stringify({request_id:uuid(),vin:check.vin})
    });
    if (!["DECODED","PARTIAL"].includes(profile.status)) throw new Error(profile.decode_error_code || "VEHICLE_DECODE_UNRESOLVED");
    const attrs = profile.attributes || {}, value = key => attrs[key]?.value ?? null;
    state.profile = {
      modelYear:value("model_year"), make:value("make"), model:value("model"), bodyClass:value("body_class"),
      trim:value("trim"), series:value("series"), driveType:value("drive_type"),
      engineCylinders:value("engine_cylinders"), displacementL:value("displacement_l"),
      fuelType:value("fuel_type_primary"), transmission:null, plantCountry:null,
      curbWeightLb:value("curb_weight_lb"),
      curbWeightKg:value("curb_weight_lb") == null ? null : value("curb_weight_lb") * 0.45359237,
      curbWeightStatus:value("curb_weight_lb") == null ? "not_reported" : "reported",
      checkDigitStatus:"VALID", providerStatus:profile.status, provider:profile.provider,
      responseSha256:profile.response_sha256, physicsInputEligibility:profile.physics_input_eligibility
    };
    state.retrievedAt = profile.requested_at; renderProfile();
    setMessage("Vehicle profile decoded and recorded by the authenticated evidence service. Attributes remain provider-reported; no ownership or condition finding is implied.");
    backendStatus("Capture session active · Vehicle identity recorded · NHTSA profile snapshot stored.");
    await refreshEvidenceReadiness();
  } catch (error) {
    state.profile = null; show("vehicle-panel",false); show("inspection-panel",false); show("report-panel",false);
    setMessage("Server-authoritative vehicle decode unavailable: " + error.message + ". Verify consent and retry.", true);
  } finally { $("decode-vin").disabled = false; }
}
$("decode-vin").addEventListener("click",decodeVin);
$("checksum-override").addEventListener("change",() => {
  if ($("checksum-override").checked) setMessage("Override acknowledged. The VIN remains flagged for manual verification; this is not proof of vehicle identity.");
});
$("vin-entry").addEventListener("input",() => {
  const value = $("vin-entry").value;
  const result = validateVin(value);
  show("checksum-override-row", result.reason === "CHECKSUM_MISMATCH");
  if (result.reason !== "CHECKSUM_MISMATCH") { $("checksum-override").checked = false; setMessage(""); }
});
async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    $("camera-status").textContent = "Camera access unavailable. Enter the VIN manually.";
    show("camera-wrap");
    return;
  }
  if (!("BarcodeDetector" in window)) {
    $("camera-status").textContent = "Barcode scanning is not supported in this browser. Enter the VIN manually; VIN-plate photo OCR is not included.";
    show("camera-wrap");
    return;
  }
  try {
    const formats = await BarcodeDetector.getSupportedFormats();
    const supported = ["code_39","code_128","qr_code","data_matrix"].filter(x => formats.includes(x));
    if (!supported.length) throw new Error("No supported barcode format is available.");
    state.detector = new BarcodeDetector({formats:supported});
    state.stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"}},audio:false});
    $("camera-video").srcObject = state.stream;
    await $("camera-video").play();
    show("camera-wrap");
    $("camera-status").textContent = "Point the rear camera at the VIN barcode.";
    const scan = async () => {
      if (!state.stream) return;
      try {
        const codes = await state.detector.detect($("camera-video"));
        const match = codes.map(x => String(x.rawValue || "").replace(/[^A-Za-z0-9]/g,"").toUpperCase()).find(x => x.length === 17);
        if (match) {
          $("vin-entry").value = match;
          stopCamera();
          setMessage("VIN barcode detected. Verify every character against the physical VIN plate before decoding.");
          return;
        }
      } catch {}
      state.scanFrame = requestAnimationFrame(scan);
    };
    state.scanFrame = requestAnimationFrame(scan);
  } catch (error) {
    $("camera-status").textContent = "Scanner could not start: " + error.message + ". Enter the VIN manually.";
    show("camera-wrap");
  }
}
function stopCamera() {
  if (state.scanFrame) cancelAnimationFrame(state.scanFrame);
  state.scanFrame = null;
  state.stream?.getTracks().forEach(track => track.stop());
  state.stream = null;
  $("camera-video").srcObject = null;
  show("camera-wrap",false);
}
$("start-camera").addEventListener("click",startCamera);
$("stop-camera").addEventListener("click",stopCamera);
$("vin-photo").addEventListener("change",() => {
  const file = $("vin-photo").files?.[0];
  if (file) $("photo-status").textContent = "VIN plate photo selected: " + file.name + ". This prototype does not OCR the image; read the VIN and enter it manually.";
});
window.addEventListener("pagehide",() => {
  stopCamera();
  for (const photo of state.photos.values()) if (photo.url) URL.revokeObjectURL(photo.url);
});
$("add-observation").addEventListener("click",() => {
  const notes = $("damage-notes").value.trim();
  const observation = {
    area:$("damage-area").value,type:$("damage-type").value,severity:$("damage-severity").value,
    photo:$("damage-photo").value,notes
  };
  if (!notes && !["No visible damage in this area","Unable to determine"].includes(observation.type)) {
    setMessage("Add a factual note describing what you observed.",true);
    return;
  }
  const estimateAction = $("estimate-action").value;
  const laborHours = Number($("estimate-hours").value);
  const partsCost = Number($("estimate-parts").value);
  const materialsCost = Number($("estimate-materials").value);
  if (![laborHours,partsCost,materialsCost].every(Number.isFinite) || laborHours < 0 || partsCost < 0 || materialsCost < 0) {
    setMessage("Estimate inputs must be non-negative numeric values.",true); return;
  }
  observation.estimate = {action:estimateAction,laborHours,partsCost,materialsCost};
  state.observations.push(observation);
  $("damage-notes").value = "";
  $("estimate-hours").value = "0";
  $("estimate-parts").value = "0";
  $("estimate-materials").value = "0";
  $("estimate-action").value = "Not assessed";
  renderObservations();
  renderEstimateSummary();
});
function renderObservations() {
  const list = $("observation-list");
  list.replaceChildren();
  state.observations.forEach((item,index) => {
    const row = document.createElement("div");
    row.className = "observation";
    const title = document.createElement("strong");
    title.textContent = (index+1) + ". " + item.area + " · " + item.type;
    const detail = document.createElement("div");
    detail.textContent = item.severity + (item.photo ? " · Photo: " + slots.find(x => x[0] === item.photo)?.[1] : "") + (item.notes ? " · " + item.notes : "");
    const estimate = document.createElement("div");
    estimate.className = "observation-estimate";
    const e = item.estimate || {};
    const rate = getEstimateRate();
    estimate.textContent = "Worksheet: " + (e.action || "Not assessed") + " · " + Number(e.laborHours || 0).toFixed(1) + " hr × $" + rate.toFixed(2) + " · Parts $" + Number(e.partsCost || 0).toFixed(2) + " · Materials/sublet $" + Number(e.materialsCost || 0).toFixed(2) + " · Subtotal $" + estimateLineSubtotal(e,rate).toFixed(2);
    row.append(title,detail,estimate);
    list.append(row);
  });
  renderEstimateSummary();
}
function getEstimateRate() {
  const rate = Number($("estimate-labor-rate").value);
  return Number.isFinite(rate) && rate >= 0 ? rate : 0;
}
function estimateLineSubtotal(line, rate) {
  return Number(line?.laborHours || 0) * rate + Number(line?.partsCost || 0) + Number(line?.materialsCost || 0);
}
function estimateTotals() {
  const rate=getEstimateRate(), taxRate=Number($("estimate-tax-rate").value);
  const normalizedTaxRate=Number.isFinite(taxRate) && taxRate >= 0 ? taxRate : 0;
  const labor=state.observations.reduce((sum,x)=>sum+Number(x.estimate?.laborHours||0)*rate,0);
  const parts=state.observations.reduce((sum,x)=>sum+Number(x.estimate?.partsCost||0),0);
  const materials=state.observations.reduce((sum,x)=>sum+Number(x.estimate?.materialsCost||0),0);
  const subtotal=labor+parts+materials, tax=subtotal*normalizedTaxRate/100;
  return {rate,taxRate:normalizedTaxRate,labor,parts,materials,subtotal,tax,total:subtotal+tax};
}
function renderEstimateSummary() {
  const node=$("estimate-summary");
  if(!node) return;
  if(!state.observations.length){node.textContent="No estimate line items yet.";return;}
  const t=estimateTotals();
  node.textContent="Labor $" + t.labor.toFixed(2) + " · Parts $" + t.parts.toFixed(2) + " · Materials/sublet $" + t.materials.toFixed(2) + " · Subtotal $" + t.subtotal.toFixed(2) + " · Tax $" + t.tax.toFixed(2) + " · Worksheet total $" + t.total.toFixed(2);
}
$("estimate-labor-rate").addEventListener("input",renderObservations);
$("estimate-tax-rate").addEventListener("input",renderEstimateSummary);
function reportHtml() {
  const p = state.profile;
  const missing = slots.filter(([slot]) => !state.photos.has(slot)).map(([slot,label]) => {
    const select = [...$("photo-grid").querySelectorAll("select")].find(node => node.value && node.getAttribute("aria-label") === "Capture status for " + label);
    return select ? label + " (" + select.options[select.selectedIndex].text + ")" : label;
  });
  const rows = [
    ["VIN",state.vin],["Model year",p.modelYear],["Make",p.make],["Model",p.model],
    ["Body class",p.bodyClass],["Trim",p.trim],["Series",p.series],["Drive type",p.driveType],
    ["Engine cylinders",p.engineCylinders],["Displacement (L)",p.displacementL],["Fuel type",p.fuelType],
    ["Transmission",p.transmission],["Plant country",p.plantCountry],
    ["Curb weight",p.curbWeightStatus === "reported" ? p.curbWeightLb + " lb / " + p.curbWeightKg.toFixed(1) + " kg" : "Not reported (" + p.curbWeightStatus + ")"]
  ];
  const table = rows.map(([k,v]) => "<tr><th>" + escapeHtml(k) + "</th><td>" + escapeHtml(v) + "</td></tr>").join("");
  const observations = state.observations.length ? state.observations.map((x,i) =>
    "<li><strong>" + escapeHtml(x.area) + " — " + escapeHtml(x.type) + "</strong><br>Operator judgment: " +
    escapeHtml(x.severity) + "<br>" + escapeHtml(x.notes || "No additional note.") +
    (x.photo ? "<br>Linked view: " + escapeHtml(slots.find(s => s[0] === x.photo)?.[1] || x.photo) : "") + "</li>"
  ).join("") : "<li>No damage observations were entered.</li>";
  const images = [...state.photos.values()].map(x =>
    "<div><strong>" + escapeHtml(x.label) + "</strong><br><img src='" + x.url + "' alt='" + escapeHtml(x.label) + "'></div>"
  ).join("");
  const localizationRows = [...state.photos.values()].map(photo => {
    const loc = photo.localization || {};
    const analysis = loc.analysis || {};
    let detail = "No localization result returned.";
    if (analysis.status === "COMPLETED") {
      const candidates = analysis.observations || [];
      detail = candidates.length ? candidates.map((candidate, i) => {
        const box = candidate.bbox_normalized || [];
        const bounds = box.length === 4 ? " · normalized bounds " + box.map(v => Number(v).toFixed(3)).join(", ") : "";
        return "<li>Candidate " + (i+1) + ": " + escapeHtml(candidate.predicted_damage_class || "unknown") +
          " · zone " + escapeHtml(candidate.zone || "unknown") +
          " · image area " + (Number(candidate.normalized_region_area_fraction || 0)*100).toFixed(2) + "%" +
          " · raw score " + Number(candidate.raw_detector_score || 0).toFixed(3) + " (uncalibrated)" + escapeHtml(bounds) + "</li>";
      }).join("") : "<li>No contrast candidates returned. This is not evidence that the view is damage-free.</li>";
      detail = "<ul>" + detail + "</ul><p>Method: " + escapeHtml(analysis.method || "baseline") + " · Version: " + escapeHtml(analysis.model_version || "unknown") + "</p>";
    } else if (loc.status === "NOT_APPLICABLE") detail = "Not an exterior view; localization not applicable.";
    else if (loc.status === "UNAVAILABLE") detail = "Unavailable: " + escapeHtml(loc.code || "unknown error") + ". Original upload remains registered.";
    return "<li><strong>" + escapeHtml(photo.label) + "</strong> · " + escapeHtml(localizationStatus(loc)) +
      (photo.sha256 ? "<br>Original SHA-256: " + escapeHtml(photo.sha256) : "") + "<br>" + detail + "</li>";
  }).join("");
  const localizationHtml = "<h3>2.1 Image-space contrast baseline (not AI)</h3><p>These are heuristic image-space candidates, not confirmed damage. Detector scores are uncalibrated; normalized boxes and area are image-relative, not physical measurements. A zero-candidate result does not establish absence of damage.</p><ul>" + (localizationRows || "<li>No localization responses recorded.</li>") + "</ul>";
  const estimate = estimateTotals();
  const estimateRows = state.observations.map((x,i) => {
    const e=x.estimate||{}, subtotal=estimateLineSubtotal(e,estimate.rate);
    return "<tr><td>" + (i+1) + ". " + escapeHtml(x.area) + " · " + escapeHtml(x.type) + "</td><td>" + escapeHtml(e.action||"Not assessed") + "</td><td>" + Number(e.laborHours||0).toFixed(1) + "</td><td>$" + Number(e.partsCost||0).toFixed(2) + "</td><td>$" + Number(e.materialsCost||0).toFixed(2) + "</td><td>$" + subtotal.toFixed(2) + "</td></tr>";
  }).join("");
  const estimateHtml = "<h3>4. Preliminary repair-cost worksheet (operator-entered)</h3><p>Labor rate: $" + estimate.rate.toFixed(2) + "/hour · Tax rate: " + estimate.taxRate.toFixed(2) + "% · These values are user-entered assumptions, not an AI appraisal or verified shop quote.</p><table><thead><tr><th>Observed item</th><th>Action</th><th>Hours</th><th>Parts</th><th>Materials / sublet</th><th>Subtotal</th></tr></thead><tbody>" + (estimateRows || "<tr><td colspan='6'>No worksheet line items.</td></tr>") + "</tbody><tfoot><tr><th colspan='5'>Labor</th><td>$" + estimate.labor.toFixed(2) + "</td></tr><tr><th colspan='5'>Parts</th><td>$" + estimate.parts.toFixed(2) + "</td></tr><tr><th colspan='5'>Materials / sublet</th><td>$" + estimate.materials.toFixed(2) + "</td></tr><tr><th colspan='5'>Subtotal</th><td>$" + estimate.subtotal.toFixed(2) + "</td></tr><tr><th colspan='5'>Tax (operator-selected)</th><td>$" + estimate.tax.toFixed(2) + "</td></tr><tr><th colspan='5'>Worksheet total</th><td><strong>$" + estimate.total.toFixed(2) + "</strong></td></tr></tfoot></table><p>Excluded unless explicitly entered: hidden damage, diagnostics, ADAS calibration, towing, storage, supplements, fees, and insurer-specific pricing. This worksheet does not establish repairability, safety, total-loss status, or authorization.</p>";
  return "<h2>Claim2Car Vehicle &amp; Condition Report</h2><p>Prototype report · Generated " + escapeHtml(now()) + " · VIN decoded " + escapeHtml(state.retrievedAt ? new Date(state.retrievedAt).toLocaleString() : "time unavailable") +
    "</p><p class='report-warning'><strong>Scope limitation:</strong> This is a documentation prototype, not an appraisal, insurance decision, ownership verification, roadworthiness inspection, or professional repair estimate. Damage observations were entered by the operator. A deterministic contrast baseline may identify image-space candidates; no trained AI damage assessment or automated repair-cost model ran.</p>" +
    "<h3>1. Vehicle identity</h3><p>Source: NHTSA vPIC. VIN check digit status: " + escapeHtml(p.checkDigitStatus) + ". A mismatch override is not proof of VIN authenticity or vehicle identity.</p><table>" + table + "</table>" +
    "<h3>2. Capture completeness</h3><p>" + [...state.photos.values()].filter(x => x.uploaded).length + " of 16 original views uploaded to the authenticated evidence service. Session: " + escapeHtml(state.sessionId || "not connected") + ".</p>" + (state.sealed ? "<p><strong>Sealed manifest SHA-256:</strong> " + escapeHtml(state.manifestDigest) + "</p>" : "<p><strong>Evidence status:</strong> Not sealed.</p>") + "<p>Views not captured: " +
    (missing.length ? missing.map(escapeHtml).join(", ") : "None") + ". Missing views are unknown, not evidence of no damage.</p><div class='report-images'>" + images + "</div>" +
    "<h3>3. Visible condition observations</h3><ul>" + observations + "</ul>" +
    estimateHtml + "<h3>5. Unresolved questions</h3><ul><li>Concealed structure and components have not been assessed.</li><li>No collision causation, fault, liability, coverage, total-loss status, repair scope, or repair price is determined.</li><li>Severity labels are qualitative operator judgments, not calibrated probabilities or verified engineering classifications.</li><li>Qualified physical inspection and diagnostic procedures may be required.</li></ul>" +
    "<h3>6. Disposition</h3><p><strong>LIMITED DOCUMENTATION ONLY — NOT ADJUDICATED.</strong> This report is not clearance to drive or repair authorization.</p>" +
    "<p>Method: server-recorded NHTSA vPIC vehicle description; user-provided photographs and observations. " + (state.sealed ? "Original evidence bytes are stored and the 16-view manifest is sealed." : "Evidence remains unsealed; no final evidence package is asserted.") + " No trained AI damage model or automated appraisal was used; exterior photos may have received a heuristic contrast baseline.</p>";
}
$("generate-report").addEventListener("click",() => {
  if (!state.profile) {
    setMessage("Decode a vehicle before generating a report.",true);
    return;
  }
  $("report-preview").innerHTML = reportHtml();
  show("report-preview");
  show("print-report");
});
$("print-report").addEventListener("click",() => window.print());
renderPhotoSlots();

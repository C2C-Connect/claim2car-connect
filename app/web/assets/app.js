import { createIndexedDbEvidenceStore, createOfflineEvidenceQueue } from "./offline_evidence_queue.mjs";
// Keep this list byte-for-byte aligned with app/evidence_manifest.py and
// contracts/shot-list.json (claims2car-12-v1).
const SLOTS = [
  ["vin_ocr","VIN plate"],["doc_ocr","Registration / document"],["front","Front"],
  ["front_left","Front left"],["driver_side","Driver side"],["rear_left","Rear left"],
  ["rear","Rear"],["rear_right","Rear right"],["passenger_side","Passenger side"],
  ["front_right","Front right"],["interior_front","Front interior"],
  ["undercarriage_engine","Undercarriage / engine"]
];
let token = null;
let identity = null;
let activeSession = null;
let pendingClaimCase = null;
let claimCaseRequestInFlight = false;
let evidenceQueue = null;
let evidenceQueueError = null;
try { evidenceQueue = createOfflineEvidenceQueue({store:createIndexedDbEvidenceStore()}); }
catch (error) { evidenceQueueError = error; }
const $ = (id) => document.getElementById(id);
const uuid = () => crypto.randomUUID();
const authHeaders = () => ({Authorization: `Bearer ${token}`});
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {...authHeaders(), ...(options.headers || {})},
    cache: "no-store"
  });
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(body?.detail || `REQUEST_FAILED_${response.status}`);
  return body;
}
function message(id, text, bad = false) {
  $(id).textContent = text;
  $(id).className = bad ? "message error" : "message";
}
function setCase(id) {
  activeSession = id;
  $("session-id").value = id;
  $("owner-session-id").value = id;
  void restoreEvidenceQueue(id);
}
async function connect() {
  token = $("access-token").value.trim();
  $("sign-in-error").textContent = "";
  if (!token) { $("sign-in-error").textContent = "An access token is required."; return; }
  try {
    identity = await api("/api/v1/identity");
    $("sign-in").hidden = true;
    $("workspace").hidden = false;
    $("connection-state").textContent = "Connected · " + identity.actor_role;
    $("actor-label").textContent = identity.actor_role[0].toUpperCase() + identity.actor_role.slice(1) + " workspace";
    $("actor-meta").textContent = `Actor ${identity.actor_id} · Tenant ${identity.tenant_id}`;
    const roles = {operator:"operator-view", owner:"owner-view", reviewer:"reviewer-view", supervisor:"reviewer-view"};
    const target = roles[identity.actor_role];
    for (const id of ["operator-view","owner-view","reviewer-view"]) $(id).hidden = id !== target;
    $("role-nav").textContent = identity.actor_role === "supervisor" ? "Supervisor · Reviewer queue" : identity.actor_role;
    if (target === "reviewer-view") await refreshQueue();
    if (target === "operator-view") { await refreshClaimCases(); await refreshOwnedSessions(); }
  } catch (error) {
    token = null; identity = null;
    $("sign-in-error").textContent = error.message === "UNAUTHORIZED" ? "Access token was rejected." : error.message;
  }
}
function disconnect() {
  token = null; identity = null; activeSession = null;
  $("access-token").value = "";
  $("workspace").hidden = true; $("sign-in").hidden = false;
  $("connection-state").textContent = "Not connected";
}
async function createClaimCase() {
  if (claimCaseRequestInFlight) return;
  claimCaseRequestInFlight = true;
  const button = $("create-claim-case");
  button.disabled = true;
  if (!pendingClaimCase) pendingClaimCase = {claimId:uuid(),requestId:uuid()};
  try {
    const result = await api("/api/v1/claim-cases", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({claim_id:pendingClaimCase.claimId,request_id:pendingClaimCase.requestId})
    });
    $("claim-case-created").textContent = result.created
      ? "Persistent claim record created: " + result.claim_id
      : "Existing claim record confirmed: " + result.claim_id;
    if (result.capture_session_id) {
      setCase(result.capture_session_id);
      message("operator-message","Persistent claim capture session is ready. Owner consent is required before VIN or evidence entry.");
    }
    pendingClaimCase = null;
    await refreshClaimCases();
  } catch(error) {
    $("claim-case-created").textContent = error.message + " · Retry will reuse the same request ID.";
  } finally {
    claimCaseRequestInFlight = false;
    button.disabled = false;
  }
}
async function refreshClaimCases() {
  const root = $("claim-cases");
  root.replaceChildren();
  try {
    const items = await api("/api/v1/claim-cases?limit=50");
    if (!items.length) { root.textContent = "No persistent claim records have been created by this operator."; return; }
    for (const item of items) {
      const row = document.createElement("article"); row.className = "owned-session";
      const details = document.createElement("div");
      const heading = document.createElement("strong"); heading.textContent = item.claim_id;
      const date = document.createElement("p"); date.className = "fine";
      date.textContent = item.state + " · Created " + new Date(item.created_at).toLocaleString();
      details.append(heading,date);
      const open = document.createElement("button"); open.className = "secondary"; open.textContent = "Open capture";
      open.addEventListener("click", async () => {
        open.disabled = true;
        try {
          const record = await api("/api/v1/claim-cases/" + encodeURIComponent(item.claim_id));
          if (!record.capture_session_id) throw new Error("CAPTURE_SESSION_NOT_LINKED");
          await api("/api/v1/capture-sessions/" + encodeURIComponent(record.capture_session_id));
          setCase(record.capture_session_id);
          message("operator-message","Persistent claim capture session reopened.");
          $("claim-case-created").textContent = "Persistent claim record reopened: " + record.claim_id;
        } catch(error) { $("claim-case-created").textContent = error.message; }
        finally { open.disabled = false; }
      });
      row.append(details,open); root.append(row);
    }
  } catch(error) { root.textContent = error.message; }
}
async function createCase() {
  try {
    const id = uuid();
    const result = await api("/api/v1/capture-sessions", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:id})});
    setCase(id);
    $("case-created").textContent = result.created ? "Case created." : "Existing case resumed.";
    message("operator-message", "Case ready. Owner consent must be recorded with the provisioned owner actor credential; this workspace does not provide end-user login.");
    await refreshOwnedSessions();
  } catch (error) { message("operator-message", error.message, true); }
}
async function refreshOwnedSessions() {
  const root=$("owned-sessions");
  root.replaceChildren();
  try {
    const items=await api("/api/v1/capture-sessions?limit=50");
    if (!items.length) { root.textContent="No capture drafts have been created by this operator."; return; }
    for (const item of items) {
      const row=document.createElement("article"); row.className="owned-session";
      const details=document.createElement("div");
      const heading=document.createElement("strong"); heading.textContent=item.session_id;
      const date=document.createElement("p"); date.className="fine";
      date.textContent="Created "+new Date(item.created_at).toLocaleString();
      details.append(heading,date);
      const open=document.createElement("button"); open.className="secondary"; open.textContent="Open";
      open.addEventListener("click",async()=>{
        try {
          await api("/api/v1/capture-sessions/"+encodeURIComponent(item.session_id));
          setCase(item.session_id);
          message("operator-message","Capture draft reopened from the server.");
        } catch(error) { message("operator-message",error.message,true); }
      });
      row.append(details,open); root.append(row);
    }
  } catch(error) { root.textContent=error.message; }
}
async function resumeCase() {
  const id = $("session-id").value.trim();
  if (!id) return message("operator-message","Enter a case UUID.",true);
  try {
    await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}`);
    setCase(id); message("operator-message","Case access verified.");
    await refreshOwnedSessions();
  } catch (error) { message("operator-message",error.message,true); }
}

async function refreshIncidentDetails() {
  const id = $("session-id").value.trim();
  const root = $("incident-details");
  root.replaceChildren();
  if (!id) return message("operator-message","Open a persistent claim-case session first.",true);
  try {
    const item = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/incident-intake`);
    const values = [
      ["Incident time", new Date(item.incident_occurred_at).toLocaleString()],
      ["Category", item.incident_type],
      ["City", item.incident_city],
      ["State", item.incident_region],
      ["ZIP code", item.incident_postal_code]
    ];
    for (const [label,value] of values) {
      const row = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = label + ": ";
      const text = document.createElement("span");
      text.textContent = value;
      row.append(strong,text);
      root.append(row);
    }
    message("operator-message","Owner-consented incident details loaded.");
  } catch(error) {
    root.textContent = error.message;
    message("operator-message",error.message,true);
  }
}

async function recordConsent() {
  const id = $("owner-session-id").value.trim();
  if (!id || !$("consent-accepted").checked) return message("owner-message","Enter the case ID and explicitly accept the disclosure.",true);
  try {
    const result = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/consent`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:uuid(),accepted:true,scope:"capture_review"})
    });
    message("owner-message",result.replayed ? "Consent record confirmed." : "Consent recorded for this case.");
  } catch (error) { message("owner-message",error.message,true); }
}
async function withdrawCaptureConsent() {
  const id = $("owner-session-id").value.trim();
  if (!id) return message("owner-message","Enter the case ID before withdrawing consent.",true);
  let result;
  try {
    result = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/consent`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:uuid(),accepted:false,scope:"capture_review"})
    });
  } catch (error) {
    return message("owner-message",`Server withdrawal was not confirmed; local evidence was not purged. ${error.message}`,true);
  }
  try {
    const localDeleted = evidenceQueue ? await evidenceQueue.deleteSession(id,{tenantId:identity.tenant_id}) : 0;
    if (activeSession === id) await refreshCaptureQueueStatus(id);
    message("owner-message",`Capture consent withdrawn. Server deleted ${result.deleted_original_artifacts ?? 0} original(s); local browser queue removed ${localDeleted} item(s).`);
  } catch (error) {
    message("owner-message",`Capture consent was withdrawn and the server deleted ${result.deleted_original_artifacts ?? 0} original(s), but local browser deletion failed: ${error.message}. Do not reuse this device until its pending evidence storage is cleared.`,true);
  }
}
async function recordIncidentConsent(accepted = true) {
  const id = $("owner-session-id").value.trim();
  if (!id || (accepted && !$("incident-consent-accepted").checked)) return message("incident-message","Enter the case ID and explicitly accept the supplemental notice.",true);
  try {
    const result = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/incident-consent`,{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({request_id:uuid(),accepted})
    });
    message("incident-message",accepted ? "Supplemental incident consent recorded." : (result.incident_details_deleted ? "Consent withdrawn; structured incident details deleted." : "Supplemental consent withdrawn."));
  } catch(error) { message("incident-message",error.message,true); }
}
async function submitIncidentIntake() {
  const id = $("owner-session-id").value.trim();
  const local = $("incident-occurred-at").value;
  const occurred = local ? new Date(local).toISOString() : "";
  const city = $("incident-city").value.trim();
  const region = $("incident-region").value.trim().toUpperCase();
  const postal = $("incident-postal-code").value.trim();
  if (!id || !occurred || !city || !region || !postal) return message("incident-message","Complete the date/time, category, city, state, and ZIP fields.",true);
  try {
    const result = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/incident-intake`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:uuid(),occurred_at:occurred,incident_type:$("incident-type").value,city,region,postal_code:postal})
    });
    message("incident-message",result.replayed ? "Existing incident details confirmed." : "Structured incident details saved.");
  } catch(error) { message("incident-message",error.message,true); }
}
async function recordVin() {
  const id = $("session-id").value.trim(), vin = $("vin").value.trim().toUpperCase();
  if (!id || vin.length !== 17) return message("operator-message","Enter a case ID and a 17-character VIN.",true);
  try {
    await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/vehicle-reference`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:uuid(),vin})
    });
    setCase(id); message("operator-message","Vehicle reference validated and stored as a keyed reference.");
  } catch (error) { message("operator-message",error.message,true); }
}
function base64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i=0;i<bytes.length;i+=chunk) binary += String.fromCharCode(...bytes.subarray(i,i+chunk));
  return btoa(binary);
}
async function refreshCaptureQueueStatus(sessionId) {
  const statuses = [...$("capture-slots").querySelectorAll(".slot-status")];
  if (!evidenceQueue) {
    for (const status of statuses) {
      status.dataset.uploaded = "false";
      if (evidenceQueueError) status.textContent = "Local evidence queue unavailable";
    }
    $("sync-pending-evidence").disabled = true;
    return;
  }
  const state = await evidenceQueue.status(sessionId,{tenantId:identity.tenant_id,actorId:identity.actor_id});
  const latestBySlot = new Map();
  for (const record of state.records) latestBySlot.set(record.slot, record);
  for (const status of statuses) {
    const record = latestBySlot.get(status.dataset.slot);
    status.dataset.uploaded = record?.uploaded ? "true" : "false";
    status.classList.toggle("error", false);
    if (!record) status.textContent = "Not captured";
    else if (record.uploaded) status.textContent = `Uploaded · ${record.byteLength.toLocaleString()} bytes · SHA-256 verified`;
    else status.textContent = `Saved on this device · waiting to sync · ${record.byteLength.toLocaleString()} bytes`;
  }
  $("sync-pending-evidence").disabled = state.pending === 0;
  $("sync-pending-evidence").textContent = state.pending
    ? `Sync pending originals (${state.pending})`
    : "All originals synced";
}
async function syncPendingUploads(sessionId) {
  if (!token || !sessionId) return null;
  if (!evidenceQueue) throw evidenceQueueError || new Error("LOCAL_EVIDENCE_QUEUE_UNAVAILABLE");
  const result = await evidenceQueue.syncSession({
    sessionId,
    tenantId:identity.tenant_id,
    actorId:identity.actor_id,
    upload: async (record) => {
      await api(`/api/v1/capture-sessions/${encodeURIComponent(sessionId)}/artifacts`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          request_id:record.requestId,
          artifact_id:record.artifactId,
          slot:record.slot,
          payload_base64:base64(record.bytes),
          sha256:record.sha256
        })
      });
      return {ok:true};
    }
  });
  await refreshCaptureQueueStatus(sessionId);
  if (result.blockedAtQueueId !== null) {
    message("operator-message", `Sync paused at queued original #${result.blockedAtQueueId}: ${result.error}. Earlier items remain recorded; later items were not sent.`, true);
  } else if (result.uploaded > 0) {
    message("operator-message", `Synced ${result.uploaded} original evidence item(s) in FIFO order. Server-side SHA-256 verification completed.`);
  }
  return result;
}
async function retryPendingEvidence() {
  if (!activeSession) return;
  try {
    await syncPendingUploads(activeSession);
  } catch (error) {
    message("operator-message",`Evidence sync could not start: ${error.message}`,true);
  }
}
async function restoreEvidenceQueue(sessionId) {
  try {
    await refreshCaptureQueueStatus(sessionId);
    if (navigator.onLine && token) await syncPendingUploads(sessionId);
  } catch (error) {
    message("operator-message", `Local evidence recovery unavailable: ${error.message}`, true);
  }
}
async function upload(slot, file, status) {
  const id = $("session-id").value.trim();
  if (!id || !file) return;
  status.dataset.uploaded = "false";
  status.classList.remove("error");
  try {
    if (!evidenceQueue) throw evidenceQueueError || new Error("LOCAL_EVIDENCE_QUEUE_UNAVAILABLE");
    const queued = await evidenceQueue.queueFile({sessionId:id,tenantId:identity.tenant_id,actorId:identity.actor_id,slot,file});
    status.textContent = `Saved on this device · queued #${queued.queueId} · waiting to sync`;
    await refreshCaptureQueueStatus(id);
    await syncPendingUploads(id);
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  }
}
function buildSlots() {
  const root = $("capture-slots");
  for (const [slot,label] of SLOTS) {
    const row = document.createElement("div"); row.className = "slot";
    const title = document.createElement("label"); title.textContent = label;
    const input = document.createElement("input"); input.type = "file"; input.accept = "image/*"; input.setAttribute("capture","environment");
    const status = document.createElement("span"); status.className = "fine slot-status"; status.dataset.slot = slot; status.dataset.uploaded = "false"; status.textContent = "Not captured";
    const qualityLabel = document.createElement("label"); qualityLabel.className = "quality-check";
    const quality = document.createElement("input"); quality.type = "checkbox";
    const qualityText = document.createElement("span"); qualityText.textContent = "I checked this original: correct view, readable, and usable.";
    qualityLabel.append(quality,qualityText);
    input.addEventListener("change",()=>{ quality.checked=false; upload(slot,input.files?.[0],status); });
    row.append(title,input,status,qualityLabel); root.append(row);
  }
}
async function recordQuality() {
  const id = $("session-id").value.trim();
  const uploaded = [...$("capture-slots").querySelectorAll(".slot")];
  if (uploaded.length !== SLOTS.length || uploaded.some(row => row.querySelector("span").dataset.uploaded !== "true")) {
    return message("operator-message","Upload an original image for every required capture slot before recording quality.",true);
  }
  if (uploaded.some(row => !row.querySelector(".quality-check input").checked)) {
    return message("operator-message","Review every original. If any image is unclear or incorrect, upload a replacement before recording quality.",true);
  }
  const results = Object.fromEntries(SLOTS.map(([slot], index) => [slot, uploaded[index].querySelector(".quality-check input").checked]));
  try {
    await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/quality`,{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({request_id:uuid(),results})
    });
    message("operator-message","Advisory quality results recorded. These checks do not certify image quality or vehicle condition.");
  } catch (error) { message("operator-message",error.message,true); }
}
async function sealCase() {
  const id = $("session-id").value.trim();
  try {
    const result = await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/seal`,{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({request_id:uuid()})
    });
    message("operator-message",`Manifest sealed · ${result.manifest_digest}`);
  } catch (error) { message("operator-message",error.message,true); }
}
async function refreshQueue() {
  try {
    const items = await api("/api/v1/review-queue");
    const root = $("review-queue"); root.replaceChildren();
    if (!items.length) { root.textContent = "No sealed cases are awaiting review."; return; }
    for (const item of items) {
      const card = document.createElement("article"); card.className = "queue-item";
      const h = document.createElement("strong"); h.textContent = item.session_id;
      const p = document.createElement("p"); p.textContent = `${item.artifact_count} artifacts · ${item.shot_list_version} · ${item.manifest_digest}`;
      const open = document.createElement("button"); open.className = "secondary"; open.textContent = "Open verified evidence";
      const detail = document.createElement("div"); detail.className = "review-detail";
      open.addEventListener("click", async () => {
        open.disabled = true; detail.textContent = "Verifying sealed manifest and loading originals…";
        try {
          const record = await api(`/api/v1/review-sessions/${encodeURIComponent(item.session_id)}`);
          detail.replaceChildren();
          const digest = document.createElement("p"); digest.className = "fine"; digest.textContent = `Verified manifest ${record.manifest_digest}`;
          detail.append(digest);
          for (const artifact of record.artifacts) {
            const row = document.createElement("div"); row.className = "review-artifact";
            const heading = document.createElement("strong"); heading.textContent = artifact.slot;
            const meta = document.createElement("p"); meta.className = "fine"; meta.textContent = `${artifact.byte_length.toLocaleString()} bytes · SHA-256 ${artifact.sha256}`;
            row.append(heading,meta);
            try {
              const response = await fetch(`/api/v1/review-sessions/${encodeURIComponent(item.session_id)}/artifacts/${encodeURIComponent(artifact.artifact_id)}`,{headers:authHeaders(),cache:"no-store"});
              if (!response.ok) throw new Error(`ARTIFACT_RETRIEVAL_FAILED_${response.status}`);
              const bytes = await response.arrayBuffer();
              const data = new Uint8Array(bytes);
              let mime = "application/octet-stream";
              if (data[0]===0xff && data[1]===0xd8 && data[2]===0xff) mime="image/jpeg";
              else if (data[0]===0x89 && data[1]===0x50 && data[2]===0x4e && data[3]===0x47) mime="image/png";
              else if (data[0]===0x52 && data[1]===0x49 && data[2]===0x46 && data[3]===0x46 && data[8]===0x57) mime="image/webp";
              const url = URL.createObjectURL(new Blob([bytes],{type:mime}));
              const link = document.createElement("a"); link.href=url; link.download=`claim2car-${artifact.slot}`; link.textContent="Open / download original";
              row.append(link);
              if (mime.startsWith("image/")) { const img=document.createElement("img"); img.src=url; img.alt=`Original evidence: ${artifact.slot}`; img.loading="lazy"; row.append(img); }
            } catch (error) {
              const failure=document.createElement("p"); failure.className="error fine"; failure.textContent=error.message; row.append(failure);
            }
            detail.append(row);
          }
          const decision = document.createElement("div"); decision.className = "review-decision";
          const disposition = document.createElement("select");
          for (const [value,label] of [["NOTE_ONLY","Note only"],["HUMAN_QC_REQUIRED","Human QC required"]]) { const option=document.createElement("option"); option.value=value; option.textContent=label; disposition.append(option); }
          const reason = document.createElement("textarea"); reason.placeholder="Required review rationale"; reason.maxLength=1000;
          const submit = document.createElement("button"); submit.className="primary"; submit.textContent="Record review decision";
          const outcome = document.createElement("p"); outcome.className="fine";
          submit.addEventListener("click",async()=>{
            if (!reason.value.trim()) { outcome.textContent="A review rationale is required."; return; }
            submit.disabled=true;
            try {
              const result=await api(`/api/v1/capture-sessions/${encodeURIComponent(item.session_id)}/review`,{
                method:"POST",headers:{"Content-Type":"application/json"},
                body:JSON.stringify({request_id:uuid(),disposition:disposition.value,reason:reason.value.trim()})
              });
              outcome.textContent=`Review recorded: ${result.disposition} · ${result.manifest_digest}`;
              await refreshQueue();
            } catch(error) { outcome.textContent=error.message; submit.disabled=false; }
          });
          decision.append(disposition,reason,submit,outcome); detail.append(decision);
        } catch(error) { detail.textContent=error.message; open.disabled=false; }
      });
      card.append(h,p,open,detail); root.append(card);
    }
  } catch (error) { $("review-queue").textContent = error.message; }
}
$("connect").addEventListener("click",connect);
$("disconnect").addEventListener("click",disconnect);
$("new-case").addEventListener("click",createCase);
$("create-claim-case").addEventListener("click",createClaimCase);
$("resume-case").addEventListener("click",resumeCase);
$("refresh-sessions").addEventListener("click",refreshOwnedSessions);
$("record-consent").addEventListener("click",recordConsent);
$("withdraw-capture-consent").addEventListener("click",withdrawCaptureConsent);
$("load-incident-details").addEventListener("click",refreshIncidentDetails);
$("record-incident-consent").addEventListener("click",()=>recordIncidentConsent(true));
$("withdraw-incident-consent").addEventListener("click",()=>recordIncidentConsent(false));
$("submit-incident-intake").addEventListener("click",submitIncidentIntake);
$("save-vin").addEventListener("click",recordVin);
$("record-quality").addEventListener("click",recordQuality);
$("seal-case").addEventListener("click",sealCase);
$("sync-pending-evidence").addEventListener("click",()=>{ void retryPendingEvidence(); });
window.addEventListener("online",()=>{ if(activeSession && token) void retryPendingEvidence(); });
$("refresh-queue").addEventListener("click",refreshQueue);
$("access-token").addEventListener("keydown",e=>{if(e.key==="Enter")connect();});
buildSlots();

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
  const claimId = uuid();
  try {
    const result = await api("/api/v1/claim-cases", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({claim_id:claimId,request_id:uuid()})
    });
    $("claim-case-created").textContent = result.created ? "Persistent claim record created." : "Existing claim record confirmed.";
    await refreshClaimCases();
  } catch(error) { $("claim-case-created").textContent = error.message; }
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
      const open = document.createElement("button"); open.className = "secondary"; open.textContent = "Reopen";
      open.addEventListener("click", async () => {
        open.disabled = true;
        try {
          await api("/api/v1/claim-cases/" + encodeURIComponent(item.claim_id));
          $("claim-case-created").textContent = "Persistent claim record reopened.";
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
    message("operator-message", "Case ready. Ask the owner to record consent using their own account.");
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
async function upload(slot, file, status) {
  const id = $("session-id").value.trim();
  if (!id || !file) return;
  status.dataset.uploaded = "false";
  status.classList.remove("error");
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))].map(v=>v.toString(16).padStart(2,"0")).join("");
    await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}/artifacts`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({request_id:uuid(),artifact_id:uuid(),slot,payload_base64:base64(bytes),sha256:digest})
    });
    status.textContent = `Uploaded · ${file.name} · ${bytes.length.toLocaleString()} bytes · SHA-256 verified`;
    status.dataset.uploaded = "true";
  } catch (error) { status.textContent = error.message; status.classList.add("error"); }
}
function buildSlots() {
  const root = $("capture-slots");
  for (const [slot,label] of SLOTS) {
    const row = document.createElement("div"); row.className = "slot";
    const title = document.createElement("label"); title.textContent = label;
    const input = document.createElement("input"); input.type = "file"; input.accept = "image/*"; input.setAttribute("capture","environment");
    const status = document.createElement("span"); status.className = "fine"; status.textContent = "Not uploaded";
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
$("save-vin").addEventListener("click",recordVin);
$("record-quality").addEventListener("click",recordQuality);
$("seal-case").addEventListener("click",sealCase);
$("refresh-queue").addEventListener("click",refreshQueue);
$("access-token").addEventListener("keydown",e=>{if(e.key==="Enter")connect();});
buildSlots();

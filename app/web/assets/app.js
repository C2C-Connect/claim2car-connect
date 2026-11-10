const SLOTS = [
  ["front_center","Front center"],["front_left","Front left"],["left_side","Left side"],
  ["rear_left","Rear left"],["rear_center","Rear center"],["rear_right","Rear right"],
  ["right_side","Right side"],["front_right","Front right"],["vin_plate","VIN plate"],
  ["odometer_cluster","Odometer cluster"],["primary_impact_closeup","Primary impact close-up"],
  ["undercarriage_or_wheel_well","Undercarriage / wheel well"]
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
async function createCase() {
  try {
    const id = uuid();
    const result = await api("/api/v1/capture-sessions", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:id})});
    setCase(id);
    $("case-created").textContent = result.created ? "Case created." : "Existing case resumed.";
    message("operator-message", "Case ready. Ask the owner to record consent using their own account.");
  } catch (error) { message("operator-message", error.message, true); }
}
async function resumeCase() {
  const id = $("session-id").value.trim();
  if (!id) return message("operator-message","Enter a case UUID.",true);
  try {
    await api(`/api/v1/capture-sessions/${encodeURIComponent(id)}`);
    setCase(id); message("operator-message","Case access verified.");
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
    input.addEventListener("change",()=>upload(slot,input.files?.[0],status));
    row.append(title,input,status); root.append(row);
  }
}
async function recordQuality() {
  const id = $("session-id").value.trim();
  const uploaded = [...$("capture-slots").querySelectorAll(".slot")];
  const results = Object.fromEntries(SLOTS.map(([slot])=>[slot,uploaded.some(row=>row.querySelector("span").dataset.uploaded==="true" && row.querySelector("input").files?.length && row.querySelector("input").files[0] && row.querySelector("label").textContent===SLOTS.find(s=>s[0]===slot)[1])]));
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
      card.append(h,p); root.append(card);
    }
  } catch (error) { $("review-queue").textContent = error.message; }
}
$("connect").addEventListener("click",connect);
$("disconnect").addEventListener("click",disconnect);
$("new-case").addEventListener("click",createCase);
$("resume-case").addEventListener("click",resumeCase);
$("record-consent").addEventListener("click",recordConsent);
$("save-vin").addEventListener("click",recordVin);
$("record-quality").addEventListener("click",recordQuality);
$("seal-case").addEventListener("click",sealCase);
$("refresh-queue").addEventListener("click",refreshQueue);
$("access-token").addEventListener("keydown",e=>{if(e.key==="Enter")connect();});
buildSlots();

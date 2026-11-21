import { validateVin } from "../src/modules/capture/vin.mjs";
const API = "/api";
const MAX_BYTES = 25 * 1024 * 1024;
const API_CAPTURE_SLOTS = [
  ["00_front_exterior", "Front exterior"],
  ["01_front_right_exterior", "Front-right 45° exterior"],
  ["02_right_side_exterior", "Right-side profile"],
  ["03_rear_right_exterior", "Rear-right 45° exterior"],
  ["04_rear_exterior", "Rear exterior"],
  ["05_rear_left_exterior", "Rear-left 45° exterior"],
  ["06_left_side_exterior", "Left-side profile"],
  ["07_front_left_exterior", "Front-left 45° exterior"],
  ["08_wheel_front_left", "Front-left wheel assembly"],
  ["09_wheel_front_right", "Front-right wheel assembly"],
  ["10_wheel_rear_right", "Rear-right wheel assembly"],
  ["11_wheel_rear_left", "Rear-left wheel assembly"],
  ["12_cabin_front_airbags", "Front cabin / visible airbag indicators"],
  ["13_instrument_cluster_odometer", "Instrument cluster / odometer"],
  ["14_physical_vin", "Physical VIN plate"],
  ["15_license_and_insurance_docs", "License / insurance documentation"]
];
const state = { token:null, role:null, claimId:null, sessionId:null, consentRecorded:false, vehicleRecorded:false, sealed:false, qualityRecorded:false, capturePaused:false, qualityResults:{}, activeExceptions:[], artifacts:new Map(), previews:new Map() };
const byId = (id) => document.getElementById(id);
const show = (id, visible=true) => { byId(id).hidden = !visible; };
const message = (id, value, isError=false) => {
  const node=byId(id); node.textContent=value||""; node.classList.toggle("error",Boolean(isError));
};
const uuid = () => crypto.randomUUID();

async function api(path, token, options={}) {
  const headers=new Headers(options.headers||{});
  headers.set("Authorization","Bearer "+token);
  headers.set("Cache-Control","no-store");
  if(options.body!==undefined) headers.set("Content-Type","application/json");
  const response=await fetch(API+path,{...options,headers,cache:"no-store"});
  if(!response.ok){
    let detail="REQUEST_FAILED_"+response.status;
    try{const body=await response.json();detail=typeof body.detail==="string"?body.detail:detail;}catch{}
    throw new Error(detail);
  }
  if(response.status===204)return null;
  return response.json();
}
function setConnected(role){
  state.role=role;show("connect-panel",false);show("workspace",true);
  show("operator-view",role==="operator");show("reviewer-view",role==="reviewer");
  byId("workspace-role").textContent=role==="operator"?"Operator workspace":"Reviewer workspace";
  byId("connection-indicator").textContent="Connected · "+role;
  byId("connection-indicator").classList.add("connected");
  if(role==="reviewer")refreshQueue();
  if(role==="operator")refreshCaseList();
}
function disconnect(){
  state.token=null;state.role=null;state.claimId=null;state.sessionId=null;state.consentRecorded=false;state.qualityRecorded=false;state.capturePaused=false;state.qualityResults={};state.activeExceptions=[];
  state.vehicleRecorded=false;state.sealed=false;state.artifacts.clear();
  state.previews.forEach((url)=>URL.revokeObjectURL(url));state.previews.clear();
  byId("access-token").value="";byId("owner-token").value="";byId("vin-input").value="";
  show("workspace",false);show("connect-panel",true);
  byId("connection-indicator").textContent="Not connected";
  byId("connection-indicator").classList.remove("connected");
  ["consent-panel","vin-panel","capture-panel"].forEach((id)=>show(id,false));
  byId("case-id").textContent="";show("case-id",false);
}
byId("connect-form").addEventListener("submit",(event)=>{
  event.preventDefault();const token=byId("access-token").value.trim();
  if(!/^[A-Za-z0-9_-]{43,128}$/.test(token)){message("connect-message","The token format is invalid. Check the credential issued for this role.",true);return;}
  state.token=token;message("connect-message","");setConnected(byId("role").value);
});
byId("disconnect-button").addEventListener("click",disconnect);
byId("refresh-cases").addEventListener("click",refreshCaseList);
byId("record-exception").addEventListener("click",async()=>{
  const slot=byId("exception-slot").value,reason=byId("exception-reason").value,explanation=byId("exception-explanation").value.trim();
  if(!slot||!explanation){message("exception-status","Choose a missing capture slot and explain the condition.",true);return;}
  const button=byId("record-exception");button.disabled=true;
  try{
    await api("/v1/capture-sessions/"+state.sessionId+"/exceptions",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),slot,reason_code:reason,explanation})});
    byId("exception-explanation").value="";
    const readiness=await api("/v1/capture-sessions/"+state.sessionId+"/evidence-readiness",state.token);
    state.activeExceptions=readiness.active_capture_exceptions||[];
    renderExceptionPanel();
    message("exception-status","Safety exception recorded in the server audit history. The case remains unsealed until all required evidence slots are satisfied.");
  }catch(error){message("exception-status",error.message,true);}
  finally{button.disabled=state.capturePaused||state.qualityRecorded||state.sealed;}
});

byId("create-case").addEventListener("click",async()=>{
  byId("create-case").disabled=true;
  try{
    const claimId=uuid();
    const created=await api("/v1/claim-cases",state.token,{method:"POST",body:JSON.stringify({
      claim_id:claimId,request_id:uuid(),capture_protocol_version:"claims2car-16-v1"
    })});
    if(!created||created.claim_id!==claimId||typeof created.capture_session_id!=="string"||!created.capture_session_id){
      throw new Error("PERSISTENT_CLAIM_CASE_RESPONSE_INVALID");
    }
    state.claimId=created.claim_id;state.sessionId=created.capture_session_id;state.sealed=false;state.qualityRecorded=false;state.capturePaused=false;state.qualityResults={};state.activeExceptions=[];state.artifacts.clear();state.previews.forEach((url)=>URL.revokeObjectURL(url));state.previews.clear();show("vin-panel",false);show("capture-panel",false);byId("owner-token").value="";byId("consent-check").checked=false;byId("vin-input").value="";
    byId("case-id").textContent="CLAIM ID  "+state.claimId+"\nCAPTURE SESSION  "+state.sessionId;show("case-id");
    refreshCaseList();
    show("consent-panel");message("consent-status","Persistent claim case created using the 16-view capture protocol. Owner consent is required before vehicle identification or evidence capture.");
  }catch(error){message("case-status",error.message,true);}
  finally{byId("create-case").disabled=false;}
});
byId("record-consent").addEventListener("click",async()=>{
  const ownerToken=byId("owner-token").value.trim();
  if(!state.sessionId||!byId("consent-check").checked||!ownerToken){message("consent-status","Owner authorization token and explicit consent confirmation are required.",true);return;}
  try{
    await api("/v1/capture-sessions/"+state.sessionId+"/consent",ownerToken,{method:"POST",body:JSON.stringify({request_id:uuid(),accepted:true,scope:"capture_review"})});
    byId("owner-token").value="";state.consentRecorded=true;
    message("consent-status","Owner consent recorded by the server. Owner token cleared from the form.");show("vin-panel");
  }catch(error){message("consent-status",error.message,true);}
});
byId("record-vin").addEventListener("click",async()=>{
  const normalized=byId("vin-input").value.trim().toUpperCase();const checked=validateVin(normalized);
  if(!checked.ok||checked.normalizationChanged||!state.consentRecorded){message("vin-status",checked.message||"Active owner consent is required.",true);return;}
  try{
    await api("/v1/capture-sessions/"+state.sessionId+"/vehicle-reference",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),vin:checked.vin})});
    byId("vin-input").value="";state.vehicleRecorded=true;
    message("vin-status","VIN accepted. The server recorded a keyed reference; the raw VIN is not retained by this page.");
    renderCaptureSlots();show("capture-panel");
  }catch(error){message("vin-status",error.message,true);}
});
function bytesToBase64(bytes){
  let binary="";const chunk=0x8000;
  for(let offset=0;offset<bytes.length;offset+=chunk)binary+=String.fromCharCode(...bytes.subarray(offset,Math.min(offset+chunk,bytes.length)));
  return btoa(binary);
}
async function sha256Hex(buffer){
  const digest=await crypto.subtle.digest("SHA-256",buffer);
  return Array.from(new Uint8Array(digest),(value)=>value.toString(16).padStart(2,"0")).join("");
}
function renderCaptureSlots(readiness=null){
  const grid=byId("slot-grid"),quality=byId("quality-grid");grid.replaceChildren();quality.replaceChildren();
  state.artifacts.clear();
  const knownArtifacts=readiness?.registered_artifacts||[];
  state.qualityResults=readiness?.quality_results||{};state.activeExceptions=readiness?.active_capture_exceptions||[];
  API_CAPTURE_SLOTS.forEach(([slot,label])=>{
    const existing=knownArtifacts.find(item=>item.slot===slot);
    if(existing)state.artifacts.set(slot,{artifactId:existing.artifact_id,sha256:existing.sha256,byteLength:existing.byte_length,label});
    const card=document.createElement("div");card.className="slot-card";
    const heading=document.createElement("h4");heading.textContent=label;
    const input=document.createElement("input");input.type="file";input.accept="image/*";input.capture="environment";input.setAttribute("aria-label","Capture "+label);
    input.disabled=state.qualityRecorded||state.sealed||state.capturePaused;
    const meta=document.createElement("div");meta.className="slot-meta";
    meta.textContent=existing?"Previously uploaded · "+existing.byte_length.toLocaleString()+" bytes · SHA-256 "+existing.sha256.slice(0,12)+"…":"Original image not uploaded";
    if(existing)meta.classList.add("done");
    const preview=document.createElement("img");preview.className="slot-preview";preview.hidden=true;
    input.addEventListener("change",async()=>{
      const file=input.files&&input.files[0];if(!file)return;
      if(!file.type.startsWith("image/")||file.size<=0||file.size>MAX_BYTES){meta.textContent="Choose a non-empty image no larger than 25 MiB.";meta.classList.add("error");input.value="";return;}
      input.disabled=true;meta.textContent="Hashing and uploading original bytes…";meta.classList.remove("done","error");
      try{
        const buffer=await file.arrayBuffer(),digest=await sha256Hex(buffer),artifactId=uuid(),encoded=bytesToBase64(new Uint8Array(buffer));
        await api("/v1/capture-sessions/"+state.sessionId+"/artifacts",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),artifact_id:artifactId,slot,payload_base64:encoded,sha256:digest})});
        state.artifacts.set(slot,{artifactId,sha256:digest,byteLength:file.size,label});
        const previous=state.previews.get(slot);if(previous)URL.revokeObjectURL(previous);
        const url=URL.createObjectURL(file);state.previews.set(slot,url);preview.src=url;preview.hidden=false;
        meta.textContent="Uploaded · "+file.size.toLocaleString()+" bytes · SHA-256 verified";meta.classList.add("done");renderExceptionPanel();updateSealButton();
      }catch(error){meta.textContent=error.message;meta.classList.add("error");}
      finally{input.disabled=state.qualityRecorded||state.sealed||state.capturePaused;}
    });
    card.append(heading,input,meta,preview);grid.append(card);
    const row=document.createElement("div");row.className="quality-item";
    const name=document.createElement("span");name.textContent=label;
    const select=document.createElement("select");select.dataset.slot=slot;
    for(const [value,text] of [["","Not checked"],["usable","Usable"],["retake","Needs retake"]]){const option=document.createElement("option");option.value=value;option.textContent=text;select.append(option);}
    if(Object.prototype.hasOwnProperty.call(state.qualityResults,slot))select.value=state.qualityResults[slot]?"usable":"retake";
    select.disabled=state.qualityRecorded||state.sealed;
    select.addEventListener("change",updateSealButton);row.append(name,select);quality.append(row);
  });
  byId("resume-capture").hidden=!state.capturePaused;
  byId("resume-capture").disabled=!state.capturePaused;
  renderExceptionPanel();
  updateSealButton();
}
function renderExceptionPanel(){
  const select=byId("exception-slot"),list=byId("exception-list");
  if(!select||!list)return;
  const activeSlots=new Set(state.activeExceptions.map(item=>item.slot));
  const available=API_CAPTURE_SLOTS.filter(([slot])=>!state.artifacts.has(slot)&&!activeSlots.has(slot));
  select.replaceChildren();
  const placeholder=document.createElement("option");placeholder.value="";placeholder.textContent="Select missing required view";select.append(placeholder);
  available.forEach(([slot,label])=>{const option=document.createElement("option");option.value=slot;option.textContent=label;select.append(option);});
  select.disabled=state.capturePaused||state.qualityRecorded||state.sealed||available.length===0;
  byId("exception-reason").disabled=select.disabled;
  byId("exception-explanation").disabled=select.disabled;
  byId("record-exception").disabled=select.disabled;
  list.replaceChildren();
  if(!state.activeExceptions.length){const empty=document.createElement("p");empty.className="muted";empty.textContent="No active capture exceptions.";list.append(empty);return;}
  state.activeExceptions.forEach(item=>{
    const row=document.createElement("article");row.className="case-list-item";
    const info=document.createElement("div");info.className="case-list-info";
    const title=document.createElement("strong");title.textContent=item.slot+" · "+item.reason_code;
    const detail=document.createElement("span");detail.textContent=item.explanation+" · recorded by "+item.recorded_by;
    info.append(title,detail);row.append(info);
    const actions=document.createElement("div");actions.className="exception-actions";
    if(state.artifacts.has(item.slot)){
      const retry=document.createElement("button");retry.type="button";retry.className="button secondary";retry.textContent="Resolve: captured after retry";
      retry.disabled=state.capturePaused||state.qualityRecorded||state.sealed;
      retry.addEventListener("click",()=>resolveException(item.slot,"CAPTURED_AFTER_RETRY","Required view captured after retry."));
      actions.append(retry);
    }
    const close=document.createElement("button");close.type="button";close.className="button quiet";close.textContent="Close exception (view still required)";
    close.disabled=state.capturePaused||state.qualityRecorded||state.sealed;
    close.addEventListener("click",()=>resolveException(item.slot,"NO_LONGER_APPLICABLE","Condition no longer applies; required capture remains outstanding."));
    actions.append(close);row.append(actions);list.append(row);
  });
}
async function resolveException(slot,resolutionCode,explanation){
  try{
    await api("/v1/capture-sessions/"+state.sessionId+"/exceptions/resolve",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),slot,resolution_code:resolutionCode,explanation})});
    const readiness=await api("/v1/capture-sessions/"+state.sessionId+"/evidence-readiness",state.token);
    state.activeExceptions=readiness.active_capture_exceptions||[];
    renderExceptionPanel();
    message("exception-status",resolutionCode==="CAPTURED_AFTER_RETRY"?"Exception resolved with a registered retry capture.":"Exception closed; the required view remains outstanding and cannot be omitted from sealing.");
  }catch(error){message("exception-status",error.message,true);}
}
function updateSealButton(){
  const allUploaded=API_CAPTURE_SLOTS.every(([slot])=>state.artifacts.has(slot));
  const allChecked=state.qualityRecorded||Array.from(byId("quality-grid").querySelectorAll("select")).every((node)=>node.value!=="");
  byId("seal-case").disabled=!allUploaded||!allChecked||state.sealed||state.capturePaused;
  byId("seal-case").textContent=state.qualityRecorded?"Retry evidence sealing":"Record checks and seal evidence";
}
byId("seal-case").addEventListener("click",async()=>{
  const button=byId("seal-case");button.disabled=true;
  try{
    if(!state.qualityRecorded){
      const results={};byId("quality-grid").querySelectorAll("select").forEach((node)=>{results[node.dataset.slot]=node.value==="usable";});
      await api("/v1/capture-sessions/"+state.sessionId+"/quality",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),results})});
      state.qualityRecorded=true;state.qualityResults=results;
      byId("quality-grid").querySelectorAll("select").forEach((node)=>node.disabled=true);
      byId("slot-grid").querySelectorAll("input[type=file]").forEach((node)=>node.disabled=true);
    }
    const sealed=await api("/v1/capture-sessions/"+state.sessionId+"/seal",state.token,{method:"POST",body:JSON.stringify({request_id:uuid()})});
    state.sealed=true;message("seal-status","Evidence sealed. Manifest SHA-256: "+sealed.manifest_digest);button.textContent="Evidence sealed";
    byId("slot-grid").querySelectorAll("input[type=file]").forEach((node)=>node.disabled=true);
    byId("quality-grid").querySelectorAll("select").forEach((node)=>node.disabled=true);
    updateSealButton();refreshCaseList();
  }catch(error){message("seal-status",error.message,true);updateSealButton();}
});
byId("resume-capture").addEventListener("click",async()=>{
  const button=byId("resume-capture");button.disabled=true;
  try{
    await api("/v1/capture-sessions/"+state.sessionId+"/resume",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),reason:"Operator resumed capture in workbench"})});
    const readiness=await api("/v1/capture-sessions/"+state.sessionId+"/evidence-readiness",state.token);
    state.capturePaused=Boolean(readiness.capture_paused);state.qualityRecorded=Boolean(readiness.quality_recorded);state.qualityResults=readiness.quality_results||{};state.activeExceptions=readiness.active_capture_exceptions||[];state.sealed=Boolean(readiness.sealed);message("seal-status","Capture resumed. Safety remains the operator's responsibility.");
    renderCaptureSlots(readiness);
  }catch(error){message("seal-status",error.message,true);button.disabled=false;}
});
async function refreshCaseList(){
  const container=byId("case-list");if(!container)return;
  container.replaceChildren();
  const status=byId("case-list-status");status.textContent="Loading persistent cases…";status.classList.remove("error");
  try{
    const cases=await api("/v1/claim-cases?limit=50",state.token);
    status.textContent=cases.length?cases.length+" recent case(s)":"No persistent cases yet.";
    cases.forEach((item)=>{
      const row=document.createElement("article");row.className="case-list-item";
      const info=document.createElement("div");info.className="case-list-info";
      const title=document.createElement("strong");title.textContent="Claim "+item.claim_id;
      const detail=document.createElement("span");detail.textContent=(item.state||"UNKNOWN")+" · "+(item.created_at||"Created date unavailable");
      info.append(title,detail);
      const button=document.createElement("button");button.type="button";button.className="button secondary";button.textContent="Resume";
      button.addEventListener("click",()=>openClaimCase(item,button));
      row.append(info,button);container.append(row);
    });
  }catch(error){status.textContent="Unable to load cases: "+error.message;status.classList.add("error");}
}
async function openClaimCase(item,button){
  if(button)button.disabled=true;
  try{
    const readiness=await api("/v1/capture-sessions/"+item.capture_session_id+"/evidence-readiness",state.token);
    state.claimId=item.claim_id;state.sessionId=item.capture_session_id;byId("owner-token").value="";byId("consent-check").checked=false;byId("vin-input").value="";
    state.consentRecorded=Boolean(readiness.consent_active);
    state.vehicleRecorded=Boolean(readiness.vehicle_reference_present);
    state.sealed=Boolean(readiness.sealed);
    state.qualityRecorded=Boolean(readiness.quality_recorded);
    state.capturePaused=Boolean(readiness.capture_paused);
    state.qualityResults=readiness.quality_results||{};state.activeExceptions=readiness.active_capture_exceptions||[];
    state.artifacts.clear();state.previews.forEach((url)=>URL.revokeObjectURL(url));state.previews.clear();
    byId("case-id").textContent="CLAIM ID  "+state.claimId+"\nCAPTURE SESSION  "+state.sessionId;show("case-id");
    show("consent-panel",!state.consentRecorded);
    show("vin-panel",state.consentRecorded&&!state.vehicleRecorded);
    show("capture-panel",state.consentRecorded&&state.vehicleRecorded);
    if(state.consentRecorded&&state.vehicleRecorded){
      renderCaptureSlots(readiness);
      message("seal-status",state.capturePaused?"Capture is paused. Resume only when the scene is safe.":state.sealed?"Evidence is already sealed; this view is read-only.":state.qualityRecorded?"Quality checks were already recorded. Use Retry evidence sealing to finish the interrupted seal operation.":"Case resumed. Existing server-registered originals and prior quality checks are restored.");
    }
    message("consent-status","Existing case selected. Owner consent status is server-authoritative.");
    message("vin-status","Existing vehicle-reference status is server-authoritative.");
  }catch(error){message("case-list-status","Unable to resume case: "+error.message,true);}
  finally{if(button)button.disabled=false;}
}
byId("refresh-queue").addEventListener("click",refreshQueue);
function sniffImageType(buffer){
  const b=new Uint8Array(buffer);
  if(b.length>=8&&b[0]===137&&b[1]===80&&b[2]===78&&b[3]===71)return "image/png";
  if(b.length>=3&&b[0]===255&&b[1]===216&&b[2]===255)return "image/jpeg";
  if(b.length>=12&&String.fromCharCode(...b.slice(0,4))==="RIFF"&&String.fromCharCode(...b.slice(8,12))==="WEBP")return "image/webp";
  if(b.length>=6&&(String.fromCharCode(...b.slice(0,6))==="GIF87a"||String.fromCharCode(...b.slice(0,6))==="GIF89a"))return "image/gif";
  return "application/octet-stream";
}
async function loadReviewImage(sessionId,artifact,image,status){
  status.textContent="Retrieving original…";
  try{
    const response=await fetch(API+"/v1/review-sessions/"+sessionId+"/artifacts/"+artifact.artifact_id,{headers:{Authorization:"Bearer "+state.token,"Cache-Control":"no-store"},cache:"no-store"});
    if(!response.ok)throw new Error("EVIDENCE_RETRIEVAL_FAILED_"+response.status);
    const buffer=await response.arrayBuffer(),mime=sniffImageType(buffer);
    if(!mime.startsWith("image/"))throw new Error("Original is not a browser-previewable image format.");
    const url=URL.createObjectURL(new Blob([buffer],{type:mime}));state.previews.set("review-"+artifact.artifact_id,url);
    image.src=url;image.hidden=false;status.textContent="Original retrieved · "+artifact.byte_length.toLocaleString()+" bytes";
  }catch(error){status.textContent=error.message;}
}
function renderReviewCase(item){
  const card=document.createElement("article");card.className="review-card";
  const title=document.createElement("h3");title.textContent="Sealed case · "+item.artifact_count+" evidence items";
  const digest=document.createElement("p");digest.className="muted";digest.textContent="Manifest SHA-256 · "+item.manifest_digest;
  const id=document.createElement("div");id.className="case-id";id.textContent=item.session_id;
  const artifacts=document.createElement("div");artifacts.className="artifact-grid";
  (item.artifacts||[]).forEach((artifact)=>{
    const tile=document.createElement("div");tile.className="artifact-tile";
    const name=document.createElement("strong");name.textContent=artifact.slot.replaceAll("_"," ");
    const image=document.createElement("img");image.alt="Original evidence "+artifact.slot;image.hidden=true;
    const status=document.createElement("div");status.className="slot-meta";
    const button=document.createElement("button");button.type="button";button.className="button secondary";button.textContent="Retrieve original";
    button.addEventListener("click",()=>loadReviewImage(item.session_id,artifact,image,status));
    tile.append(name,image,button,status);artifacts.append(tile);
  });
  const form=document.createElement("form");form.className="review-form";
  const dispositionLabel=document.createElement("label");dispositionLabel.textContent="Human disposition";
  const disposition=document.createElement("select");for(const [value,text] of [["NOTE_ONLY","Note only"],["HUMAN_QC_REQUIRED","Human QC required"]]){const option=document.createElement("option");option.value=value;option.textContent=text;disposition.append(option);}
  const reasonLabel=document.createElement("label");reasonLabel.textContent="Review rationale";
  const reason=document.createElement("textarea");reason.required=true;reason.maxLength=1000;reason.placeholder="Record the evidence-based reason for this disposition.";
  const submit=document.createElement("button");submit.type="submit";submit.className="button primary";submit.textContent="Record human review";
  const result=document.createElement("div");result.className="inline-status";
  form.addEventListener("submit",async(event)=>{
    event.preventDefault();submit.disabled=true;
    try{
      await api("/v1/capture-sessions/"+item.session_id+"/review",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),disposition:disposition.value,reason:reason.value.trim()})});
      result.textContent="Human review recorded.";form.querySelectorAll("input,select,textarea,button").forEach((node)=>{node.disabled=true;});
    }catch(error){result.textContent=error.message;result.classList.add("error");submit.disabled=false;}
  });
  form.append(dispositionLabel,disposition,reasonLabel,reason,submit,result);
  card.append(title,digest,id,artifacts,form);return card;
}
async function refreshQueue(){
  const container=byId("review-queue");container.replaceChildren();
  const loading=document.createElement("div");loading.className="empty-state";loading.textContent="Loading authorized review queue…";container.append(loading);
  try{
    const items=await api("/v1/review-queue",state.token);container.replaceChildren();
    if(!items.length){const empty=document.createElement("div");empty.className="empty-state";empty.textContent="No sealed cases are waiting for review.";container.append(empty);return;}
    items.forEach((item)=>container.append(renderReviewCase(item)));
  }catch(error){container.replaceChildren();const failed=document.createElement("div");failed.className="empty-state";failed.textContent="Review queue unavailable: "+error.message;container.append(failed);}
}
if(!globalThis.crypto||!crypto.subtle||!crypto.randomUUID){
  message("connect-message","This browser does not provide the secure cryptography features required by Claim2Car.",true);
  byId("connect-form").querySelector("button").disabled=true;
}
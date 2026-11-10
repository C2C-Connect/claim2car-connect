import { validateVin } from "../src/modules/capture/vin.mjs";
const API = "/api";
const MAX_BYTES = 25 * 1024 * 1024;
const API_CAPTURE_SLOTS = [
  ["vin_ocr", "VIN plate"], ["doc_ocr", "Vehicle documents"], ["front", "Front"],
  ["front_left", "Front-left corner"], ["driver_side", "Driver side"],
  ["rear_left", "Rear-left corner"], ["rear", "Rear"], ["rear_right", "Rear-right corner"],
  ["passenger_side", "Passenger side"], ["front_right", "Front-right corner"],
  ["interior_front", "Front interior"], ["undercarriage_engine", "Undercarriage / engine"]
];
const state = { token:null, role:null, sessionId:null, consentRecorded:false, vehicleRecorded:false, sealed:false, artifacts:new Map(), previews:new Map() };
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
}
function disconnect(){
  state.token=null;state.role=null;state.sessionId=null;state.consentRecorded=false;
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

byId("create-case").addEventListener("click",async()=>{
  byId("create-case").disabled=true;
  try{
    const sessionId=uuid();
    await api("/v1/capture-sessions",state.token,{method:"POST",body:JSON.stringify({session_id:sessionId})});
    state.sessionId=sessionId;byId("case-id").textContent="CASE ID  "+sessionId;show("case-id");
    show("consent-panel");message("consent-status","Case created. Owner consent is required before vehicle identification or evidence capture.");
  }catch(error){message("connect-message",error.message,true);}
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
function renderCaptureSlots(){
  const grid=byId("slot-grid"),quality=byId("quality-grid");grid.replaceChildren();quality.replaceChildren();
  API_CAPTURE_SLOTS.forEach(([slot,label])=>{
    const card=document.createElement("div");card.className="slot-card";
    const heading=document.createElement("h4");heading.textContent=label;
    const input=document.createElement("input");input.type="file";input.accept="image/*";input.capture="environment";input.setAttribute("aria-label","Capture "+label);
    const meta=document.createElement("div");meta.className="slot-meta";meta.textContent="Original image not uploaded";
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
        meta.textContent="Uploaded · "+file.size.toLocaleString()+" bytes · SHA-256 verified";meta.classList.add("done");updateSealButton();
      }catch(error){meta.textContent=error.message;meta.classList.add("error");}
      finally{input.disabled=false;}
    });
    card.append(heading,input,meta,preview);grid.append(card);
    const row=document.createElement("div");row.className="quality-item";
    const name=document.createElement("span");name.textContent=label;
    const select=document.createElement("select");select.dataset.slot=slot;
    select.innerHTML='<option value="">Not checked</option><option value="usable">Usable</option><option value="retake">Needs retake</option>';
    select.addEventListener("change",updateSealButton);row.append(name,select);quality.append(row);
  });
  updateSealButton();
}
function updateSealButton(){
  const allUploaded=API_CAPTURE_SLOTS.every(([slot])=>state.artifacts.has(slot));
  const allChecked=Array.from(byId("quality-grid").querySelectorAll("select")).every((node)=>node.value!=="");
  byId("seal-case").disabled=!allUploaded||!allChecked||state.sealed;
}
byId("seal-case").addEventListener("click",async()=>{
  const button=byId("seal-case");button.disabled=true;
  try{
    const results={};byId("quality-grid").querySelectorAll("select").forEach((node)=>{results[node.dataset.slot]=node.value==="usable";});
    await api("/v1/capture-sessions/"+state.sessionId+"/quality",state.token,{method:"POST",body:JSON.stringify({request_id:uuid(),results})});
    const sealed=await api("/v1/capture-sessions/"+state.sessionId+"/seal",state.token,{method:"POST",body:JSON.stringify({request_id:uuid()})});
    state.sealed=true;message("seal-status","Evidence sealed. Manifest SHA-256: "+sealed.manifest_digest);button.textContent="Evidence sealed";
  }catch(error){message("seal-status",error.message,true);updateSealButton();}
});
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
  const disposition=document.createElement("select");disposition.innerHTML='<option value="NOTE_ONLY">Note only</option><option value="HUMAN_QC_REQUIRED">Human QC required</option>';
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
import { validateVin } from "../src/modules/capture/vin.mjs";
import { parseVpicResponse } from "../src/modules/capture/vpic.mjs";

const $ = (id) => document.getElementById(id);
const state = { profile:null, vin:null, checksumStatus:null, photos:new Map(), observations:[], stream:null, detector:null, scanFrame:null, reportBuilt:false };
const slots = [
  ["front","Front exterior"],["front_left","Front-left 45°"],["left_profile","Left profile"],["rear_left","Rear-left 45°"],
  ["rear","Rear exterior"],["rear_right","Rear-right 45°"],["right_profile","Right profile"],["front_right","Front-right 45°"],
  ["underbody","Underbody / frame rails"],["wheel_wells","Wheel wells / suspension"],["engine_bay","Engine bay / firewall"],["roof_pillars","Roofline / pillars"],
  ["cabin_restraints","Cabin / airbag indicators"],["dashboard","Dashboard / warning indicators"],["odometer","Odometer"],["documents","Registration / insurance document"]
];
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const setMessage = (value, error=false) => { $("vin-message").textContent=value; $("vin-message").classList.toggle("error",error); };
const show = (id, yes=true) => { $(id).hidden=!yes; };
const now = () => new Date().toLocaleString();

function renderPhotoSlots(){
  const grid=$("photo-grid");grid.replaceChildren();
  for(const [slot,label] of slots){
    const card=document.createElement("div");card.className="lab-photo-card";
    const title=document.createElement("strong");title.textContent=label;
    const input=document.createElement("input");input.type="file";input.accept="image/*";input.capture="environment";input.setAttribute("aria-label","Photograph "+label);
    const stateText=document.createElement("div");stateText.className="photo-state";stateText.textContent="Not captured";
    const preview=document.createElement("img");preview.alt=label;preview.hidden=true;
    input.addEventListener("change",()=>{
      const file=input.files?.[0];if(!file)return;
      if(!file.type.startsWith("image/")||file.size>20*1024*1024){stateText.textContent="Image must be under 20 MiB.";return;}
      const old=state.photos.get(slot);if(old?.url)URL.revokeObjectURL(old.url);
      const url=URL.createObjectURL(file);state.photos.set(slot,{file,url,label});
      preview.src=url;preview.hidden=false;stateText.textContent="Captured in this browser · "+Math.round(file.size/1024)+" KB";
      updateReportAvailability();
    });
    card.append(title,input,stateText,preview);grid.append(card);
  }
}
function updateReportAvailability(){show("report-panel",Boolean(state.profile));}
function renderProfile(){
  const profile=state.profile.profile;
  $("vehicle-title").textContent=[profile.modelYear,profile.make,profile.model].filter(Boolean).join(" ");
  $("decode-status").textContent=state.profile.status;
  const attrs=[
    ["Model year",profile.modelYear],["Make",profile.make],["Model",profile.model],["Body class",profile.bodyClass],
    ["Trim",profile.trim],["Series",profile.series],["Drive type",profile.driveType],["Engine cylinders",profile.engineCylinders],
    ["Displacement",profile.displacementL ? profile.displacementL+" L" : null],["Fuel type",profile.fuelType],["Transmission",profile.transmission],
    ["Plant country",profile.plantCountry]
  ];
  const grid=$("vehicle-attributes");grid.replaceChildren();
  for(const [label,value] of attrs){const item=document.createElement("div");item.className="attribute";const small=document.createElement("small");small.textContent=label;const strong=document.createElement("strong");strong.textContent=value||"Not reported";item.append(small,strong);grid.append(item);}
  $("vehicle-provenance").textContent="Source: NHTSA vPIC DecodeVinValuesExtended · Retrieved "+now()+". Values are manufacturer-reported decoder output; unavailable fields are not inferred. VIN checksum status: "+state.checksumStatus+". This is not ownership, condition, roadworthiness, or safety verification.";
  const select=$("damage-photo");select.replaceChildren(new Option("No linked photo selected",""));
  for(const [slot,label] of slots)if(state.photos.has(slot))select.add(new Option(label,slot));
  renderPhotoSlots();updateReportAvailability();show("vehicle-panel");show("inspection-panel");
}
function normalizedProfile(parsed){
  const a=parsed.profile.attributes;
  const value=(key)=>a[key]?.value ?? null;
  return {
    modelYear:value("model_year"),make:value("make"),model:value("model"),bodyClass:value("body_class"),
    trim:value("trim"),series:value("series"),driveType:value("drive_type"),engineCylinders:value("engine_cylinders"),
    displacementL:value("displacement_l"),fuelType:value("fuel_type_primary"),transmission:value("transmission_style"),
    plantCountry:value("plant_country")
  };
}
async function decodeVin(){
  const raw=$("vin-entry").value.trim().toUpperCase();
  const check=validateVin(raw);
  if(!check.vin||check.reason==="INVALID_LENGTH"||check.reason==="ILLEGAL_CHARACTERS"||check.reason==="ILLEGAL_INPUT"||!check.ok&&check.reason!=="CHECKSUM_MISMATCH"){
    setMessage("Enter a valid 17-character VIN using permitted VIN characters.",true);return;
  }
  if(!$("decode-consent").checked){setMessage("Please provide explicit consent before sending the VIN to NHTSA vPIC.",true);return;}
  if(check.normalizationChanged){setMessage("The VIN contains lowercase or formatting differences. Confirm the exact 17 characters from the physical VIN plate, then enter it without spaces or punctuation.",true);return;}
  if(check.reason==="CHECKSUM_MISMATCH"&&!$("checksum-override").checked){show("checksum-override-row");setMessage("The North American check digit does not match. Recheck the physical VIN. For vehicles from other markets this check digit rule may not apply; explicitly acknowledge before attempting the lookup.",true);return;}
  state.vin=check.vin;state.checksumStatus=check.ok?"MATCH":"MISMATCH — MANUAL VERIFICATION REQUIRED";
  $("decode-vin").disabled=true;setMessage("Requesting vehicle description from NHTSA vPIC…");
  try{
    const endpoint="https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/"+encodeURIComponent(check.vin)+"?format=json";
    const response=await fetch(endpoint,{method:"GET",mode:"cors",credentials:"omit",cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)throw new Error("NHTSA vPIC returned HTTP "+response.status);
    const payload=await response.json();
    const parsed=parseVpicResponse(check.vin,payload);
    if(parsed.status!=="parsed")throw new Error("Vehicle decode could not be verified: "+parsed.reason);
    state.profile={status:"DECODED",profile:normalizedProfile(parsed),provider:"NHTSA_VPIC",retrievedAt:new Date().toISOString(),response:parsed};
    renderProfile();setMessage("Vehicle profile decoded. Review every field; the decoder may omit or misreport attributes.");
  }catch(error){setMessage("Decode unavailable: "+error.message+". Check the VIN and network connection, then retry.",true);}
  finally{$("decode-vin").disabled=false;}
}
$("decode-vin").addEventListener("click",decodeVin);
$("vin-entry").addEventListener("input",()=>{const value=$("vin-entry").value.trim().toUpperCase();const result=validateVin(value);if(result.reason!=="CHECKSUM_MISMATCH")show("checksum-override-row",false);});
$("checksum-override").addEventListener("change",()=>{if($("checksum-override").checked)setMessage("Check-digit override acknowledged. A successful decode still does not authenticate the physical vehicle.");});

async function startCamera(){
  if(!navigator.mediaDevices?.getUserMedia){$("camera-status").textContent="Camera access is unavailable. Enter the VIN manually.";show("camera-wrap");return;}
  if(!("BarcodeDetector" in window)){ $("camera-status").textContent="This browser does not support native barcode scanning. Use manual VIN entry or photograph the VIN plate.";show("camera-wrap");return;}
  try{
    const formats=await BarcodeDetector.getSupportedFormats();
    const supported=["code_39","code_128","qr_code","data_matrix"].filter((x)=>formats.includes(x));
    if(!supported.length)throw new Error("No supported VIN barcode format found.");
    state.detector=new BarcodeDetector({formats:supported});
    state.stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"}},audio:false});
    $("camera-video").srcObject=state.stream;await $("camera-video").play();show("camera-wrap");
    $("camera-status").textContent="Point the rear camera at the VIN barcode.";
    const scan=async()=>{
      if(!state.stream)return;
      try{
        const codes=await state.detector.detect($("camera-video"));
        const match=codes.map(x=>String(x.rawValue||"").replace(/[^A-Za-z0-9]/g,"").toUpperCase()).find(x=>x.length===17);
        if(match){$("vin-entry").value=match;stopCamera();setMessage("VIN barcode detected. Verify it against the physical plate before decoding.");return;}
      }catch{}
      state.scanFrame=requestAnimationFrame(scan);
    };state.scanFrame=requestAnimationFrame(scan);
  }catch(error){$("camera-status").textContent="Scanner could not start: "+error.message+". Enter VIN manually.";show("camera-wrap");}
}
function stopCamera(){
  if(state.scanFrame)cancelAnimationFrame(state.scanFrame);state.scanFrame=null;
  state.stream?.getTracks().forEach(track=>track.stop());state.stream=null;
  $("camera-video").srcObject=null;show("camera-wrap",false);
}
$("start-camera").addEventListener("click",startCamera);
$("stop-camera").addEventListener("click",stopCamera);
$("vin-photo").addEventListener("change",()=>{const file=$("vin-photo").files?.[0];if(file)$("photo-status").textContent="VIN plate photo selected: "+file.name+". This prototype does not OCR the image; read the VIN and enter it manually.";});
window.addEventListener("pagehide",stopCamera);

$("add-observation").addEventListener("click",()=>{
  const notes=$("damage-notes").value.trim();
  const observation={area:$("damage-area").value,type:$("damage-type").value,severity:$("damage-severity").value,photo:$("damage-photo").value,notes};
  if(!notes&&observation.type!=="No visible damage in this area"&&observation.type!=="Unable to determine"){setMessage("Add a brief factual note describing what you observed.",true);return;}
  state.observations.push(observation);$("damage-notes").value="";renderObservations();updateReportAvailability();
});
function renderObservations(){
  const list=$("observation-list");list.replaceChildren();
  state.observations.forEach((item,index)=>{
    const row=document.createElement("div");row.className="observation";
    const title=document.createElement("strong");title.textContent=(index+1)+". "+item.area+" · "+item.type;
    const detail=document.createElement("div");detail.textContent=item.severity+(item.photo?" · Photo: "+slots.find(x=>x[0]===item.photo)?.[1]:"")+(item.notes?" · "+item.notes:"");
    row.append(title,detail);list.append(row);
  });
}
function reportHtml(){
  const p=state.profile.profile;
  const photoCount=state.photos.size;
  const missing=slots.filter(([slot])=>!state.photos.has(slot)).map(([,label])=>label);
  const vehicleRows=[["VIN",state.vin],["Model year",p.modelYear],["Make",p.make],["Model",p.model],["Body class",p.bodyClass],["Trim",p.trim],["Series",p.series],["Drive type",p.driveType],["Engine cylinders",p.engineCylinders],["Displacement (L)",p.displacementL],["Fuel type",p.fuelType],["Transmission",p.transmission],["Plant country",p.plantCountry]];
  const table=vehicleRows.map(([k,v])=>"<tr><th>"+escapeHtml(k)+"</th><td>"+escapeHtml(v||"Not reported")+"</td></tr>").join("");
  const observations=state.observations.length?state.observations.map((x,i)=>"<li><strong>"+escapeHtml(x.area)+" — "+escapeHtml(x.type)+"</strong><br>Operator severity: "+escapeHtml(x.severity)+"<br>"+escapeHtml(x.notes||"No additional note.")+(x.photo?"<br>Linked view: "+escapeHtml(slots.find(s=>s[0]===x.photo)?.[1]||x.photo):"")+"</li>").join(""):"<li>No damage observations were entered.</li>";
  const images=[...state.photos.values()].map(x=>"<div><strong>"+escapeHtml(x.label)+"</strong><br><img src='"+x.url+"' alt='"+escapeHtml(x.label)+"'></div>").join("");
  const checksum=state.checksumStatus==="MATCH"?"North American check digit matched":"Check digit mismatch; manual VIN verification required";
  return "<h2>Claim2Car Vehicle & Condition Report</h2><p>Prototype report · Generated "+escapeHtml(now())+"</p><p class='report-warning'><strong>Scope limitation:</strong> This is a prototype record, not an independent appraisal, insurance decision, ownership verification, roadworthiness inspection, or professional repair estimate. Damage observations were entered by the user. No automated image assessment or repair-cost model ran.</p><h3>1. Vehicle identity</h3><p>Decoder: NHTSA vPIC · "+escapeHtml(checksum)+". The check digit does not prove the physical VIN belongs to this vehicle.</p><table>"+table+"</table><h3>2. Capture completeness</h3><p>"+photoCount+" of 16 target views recorded in this browser session.</p><p>Views not captured: "+(missing.length?missing.map(escapeHtml).join(", "):"None")+". A missing view is not evidence of no damage. Some views may be unsafe or inaccessible.</p><div class='report-images'>"+images+"</div><h3>3. Visible condition observations</h3><ul>"+observations+"</ul><h3>4. Important limitations and unresolved questions</h3><ul><li>Photographs show only visible surfaces and the captured viewpoints.</li><li>Concealed structure, frame, restraint systems, sensors, cooling, mechanical and electrical systems have not been established by this report.</li><li>No collision causation, fault, liability, coverage, total-loss status, repair scope, or repair price is determined.</li><li>Operator severity labels are qualitative judgments, not calibrated probabilities or verified engineering classifications.</li><li>Qualified physical inspection and diagnostic procedures may be required.</li></ul><h3>5. Assessment disposition</h3><p><strong>Disposition: LIMITED DOCUMENTATION ONLY — NOT ADJUDICATED.</strong> Use the evidence record to plan qualified review. Do not treat this prototype report as clearance to drive or repair authorization.</p><p>Source and method: NHTSA vPIC vehicle description; user-provided photographs and observations; Claim2Car prototype report formatter. No automated damage model was used.</p>";
}
$("generate-report").addEventListener("click",()=>{
  if(!state.profile){setMessage("Decode a vehicle before generating a report.",true);return;}
  $("report-preview").innerHTML=reportHtml();show("report-preview");show("print-report");state.reportBuilt=true;
});
$("print-report").addEventListener("click",()=>window.print());
renderPhotoSlots();

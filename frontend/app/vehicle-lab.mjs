import { validateVin } from "../src/modules/capture/vin.mjs";
import { fetchVpicPayload } from "../src/modules/capture/vpic_transport.mjs";
import { parseVpicResponse } from "../src/modules/capture/vpic.mjs";

const $ = (id) => document.getElementById(id);
const state = { profile:null, vin:null, photos:new Map(), observations:[], stream:null, detector:null, scanFrame:null };
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
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));

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
    const exception = document.createElement("select");
    exception.setAttribute("aria-label", "Capture status for " + label);
    for (const [value,text] of [["","Capture status"],["unsafe","Unsafe to capture"],["inaccessible","Inaccessible"],["not_applicable","Not applicable"]]) {
      exception.add(new Option(text,value));
    }
    exception.addEventListener("change", () => {
      const photo = state.photos.get(slot);
      if (photo?.url) URL.revokeObjectURL(photo.url);
      state.photos.delete(slot);
      preview.removeAttribute("src");
      preview.hidden = true;
      input.value = "";
      stateText.textContent = exception.value ? "Not captured · " + exception.options[exception.selectedIndex].text : "Not captured";
      updateReportAvailability();
    });
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) return;
      if (!file.type.startsWith("image/") || file.size <= 0 || file.size > 20*1024*1024) {
        stateText.textContent = "Choose a non-empty image under 20 MiB.";
        input.value = "";
        return;
      }
      const old = state.photos.get(slot);
      if (old?.url) URL.revokeObjectURL(old.url);
      const url = URL.createObjectURL(file);
      state.photos.set(slot,{file,url,label});
      exception.value = "";
      preview.src = url;
      preview.hidden = false;
      stateText.textContent = "Captured in this browser · " + Math.round(file.size/1024) + " KB";
      updateReportAvailability();
      syncPhotoSelect();
    });
    card.append(title,input,exception,stateText,preview);
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
    "Source: NHTSA vPIC DecodeVinValuesExtended · Retrieved " + now() +
    ". Parsed response is format-checked but the source is not independently authenticated. Missing fields remain missing. " +
    "VIN check digit status: " + p.checkDigitStatus + ". Vehicle identity decoding does not establish ownership, history, condition, roadworthiness, or safety.";
  renderPhotoSlots();
  updateReportAvailability();
  show("vehicle-panel");
  show("inspection-panel");
}
async function decodeVin() {
  const raw = $("vin-entry").value.trim();
  const check = validateVin(raw);
  const mismatchOverride = check.reason === "CHECKSUM_MISMATCH";
  if ((!check.ok && !mismatchOverride) || check.normalizationChanged) {
    setMessage(check.reason === "CHECKSUM_MISMATCH"
      ? "The North American VIN check digit does not match. Recheck the VIN plate; this prototype currently supports VINs that pass the North American check-digit rule."
      : "Enter the exact 17-character VIN using permitted VIN characters, without spaces or punctuation.", true);
    return;
  }
  if (mismatchOverride && !$("checksum-override").checked) {
    show("checksum-override-row");
    setMessage("The North American check digit does not match. Recheck the physical VIN; only use the override if the physical plate is verified and the vehicle market does not require this check digit.",true);
    return;
  }
  if (!mismatchOverride) show("checksum-override-row",false);
  if (!$("decode-consent").checked) {
    setMessage("Explicit consent is required before sending the VIN to NHTSA vPIC.",true);
    return;
  }
  state.vin = check.vin;
  $("decode-vin").disabled = true;
  setMessage("Requesting a bounded vehicle decode from NHTSA vPIC…");
  try {
    const transport = await fetchVpicPayload(check.vin,{allowCheckDigitMismatch:mismatchOverride});
    if (transport.status !== "response_received") throw new Error("NHTSA lookup unavailable: " + transport.reason);
    const parsed = parseVpicResponse(check.vin,transport.payload,{allowCheckDigitMismatch:mismatchOverride});
    if (parsed.status !== "parsed") throw new Error("Vehicle decode was blocked: " + parsed.reason);
    state.profile = parsed.profile;
    renderProfile();
    setMessage("Vehicle description decoded. Review the reported fields; no damage or ownership assessment has been performed.");
  } catch (error) {
    state.profile = null;
    show("vehicle-panel",false);
    show("inspection-panel",false);
    show("report-panel",false);
    setMessage("Decode unavailable: " + error.message + ". Verify the VIN and retry.",true);
  } finally {
    $("decode-vin").disabled = false;
  }
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
  state.observations.push(observation);
  $("damage-notes").value = "";
  renderObservations();
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
    row.append(title,detail);
    list.append(row);
  });
}
function reportHtml() {
  const p = state.profile;
  const missing = slots.filter(([slot]) => !state.photos.has(slot)).map(([slot,label]) => {
    const select = [...$("photo-grid").querySelectorAll("select")].find(node => node.value && node.getAttribute("aria-label") === "Capture status for " + label);
    return select ? label + " (" + select.options[select.selectedIndex].text + ")" : label;
  });
  const rows = [
    ["VIN",state.vin],["Model year",p.modelYear],["Make",p.make],["Model",p.model],
    ["Body class",p.bodyClass],["Curb weight",p.curbWeightStatus === "reported" ? p.curbWeightLb + " lb / " + p.curbWeightKg.toFixed(1) + " kg" : "Not reported (" + p.curbWeightStatus + ")"]
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
  return "<h2>Claim2Car Vehicle &amp; Condition Report</h2><p>Prototype report · Generated " + escapeHtml(now()) +
    "</p><p class='report-warning'><strong>Scope limitation:</strong> This is a documentation prototype, not an appraisal, insurance decision, ownership verification, roadworthiness inspection, or professional repair estimate. Damage observations were entered by the operator. No automated damage assessment or repair-cost model ran.</p>" +
    "<h3>1. Vehicle identity</h3><p>Source: NHTSA vPIC. VIN check digit status: " + escapeHtml(p.checkDigitStatus) + ". A mismatch override is not proof of VIN authenticity or vehicle identity.</p><table>" + table + "</table>" +
    "<h3>2. Capture completeness</h3><p>" + state.photos.size + " of 16 contract views recorded in this browser session.</p><p>Views not captured: " +
    (missing.length ? missing.map(escapeHtml).join(", ") : "None") + ". Missing views are unknown, not evidence of no damage.</p><div class='report-images'>" + images + "</div>" +
    "<h3>3. Visible condition observations</h3><ul>" + observations + "</ul>" +
    "<h3>4. Unresolved questions</h3><ul><li>Concealed structure and components have not been assessed.</li><li>No collision causation, fault, liability, coverage, total-loss status, repair scope, or repair price is determined.</li><li>Severity labels are qualitative operator judgments, not calibrated probabilities or verified engineering classifications.</li><li>Qualified physical inspection and diagnostic procedures may be required.</li></ul>" +
    "<h3>5. Disposition</h3><p><strong>LIMITED DOCUMENTATION ONLY — NOT ADJUDICATED.</strong> This report is not clearance to drive or repair authorization.</p>" +
    "<p>Method: NHTSA vPIC vehicle description; user-provided photographs and observations; local browser report formatter. No automated damage model was used. Evidence has not been uploaded or sealed by this lab.</p>";
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

// Browser exercise of the real UI flow to an active inspection, then pause/resume.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../../app/vehicle-lab.html", import.meta.url), "utf8");
const moduleSource = readFileSync(new URL("../../app/vehicle-lab.mjs", import.meta.url), "utf8");
const vinSource = readFileSync(new URL("../../src/modules/capture/vin.mjs", import.meta.url), "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [], consoleErrors = [], failedRequests = [], requests = [];
  page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("requestfailed", request => failedRequests.push({url:request.url(),error:request.failure()?.errorText}));
  let paused = false;
  const sessionId = "browser-session-fixture";
  let claimId = null;
  const ownerToken = "synthetic-owner-token";
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/frontend/app/vehicle-lab.html", route => route.fulfill({ status: 200, contentType: "text/html", body: html
    .replace("/prototype/styles.css", "/test-styles.css")
    .replace("/prototype/vehicle-lab.css", "/frontend/app/vehicle-lab.css")
    .replace("/prototype/vehicle-lab.mjs", "/frontend/app/vehicle-lab.mjs") }));
  await page.route("**/test-styles.css", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("**/frontend/app/vehicle-lab.mjs", route => route.fulfill({ status: 200, contentType: "text/javascript", body: moduleSource }));
  await page.route("**/frontend/src/modules/capture/vin.mjs", route => route.fulfill({ status: 200, contentType: "text/javascript", body: vinSource }));
  await page.route("**/api/**", async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    requests.push({ method: request.method(), path });
    const json = (status, body) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/api/v1/claim-cases" && request.method() === "POST") { claimId = JSON.parse(request.postData() || "{}").claim_id; return json(201,{scope:"persistent-claim-case",claim_id:claimId,capture_session_id:sessionId,created:true}); }
    if (path.endsWith("/consent") && request.method() === "POST") return json(201,{accepted:true});
    if (path.endsWith("/vehicle-reference") && request.method() === "POST") return json(201,{recorded:true});
    if (path === "/api/v1/vehicle-decode-disclosure" && request.method() === "GET") return json(200,{disclosure_version:"test-disclosure-v1"});
    if (path.endsWith("/vehicle-decode-consent") && request.method() === "POST") return json(201,{accepted:true});
    if (path.endsWith("/artifacts") && request.method() === "POST") {
      const body=JSON.parse(request.postData()||"{}");
      return json(200,{request_id:body.request_id,artifact_id:body.artifact_id,slot:body.slot,sha256:body.sha256,byte_length:68,replayed:false,
        localization:{image:{sha256:body.sha256,byte_length:68,persisted:true},analysis:{status:"COMPLETED",method:"heuristic_contrast_baseline",model_status:"BASELINE_NOT_AI",model_version:"damage-localization-v1/heuristic-baseline",trained_model_inference:false,appraisal:false,physical_measurements:false,note:"heuristic only",observations:[{slot:body.slot,zone:"front",normalized_region_area_fraction:0.04,predicted_damage_class:"unknown",raw_detector_score:0.25,score_semantics:"uncalibrated_detector_score",model_version:"damage-localization-v1/heuristic-baseline",protocol_version:"claims2car-16-v1",bbox_normalized:[0.1,0.2,0.3,0.4]}]}});
    }
    if (path.endsWith("/vehicle-profile") && request.method() === "POST") return json(200,{
      status:"DECODED",provider:"NHTSA vPIC",requested_at:"2026-11-20T12:00:00Z",response_sha256:"a".repeat(64),
      physics_input_eligibility:"NOT_EVALUATED",attributes:{
        model_year:{value:2003},make:{value:"Honda"},model:{value:"Accord"},body_class:{value:"Sedan"},
        trim:{value:"EX"},series:{value:null},drive_type:{value:"FWD"},engine_cylinders:{value:4},
        displacement_l:{value:2.4},fuel_type_primary:{value:"Gasoline"},curb_weight_lb:{value:null}
      }});
    if (path.endsWith("/evidence-readiness") && request.method() === "GET") return json(200,{
      session_id:sessionId,capture_paused:paused,active_capture_exceptions:[],consent_active:true,vehicle_reference_present:true
    });
    if (path.endsWith("/pause") && request.method() === "POST") { paused=true; return json(200,{session_id:sessionId,paused:true}); }
    if (path.endsWith("/resume") && request.method() === "POST") { paused=false; return json(200,{session_id:sessionId,paused:false}); }
    return json(404,{detail:"UNEXPECTED_TEST_ROUTE"});
  });
  await page.goto("http://127.0.0.1:4173/frontend/app/vehicle-lab.html");
  const pause=page.locator("#pause-capture"), resume=page.locator("#resume-capture");
  assert.equal(await pause.isDisabled(),true,"pause starts disabled before authenticated session");
  assert.equal(await resume.isDisabled(),true,"resume starts disabled before authenticated session");
  await page.locator("#capture-operator-token").fill("O".repeat(43));
  await page.locator("#create-claim-case").click();
  try { await page.waitForFunction(() => document.querySelector("#owner-consent-panel").hidden === false, {timeout:10000}); } catch(error) { throw new Error("Session creation UI did not initialize. console: "+JSON.stringify(consoleErrors)+" failed requests: "+JSON.stringify(failedRequests)+"; "+error.message); }
  await page.waitForFunction(() => document.querySelector("#pause-capture").disabled === false);
  assert.equal(await pause.isVisible(),true);
  assert.equal(await resume.isVisible(),false);
  assert.equal(await resume.isDisabled(),true);
  assert.equal(requests.filter(x=>x.path.endsWith("/evidence-readiness")).length,1,"readiness queried after persistent case creation");
  assert.equal(requests.filter(x=>x.path === "/api/v1/claim-cases" && x.method === "POST").length,1,"persistent claim case created exactly once");
  assert.equal(requests.some(x=>x.path === "/api/v1/capture-sessions" && x.method === "POST"),false,"controlled-test session route is not used");
  assert.match(await page.locator("#claim-case-id").textContent(),new RegExp(claimId+".*browser-session-fixture"));

  await page.locator("#capture-pause-reason").fill("Synthetic browser safety-stop test");
  await pause.click();
  await page.waitForFunction(() => document.querySelector("#resume-capture").disabled === false);
  assert.equal(await pause.isVisible(),false);
  assert.equal(await resume.isVisible(),true);
  assert.match(await page.locator("#capture-paused-status").textContent(),/CAPTURE PAUSED/);

  await page.locator("#capture-pause-reason").fill("Synthetic browser resume test");
  await resume.click();
  await page.waitForFunction(() => document.querySelector("#pause-capture").disabled === false);
  assert.equal(await pause.isVisible(),true);
  assert.equal(await resume.isVisible(),false);
  assert.match(await page.locator("#capture-paused-status").textContent(),/Capture active/);
  assert.equal(requests.filter(x=>x.path.endsWith("/pause")&&x.method==="POST").length,1);
  assert.equal(requests.filter(x=>x.path.endsWith("/resume")&&x.method==="POST").length,1);
  await page.locator("#owner-capture-token").fill(ownerToken);
  await page.locator("#owner-capture-consent").check();
  await page.locator("#record-capture-consent").click();
  await page.waitForFunction(() => document.querySelector("#record-capture-consent").disabled === true);
  await page.locator("#vin-entry").fill("1HGCM82633A004352");
  await page.locator("#decode-consent").check();
  await page.locator("#decode-owner-token").fill(ownerToken);
  await page.locator("#decode-vin").click();
  try { await page.waitForFunction(() => document.querySelector("#inspection-panel").hidden === false, {timeout:10000}); }
  catch(error){ throw new Error("Inspection panel did not activate. Backend status: "+await page.locator("#backend-status").textContent()+"; VIN status: "+await page.locator("#vin-message").textContent()+"; requests: "+JSON.stringify(requests)+"; page errors: "+JSON.stringify(errors)+"; console errors: "+JSON.stringify(consoleErrors)+"; failed requests: "+JSON.stringify(failedRequests)+"; "+error.message); }
  assert.equal(await pause.isVisible(),true);
  assert.equal(await resume.isVisible(),false);
  assert.equal(requests.filter(x=>x.path.endsWith("/evidence-readiness")).length,4,"readiness refreshed after session, pause, resume, and profile");
  // Upload a real file fixture and exercise the disclosed localization feedback.
  const pngBytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a4sAAAAASUVORK5CYII=","base64");
  await page.getByLabel("Photograph Front exterior").setInputFiles({name:"front.png",mimeType:"image/png",buffer:pngBytes});
  await page.waitForFunction(() => [...document.querySelectorAll("#photo-grid .lab-photo-card .photo-state")].some(el => el.textContent.includes("Contrast baseline: 1 candidate region")));
  // Exercise the operator-entered worksheet and report calculation in the actual browser.
  await page.locator("#damage-area").selectOption("Front-left");
  await page.locator("#damage-type").selectOption("Dent / deformation");
  await page.locator("#damage-severity").selectOption("Moderate visible deformation");
  await page.locator("#damage-notes").fill("Synthetic fixture: visible panel dent");
  await page.locator("#estimate-action").selectOption("Repair");
  await page.locator("#estimate-hours").fill("2");
  await page.locator("#estimate-parts").fill("250");
  await page.locator("#estimate-materials").fill("40");
  await page.locator("#estimate-labor-rate").fill("85");
  await page.locator("#estimate-tax-rate").fill("0");
  await page.locator("#add-observation").click();
  assert.match(await page.locator("#estimate-summary").textContent(),/Worksheet total \$460\.00/);
  await page.locator("#generate-report").click();
  assert.match(await page.locator("#report-preview").textContent(),/Worksheet total/);
  assert.match(await page.locator("#report-preview").textContent(),/\$460\.00/);
  assert.match(await page.locator("#report-preview").textContent(),/operator-entered/);
  assert.match(await page.locator("#report-preview").textContent(),/Image-space contrast baseline/);
  assert.match(await page.locator("#report-preview").textContent(),/Candidate 1: unknown/);
  assert.match(await page.locator("#report-preview").textContent(),/uncalibrated/);
  assert.deepEqual(errors,[]);
  process.stdout.write(JSON.stringify({outcome:"passed",checks:[
    "authenticated session creation",
    "owner capture consent flow",
    "VIN reference and separate decode consent",
    "pause controls available before consent and VIN decoding",
    "pause enables resume and disables pause",
    "resume enables pause and disables resume",
    "server readiness refreshed after both transitions"
  ]},null,2)+"\n");
} finally { await browser.close(); }

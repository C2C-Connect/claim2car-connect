// Browser exercise of the real UI flow to an active inspection, then pause/resume.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../../app/vehicle-lab.html", import.meta.url), "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [], requests = [];
  let paused = false;
  const sessionId = "browser-session-fixture";
  const ownerToken = "synthetic-owner-token";
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/frontend/app/vehicle-lab.html", route => route.fulfill({ status: 200, contentType: "text/html", body: html
    .replace("/prototype/styles.css", "/test-styles.css")
    .replace("/prototype/vehicle-lab.css", "/frontend/app/vehicle-lab.css")
    .replace("/prototype/vehicle-lab.mjs", "/frontend/app/vehicle-lab.mjs") }));
  await page.route("**/test-styles.css", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("**/api/**", async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    requests.push({ method: request.method(), path });
    const json = (status, body) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/api/v1/capture-sessions" && request.method() === "POST") return json(201,{session_id:sessionId});
    if (path.endsWith("/consent") && request.method() === "POST") return json(201,{accepted:true});
    if (path.endsWith("/vehicle-reference") && request.method() === "POST") return json(201,{recorded:true});
    if (path === "/api/v1/vehicle-decode-disclosure" && request.method() === "GET") return json(200,{disclosure_version:"test-disclosure-v1"});
    if (path.endsWith("/vehicle-decode-consent") && request.method() === "POST") return json(201,{accepted:true});
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
  await page.locator("#create-capture-session").click();
  await page.waitForFunction(() => document.querySelector("#owner-consent-panel").hidden === false);
  await page.waitForFunction(() => document.querySelector("#pause-capture").disabled === false);
  assert.equal(await pause.isVisible(),true);
  assert.equal(await resume.isVisible(),false);
  assert.equal(await resume.isDisabled(),true);
  assert.equal(requests.filter(x=>x.path.endsWith("/evidence-readiness")).length,1,"readiness queried after session creation");

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
  catch(error){ throw new Error("Inspection panel did not activate. Backend status: "+await page.locator("#backend-status").textContent()+"; VIN status: "+await page.locator("#vin-message").textContent()+"; requests: "+JSON.stringify(requests)+"; page errors: "+JSON.stringify(errors)+"; "+error.message); }
  assert.equal(await pause.isVisible(),true);
  assert.equal(await resume.isVisible(),false);
  assert.equal(requests.filter(x=>x.path.endsWith("/evidence-readiness")).length,4,"readiness refreshed after session, pause, resume, and profile");
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

// Browser-level owner consent and operator vehicle-profile journey.
// All identities, VINs, and provider responses are synthetic fixtures.
import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({headless:true});
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const pageErrors = [];
  const calls = [];
  let role = "owner";
  let decodeConsentAccepted = false;
  page.on("pageerror", error => pageErrors.push(error.message));
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = request.postDataJSON?.() || {};
    calls.push({path,method,body});
    const json = (value,status=200) => route.fulfill({
      status,contentType:"application/json",body:JSON.stringify(value),
    });
    if (path === "/api/v1/identity" && method === "GET") {
      return json({actor_id:`synthetic-${role}`,tenant_id:"synthetic-tenant",actor_role:role});
    }
    if (path === "/api/v1/capture-protocols" && method === "GET") {
      return json({
        default_protocol_version:"claims2car-16-v1",
        protocols:[{version:"claims2car-16-v1",capture_enabled:true,required_slots:[],slot_descriptions:{}}],
      });
    }
    if (path === "/api/v1/vehicle-decode-disclosure" && method === "GET") {
      return json({
        disclosure_version:"vehicle-decode-disclosure-v1",
        purpose:"Optional manufacturer-reported VIN description lookup through NHTSA vPIC.",
        sections:[
          "The VIN you provided will be sent to NHTSA vPIC.",
          "Returned attributes may be unavailable, incomplete, or inaccurate.",
          "This lookup does not establish ownership, physical condition, damage, or roadworthiness.",
        ],
      });
    }
    if (path.endsWith("/vehicle-decode-consent") && method === "POST") {
      decodeConsentAccepted = body.accepted === true;
      return json({accepted:body.accepted,replayed:false,scope:body.scope,disclosure_version:body.disclosure_version});
    }
    if (path.endsWith("/vehicle-profile") && method === "POST") {
      if (!decodeConsentAccepted) return json({detail:"ACTIVE_VEHICLE_DECODE_CONSENT_REQUIRED"},403);
      return json({
        status:"DECODED",provider:"NHTSA_VPIC",provider_api:"DecodeVinValuesExtended",
        requested_at:"2026-11-18T12:00:00Z",response_sha256:"a".repeat(64),
        physics_input_eligibility:"NOT_ESTABLISHED",replayed:false,
        attributes:{
          make:{value:"HONDA",status:"REPORTED",source:"NHTSA_VPIC",source_field:"Make",unit:null},
          model:{value:"Accord",status:"REPORTED",source:"NHTSA_VPIC",source_field:"Model",unit:null},
          model_year:{value:2003,status:"REPORTED",source:"NHTSA_VPIC",source_field:"ModelYear",unit:null},
          curb_weight_lb:{value:null,status:"UNAVAILABLE",source:"NHTSA_VPIC",source_field:"CurbWeightLB",unit:"lb"},
        },
      });
    }
    if (path === "/api/v1/claim-cases" && method === "GET") return json([]);
    if (path === "/api/v1/capture-sessions" && method === "GET") return json([]);
    return json({detail:"UNEXPECTED_TEST_REQUEST",path,method},404);
  });

  await page.goto("http://127.0.0.1:4174/");
  await page.locator("#access-token").fill("synthetic-owner-token");
  await page.locator("#connect").click();
  await page.waitForFunction(() => !document.querySelector("#owner-view").hidden);
  await page.locator("#owner-session-id").fill("synthetic-session-001");
  await page.locator("#load-vehicle-decode-disclosure").click();
  await page.waitForFunction(() => !document.querySelector("#vehicle-decode-disclosure").hidden);
  const disclosureText = await page.locator("#vehicle-decode-disclosure").innerText();
  assert.match(disclosureText,/NHTSA vPIC/);
  assert.match(disclosureText,/does not establish ownership/);
  await page.locator("#vehicle-decode-consent-accepted").check();
  await page.locator("#record-vehicle-decode-consent").click();
  await page.waitForFunction(() => document.querySelector("#vehicle-decode-consent-message").textContent.includes("consent recorded"));
  const accepted = calls.find(item => item.path.endsWith("/vehicle-decode-consent") && item.body.accepted === true);
  assert.ok(accepted);
  assert.equal(accepted.body.scope,"nhtsa_vpic_decode");
  assert.equal(accepted.body.disclosure_version,"vehicle-decode-disclosure-v1");
  assert.equal(calls.some(item => item.path.endsWith("/consent")),false,"decode consent must not imply capture consent");

  await page.locator("#disconnect").click();
  role = "operator";
  await page.locator("#access-token").fill("synthetic-operator-token");
  await page.locator("#connect").click();
  await page.waitForFunction(() => !document.querySelector("#operator-view").hidden);
  await page.locator("#session-id").fill("synthetic-session-001");
  await page.locator("#vin").fill("1HGCM82633A004352");
  await page.locator("#decode-vehicle-profile").click();
  await page.waitForFunction(() => document.querySelector("#vehicle-profile-result").innerText.includes("HONDA"));
  const profileText = await page.locator("#vehicle-profile-result").innerText();
  assert.match(profileText,/NHTSA_VPIC/);
  assert.match(profileText,/NOT_ESTABLISHED/);
  assert.match(profileText,/not proof of ownership/);
  assert.doesNotMatch(profileText,/1HGCM82633A004352/);

  await page.locator("#disconnect").click();
  role = "owner";
  await page.locator("#access-token").fill("synthetic-owner-token");
  await page.locator("#connect").click();
  await page.waitForFunction(() => !document.querySelector("#owner-view").hidden);
  await page.locator("#owner-session-id").fill("synthetic-session-001");
  await page.locator("#load-vehicle-decode-disclosure").click();
  await page.waitForFunction(() => !document.querySelector("#vehicle-decode-disclosure").hidden);
  await page.locator("#withdraw-vehicle-decode-consent").click();
  await page.waitForFunction(() => document.querySelector("#vehicle-decode-consent-message").textContent.includes("withdrawn"));
  assert.equal(decodeConsentAccepted,false);

  await page.locator("#disconnect").click();
  role = "operator";
  await page.locator("#access-token").fill("synthetic-operator-token");
  await page.locator("#connect").click();
  await page.waitForFunction(() => !document.querySelector("#operator-view").hidden);
  await page.locator("#session-id").fill("synthetic-session-001");
  await page.locator("#vin").fill("1HGCM82633A004352");
  await page.locator("#decode-vehicle-profile").click();
  await page.waitForFunction(() => document.querySelector("#vehicle-profile-result").innerText.includes("ACTIVE_VEHICLE_DECODE_CONSENT_REQUIRED"));
  assert.deepEqual(pageErrors,[]);
  await context.close();
  process.stdout.write(JSON.stringify({
    outcome:"passed",
    checks:[
      "owner loads current server disclosure",
      "VIN lookup consent is separate from capture consent",
      "operator receives provider-attributed profile after consent",
      "profile UI disclaims ownership and physical-condition conclusions",
      "raw VIN is not rendered in profile output",
      "owner withdrawal blocks subsequent operator lookup",
    ],
  },null,2)+"\n");
} finally {
  await browser.close();
}

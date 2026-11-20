import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const html = readFileSync(new URL("../app/vehicle-lab.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../app/vehicle-lab.mjs", import.meta.url), "utf8");
const ids = ["backend-panel","capture-operator-token","create-claim-case","owner-capture-token","owner-capture-consent","record-capture-consent","decode-owner-token","seal-evidence","seal-status","capture-paused-status","pause-capture","resume-capture","capture-pause-reason"];
for (const id of ids) assert.match(html, new RegExp('id="' + id + '"'), "missing backend control: " + id);
for (const route of ["/v1/claim-cases", "/v1/capture-sessions","/consent","/vehicle-reference","/vehicle-decode-disclosure","/vehicle-decode-consent","/vehicle-profile","/artifacts","/quality","/seal","/evidence-readiness","/exceptions","/exceptions/resolve","/pause","/resume"]) assert.ok(source.includes(route), "missing authoritative route " + route);
assert.match(source,/crypto\.subtle\.digest\("SHA-256"/);
assert.match(source,/state\.photos\.get\(slot\)\?\.uploaded === true/);
assert.match(source,/state\.manifestDigest = sealed\.manifest_digest/);
assert.doesNotMatch(source,/localStorage|sessionStorage|fetchVpicPayload|parseVpicResponse/);
assert.match(source,/state\.vehicleRecorded && state\.vin !== check\.vin/);
assert.match(source,/state\.photos\.size > 0/);
assert.match(html, /id="claim-case-id"/);
assert.match(html, /Create persistent claim case/);
assert.match(source, /captureApi\("\/v1\/claim-cases"/);
assert.match(source, /created\.capture_session_id/);
assert.match(source, /created\.claim_id/);
assert.match(source, /persistent-claim-case/);
assert.doesNotMatch(source, /captureApi\("\/v1\/capture-sessions",/);
assert.match(source, /state\.claimRequestId \|\|= uuid\(\)/);
assert.doesNotMatch(html,/lookup is performed from this browser|not saved by this lab/);
assert.match(html,/audited exceptions/i);
assert.match(source,/activeExceptions = new Map/);
assert.match(source,/refreshEvidenceReadiness/);
assert.match(source,/capturePaused/);
assert.match(source,/Record audited exception/);
assert.match(source,/Resolve exception/);
console.log(JSON.stringify({suite:"vehicle-lab-backend-contract",assertions:ids.length+13,status:"passed"}));

assert.match(source,/pause-capture\"\)\.disabled = !state\.captureToken \|\| !state\.sessionId \|\| state\.capturePaused/);
assert.match(source,/resume-capture\"\)\.disabled = !state\.captureToken \|\| !state\.sessionId \|\| !state\.capturePaused/);

assert.match(html,/<button id="pause-capture"[^>]*disabled/);
assert.match(html,/<button id="resume-capture"[^>]*hidden[^>]*disabled/);

// Transparent estimate worksheet is strictly operator-entered, with live math and report inclusion.
for (const id of ["estimate-action","estimate-hours","estimate-parts","estimate-materials","estimate-labor-rate","estimate-tax-rate","estimate-summary"]) assert.match(html,new RegExp('id="'+id+'"'));
assert.match(source,/function estimateLineSubtotal/);
assert.match(source,/function estimateTotals/);
assert.match(source,/operator-entered/);
assert.match(source,/worksheet total/i);
assert.match(source,/state\.observations\.push\(observation\)/);
assert.match(source,/estimateHtml/);

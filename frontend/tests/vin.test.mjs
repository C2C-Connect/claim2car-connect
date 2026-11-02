// Pure offline assertions. These fixtures are not decoded vehicle identities.
import assert from 'node:assert/strict';
import {validateVin,VIN_WEIGHTS} from '../src/modules/capture/vin.mjs';
const records = [];
function test(id,action) {
  try { action(); records.push({id,outcome:'passed'}); }
  catch (error) { records.push({id,outcome:'failed',error_type:error.name}); }
}
const numeric = '1HGCM82633A004352';
const withX = '1M8GDM9AXKP042788';
test('numeric_check_digit',()=>{const r=validateVin(numeric);assert.equal(r.ok,true);assert.equal(r.expectedCheckDigit,'3');});
test('remainder_ten_requires_x',()=>{const r=validateVin(withX);assert.equal(r.ok,true);assert.equal(r.expectedCheckDigit,'X');});
test('lowercase_normalizes_without_changing_identity',()=>{const r=validateVin(numeric.toLowerCase());assert.equal(r.ok,true);assert.equal(r.vin,numeric);assert.equal(r.rawVin,numeric.toLowerCase());assert.equal(r.normalizationChanged,true);});
test('ascii_separators_are_removed_and_original_retained',()=>{const raw=' 1HG-CM82633A004352 ';const r=validateVin(raw);assert.equal(r.ok,true);assert.equal(r.rawVin,raw);assert.equal(r.vin,numeric);});
test('wrong_check_digit_is_not_repaired',()=>{const bad=numeric.slice(0,8)+'4'+numeric.slice(9);const r=validateVin(bad);assert.equal(r.ok,false);assert.equal(r.reason,'CHECKSUM_MISMATCH');assert.equal(r.vin,bad);assert.equal(r.receivedCheckDigit,'4');assert.equal(r.expectedCheckDigit,'3');});
test('illegal_i_o_q_are_never_substituted',()=>{for(const char of ['I','O','Q']){const r=validateVin(numeric.slice(0,4)+char+numeric.slice(5));assert.equal(r.ok,false);assert.equal(r.reason,'ILLEGAL_CHARACTERS');}});
test('short_and_long_vins_rejected',()=>{for(const value of ['',numeric.slice(1),numeric+'0'])assert.equal(validateVin(value).reason,'INVALID_LENGTH');});
test('non_string_inputs_rejected',()=>{for(const value of [undefined,null,123,{},[]])assert.equal(validateVin(value).reason,'INVALID_INPUT');});
test('unicode_confusables_not_silently_rewritten',()=>{for(const raw of ['１'+numeric.slice(1),numeric+'ß']){const r=validateVin(raw);assert.equal(r.ok,false);assert.equal(r.vin,null);assert.equal(r.rawVin,raw);}});
test('oversized_input_has_bounded_report',()=>{const r=validateVin('A'.repeat(257));assert.equal(r.reason,'INPUT_TOO_LONG');assert.equal(r.rawVin,null);});
test('standard_weights_are_immutable',()=>{assert.deepEqual(VIN_WEIGHTS,[8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2]);assert.throws(()=>{VIN_WEIGHTS[0]=0;},TypeError);});
test('report_is_immutable',()=>{const r=validateVin(numeric);assert.throws(()=>{r.ok=false;},TypeError);});
test('failure_has_exact_recapture_message',()=>assert.equal(validateVin(null).message,'VIN VALIDATION FAILED: Recapture VIN Plate'));
test('checksum_pass_is_not_decoded_identity',()=>{const r=validateVin('0'.repeat(17));assert.equal(r.ok,true);assert.equal(r.scope,'format-and-check-digit-only');for(const key of ['make','model','bodyClass','massKg'])assert.equal(Object.hasOwn(r,key),false);});
const failures=records.filter(r=>r.outcome!=='passed').length;
const successful=records.length>0 && new Set(records.map(r=>r.id)).size===records.length && failures===0;
console.log(JSON.stringify({classification:'offline-vin-format-checkdigit-unit-tests-not-vehicle-authenticity',commit:process.env.GITHUB_SHA ?? null,runtime:process.version,executed:records.length,failures,successful,tests:records},null,2));
process.exitCode=successful?0:1;

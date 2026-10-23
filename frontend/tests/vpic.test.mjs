// Synthetic vPIC-format fixtures only. No service calls or source-authenticity claim.
import assert from 'node:assert/strict';
import {parseVpicResponse} from '../src/modules/capture/vpic.mjs';
const vin='1HGCM82633A004352';
const records=[];
function test(id,action){try{action();records.push({id,outcome:'passed'});}catch(error){records.push({id,outcome:'failed',error_type:error.name});}}
function fixture(changes={}){return {Count:1,Results:[{VIN:vin,ErrorCode:'0',SuggestedVIN:'',Make:'FIXTURE MAKE',Model:'Fixture Model',ModelYear:'2003',BodyClass:'Sedan/Saloon',CurbWeightLB:'1000',...changes}]};}
test('clean_profile_and_explicit_lb_to_kg_conversion',()=>{const r=parseVpicResponse(vin,fixture());assert.equal(r.status,'parsed');assert.equal(r.profile.bodyClass,'Sedan/Saloon');assert.equal(r.profile.modelYear,2003);assert.ok(Math.abs(r.profile.curbWeightKg-453.59237)<1e-9);assert.equal(r.physicsReady,false);assert.equal(r.massBoundsConfigured,false);});
test('missing_mass_is_not_zero_or_gvwr',()=>{const r=parseVpicResponse(vin,fixture({CurbWeightLB:'',GVWR:'10000'}));assert.equal(r.status,'parsed');assert.equal(r.profile.curbWeightKg,null);assert.equal(r.profile.curbWeightStatus,'unavailable');});
test('invalid_mass_is_never_clamped_or_defaulted',()=>{for(const value of ['0','-10','NaN','Infinity','3000 - 4000','1e309']){const r=parseVpicResponse(vin,fixture({CurbWeightLB:value}));assert.equal(r.profile.curbWeightKg,null);assert.equal(r.profile.curbWeightStatus,'invalid');assert.equal(r.physicsReady,false);}});
test('mass_outside_unspecified_bounds_is_preserved_not_approved',()=>{const r=parseVpicResponse(vin,fixture({CurbWeightLB:'100000'}));assert.equal(r.profile.curbWeightLb,100000);assert.equal(r.massBoundsConfigured,false);assert.equal(r.physicsReady,false);});
test('decode_errors_and_mixed_codes_block',()=>{for(const code of ['',null,'1','0,10']){const r=parseVpicResponse(vin,fixture({ErrorCode:code}));assert.equal(r.reason,'DECODE_STATUS_UNRESOLVED');assert.equal(r.profile,null);}});
test('missing_decode_status_blocks',()=>{const value=fixture();delete value.Results[0].ErrorCode;assert.equal(parseVpicResponse(vin,value).status,'blocked');});
test('suggested_vin_is_never_substituted',()=>{const value='1M8GDM9AXKP042788';const r=parseVpicResponse(vin,fixture({SuggestedVIN:value}));assert.equal(r.reason,'SUGGESTED_VIN_REQUIRES_REVIEW');assert.equal(r.suggestedVin,value);assert.equal(r.profile,null);});
test('response_for_another_vin_cannot_become_active_profile',()=>{const r=parseVpicResponse(vin,fixture({VIN:'1M8GDM9AXKP042788'}));assert.equal(r.reason,'VIN_MISMATCH');assert.equal(r.profile,null);});
test('invalid_request_vin_blocks_before_touching_payload',()=>{const payload=new Proxy({},{get(){throw Error('UNEXPECTED_RESPONSE_ACCESS');}});assert.equal(parseVpicResponse('bad',payload).reason,'INVALID_REQUEST_VIN');});
test('malformed_and_ambiguous_response_shapes_block',()=>{for(const payload of [null,{},[],{Count:1,Results:[]},{Count:1,Results:[null]},{Count:2,Results:[{},{}]}])assert.equal(parseVpicResponse(vin,payload).reason,'INVALID_RESPONSE');});
test('required_profile_fields_remain_missing_not_generic_defaults',()=>{for(const key of ['Make','Model','BodyClass','ModelYear']){const r=parseVpicResponse(vin,fixture({[key]:''}));assert.equal(r.reason,'INCOMPLETE_PROFILE');assert.equal(r.profile,null);}});
test('malformed_year_does_not_become_a_default',()=>{for(const value of ['0000','2003.0','20A3'])assert.equal(parseVpicResponse(vin,fixture({ModelYear:value})).reason,'INCOMPLETE_PROFILE');});
test('request_normalization_uses_the_same_vin_guard',()=>assert.equal(parseVpicResponse(' 1HG-CM82633A004352 ',fixture()).profile.vin,vin));
test('raw_fields_are_retained_without_aliasing_input',()=>{const payload=fixture({AdditionalVariable:'fixture-extra'});const r=parseVpicResponse(vin,payload);payload.Results[0].Make='changed';assert.equal(r.rawResult.Make,'FIXTURE MAKE');assert.equal(r.rawResult.AdditionalVariable,'fixture-extra');assert.throws(()=>{r.profile.make='changed';},TypeError);});
test('oversized_response_blocks',()=>assert.equal(parseVpicResponse(vin,fixture({Extra:'x'.repeat(262145)})).reason,'INVALID_RESPONSE'));
test('unknown_profile_sentinel_is_not_treated_as_identity',()=>assert.equal(parseVpicResponse(vin,fixture({Make:'Unknown'})).reason,'INCOMPLETE_PROFILE'));
const failures=records.filter(r=>r.outcome!=='passed').length;
const successful=records.length>0&&new Set(records.map(r=>r.id)).size===records.length&&failures===0;
console.log(JSON.stringify({classification:'offline-synthetic-vpic-response-adapter-not-live-service-validation',commit:process.env.GITHUB_SHA??null,runtime:process.version,executed:records.length,failures,successful,tests:records},null,2));
process.exitCode=successful?0:1;

/** Offline parser for one extended flat vPIC result. Never calls a service or authenticates its source. */
import {validateVin} from './vin.mjs';
const SCOPE='parsed-vpic-format-not-source-authentication';
function text(value) {
  if (typeof value!=='string' || value.length>200) return null;
  const result=value.trim();
  return !result || /^(?:unknown|not applicable|not available|n\/a|null)$/i.test(result) ? null : result;
}
function mass(value) {
  if (value===null || value===undefined || (typeof value==='string' && !value.trim()))
    return {curbWeightStatus:'unavailable',curbWeightLb:null,curbWeightKg:null};
  const raw=typeof value==='string' ? value.trim() : '';
  const lb=/^\d+(?:\.\d+)?$/.test(raw) ? Number(raw) : NaN;
  const kg=lb*0.45359237;
  return Number.isFinite(lb)&&lb>0&&Number.isFinite(kg)&&kg>0
    ? {curbWeightStatus:'reported',curbWeightLb:lb,curbWeightKg:kg}
    : {curbWeightStatus:'invalid',curbWeightLb:null,curbWeightKg:null};
}
export function parseVpicResponse(requestedVin,payload) {
  let rawResult=null,decodeErrorCode=null,suggestedVin=null;
  const blocked=reason=>Object.freeze({status:'blocked',reason,scope:SCOPE,profile:null,rawResult,decodeErrorCode,suggestedVin,physicsReady:false,massBoundsConfigured:false});
  const validation=validateVin(requestedVin);
  if (!validation.ok) return blocked('INVALID_REQUEST_VIN');
  try {
    if (!payload || typeof payload!=='object' || JSON.stringify(payload).length>262144
        || payload.Count!==1 || !Array.isArray(payload.Results) || payload.Results.length!==1)
      return blocked('INVALID_RESPONSE');
    const row=payload.Results[0];
    if (!row || typeof row!=='object' || Array.isArray(row)) return blocked('INVALID_RESPONSE');
    rawResult=Object.freeze(JSON.parse(JSON.stringify(row)));
    if (typeof row.VIN!=='string' || !/^[A-Za-z0-9]{17}$/.test(row.VIN.trim())
        || row.VIN.trim().toUpperCase()!==validation.vin) return blocked('VIN_MISMATCH');
    decodeErrorCode=typeof row.ErrorCode==='string' ? row.ErrorCode.trim() : null;
    if (decodeErrorCode!=='0') return blocked('DECODE_STATUS_UNRESOLVED');
    if (row.SuggestedVIN!==null && row.SuggestedVIN!==undefined && typeof row.SuggestedVIN!=='string')
      return blocked('INVALID_RESPONSE');
    suggestedVin=typeof row.SuggestedVIN==='string' ? row.SuggestedVIN.trim() || null : null;
    if (suggestedVin) return blocked('SUGGESTED_VIN_REQUIRES_REVIEW');
    const make=text(row.Make),model=text(row.Model),bodyClass=text(row.BodyClass),yearText=text(row.ModelYear);
    const modelYear=yearText && /^[1-9]\d{3}$/.test(yearText) ? Number(yearText) : null;
    if (!make || !model || !bodyClass || modelYear===null) return blocked('INCOMPLETE_PROFILE');
    const profile=Object.freeze({vin:validation.vin,make,model,modelYear,bodyClass,...mass(row.CurbWeightLB)});
    return Object.freeze({status:'parsed',reason:null,scope:SCOPE,profile,rawResult,decodeErrorCode,suggestedVin,physicsReady:false,massBoundsConfigured:false});
  } catch {
    return blocked('INVALID_RESPONSE');
  }
}

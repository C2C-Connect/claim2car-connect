/** Bounded vPIC JSON transport only. Pass received payloads through parseVpicResponse.
 * No request at module import, no cached/fallback profile, and no camera activation.
 */
import {validateVin} from './vin.mjs';
class TransportFailure extends Error { constructor(reason){super(reason);this.reason=reason;} }
export async function fetchVpicPayload(input,options={}) {
  const validation=validateVin(input);
  let httpStatus=null;
  const fail=reason=>Object.freeze({status:'transport_error',reason,scope:'transport-only',vin:validation.ok?validation.vin:null,httpStatus,payload:null});
  if(!validation.ok)return fail('INVALID_VIN');
  if(!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(k=>!['fetchImpl','signal','timeoutMs','maxBytes'].includes(k)))return fail('INVALID_OPTIONS');
  const {fetchImpl=globalThis.fetch,signal,timeoutMs=10000,maxBytes=262144}=options;
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30000||!Number.isInteger(maxBytes)||maxBytes<1||maxBytes>1048576)return fail('INVALID_OPTIONS');
  if(typeof fetchImpl!=='function')return fail('FETCH_UNAVAILABLE');
  if(signal&&(typeof signal.aborted!=='boolean'||typeof signal.addEventListener!=='function'||typeof signal.removeEventListener!=='function'))return fail('INVALID_OPTIONS');
  if(signal?.aborted)return fail('CANCELLED');
  const controller=new AbortController();
  const url='https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/'+encodeURIComponent(validation.vin)+'?format=json';
  let stopReason=null,rejectStop,reader=null;
  const stopped=new Promise((_,reject)=>{rejectStop=reject;});
  const stop=reason=>{if(!stopReason){stopReason=reason;controller.abort();rejectStop(new TransportFailure(reason));}};
  const guard=()=>{if(stopReason)throw new TransportFailure(stopReason);};
  const cancel=()=>stop('CANCELLED');
  signal?.addEventListener('abort',cancel,{once:true});
  if(signal?.aborted)cancel();
  const timer=setTimeout(()=>stop('TIMEOUT'),timeoutMs);
  async function receive(){
    guard();
    const response=await fetchImpl(url,{method:'GET',headers:{Accept:'application/json'},credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',mode:'cors',signal:controller.signal});
    guard();
    if(!response||typeof response.status!=='number'||!response.headers||typeof response.headers.get!=='function')throw new TransportFailure('INVALID_RESPONSE');
    httpStatus=response.status;
    if(response.redirected||response.url!==url)throw new TransportFailure('UNEXPECTED_RESPONSE_ORIGIN');
    if(response.status===429)throw new TransportFailure('HTTP_RATE_LIMITED');
    if(response.status<200||response.status>=300)throw new TransportFailure('HTTP_ERROR');
    const type=response.headers.get('content-type')?.split(';')[0].trim().toLowerCase();
    if(type!=='application/json')throw new TransportFailure('INVALID_CONTENT_TYPE');
    const length=response.headers.get('content-length');
    if(length!==null&&(!/^\d+$/.test(length)||!Number.isSafeInteger(Number(length))))throw new TransportFailure('INVALID_RESPONSE');
    if(length!==null&&Number(length)>maxBytes)throw new TransportFailure('RESPONSE_TOO_LARGE');
    if(!response.body||typeof response.body.getReader!=='function')throw new TransportFailure('RESPONSE_BODY_UNAVAILABLE');
    reader=response.body.getReader();
    const decoder=new TextDecoder('utf-8',{fatal:true});
    let size=0,text='';
    while(true){
      const chunk=await reader.read();guard();
      if(chunk.done)break;
      if(!(chunk.value instanceof Uint8Array))throw new TransportFailure('INVALID_RESPONSE');
      size+=chunk.value.byteLength;
      if(size>maxBytes)throw new TransportFailure('RESPONSE_TOO_LARGE');
      try{text+=decoder.decode(chunk.value,{stream:true});}catch{throw new TransportFailure('INVALID_RESPONSE_ENCODING');}
    }
    try{text+=decoder.decode();}catch{throw new TransportFailure('INVALID_RESPONSE_ENCODING');}
    guard();
    let payload;
    try{payload=JSON.parse(text);}catch{throw new TransportFailure('INVALID_JSON');}
    return Object.freeze({status:'response_received',reason:null,scope:'transport-only',vin:validation.vin,httpStatus,payload});
  }
  try{return await Promise.race([receive(),stopped]);}
  catch(error){return fail(stopReason??(error instanceof TransportFailure?error.reason:'NETWORK_ERROR'));}
  finally{
    clearTimeout(timer);signal?.removeEventListener('abort',cancel);controller.abort();
    if(reader){try{void reader.cancel().catch(()=>{});reader.releaseLock();}catch{}}
  }
}

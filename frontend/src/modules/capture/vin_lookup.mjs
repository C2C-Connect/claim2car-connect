/** Explicit-call VIN -> bounded transport -> parser composition.
 * No import-time request, persistence, camera access, or physics eligibility claim.
 * Pass controller AbortSignal through options.signal. Never expose raw service rows.
 */
import {validateVin} from './vin.mjs';
import {fetchVpicPayload} from './vpic_transport.mjs';
import {parseVpicResponse} from './vpic.mjs';
export async function lookupVin(input,options={}) {
  const result=(status,reason,profile=null)=>Object.freeze({status,reason,profile,physicsReady:false,massBoundsConfigured:false});
  const validation=validateVin(input);
  if(!validation.ok)return result('blocked',validation.reason);
  const received=await fetchVpicPayload(validation.vin,options);
  if(received.status!=='response_received')return result('transport_error',received.reason);
  if(options.signal?.aborted)return result('transport_error','CANCELLED');
  const parsed=parseVpicResponse(validation.vin,received.payload);
  return result(parsed.status,parsed.reason,parsed.profile);
}

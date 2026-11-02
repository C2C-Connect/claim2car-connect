/** Controller over the real VIN lookup adapter. No import-time request or camera access.
 * subscribe receives future states; getState reads the initial state.
 * Invalidated submit promises resolve as superseded; current state distinguishes cancel/reset/dispose.
 */
import {lookupVin} from './vin_lookup.mjs';
export function createVinLookupController(options={}) {
  if(!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(k=>!['fetchImpl','timeoutMs','maxBytes'].includes(k)))throw new TypeError('INVALID_OPTIONS');
  const config=Object.freeze({...options}),listeners=new Set();
  const state=(status,reason=null)=>Object.freeze({status,reason,profile:null,physicsReady:false,massBoundsConfigured:false});
  let current=state('idle'),generation=0,active=null,disposed=false;
  function publish(next){
    current=next;
    for(const listener of [...listeners]){
      if(current!==next)break;
      try{listener(next);}catch{}
    }
  }
  function invalidate(){
    const id=++generation,previous=active;
    active=null;
    previous?.resolve(state('superseded','SUPERSEDED'));
    previous?.controller.abort();
    return id;
  }
  function submit(input){
    if(disposed)return Promise.resolve(state('disposed','DISPOSED'));
    const id=invalidate();
    if(disposed||id!==generation)return Promise.resolve(state('superseded','SUPERSEDED'));
    const controller=new AbortController();
    let resolve;
    const promise=new Promise(done=>{resolve=done;});
    active={controller,resolve};
    publish(state('loading'));
    if(disposed||id!==generation)return promise;
    Promise.resolve().then(()=>{
      if(disposed||id!==generation)return null;
      return lookupVin(input,{...config,signal:controller.signal});
    }).then(result=>{
      if(disposed||id!==generation)return;
      active=null;resolve(result);publish(result);
    },()=>{
      if(disposed||id!==generation)return;
      const next=state('transport_error','LOOKUP_FAILED');
      active=null;resolve(next);publish(next);
    });
    return promise;
  }
  function cancel(){if(!disposed){const id=invalidate();if(!disposed&&id===generation)publish(state('cancelled','CANCELLED'));}}
  function reset(){if(!disposed){const id=invalidate();if(!disposed&&id===generation)publish(state('idle'));}}
  function dispose(){if(!disposed){disposed=true;invalidate();publish(state('disposed','DISPOSED'));listeners.clear();}}
  function subscribe(listener){
    if(typeof listener!=='function')throw new TypeError('LISTENER_REQUIRED');
    if(disposed)return ()=>{};
    listeners.add(listener);return ()=>listeners.delete(listener);
  }
  return Object.freeze({getState:()=>current,submit,cancel,reset,dispose,subscribe});
}

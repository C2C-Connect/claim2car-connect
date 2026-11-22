import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { createOfflineEvidenceQueue } from "../app/offline_evidence_queue.mjs";

const appSource=await readFile(new URL("../app/app.mjs",import.meta.url),"utf8");
const queueSource=await readFile(new URL("../app/offline_evidence_queue.mjs",import.meta.url),"utf8");
const appHtml=await readFile(new URL("../app/index.html",import.meta.url),"utf8");
assert.ok(appSource.includes("createOfflineEvidenceQueue"));
assert.ok(appSource.includes("queueFile({sessionId:state.sessionId,tenantId:state.tenantId,actorId:state.actorId,slot,file,keyMaterial:state.token})"));
const syncAt=appSource.indexOf("syncSession({");
assert.ok(syncAt>=0&&appSource.slice(syncAt,syncAt+200).includes("keyMaterial:state.token"));
assert.ok(appSource.includes("window.addEventListener(\"online\""));
assert.ok(appSource.includes('api("/v1/identity",token)'));
assert.ok(queueSource.includes("subtle.encrypt"));
assert.ok(queueSource.includes("subtle.decrypt"));
assert.ok(queueSource.includes("HKDF"));
assert.ok(queueSource.includes("claim2car-integrated-evidence"));
assert.ok(appHtml.includes('id="offline-queue-status"'));
assert.ok(appHtml.includes('id="sync-queued-evidence"'));
assert.ok(appHtml.includes("AES-GCM encrypted"));

class MemoryStore {
  constructor(){this.records=[];this.nextId=1;}
  async enqueue(record){const stored={...record,queueId:this.nextId++};this.records.push(stored);return {...stored};}
  async list(sessionId,{tenantId,actorId,includeBytes=true}={}){
    const rows=this.records.filter(r=>r.sessionId===sessionId&&r.tenantId===tenantId&&r.actorId===actorId).sort((a,b)=>a.queueId-b.queueId);
    return rows.map(r=>{if(includeBytes)return {...r};const {bytes,...meta}=r;return meta;});
  }
  async markUploaded(queueId,syncedAt){
    const record=this.records.find(r=>r.queueId===queueId);if(!record)throw new Error("NOT_FOUND");
    record.uploaded=true;record.syncedAt=syncedAt;delete record.bytes;return {...record};
  }
  async deleteSession(sessionId,{tenantId}={}){
    const before=this.records.length;this.records=this.records.filter(r=>!(r.sessionId===sessionId&&r.tenantId===tenantId));return before-this.records.length;
  }
}
const store=new MemoryStore(),ids=["artifact-1","request-1","artifact-2","request-2"];
const queue=createOfflineEvidenceQueue({store,cryptoProvider:webcrypto,makeUuid:()=>ids.shift(),now:()=>"2026-11-22T00:00:00.000Z"});
const scope={sessionId:"session-a",tenantId:"tenant-a",actorId:"operator-a"};
const tokenMaterial="operator-token-material-for-offline-recovery-0123456789";
const file=(text,type="image/jpeg")=>({type,size:Buffer.byteLength(text),arrayBuffer:async()=>Buffer.from(text)});
const first=await queue.queueFile({...scope,slot:"00_front_exterior",file:file("original-one"),keyMaterial:tokenMaterial});
const second=await queue.queueFile({...scope,slot:"01_front_right_exterior",file:file("original-two","image/png"),keyMaterial:tokenMaterial});
assert.equal(first.artifactId,"artifact-1");assert.equal(first.requestId,"request-1");
assert.equal(second.artifactId,"artifact-2");assert.equal(second.requestId,"request-2");
assert.equal(first.mimeType,"image/jpeg");assert.equal(second.mimeType,"image/png");
assert.equal(first.bytes instanceof Uint8Array,true);
assert.notEqual(Buffer.from(first.bytes).toString(),"original-one");
assert.equal(first.encryptionAlgorithm,"AES-GCM");
assert.equal(first.bytes.byteLength,first.byteLength+16);
let snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.deepEqual({total:snapshot.total,pending:snapshot.pending,uploaded:snapshot.uploaded},{total:2,pending:2,uploaded:0});
const wrongKey=await queue.syncSession({...scope,keyMaterial:"wrong-key-material-not-the-original-token-12345",upload:async()=>{throw new Error("should-not-upload");}});
assert.equal(wrongKey.uploaded,0);assert.ok(wrongKey.error);
snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.equal(snapshot.pending,2);
const failed=await queue.syncSession({...scope,keyMaterial:tokenMaterial,upload:async(record)=>{assert.equal(record.queueId,first.queueId);throw new Error("NETWORK_INTERRUPTED");}});
assert.equal(failed.uploaded,0);assert.equal(failed.blockedAtQueueId,first.queueId);assert.equal(failed.error,"NETWORK_INTERRUPTED");
snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.equal(snapshot.pending,2);assert.equal(store.records.every(r=>r.bytes instanceof Uint8Array),true);
const attempted=[];
const retry=await queue.syncSession({...scope,keyMaterial:tokenMaterial,upload:async(record)=>{attempted.push({queueId:record.queueId,artifactId:record.artifactId,requestId:record.requestId,bytes:Buffer.from(record.bytes).toString()});return {ok:true};}});
assert.equal(retry.uploaded,2);assert.equal(retry.error,null);
assert.deepEqual(attempted.map(x=>x.queueId),[first.queueId,second.queueId]);
assert.deepEqual(attempted.map(x=>x.artifactId),["artifact-1","artifact-2"]);
assert.deepEqual(attempted.map(x=>x.requestId),["request-1","request-2"]);
assert.deepEqual(attempted.map(x=>x.bytes),["original-one","original-two"]);
snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.equal(snapshot.pending,0);assert.equal(snapshot.uploaded,2);
assert.equal(store.records.every(r=>!("bytes" in r)),true);
const other=await queue.status(scope.sessionId,{tenantId:"tenant-a",actorId:"different-actor"});
assert.equal(other.total,0);
await assert.rejects(queue.status(scope.sessionId,{tenantId:"tenant-a"}),/IDENTITY_SCOPE_REQUIRED/);
process.stdout.write(JSON.stringify({outcome:"passed",checks:["AES-GCM encryption at rest","token-derived key recovery","wrong-key fails closed without deleting queued originals","tenant/actor/session scoping","FIFO stop on upload failure","stable artifact/request IDs across retry","MIME metadata","remove ciphertext after server acceptance","isolated IndexedDB database","identity-scope validation"]},null,2)+"\n");

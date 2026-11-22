import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { createOfflineEvidenceQueue } from "../app/offline_evidence_queue.mjs";

const appSource=await readFile(new URL("../app/app.mjs",import.meta.url),"utf8");
const appHtml=await readFile(new URL("../app/index.html",import.meta.url),"utf8");
assert.match(appSource,/createOfflineEvidenceQueue/);
assert.match(appSource,/queueFile\(\{sessionId:state\.sessionId,tenantId:state\.tenantId,actorId:state\.actorId,slot,file\}\)/);
assert.match(appSource,/syncQueuedEvidence/);
assert.match(appSource,/window\.addEventListener\("online"/);
assert.match(appSource,/!state\.tenantId\|\|!state\.actorId/);
assert.match(appSource,/api\("\/v1\/identity",token\)/);
assert.match(appHtml,/id="offline-queue-status"/);
assert.match(appHtml,/id="sync-queued-evidence"/);
assert.match(appHtml,/not encrypted vault storage/i);
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
  async deleteSession(sessionId,{tenantId}={}){const before=this.records.length;this.records=this.records.filter(r=>!(r.sessionId===sessionId&&r.tenantId===tenantId));return before-this.records.length;}
}
const store=new MemoryStore(),ids=["artifact-1","request-1","artifact-2","request-2"];
const queue=createOfflineEvidenceQueue({store,cryptoProvider:webcrypto,makeUuid:()=>ids.shift(),now:()=>"2026-11-22T00:00:00.000Z"});
const scope={sessionId:"session-a",tenantId:"tenant-a",actorId:"operator-a"};
const file=(text,type="image/jpeg")=>({type,size:Buffer.byteLength(text),arrayBuffer:async()=>Buffer.from(text)});
const first=await queue.queueFile({...scope,slot:"00_front_exterior",file:file("original-one")});
const second=await queue.queueFile({...scope,slot:"01_front_right_exterior",file:file("original-two","image/png")});
assert.equal(first.artifactId,"artifact-1");assert.equal(first.requestId,"request-1");
assert.equal(second.artifactId,"artifact-2");assert.equal(second.requestId,"request-2");
assert.equal(first.mimeType,"image/jpeg");assert.equal(second.mimeType,"image/png");
assert.equal(first.bytes instanceof Uint8Array,true);
let snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.deepEqual({total:snapshot.total,pending:snapshot.pending,uploaded:snapshot.uploaded},{total:2,pending:2,uploaded:0});
const failed=await queue.syncSession({...scope,upload:async(record)=>{assert.equal(record.queueId,first.queueId);throw new Error("NETWORK_INTERRUPTED");}});
assert.equal(failed.uploaded,0);assert.equal(failed.blockedAtQueueId,first.queueId);assert.equal(failed.error,"NETWORK_INTERRUPTED");
snapshot=await queue.status(scope.sessionId,{tenantId:scope.tenantId,actorId:scope.actorId});
assert.equal(snapshot.pending,2);assert.equal(store.records.every(r=>r.bytes instanceof Uint8Array),true);
const attempted=[];
const retry=await queue.syncSession({...scope,upload:async(record)=>{attempted.push({queueId:record.queueId,artifactId:record.artifactId,requestId:record.requestId,bytes:Buffer.from(record.bytes).toString()});return {ok:true};}});
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
process.stdout.write(JSON.stringify({outcome:"passed",checks:["queue original bytes before network","scope by tenant/actor/session","FIFO fail-stop on first upload failure","retry preserves artifact/request IDs","queued MIME metadata","discard local bytes after confirmed upload","identity-scope validation"]},null,2)+"\n");

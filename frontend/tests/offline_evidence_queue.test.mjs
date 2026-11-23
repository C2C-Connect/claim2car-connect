// Browser-persistent original evidence queue assertions.
// Uses an injected store and WebCrypto; no network or real participant data.
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import {
  createIndexedDbEvidenceStore,
  createOfflineEvidenceQueue,
} from "../../app/web/assets/offline_evidence_queue.mjs";

const outcomes = [];
function test(id, action) {
  return Promise.resolve().then(action).then(
    () => outcomes.push({ id, outcome: "passed" }),
    (error) => outcomes.push({ id, outcome: "failed", error_type: error.name, message: error.message }),
  );
}
function makeStore() {
  const records = [];
  let nextId = 1;
  return {
    records,
    async enqueue(record) {
      const stored = { ...record, queueId: nextId++ };
      records.push(stored);
      return stored;
    },
    async updateRecord(queueId,replacement){const record=records.find(item=>item.queueId===queueId);if(!record)throw new Error('EVIDENCE_QUEUE_RECORD_NOT_FOUND');Object.assign(record,replacement,{queueId});return record;},
    async list(sessionId, { tenantId, actorId, includeBytes = true } = {}) {
      const matching = records.filter((record) => record.sessionId === sessionId
        && record.tenantId === tenantId && record.actorId === actorId)
        .sort((a, b) => a.queueId - b.queueId);
      return includeBytes ? matching : matching.map(({ bytes, ...metadata }) => metadata);
    },
    async markUploaded(queueId, syncedAt) {
      const record = records.find((item) => item.queueId === queueId);
      if (!record) throw new Error("EVIDENCE_QUEUE_RECORD_NOT_FOUND");
      record.uploaded = true;
      record.syncedAt = syncedAt;
      delete record.bytes;
      return record;
    },
    async deleteSession(sessionId, { tenantId } = {}) {
      const before = records.length;
      for (let index = records.length - 1; index >= 0; index -= 1) {
        if (records[index].sessionId === sessionId && records[index].tenantId === tenantId) {
          records.splice(index, 1);
        }
      }
      return before - records.length;
    },
  };
}
const keyMaterial='operator-token-material-for-offline-recovery-0123456789';
function makeFile(text,type='image/jpeg') {
  const bytes = new TextEncoder().encode(text);
  return { type, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
}
function makeQueue(store, ids = ["artifact-1", "request-1", "artifact-2", "request-2"]) {
  let index = 0;
  return createOfflineEvidenceQueue({
    store,
    cryptoProvider: webcrypto,
    makeUuid: () => ids[index++],
    now: () => "2026-11-10T12:00:00.000Z",
  });
}

await test("canonical_queue_encrypts_originals_and_requires_same_token", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  const item = await queue.queueFile({ sessionId: "session-a", tenantId: "tenant-a", actorId: "actor-a", slot: "front", file: makeFile("original-image"), keyMaterial });
  assert.equal(item.uploaded, false);
  assert.equal(item.byteLength, 14);
  assert.equal(item.bytes instanceof Uint8Array, true);
  assert.equal(item.encryptionAlgorithm,"AES-GCM-HKDF-SHA256-v2");
  assert.notEqual(new TextDecoder().decode(item.bytes),"original-image");
  assert.equal(item.bytes.byteLength,item.byteLength+16);
  assert.equal(item.sha256, "27f0c6997c0fc4780eb0d9a0e8a1f5f02418196494e213a91911b54bea2816cb");
  const wrongKey=await queue.syncSession({sessionId:"session-a",tenantId:"tenant-a",actorId:"actor-a",keyMaterial:"wrong-key-material-not-original-token-1234567890",
    upload:async()=>{throw new Error("SHOULD_NOT_UPLOAD");}});
  assert.equal(wrongKey.error,"EVIDENCE_DECRYPTION_FAILED");
  assert.equal(wrongKey.uploaded,0);
  const status = await queue.status("session-a",{tenantId:"tenant-a",actorId:"actor-a"});
  assert.equal(status.pending, 1);
  assert.equal(status.records[0].encryptionAlgorithm,"AES-GCM-HKDF-SHA256-v2");
  assert.equal("bytes" in status.records[0], false);
});

await test("fifo_sync_stops_at_first_failure_and_retry_reuses_ids", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  await queue.queueFile({ sessionId: "session-a", tenantId: "tenant-a", actorId: "actor-a", slot: "front", file: makeFile("first"), keyMaterial });
  await queue.queueFile({ sessionId: "session-a", tenantId: "tenant-a", actorId: "actor-a", slot: "rear", file: makeFile("second"), keyMaterial });
  const attempted = [];
  const first = await queue.syncSession({
    sessionId: "session-a", tenantId:"tenant-a", actorId:"actor-a", keyMaterial,
    upload: async (record) => {
      attempted.push(record.artifactId);
      throw new Error("NETWORK_UNAVAILABLE");
    },
  });
  assert.equal(first.uploaded, 0);
  assert.equal(first.error, "NETWORK_UNAVAILABLE");
  assert.deepEqual(attempted, ["artifact-1"]);
  assert.equal((await queue.status("session-a",{tenantId:"tenant-a",actorId:"actor-a"})).pending, 2);

  const retryIds = [];
  const second = await queue.syncSession({
    sessionId: "session-a", tenantId:"tenant-a", actorId:"actor-a", keyMaterial,
    upload: async (record) => { retryIds.push([record.artifactId, record.requestId]); return { ok: true }; },
  });
  assert.deepEqual(retryIds, [["artifact-1", "request-1"], ["artifact-2", "request-2"]]);
  assert.equal(second.uploaded, 2);
  assert.equal(second.blockedAtQueueId, null);
  const status = await queue.status("session-a",{tenantId:"tenant-a",actorId:"actor-a"});
  assert.equal(status.uploaded, 2);
  assert.equal(status.pending, 0);
  assert.equal("bytes" in status.records[0], false);
});

await test("session_queues_are_isolated", async () => {
  const store = makeStore();
  const queue = makeQueue(store, ["artifact-a", "request-a", "artifact-b", "request-b"]);
  await queue.queueFile({ sessionId: "session-a", tenantId: "tenant-a", actorId: "actor-a", slot: "front", file: makeFile("a"), keyMaterial });
  await queue.queueFile({ sessionId: "session-b", tenantId: "tenant-a", actorId: "actor-a", slot: "front", file: makeFile("b"), keyMaterial });
  const uploaded = [];
  const result = await queue.syncSession({
    sessionId: "session-b", tenantId:"tenant-a", actorId:"actor-a", keyMaterial,
    upload: async (record) => { uploaded.push(record.sessionId); return { ok: true }; },
  });
  assert.equal(result.uploaded, 1);
  assert.deepEqual(uploaded, ["session-b"]);
  assert.equal((await queue.status("session-a",{tenantId:"tenant-a",actorId:"actor-a"})).pending, 1);
});

await test("tenant_and_actor_scopes_isolate_same_session", async () => {
  const store = makeStore();
  const queue = makeQueue(store, ["artifact-owner-a", "request-owner-a", "artifact-owner-b", "request-owner-b"]);
  await queue.queueFile({ sessionId:"shared-session", tenantId:"tenant-a", actorId:"actor-a", slot:"front", file:makeFile("actor-a"), keyMaterial });
  await queue.queueFile({ sessionId:"shared-session", tenantId:"tenant-a", actorId:"actor-b", slot:"front", file:makeFile("actor-b"), keyMaterial });
  assert.equal((await queue.status("shared-session",{tenantId:"tenant-a",actorId:"actor-a"})).total, 1);
  assert.equal((await queue.status("shared-session",{tenantId:"tenant-a",actorId:"actor-b"})).total, 1);
  assert.equal((await queue.status("shared-session",{tenantId:"tenant-b",actorId:"actor-a"})).total, 0);
  const removed = await queue.deleteSession("shared-session",{tenantId:"tenant-a"});
  assert.equal(removed, 2);
});

await test("consent_withdrawal_purges_local_originals", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  await queue.queueFile({ sessionId: "session-a", tenantId: "tenant-a", actorId: "actor-a", slot: "front", file: makeFile("pending-original"), keyMaterial });
  const removed = await queue.deleteSession("session-a",{tenantId:"tenant-a"});
  assert.equal(removed, 1);
  assert.equal((await queue.status("session-a",{tenantId:"tenant-a",actorId:"actor-a"})).total, 0);
});


await test("aad_metadata_tampering_fails_closed_before_upload", async () => {
  const store=makeStore(),queue=makeQueue(store);
  const queued=await queue.queueFile({sessionId:"session-tamper",tenantId:"tenant-a",actorId:"actor-a",slot:"front",file:makeFile("protected-original"),keyMaterial});
  store.records[0].slot="rear";
  let attempted=false;
  const result=await queue.syncSession({sessionId:"session-tamper",tenantId:"tenant-a",actorId:"actor-a",keyMaterial,
    upload:async()=>{attempted=true;return {ok:true};}});
  assert.equal(result.error,"EVIDENCE_DECRYPTION_FAILED");
  assert.equal(attempted,false);
  assert.equal(store.records[0].queueId,queued.queueId);
});
await test("prior_aes_gcm_queue_record_upgrades_to_aad_format_before_upload", async () => {
  const store=makeStore(),queue=makeQueue(store);
  const bytes=new TextEncoder().encode("prior-encrypted-original");
  const digest=Array.from(new Uint8Array(await webcrypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
  const salt=webcrypto.getRandomValues(new Uint8Array(16)),iv=webcrypto.getRandomValues(new Uint8Array(12));
  const imported=await webcrypto.subtle.importKey("raw",new TextEncoder().encode(keyMaterial),"HKDF",false,["deriveKey"]);
  const oldKey=await webcrypto.subtle.deriveKey({name:"HKDF",hash:"SHA-256",salt,info:new TextEncoder().encode("Claim2Car offline evidence queue v1")},imported,{name:"AES-GCM",length:256},false,["encrypt","decrypt"]);
  const ciphertext=new Uint8Array(await webcrypto.subtle.encrypt({name:"AES-GCM",iv},oldKey,bytes));
  await store.enqueue({sessionId:"session-v1",tenantId:"tenant-a",actorId:"actor-a",slot:"front",artifactId:"v1-artifact",requestId:"v1-request",
    sha256:digest,byteLength:bytes.byteLength,mimeType:"image/jpeg",queuedAt:"2026-11-10T00:00:00.000Z",uploaded:false,
    encryptionAlgorithm:"AES-GCM",salt,iv,bytes:ciphertext});
  const result=await queue.syncSession({sessionId:"session-v1",tenantId:"tenant-a",actorId:"actor-a",keyMaterial,
    upload:async record=>{assert.equal(new TextDecoder().decode(record.bytes),"prior-encrypted-original");return {ok:true};}});
  assert.equal(result.error,null);
  assert.equal(result.uploaded,1);
  assert.equal(store.records[0].encryptionAlgorithm,"AES-GCM-HKDF-SHA256-v2");
  assert.equal(store.records[0].uploaded,true);
  assert.equal("bytes" in store.records[0],false);
});
\nawait test("legacy_plaintext_queue_record_is_integrity_checked_and_migrated_before_upload", async () => {
  const store=makeStore(),queue=makeQueue(store,["legacy-artifact","legacy-request"]);
  const bytes=new TextEncoder().encode("legacy-original");
  const legacy=await store.enqueue({sessionId:"session-legacy",tenantId:"tenant-a",actorId:"actor-a",slot:"front",
    artifactId:"legacy-artifact-id",requestId:"legacy-request-id",sha256:"",byteLength:bytes.byteLength,queuedAt:"2026-11-10T00:00:00.000Z",uploaded:false,bytes});
  legacy.sha256=Array.from(new Uint8Array(await webcrypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
  const uploaded=[];
  const result=await queue.syncSession({sessionId:"session-legacy",tenantId:"tenant-a",actorId:"actor-a",keyMaterial,
    upload:async record=>{uploaded.push(new TextDecoder().decode(record.bytes));return {ok:true};}});
  assert.equal(result.error,null);
  assert.equal(result.uploaded,1);
  assert.deepEqual(uploaded,["legacy-original"]);
  const stored=store.records[0];
  assert.equal(stored.encryptionAlgorithm,"AES-GCM-HKDF-SHA256-v2");
  assert.notEqual(new TextDecoder().decode(stored.bytes),"legacy-original");
  assert.equal(stored.uploaded,true);
  assert.equal("bytes" in stored,false);
});

await test("legacy_plaintext_with_bad_digest_is_not_uploaded_or_migrated", async () => {
  const store=makeStore(),queue=makeQueue(store);
  const bytes=new TextEncoder().encode("corrupted-legacy");
  await store.enqueue({sessionId:"session-bad",tenantId:"tenant-a",actorId:"actor-a",slot:"front",
    artifactId:"bad-artifact",requestId:"bad-request",sha256:"0".repeat(64),byteLength:bytes.byteLength,
    queuedAt:"2026-11-10T00:00:00.000Z",uploaded:false,bytes});
  let attempted=false;
  const result=await queue.syncSession({sessionId:"session-bad",tenantId:"tenant-a",actorId:"actor-a",keyMaterial,
    upload:async()=>{attempted=true;return {ok:true};}});
  assert.equal(result.error,"LOCAL_ORIGINAL_INTEGRITY_FAILED");
  assert.equal(attempted,false);
  assert.equal(store.records[0].encryptionAlgorithm,undefined);
  assert.equal(store.records[0].bytes instanceof Uint8Array,true);
});
await test("missing_indexeddb_fails_closed", async () => {
  assert.throws(() => createIndexedDbEvidenceStore(null), /INDEXEDDB_UNAVAILABLE/);
});

await test("invalid_store_rejected", async () => {
  assert.throws(() => createOfflineEvidenceQueue({ store: {} }), /EVIDENCE_QUEUE_STORE_REQUIRED/);
});

process.stdout.write(JSON.stringify({ tests: outcomes.length, passed: outcomes.filter((x) => x.outcome === "passed").length, outcomes }, null, 2) + "\n");
if (outcomes.some((x) => x.outcome !== "passed")) process.exitCode = 1;

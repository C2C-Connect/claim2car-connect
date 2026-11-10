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
    async list(sessionId, { includeBytes = true } = {}) {
      const matching = records.filter((record) => record.sessionId === sessionId)
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
    async deleteSession(sessionId) {
      const before = records.length;
      for (let index = records.length - 1; index >= 0; index -= 1) {
        if (records[index].sessionId === sessionId) records.splice(index, 1);
      }
      return before - records.length;
    },
  };
}
function makeFile(text) {
  const bytes = new TextEncoder().encode(text);
  return { arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
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

await test("queue_persists_original_bytes_and_server_digest", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  const item = await queue.queueFile({ sessionId: "session-a", slot: "front", file: makeFile("original-image") });
  assert.equal(item.uploaded, false);
  assert.equal(item.byteLength, 14);
  assert.equal(item.bytes instanceof Uint8Array, true);
  assert.equal(item.sha256, "27f0c6997c0fc4780eb0d9a0e8a1f5f02418196494e213a91911b54bea2816cb");
  const status = await queue.status("session-a");
  assert.equal(status.pending, 1);
  assert.equal("bytes" in status.records[0], false);
});

await test("fifo_sync_stops_at_first_failure_and_retry_reuses_ids", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  await queue.queueFile({ sessionId: "session-a", slot: "front", file: makeFile("first") });
  await queue.queueFile({ sessionId: "session-a", slot: "rear", file: makeFile("second") });
  const attempted = [];
  const first = await queue.syncSession({
    sessionId: "session-a",
    upload: async (record) => {
      attempted.push(record.artifactId);
      throw new Error("NETWORK_UNAVAILABLE");
    },
  });
  assert.equal(first.uploaded, 0);
  assert.equal(first.error, "NETWORK_UNAVAILABLE");
  assert.deepEqual(attempted, ["artifact-1"]);
  assert.equal((await queue.status("session-a")).pending, 2);

  const retryIds = [];
  const second = await queue.syncSession({
    sessionId: "session-a",
    upload: async (record) => { retryIds.push([record.artifactId, record.requestId]); return { ok: true }; },
  });
  assert.deepEqual(retryIds, [["artifact-1", "request-1"], ["artifact-2", "request-2"]]);
  assert.equal(second.uploaded, 2);
  assert.equal(second.blockedAtQueueId, null);
  const status = await queue.status("session-a");
  assert.equal(status.uploaded, 2);
  assert.equal(status.pending, 0);
  assert.equal("bytes" in status.records[0], false);
});

await test("session_queues_are_isolated", async () => {
  const store = makeStore();
  const queue = makeQueue(store, ["artifact-a", "request-a", "artifact-b", "request-b"]);
  await queue.queueFile({ sessionId: "session-a", slot: "front", file: makeFile("a") });
  await queue.queueFile({ sessionId: "session-b", slot: "front", file: makeFile("b") });
  const uploaded = [];
  const result = await queue.syncSession({
    sessionId: "session-b",
    upload: async (record) => { uploaded.push(record.sessionId); return { ok: true }; },
  });
  assert.equal(result.uploaded, 1);
  assert.deepEqual(uploaded, ["session-b"]);
  assert.equal((await queue.status("session-a")).pending, 1);
});

await test("consent_withdrawal_purges_local_originals", async () => {
  const store = makeStore();
  const queue = makeQueue(store);
  await queue.queueFile({ sessionId: "session-a", slot: "front", file: makeFile("pending-original") });
  const removed = await queue.deleteSession("session-a");
  assert.equal(removed, 1);
  assert.equal((await queue.status("session-a")).total, 0);
});

await test("missing_indexeddb_fails_closed", async () => {
  assert.throws(() => createIndexedDbEvidenceStore(null), /INDEXEDDB_UNAVAILABLE/);
});

await test("invalid_store_rejected", async () => {
  assert.throws(() => createOfflineEvidenceQueue({ store: {} }), /EVIDENCE_QUEUE_STORE_REQUIRED/);
});

process.stdout.write(JSON.stringify({ tests: outcomes.length, passed: outcomes.filter((x) => x.outcome === "passed").length, outcomes }, null, 2) + "\n");
if (outcomes.some((x) => x.outcome !== "passed")) process.exitCode = 1;

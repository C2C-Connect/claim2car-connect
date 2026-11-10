/**
 * Browser-persistent original-evidence queue for the integrated field shell.
 *
 * Stores original bytes in IndexedDB before attempting network transfer.
 * Uploads are serial per session (oldest first) and stop at the first failure.
 * Request/artifact IDs remain stable across retries so the server can apply
 * its existing idempotency contract. This is a browser recovery aid, not a
 * WORM store, encrypted vault, or field-qualified device-storage guarantee.
 */
const DATABASE_NAME = "claim2car-evidence";
const DATABASE_VERSION = 1;
const STORE_NAME = "originals";
const MAX_ORIGINAL_BYTES = 25 * 1024 * 1024;

function requestValue(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("INDEXEDDB_REQUEST_FAILED"));
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error || new Error("INDEXEDDB_TRANSACTION_ABORTED"));
    transaction.onerror = () => reject(transaction.error || new Error("INDEXEDDB_TRANSACTION_FAILED"));
  });
}

export function createIndexedDbEvidenceStore(indexedDb = globalThis.indexedDB) {
  if (!indexedDb || typeof indexedDb.open !== "function") {
    throw new Error("INDEXEDDB_UNAVAILABLE");
  }
  let databasePromise;

  function database() {
    if (!databasePromise) {
      databasePromise = new Promise((resolve, reject) => {
        const request = indexedDb.open(DATABASE_NAME, DATABASE_VERSION);
        request.onupgradeneeded = () => {
          const db = request.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: "queueId", autoIncrement: true });
            store.createIndex("by_session", "sessionId", { unique: false });
          }
        };
        request.onsuccess = () => {
          const db = request.result;
          db.onversionchange = () => db.close();
          resolve(db);
        };
        request.onerror = () => reject(request.error || new Error("INDEXEDDB_OPEN_FAILED"));
        request.onblocked = () => reject(new Error("INDEXEDDB_UPGRADE_BLOCKED"));
      }).catch((error) => {
        databasePromise = null;
        throw error;
      });
    }
    return databasePromise;
  }

  return Object.freeze({
    async enqueue(record) {
      const db = await database();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const done = transactionDone(tx);
        const request = tx.objectStore(STORE_NAME).add(record);
        let queueId;
        request.onsuccess = () => { queueId = request.result; };
        request.onerror = () => reject(request.error || new Error("EVIDENCE_QUEUE_WRITE_FAILED"));
        done.then(() => resolve({ ...record, queueId }), reject);
      });
    },

    async list(sessionId) {
      const db = await database();
      const tx = db.transaction(STORE_NAME, "readonly");
      const done = transactionDone(tx);
      const request = tx.objectStore(STORE_NAME).index("by_session").getAll(sessionId);
      const records = await requestValue(request);
      await done;
      return records.sort((a, b) => a.queueId - b.queueId);
    },

    async markUploaded(queueId, syncedAt) {
      const db = await database();
      const tx = db.transaction(STORE_NAME, "readwrite");
      const done = transactionDone(tx);
      const store = tx.objectStore(STORE_NAME);
      const record = await requestValue(store.get(queueId));
      if (!record) {
        tx.abort();
        throw new Error("EVIDENCE_QUEUE_RECORD_NOT_FOUND");
      }
      record.uploaded = true;
      record.syncedAt = syncedAt;
      delete record.bytes;
      store.put(record);
      await done;
      return record;
    },
  });
}

function toHex(buffer) {
  return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function createOfflineEvidenceQueue({
  store,
  cryptoProvider = globalThis.crypto,
  makeUuid = () => cryptoProvider.randomUUID(),
  now = () => new Date().toISOString(),
} = {}) {
  if (!store || typeof store.enqueue !== "function" || typeof store.list !== "function"
      || typeof store.markUploaded !== "function") {
    throw new Error("EVIDENCE_QUEUE_STORE_REQUIRED");
  }
  const activeSyncs = new Map();

  async function queueFile({ sessionId, slot, file }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof slot !== "string" || !slot.trim()
        || !file || typeof file.arrayBuffer !== "function") {
      throw new Error("INVALID_EVIDENCE_QUEUE_INPUT");
    }
    if (!cryptoProvider?.subtle || typeof makeUuid !== "function") {
      throw new Error("WEBCRYPTO_UNAVAILABLE");
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (!bytes.byteLength || bytes.byteLength > MAX_ORIGINAL_BYTES) {
      throw new Error("ORIGINAL_SIZE_OUT_OF_RANGE");
    }
    const digest = toHex(await cryptoProvider.subtle.digest("SHA-256", bytes));
    const record = {
      sessionId,
      slot,
      artifactId: makeUuid(),
      requestId: makeUuid(),
      sha256: digest,
      byteLength: bytes.byteLength,
      capturedAt: now(),
      uploaded: false,
      bytes,
    };
    return store.enqueue(record);
  }

  async function syncSession({ sessionId, upload }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof upload !== "function") {
      throw new Error("INVALID_EVIDENCE_SYNC_INPUT");
    }
    if (activeSyncs.has(sessionId)) return activeSyncs.get(sessionId);

    const task = (async () => {
      const records = (await store.list(sessionId)).filter((record) => !record.uploaded);
      let uploaded = 0;
      for (const record of records) {
        if (!(record.bytes instanceof Uint8Array) || record.bytes.byteLength !== record.byteLength) {
          return { uploaded, blockedAtQueueId: record.queueId, error: "LOCAL_ORIGINAL_UNAVAILABLE" };
        }
        try {
          const result = await upload(record);
          if (result === false || result?.ok === false) {
            throw new Error(result?.error || "EVIDENCE_UPLOAD_REJECTED");
          }
          await store.markUploaded(record.queueId, now());
          uploaded += 1;
        } catch (error) {
          return {
            uploaded,
            blockedAtQueueId: record.queueId,
            error: error instanceof Error ? error.message : "EVIDENCE_UPLOAD_FAILED",
          };
        }
      }
      return { uploaded, blockedAtQueueId: null, error: null };
    })();

    activeSyncs.set(sessionId, task);
    try {
      return await task;
    } finally {
      activeSyncs.delete(sessionId);
    }
  }

  async function status(sessionId) {
    const records = await store.list(sessionId);
    return {
      total: records.length,
      uploaded: records.filter((record) => record.uploaded).length,
      pending: records.filter((record) => !record.uploaded).length,
      records,
    };
  }

  return Object.freeze({ queueFile, syncSession, status });
}

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
const DATABASE_VERSION = 2;
const STORE_NAME = "originals";
const MAX_ORIGINAL_BYTES = 25 * 1024 * 1024;

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
          let store;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            store = db.createObjectStore(STORE_NAME, { keyPath: "queueId", autoIncrement: true });
          } else {
            store = request.transaction.objectStore(STORE_NAME);
          }
          if (!store.indexNames.contains("by_scope")) {
            store.createIndex("by_scope", ["tenantId", "actorId", "sessionId"], { unique: false });
          }
          if (!store.indexNames.contains("by_tenant_session")) {
            store.createIndex("by_tenant_session", ["tenantId", "sessionId"], { unique: false });
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

    async list(sessionId, { tenantId, actorId, includeBytes = true } = {}) {
      if (!tenantId || !actorId) throw new Error("EVIDENCE_QUEUE_IDENTITY_SCOPE_REQUIRED");
      const db = await database();
      const tx = db.transaction(STORE_NAME, "readonly");
      const done = transactionDone(tx);
      const request = tx.objectStore(STORE_NAME).index("by_scope").openCursor([tenantId, actorId, sessionId]);
      const records = [];
      request.onsuccess = () => {
        const cursor = request.result;
        if (!cursor) return;
        if (includeBytes) records.push(cursor.value);
        else {
          const { bytes, ...metadata } = cursor.value;
          records.push(metadata);
        }
        cursor.continue();
      };
      request.onerror = () => {}; // Transaction error/abort is propagated by transactionDone.
      await done;
      return records.sort((a, b) => a.queueId - b.queueId);
    },

    async markUploaded(queueId, syncedAt) {
      const db = await database();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        let updated = null;
        let missing = false;
        const request = store.get(queueId);
        request.onsuccess = () => {
          const record = request.result;
          if (!record) {
            missing = true;
            return;
          }
          record.uploaded = true;
          record.syncedAt = syncedAt;
          delete record.bytes;
          updated = record;
          store.put(record);
        };
        request.onerror = () => reject(request.error || new Error("EVIDENCE_QUEUE_READ_FAILED"));
        tx.oncomplete = () => {
          if (missing) reject(new Error("EVIDENCE_QUEUE_RECORD_NOT_FOUND"));
          else resolve(updated);
        };
        tx.onabort = () => reject(tx.error || new Error("INDEXEDDB_TRANSACTION_ABORTED"));
        tx.onerror = () => reject(tx.error || new Error("INDEXEDDB_TRANSACTION_FAILED"));
      });
    },

    async deleteSession(sessionId, { tenantId } = {}) {
      if (!tenantId) throw new Error("EVIDENCE_QUEUE_TENANT_SCOPE_REQUIRED");
      const db = await database();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        let deleted = 0;
        const request = store.index("by_tenant_session").getAllKeys([tenantId, sessionId]);
        request.onsuccess = () => {
          for (const key of request.result) {
            store.delete(key);
            deleted += 1;
          }
        };
        request.onerror = () => reject(request.error || new Error("EVIDENCE_QUEUE_READ_FAILED"));
        tx.oncomplete = () => resolve(deleted);
        tx.onabort = () => reject(tx.error || new Error("INDEXEDDB_TRANSACTION_ABORTED"));
        tx.onerror = () => reject(tx.error || new Error("INDEXEDDB_TRANSACTION_FAILED"));
      });
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
      || typeof store.markUploaded !== "function" || typeof store.deleteSession !== "function") {
    throw new Error("EVIDENCE_QUEUE_STORE_REQUIRED");
  }
  const activeSyncs = new Map();

  async function queueFile({ sessionId, tenantId, actorId, slot, file }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof tenantId !== "string" || !tenantId.trim()
        || typeof actorId !== "string" || !actorId.trim()
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
      tenantId,
      actorId,
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

  async function syncSession({ sessionId, tenantId, actorId, upload }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof tenantId !== "string" || !tenantId.trim()
        || typeof actorId !== "string" || !actorId.trim()
        || typeof upload !== "function") {
      throw new Error("INVALID_EVIDENCE_SYNC_INPUT");
    }
    const syncKey = `${tenantId}:${actorId}:${sessionId}`;
    if (activeSyncs.has(syncKey)) return activeSyncs.get(syncKey);

    const task = (async () => {
      const records = (await store.list(sessionId, {tenantId,actorId,includeBytes:true})).filter((record) => !record.uploaded);
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

    activeSyncs.set(syncKey, task);
    try {
      return await task;
    } finally {
      activeSyncs.delete(syncKey);
    }
  }

  async function deleteSession(sessionId, {tenantId} = {}) {
    if (typeof sessionId !== "string" || !sessionId.trim() || !tenantId) {
      throw new Error("INVALID_EVIDENCE_SESSION_ID");
    }
    return store.deleteSession(sessionId, {tenantId});
  }

  async function status(sessionId, {tenantId,actorId} = {}) {
    if (!tenantId || !actorId) throw new Error("EVIDENCE_QUEUE_IDENTITY_SCOPE_REQUIRED");
    const records = await store.list(sessionId, {tenantId,actorId,includeBytes:false});
    return {
      total: records.length,
      uploaded: records.filter((record) => record.uploaded).length,
      pending: records.filter((record) => !record.uploaded).length,
      records,
    };
  }

  return Object.freeze({ queueFile, syncSession, status, deleteSession });
}

/**
 * Browser-persistent original-evidence queue for the integrated field shell.
 *
 * Stores original bytes in IndexedDB before attempting network transfer.
 * Uploads are serial per session (oldest first) and stop at the first failure.
 * Request/artifact IDs remain stable across retries so the server can apply
 * its existing idempotency contract. This is a browser recovery aid, not a
 * WORM store, encrypted vault, or field-qualified device-storage guarantee.
 */
const DATABASE_NAME = "claim2car-integrated-evidence";
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

    async updateRecord(queueId, replacement) {
      const db = await database();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        let updated = null;
        let missing = false;
        const request = store.get(queueId);
        request.onsuccess = () => {
          if (!request.result) { missing = true; return; }
          updated = { ...replacement, queueId };
          store.put(updated);
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

const encoder = new TextEncoder();
function recordAad(record) {
  return encoder.encode(JSON.stringify({
    encryptionAlgorithm:record.encryptionAlgorithm,tenantId:record.tenantId,actorId:record.actorId,sessionId:record.sessionId,slot:record.slot,
    artifactId:record.artifactId,requestId:record.requestId,sha256:record.sha256,
    byteLength:record.byteLength,mimeType:record.mimeType,queuedAt:record.queuedAt,
  }));
}
async function deriveStorageKey(keyMaterial, salt, cryptoProvider) {
  const imported = await cryptoProvider.subtle.importKey("raw", encoder.encode(keyMaterial), "HKDF", false, ["deriveKey"]);
  return cryptoProvider.subtle.deriveKey({
    name:"HKDF",hash:"SHA-256",salt,info:encoder.encode("Claim2Car offline evidence queue v1")
  },imported,{name:"AES-GCM",length:256},false,["encrypt","decrypt"]);
}

export function createOfflineEvidenceQueue({
  store,
  cryptoProvider = globalThis.crypto,
  makeUuid = () => cryptoProvider.randomUUID(),
  now = () => new Date().toISOString(),
} = {}) {
  if (!store || typeof store.enqueue !== "function" || typeof store.list !== "function"
      || typeof store.markUploaded !== "function" || typeof store.deleteSession !== "function"
      || typeof store.updateRecord !== "function") {
    throw new Error("EVIDENCE_QUEUE_STORE_REQUIRED");
  }
  const activeSyncs = new Map();

  async function queueFile({ sessionId, tenantId, actorId, slot, file, keyMaterial }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof tenantId !== "string" || !tenantId.trim()
        || typeof actorId !== "string" || !actorId.trim()
        || typeof slot !== "string" || !slot.trim()
        || typeof keyMaterial !== "string" || keyMaterial.length < 43
        || !file || typeof file.arrayBuffer !== "function") {
      throw new Error("INVALID_EVIDENCE_QUEUE_INPUT");
    }
    if (!cryptoProvider?.subtle || typeof makeUuid !== "function" || typeof cryptoProvider.getRandomValues !== "function") {
      throw new Error("WEBCRYPTO_UNAVAILABLE");
    }
    const original = new Uint8Array(await file.arrayBuffer());
    if (!original.byteLength || original.byteLength > MAX_ORIGINAL_BYTES) {
      throw new Error("ORIGINAL_SIZE_OUT_OF_RANGE");
    }
    const digest = toHex(await cryptoProvider.subtle.digest("SHA-256", original));
    const salt = cryptoProvider.getRandomValues(new Uint8Array(16));
    const iv = cryptoProvider.getRandomValues(new Uint8Array(12));
    const record = {
      sessionId,tenantId,actorId,slot,
      artifactId:makeUuid(),requestId:makeUuid(),sha256:digest,
      byteLength:original.byteLength,
      mimeType:typeof file.type==="string"?file.type:"application/octet-stream",
      encryptionAlgorithm:"AES-GCM-HKDF-SHA256-v2",salt,iv,
      queuedAt:now(),uploaded:false,
    };
    const key = await deriveStorageKey(keyMaterial, salt, cryptoProvider);
    const encrypted = new Uint8Array(await cryptoProvider.subtle.encrypt({name:"AES-GCM",iv,additionalData:recordAad(record)},key,original));
    record.bytes=encrypted;
    return store.enqueue(record);
  }

  async function syncSession({ sessionId, tenantId, actorId, keyMaterial, upload }) {
    if (typeof sessionId !== "string" || !sessionId.trim()
        || typeof tenantId !== "string" || !tenantId.trim()
        || typeof actorId !== "string" || !actorId.trim()
        || typeof keyMaterial !== "string" || keyMaterial.length < 43
        || typeof upload !== "function") {
      throw new Error("INVALID_EVIDENCE_SYNC_INPUT");
    }
    if (!cryptoProvider?.subtle || typeof cryptoProvider.getRandomValues !== "function") {
      throw new Error("WEBCRYPTO_UNAVAILABLE");
    }
    const syncKey = JSON.stringify([tenantId,actorId,sessionId]);
    if (activeSyncs.has(syncKey)) return activeSyncs.get(syncKey);
    const task = (async () => {
      const records=(await store.list(sessionId,{tenantId,actorId,includeBytes:true})).filter(record=>!record.uploaded);
      let uploaded=0;
      for (let record of records) {
        try {
          let original;
          if (record.encryptionAlgorithm==="AES-GCM-HKDF-SHA256-v2" && record.iv && record.salt) {
            const key=await deriveStorageKey(keyMaterial,record.salt,cryptoProvider);
            try { original=new Uint8Array(await cryptoProvider.subtle.decrypt({name:"AES-GCM",iv:record.iv,additionalData:recordAad(record)},key,record.bytes)); }
            catch { return {uploaded,blockedAtQueueId:record.queueId,error:"EVIDENCE_DECRYPTION_FAILED"}; }
            if(original.byteLength!==record.byteLength||toHex(await cryptoProvider.subtle.digest("SHA-256",original))!==record.sha256)
              return {uploaded,blockedAtQueueId:record.queueId,error:"LOCAL_ORIGINAL_INTEGRITY_FAILED"};
          } else if (record.encryptionAlgorithm==="AES-GCM" && record.iv && record.salt) {
            // Upgrade ciphertext from the prior format, which did not bind metadata as AAD.
            const key=await deriveStorageKey(keyMaterial,record.salt,cryptoProvider);
            try { original=new Uint8Array(await cryptoProvider.subtle.decrypt({name:"AES-GCM",iv:record.iv},key,record.bytes)); }
            catch { return {uploaded,blockedAtQueueId:record.queueId,error:"EVIDENCE_DECRYPTION_FAILED"}; }
            if(original.byteLength!==record.byteLength||toHex(await cryptoProvider.subtle.digest("SHA-256",original))!==record.sha256)
              return {uploaded,blockedAtQueueId:record.queueId,error:"LOCAL_ORIGINAL_INTEGRITY_FAILED"};
            const salt=cryptoProvider.getRandomValues(new Uint8Array(16)),iv=cryptoProvider.getRandomValues(new Uint8Array(12));
            const migrated={...record,encryptionAlgorithm:"AES-GCM-HKDF-SHA256-v2",salt,iv};
            const newKey=await deriveStorageKey(keyMaterial,salt,cryptoProvider);
            migrated.bytes=new Uint8Array(await cryptoProvider.subtle.encrypt({name:"AES-GCM",iv,additionalData:recordAad(migrated)},newKey,original));
            await store.updateRecord(record.queueId,migrated);
            record=migrated;
          } else {
            // One-time migration for records written by the prior plaintext queue.
            if(!(record.bytes instanceof Uint8Array)||record.bytes.byteLength!==record.byteLength)
              return {uploaded,blockedAtQueueId:record.queueId,error:"LOCAL_ORIGINAL_UNAVAILABLE"};
            original=record.bytes;
            if(!record.sha256||toHex(await cryptoProvider.subtle.digest("SHA-256",original))!==record.sha256)
              return {uploaded,blockedAtQueueId:record.queueId,error:"LOCAL_ORIGINAL_INTEGRITY_FAILED"};
            const salt=cryptoProvider.getRandomValues(new Uint8Array(16)),iv=cryptoProvider.getRandomValues(new Uint8Array(12));
            const migrated={...record,encryptionAlgorithm:"AES-GCM-HKDF-SHA256-v2",salt,iv};
            const key=await deriveStorageKey(keyMaterial,salt,cryptoProvider);
            migrated.bytes=new Uint8Array(await cryptoProvider.subtle.encrypt({name:"AES-GCM",iv,additionalData:recordAad(migrated)},key,original));
            await store.updateRecord(record.queueId,migrated);
            record=migrated;
          }
          const result=await upload({...record,bytes:original});
          if(result===false||result?.ok===false)throw new Error(result?.error||"EVIDENCE_UPLOAD_REJECTED");
          await store.markUploaded(record.queueId,now());
          uploaded+=1;
        } catch(error) {
          return {uploaded,blockedAtQueueId:record.queueId,error:error instanceof Error&&error.message.trim()?error.message:"EVIDENCE_UPLOAD_FAILED"};
        }
      }
      return {uploaded,blockedAtQueueId:null,error:null};
    })();
    activeSyncs.set(syncKey,task);
    try{return await task;}finally{activeSyncs.delete(syncKey);}
  }

  async function deleteSession(sessionId,{tenantId}={}) {
    if(typeof sessionId!=="string"||!sessionId.trim()||!tenantId)throw new Error("INVALID_EVIDENCE_SESSION_ID");
    return store.deleteSession(sessionId,{tenantId});
  }
  async function status(sessionId,{tenantId,actorId}={}) {
    if(!tenantId||!actorId)throw new Error("EVIDENCE_QUEUE_IDENTITY_SCOPE_REQUIRED");
    const records=await store.list(sessionId,{tenantId,actorId,includeBytes:false});
    return {total:records.length,uploaded:records.filter(r=>r.uploaded).length,pending:records.filter(r=>!r.uploaded).length,records};
  }
  return Object.freeze({queueFile,syncSession,status,deleteSession});
}

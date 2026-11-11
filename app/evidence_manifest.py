"""Synthetic byte-integrity checks, not authenticity or durable trusted sealing."""
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from app.capture_protocols import DEFAULT_CAPTURE_PROTOCOL, LEGACY_CAPTURE_PROTOCOL, require_implemented_protocol

VERSION = '0.1'
DEFAULT_CANONICAL_SLOTS = require_implemented_protocol(DEFAULT_CAPTURE_PROTOCOL).slots
LEGACY_CANONICAL_SLOTS = require_implemented_protocol(LEGACY_CAPTURE_PROTOCOL).slots
CANONICAL_SLOTS = DEFAULT_CANONICAL_SLOTS

@dataclass(frozen=True)
class ManifestEntry:
    artifact_id: str
    slot: str
    sha256_hex: str

@dataclass(frozen=True)
class Manifest:
    session_id: str
    shot_list_version: str
    entries: tuple[ManifestEntry, ...]
    schema_version: str = VERSION

    def digest(self):
        content = {'schema_version':self.schema_version,'session_id':self.session_id,
                   'shot_list_version':self.shot_list_version,
                   'entries':[{'artifact_id':e.artifact_id,'slot':e.slot,'sha256_hex':e.sha256_hex} for e in self.entries]}
        encoded = json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        return sha256(b'Claims2Car:manifest:0.1\0'+encoded).hexdigest()

def load_shot_contract(protocol_version=DEFAULT_CAPTURE_PROTOCOL):
    protocol=require_implemented_protocol(protocol_version)
    return protocol.version,protocol.slots

def build_manifest(session_id,entries,protocol_version=DEFAULT_CAPTURE_PROTOCOL):
    if not isinstance(session_id,str) or not session_id.strip():
        raise ValueError('INVALID_SESSION')
    version,slots=load_shot_contract(protocol_version)
    records=tuple(entries)
    for e in records:
        if (not isinstance(e,ManifestEntry) or not isinstance(e.artifact_id,str) or not e.artifact_id.strip()
                or not isinstance(e.slot,str) or e.slot not in slots or not isinstance(e.sha256_hex,str)
                or re.fullmatch(r'[0-9a-f]{64}',e.sha256_hex) is None):
            raise ValueError('INVALID_MANIFEST_ENTRY')
    if (len(records)!=len(slots) or len({e.artifact_id for e in records})!=len(records)
            or len({e.slot for e in records})!=len(records)):
        raise ValueError('CAPTURE_SET_INCOMPLETE_OR_DUPLICATE')
    by_slot={e.slot:e for e in records}
    return Manifest(session_id,version,tuple(by_slot[s] for s in slots))

def verify_manifest(session_id,manifest,trusted_digest,supplied_bytes):
    if not isinstance(manifest,Manifest) or manifest.schema_version!=VERSION or manifest.session_id!=session_id:
        return False
    try:
        canonical=build_manifest(session_id,manifest.entries,manifest.shot_list_version)
    except (ValueError,TypeError):
        return False
    if manifest!=canonical or not isinstance(trusted_digest,str) or manifest.digest()!=trusted_digest:
        return False
    if type(supplied_bytes) is not dict or set(supplied_bytes)!={e.artifact_id for e in manifest.entries}:
        return False
    return all(type(supplied_bytes[e.artifact_id]) is bytes and bool(supplied_bytes[e.artifact_id])
               and sha256(supplied_bytes[e.artifact_id]).hexdigest()==e.sha256_hex for e in manifest.entries)

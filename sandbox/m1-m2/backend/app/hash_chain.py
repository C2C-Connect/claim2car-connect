"""Sequential SHA-256 forensic hash chain utilities."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(payload: Dict[str, Any], prev_hash: Optional[str]) -> str:
    material = canonical_json(payload) + (prev_hash or "")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verify_chain(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """entries: list of {payload, entry_hash, prev_hash}"""
    if not entries:
        return {"valid": True, "master_hash": None, "count": 0}
    prev: Optional[str] = None
    for i, e in enumerate(entries):
        expected = compute_entry_hash(e["payload"], prev)
        if e.get("entry_hash") != expected:
            return {"valid": False, "broken_at": i, "master_hash": None, "count": len(entries)}
        if e.get("prev_hash") != prev:
            return {"valid": False, "broken_at": i, "reason": "prev_hash_mismatch", "master_hash": None, "count": len(entries)}
        prev = e["entry_hash"]
    return {"valid": True, "master_hash": prev, "count": len(entries)}

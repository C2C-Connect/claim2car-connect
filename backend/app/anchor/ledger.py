"""
Internal append-only anchoring ledger.

Stores Merkle roots with timestamps. Full public verify flow recomputes
and compares. Chain-anchor adapter interface reserved for later external anchoring.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def merkle_root(leaves: List[str]) -> str:
    """Pairwise SHA-256 Merkle root over hex leaf hashes."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(h) if len(h) == 64 else hashlib.sha256(h.encode()).digest() for h in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else a
            nxt.append(hashlib.sha256(a + b).digest())
        level = nxt
    return level[0].hex()


@dataclass
class AnchorRecord:
    session_id: str
    merkle_root: str
    master_hash: str
    timestamp_unix: float
    prev_ledger_hash: str
    entry_hash: str
    meta: dict = field(default_factory=dict)


class AnchorLedger:
    """In-process append-only ledger (swap for Postgres/Mongo later)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: List[AnchorRecord] = []
        self._by_session: Dict[str, AnchorRecord] = {}
        self._tip = hashlib.sha256(b"GENESIS").hexdigest()
        self.kill_switch = False  # when True, verify returns invalid

    def append(
        self,
        session_id: str,
        merkle_root_hex: str,
        master_hash: str,
        meta: Optional[dict] = None,
    ) -> AnchorRecord:
        with self._lock:
            prev = self._tip
            payload = {
                "session_id": session_id,
                "merkle_root": merkle_root_hex,
                "master_hash": master_hash,
                "prev": prev,
                "ts": time.time(),
            }
            entry_hash = hashlib.sha256(_canonical(payload).encode()).hexdigest()
            rec = AnchorRecord(
                session_id=session_id,
                merkle_root=merkle_root_hex,
                master_hash=master_hash,
                timestamp_unix=payload["ts"],
                prev_ledger_hash=prev,
                entry_hash=entry_hash,
                meta=meta or {},
            )
            self._entries.append(rec)
            self._by_session[session_id] = rec
            self._tip = entry_hash
            return rec

    def get(self, session_id: str) -> Optional[AnchorRecord]:
        return self._by_session.get(session_id)

    def verify(
        self,
        session_id: str,
        recomputed_merkle: str,
        recomputed_master: str,
    ) -> dict:
        if self.kill_switch:
            return {
                "valid": False,
                "reason": "kill_switch_engaged",
                "session_id": session_id,
            }
        rec = self.get(session_id)
        if not rec:
            return {"valid": False, "reason": "not_anchored", "session_id": session_id}
        root_ok = rec.merkle_root == recomputed_merkle
        master_ok = rec.master_hash == recomputed_master
        return {
            "valid": root_ok and master_ok,
            "reason": "ok" if (root_ok and master_ok) else "mismatch",
            "session_id": session_id,
            "anchored_merkle": rec.merkle_root,
            "recomputed_merkle": recomputed_merkle,
            "anchored_master": rec.master_hash,
            "recomputed_master": recomputed_master,
            "anchored_at": rec.timestamp_unix,
            "entry_hash": rec.entry_hash,
        }


# Process-wide singleton for M5
LEDGER = AnchorLedger()

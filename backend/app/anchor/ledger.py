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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, List, Optional
from uuid import UUID


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


# Financial ledger artifact from the approved production engineering spec.
FEE_SCHEDULE_VERSION = "c2c-commercial-v1"
DEALER_ACQUISITION_FEE_CENTS: int = 37_500
REPAIR_SHOP_ACCEPTANCE_FEE_CENTS: int = 27_500

PROHIBITED_PARTY_TYPES = frozenset({
    "owner", "vehicle_owner", "driver", "owner_incentive", "owner_cash_incentive",
})


class LedgerError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _require_strict_int_cents(value: object, field_name: str = "amount_cents") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerError(
            "FLOATING_POINT_OR_NON_INT_PROHIBITED",
            f"{field_name} must be a strict int in cents, got {type(value).__name__}",
        )
    if value <= 0:
        raise LedgerError("NON_POSITIVE_AMOUNT_CENTS", f"{field_name} must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class PartnerAcceptanceRecord:
    acceptance_id: str
    tenant_id: UUID
    session_id: str
    party_type: str  # "dealer" | "shop"
    partner_org_id: str
    accepted_by_actor: str
    accepted_at: str


@dataclass(frozen=True)
class LedgerPostingLine:
    account_code: str
    direction: str  # "DEBIT" | "CREDIT"
    amount_cents: int


@dataclass(frozen=True)
class LedgerJournalEntry:
    sequence: int
    entry_id: str
    idempotency_key: str
    tenant_id: str
    session_id: str
    entry_kind: str
    fee_type: str
    partner_org_id: str
    acceptance_id: str
    amount_cents: int
    currency: str
    lines: tuple[LedgerPostingLine, ...]
    actor_id: str
    occurred_at: str
    reason: str
    reverses_entry_id: str | None
    previous_hash: str
    entry_hash: str


class IntegerFinancialLedger:
    def __init__(self, *, operator_payout_policy_approved: bool = False) -> None:
        if type(operator_payout_policy_approved) is not bool:
            raise LedgerError("OPERATOR_PAYOUT_POLICY_FLAG_MUST_BE_BOOLEAN")
        self.operator_payout_policy_approved = operator_payout_policy_approved
        self._entries: list[LedgerJournalEntry] = []
        self._by_idempotency: dict[str, LedgerJournalEntry] = {}
        self._by_entry_id: dict[str, LedgerJournalEntry] = {}
        self._reversed_entry_ids: set[str] = set()

    def guard_prohibited_compensation(self, fee_or_party_label: str, amount_cents: object = None) -> None:
        normalized = str(fee_or_party_label).strip().lower()
        if any(t in normalized for t in ("owner", "driver_incentive", "cash_incentive")) or amount_cents == 8_000:
            raise LedgerError(
                "OWNER_CASH_INCENTIVE_PERMANENTLY_PROHIBITED",
                "DECISION-02: no vehicle-owner cash incentive may ever be created or paid.",
            )
        if "operator" in normalized or amount_cents == 11_000:
            if not self.operator_payout_policy_approved:
                raise LedgerError(
                    "OPERATOR_PAYOUT_DISABLED_BY_GATE",
                    "DECISION-03: operator payout is disabled pending Founder policy approval.",
                )

    def record_partner_acceptance_obligation(
        self, acceptance: PartnerAcceptanceRecord, *, idempotency_key: str, actor_id: str,
        amount_override_cents: object = None, now_iso: str | None = None,
    ) -> LedgerJournalEntry:
        if not isinstance(acceptance, PartnerAcceptanceRecord):
            raise LedgerError("ACCEPTANCE_RECORD_REQUIRED")
        if not idempotency_key or not idempotency_key.strip():
            raise LedgerError("IDEMPOTENCY_KEY_REQUIRED")

        party = acceptance.party_type.strip().lower()
        self.guard_prohibited_compensation(party, amount_override_cents)

        if party == "dealer":
            expected, fee_type = DEALER_ACQUISITION_FEE_CENTS, "DEALER_ACQUISITION_FEE"
            ar, rev = f"AR:DEALER:{acceptance.partner_org_id}", "REV:DEALER_ACQUISITION"
        elif party == "shop":
            expected, fee_type = REPAIR_SHOP_ACCEPTANCE_FEE_CENTS, "REPAIR_SHOP_ACCEPTANCE_FEE"
            ar, rev = f"AR:SHOP:{acceptance.partner_org_id}", "REV:REPAIR_SHOP_ACCEPTANCE"
        else:
            raise LedgerError("UNSUPPORTED_PARTNER_PARTY_TYPE", acceptance.party_type)

        if amount_override_cents is not None:
            checked = _require_strict_int_cents(amount_override_cents, "amount_override_cents")
            if checked != expected:
                raise LedgerError(
                    "FEE_SCHEDULE_MISMATCH",
                    f"{fee_type} is fixed at {expected} cents, got {checked}",
                )

        existing = self._by_idempotency.get(idempotency_key)
        if existing is not None:
            if (existing.tenant_id == str(acceptance.tenant_id)
                    and existing.session_id == acceptance.session_id
                    and existing.partner_org_id == acceptance.partner_org_id
                    and existing.acceptance_id == acceptance.acceptance_id
                    and existing.amount_cents == expected
                    and existing.fee_type == fee_type):
                return existing
            raise LedgerError("IDEMPOTENCY_KEY_CONFLICT", idempotency_key)

        lines = (
            LedgerPostingLine(ar, "DEBIT", expected),
            LedgerPostingLine(rev, "CREDIT", expected),
        )
        return self._append_entry(
            idempotency_key=idempotency_key, tenant_id=str(acceptance.tenant_id),
            session_id=acceptance.session_id, entry_kind="OBLIGATION_BOOKED",
            fee_type=fee_type, partner_org_id=acceptance.partner_org_id,
            acceptance_id=acceptance.acceptance_id, amount_cents=expected, lines=lines,
            actor_id=actor_id, reason=f"Verified {party} acceptance ({acceptance.acceptance_id})",
            reverses_entry_id=None, now_iso=now_iso,
        )

    def record_reversal_or_dispute_refund(
        self, original_entry_id: str, *, idempotency_key: str, actor_id: str,
        reason: str, now_iso: str | None = None,
    ) -> LedgerJournalEntry:
        if not reason or not reason.strip():
            raise LedgerError("REVERSAL_REASON_REQUIRED")
        existing = self._by_idempotency.get(idempotency_key)
        if existing is not None:
            if existing.reverses_entry_id == original_entry_id:
                return existing
            raise LedgerError("IDEMPOTENCY_KEY_CONFLICT", idempotency_key)
        original = self._by_entry_id.get(original_entry_id)
        if original is None:
            raise LedgerError("ORIGINAL_ENTRY_NOT_FOUND", original_entry_id)
        if original_entry_id in self._reversed_entry_ids:
            raise LedgerError("ENTRY_ALREADY_REVERSED", original_entry_id)

        inverted = tuple(
            LedgerPostingLine(l.account_code, "CREDIT" if l.direction == "DEBIT" else "DEBIT", l.amount_cents)
            for l in original.lines
        )
        reversal = self._append_entry(
            idempotency_key=idempotency_key, tenant_id=original.tenant_id,
            session_id=original.session_id, entry_kind="REVERSAL_BOOKED",
            fee_type=original.fee_type, partner_org_id=original.partner_org_id,
            acceptance_id=original.acceptance_id, amount_cents=original.amount_cents,
            lines=inverted, actor_id=actor_id, reason=reason.strip(),
            reverses_entry_id=original.entry_id, now_iso=now_iso,
        )
        self._reversed_entry_ids.add(original_entry_id)
        return reversal

    def account_balance_cents(self, account_code: str, *, tenant_id: UUID | str | None = None) -> int:
        tenant_str = str(tenant_id) if tenant_id is not None else None
        debits = credits = 0
        for e in self._entries:
            if tenant_str is not None and e.tenant_id != tenant_str:
                continue
            for l in e.lines:
                if l.account_code == account_code:
                    if l.direction == "DEBIT":
                        debits += l.amount_cents
                    else:
                        credits += l.amount_cents
        return debits - credits

    def export_audit_ledger(self, *, tenant_id: UUID | str | None = None) -> dict:
        tenant_str = str(tenant_id) if tenant_id is not None else None
        filtered = [e for e in self._entries if tenant_str is None or e.tenant_id == tenant_str]
        total_debits = sum(l.amount_cents for e in filtered for l in e.lines if l.direction == "DEBIT")
        total_credits = sum(l.amount_cents for e in filtered for l in e.lines if l.direction == "CREDIT")
        assert total_debits == total_credits, "Double-entry ledger invariant violated"
        chain_root = sha256("|".join(e.entry_hash for e in self._entries).encode()).hexdigest()
        return {
            "fee_schedule_version": FEE_SCHEDULE_VERSION,
            "currency": "USD_CENTS",
            "entry_count": len(filtered),
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "balanced": total_debits == total_credits,
            "chain_root_sha256": chain_root,
            "entries": [asdict(e) for e in filtered],
        }

    def _append_entry(
        self, *, idempotency_key: str, tenant_id: str, session_id: str, entry_kind: str,
        fee_type: str, partner_org_id: str, acceptance_id: str, amount_cents: int,
        lines: tuple[LedgerPostingLine, ...], actor_id: str, reason: str,
        reverses_entry_id: str | None, now_iso: str | None,
    ) -> LedgerJournalEntry:
        _require_strict_int_cents(amount_cents, "amount_cents")
        debits = sum(l.amount_cents for l in lines if l.direction == "DEBIT")
        credits = sum(l.amount_cents for l in lines if l.direction == "CREDIT")
        if debits != credits or debits != amount_cents:
            raise LedgerError("UNBALANCED_DOUBLE_ENTRY_POSTING")

        seq = len(self._entries) + 1
        prev_hash = self._entries[-1].entry_hash if self._entries else "0" * 64
        occurred_at = now_iso or datetime.now(timezone.utc).isoformat()
        entry_id = f"led-{seq:06d}-{sha256(idempotency_key.encode()).hexdigest()[:10]}"
        payload = (
            f"{seq}|{entry_id}|{idempotency_key}|{tenant_id}|{session_id}|{entry_kind}|"
            f"{fee_type}|{partner_org_id}|{acceptance_id}|{amount_cents}|{reverses_entry_id}|"
            f"{[(l.account_code, l.direction, l.amount_cents) for l in lines]}|{prev_hash}"
        )
        entry = LedgerJournalEntry(
            sequence=seq, entry_id=entry_id, idempotency_key=idempotency_key,
            tenant_id=tenant_id, session_id=session_id, entry_kind=entry_kind,
            fee_type=fee_type, partner_org_id=partner_org_id, acceptance_id=acceptance_id,
            amount_cents=amount_cents, currency="USD_CENTS", lines=lines, actor_id=actor_id,
            occurred_at=occurred_at, reason=reason, reverses_entry_id=reverses_entry_id,
            previous_hash=prev_hash, entry_hash=sha256(payload.encode()).hexdigest(),
        )
        self._entries.append(entry)
        self._by_idempotency[idempotency_key] = entry
        self._by_entry_id[entry_id] = entry
        return entry

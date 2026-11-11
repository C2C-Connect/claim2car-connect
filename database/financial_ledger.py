"""Tenant-bound persistent commercial obligation journal."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json

from backend.app.anchor.ledger import (
    REPAIR_SHOP_ACCEPTANCE_FEE_CENTS, LedgerError, LedgerJournalEntry,
    LedgerPostingLine, PartnerAcceptanceRecord, _require_strict_int_cents,
)

GENESIS = "0" * 64


class PersistentFinancialLedger:
    """Persist the approved integer-cent ledger through a tenant-authorized store."""
    def __init__(self, sessions):
        self._sessions = sessions

    def record_partner_acceptance_obligation(self, authorization, acceptance, *, idempotency_key,
                                             actor_id, amount_override_cents=None, now_iso=None):
        if not isinstance(acceptance, PartnerAcceptanceRecord):
            raise LedgerError("ACCEPTANCE_RECORD_REQUIRED")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise LedgerError("IDEMPOTENCY_KEY_REQUIRED")
        party = acceptance.party_type.strip().lower()
        if party == "dealer":
            raise LedgerError(
                "DEALER_FEE_REQUIRES_QUALIFIED_ACQUISITION_CLOSE",
                "A dealer acceptance is not a qualified acquisition close.",
            )
        elif party == "shop":
            amount, fee, ar, revenue = REPAIR_SHOP_ACCEPTANCE_FEE_CENTS, "REPAIR_SHOP_ACCEPTANCE_FEE", f"AR:SHOP:{acceptance.partner_org_id}", "REV:REPAIR_SHOP_ACCEPTANCE"
        else:
            raise LedgerError("UNSUPPORTED_PARTNER_PARTY_TYPE", acceptance.party_type)
        if amount_override_cents is not None and _require_strict_int_cents(amount_override_cents) != amount:
            raise LedgerError("FEE_SCHEDULE_MISMATCH")
        if str(acceptance.tenant_id) == "" or not acceptance.partner_org_id or not acceptance.acceptance_id:
            raise LedgerError("INVALID_ACCEPTANCE_RECORD")
        lines = (LedgerPostingLine(ar, "DEBIT", amount), LedgerPostingLine(revenue, "CREDIT", amount))
        return self._append(authorization, tenant_id=str(acceptance.tenant_id),
            session_id=acceptance.session_id, entry_kind="OBLIGATION_BOOKED", fee_type=fee,
            partner_org_id=acceptance.partner_org_id, acceptance_id=acceptance.acceptance_id,
            amount=amount, lines=lines, idempotency_key=idempotency_key, actor_id=actor_id,
            reason=f"Verified {party} acceptance ({acceptance.acceptance_id})", reverses=None, now_iso=now_iso)

    def _append(self, authorization, *, tenant_id, session_id, entry_kind, fee_type, partner_org_id,
                acceptance_id, amount, lines, idempotency_key, actor_id, reason, reverses, now_iso):
        with self._sessions._authorized(authorization) as (conn, actor):
            if str(actor.tenant_id) != tenant_id:
                raise LedgerError("TENANT_CONTEXT_MISMATCH")
            if actor.actor_role not in ("operator", "supervisor") or actor.actor_id != actor_id:
                raise LedgerError("LEDGER_ACTOR_NOT_AUTHORIZED")
            prior = conn.execute("SELECT entry_id,session_id,entry_kind,fee_type,partner_org_id,acceptance_id,amount_cents,reverses_entry_id FROM faos.financial_ledger_entries WHERE tenant_id=%s AND idempotency_key=%s", (tenant_id,idempotency_key)).fetchone()
            if prior:
                expected=(session_id,entry_kind,fee_type,partner_org_id,acceptance_id,amount,reverses)
                if prior[1:] != expected:
                    raise LedgerError("IDEMPOTENCY_KEY_CONFLICT", idempotency_key)
                return self._read(conn, tenant_id, prior[0])
            tip = conn.execute("SELECT sequence,entry_hash FROM faos.financial_ledger_entries WHERE tenant_id=%s ORDER BY sequence DESC LIMIT 1",(tenant_id,)).fetchone()
            sequence, previous = (tip[0]+1,tip[1]) if tip else (1,GENESIS)
            entry_id=f"led-{sequence:06d}-{sha256(idempotency_key.encode()).hexdigest()[:10]}"
            occurred_at=now_iso or datetime.now(timezone.utc).isoformat()
            payload=(f"{sequence}|{entry_id}|{idempotency_key}|{tenant_id}|{session_id}|{entry_kind}|"
                f"{fee_type}|{partner_org_id}|{acceptance_id}|{amount}|{reverses}|"
                f"{[(line.account_code,line.direction,line.amount_cents) for line in lines]}|{previous}")
            entry_hash=sha256(payload.encode()).hexdigest()
            line_data=[asdict(line) for line in lines]
            result=conn.execute("SELECT faos.append_financial_entry(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (tenant_id,entry_id,sequence,idempotency_key,session_id,entry_kind,fee_type,partner_org_id,
                 acceptance_id,amount,"USD_CENTS",actor_id,occurred_at,reason,reverses,previous,entry_hash,
                 json.dumps(line_data,separators=(",",":")))).fetchone()[0]
            if result not in ("ACCEPTED","DUPLICATE"):
                raise LedgerError("FINANCIAL_ENTRY_NOT_ACCEPTED")
            return self._read(conn,tenant_id,entry_id)

    @staticmethod
    def _read(conn, tenant_id, entry_id):
        row=conn.execute("SELECT sequence,entry_id,idempotency_key,tenant_id::text,session_id,entry_kind,fee_type,partner_org_id,acceptance_id,amount_cents,currency,actor_id,occurred_at,reason,reverses_entry_id,previous_hash,entry_hash FROM faos.financial_ledger_entries WHERE tenant_id=%s AND entry_id=%s",(tenant_id,entry_id)).fetchone()
        if row is None:
            raise LedgerError("FINANCIAL_ENTRY_NOT_FOUND")
        postings=conn.execute("SELECT account_code,direction,amount_cents FROM faos.financial_ledger_postings WHERE tenant_id=%s AND entry_id=%s ORDER BY line_number",(tenant_id,entry_id)).fetchall()
        return LedgerJournalEntry(*row[:11],tuple(LedgerPostingLine(*line) for line in postings),*row[11:])

    def record_reversal_or_dispute_refund(self, authorization, original_entry_id, *,
                                          idempotency_key, actor_id, reason, now_iso=None):
        if not isinstance(reason,str) or not reason.strip():
            raise LedgerError("REVERSAL_REASON_REQUIRED")
        with self._sessions._authorized(authorization) as (conn, actor):
            if actor.actor_role not in ("operator","supervisor") or actor.actor_id != actor_id:
                raise LedgerError("LEDGER_ACTOR_NOT_AUTHORIZED")
            duplicate=conn.execute("SELECT entry_id,reverses_entry_id FROM faos.financial_ledger_entries WHERE tenant_id=%s AND idempotency_key=%s",(actor.tenant_id,idempotency_key)).fetchone()
            if duplicate:
                if duplicate[1] != original_entry_id:
                    raise LedgerError("IDEMPOTENCY_KEY_CONFLICT",idempotency_key)
                return self._read(conn,str(actor.tenant_id),duplicate[0])
            original=self._read(conn,str(actor.tenant_id),original_entry_id)
            if original.entry_kind != "OBLIGATION_BOOKED":
                raise LedgerError("INVALID_REVERSAL_REFERENCE")
            if conn.execute("SELECT 1 FROM faos.financial_ledger_entries WHERE tenant_id=%s AND reverses_entry_id=%s",(actor.tenant_id,original_entry_id)).fetchone():
                raise LedgerError("ENTRY_ALREADY_REVERSED",original_entry_id)
            inverted=tuple(LedgerPostingLine(line.account_code,"CREDIT" if line.direction=="DEBIT" else "DEBIT",line.amount_cents) for line in original.lines)
        return self._append(authorization,tenant_id=original.tenant_id,session_id=original.session_id,
            entry_kind="REVERSAL_BOOKED",fee_type=original.fee_type,partner_org_id=original.partner_org_id,
            acceptance_id=original.acceptance_id,amount=original.amount_cents,lines=inverted,
            idempotency_key=idempotency_key,actor_id=actor_id,reason=reason.strip(),
            reverses=original.entry_id,now_iso=now_iso)

    def export_audit_ledger(self, authorization):
        with self._sessions._authorized(authorization) as (conn,actor):
            rows=conn.execute("SELECT entry_id FROM faos.financial_ledger_entries WHERE tenant_id=%s ORDER BY sequence",(actor.tenant_id,)).fetchall()
            entries=[self._read(conn,str(actor.tenant_id),row[0]) for row in rows]
        previous=GENESIS
        for entry in entries:
            payload=(f"{entry.sequence}|{entry.entry_id}|{entry.idempotency_key}|{entry.tenant_id}|{entry.session_id}|{entry.entry_kind}|"
                f"{entry.fee_type}|{entry.partner_org_id}|{entry.acceptance_id}|{entry.amount_cents}|{entry.reverses_entry_id}|"
                f"{[(line.account_code,line.direction,line.amount_cents) for line in entry.lines]}|{previous}")
            if entry.previous_hash != previous or sha256(payload.encode()).hexdigest() != entry.entry_hash:
                raise LedgerError("FINANCIAL_CHAIN_INTEGRITY_FAILURE")
            previous=entry.entry_hash
        debits=sum(line.amount_cents for entry in entries for line in entry.lines if line.direction=="DEBIT")
        credits=sum(line.amount_cents for entry in entries for line in entry.lines if line.direction=="CREDIT")
        if debits != credits:
            raise LedgerError("UNBALANCED_DOUBLE_ENTRY_POSTING")
        from backend.app.anchor.ledger import FEE_SCHEDULE_VERSION
        return {"fee_schedule_version":FEE_SCHEDULE_VERSION,"currency":"USD_CENTS","entry_count":len(entries),
            "total_debits_cents":debits,"total_credits_cents":credits,"balanced":True,
            "chain_root_sha256":sha256("|".join(e.entry_hash for e in entries).encode()).hexdigest(),
            "entries":[asdict(entry) for entry in entries]}

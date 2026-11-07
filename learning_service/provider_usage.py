"""Durable conservative provider limits, separate from learning transactions.

Amounts are integer millionths of one explicitly configured currency. A token
estimate is never an invoice. Unknown/crashed attempts retain their hold;
retries reserve another hold. Only an operator's invoice reference can settle
one. No payload or student identifier belongs in this ledger.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .db import Database, new_id, utc_now


class ProviderLimit(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def safe_reference(value: Any) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value) else None


def token_cost(prompt: int, completion: int, input_rate: int, output_rate: int) -> int:
    return (prompt * input_rate + completion * output_rate + 999999) // 1000000


_CHARGE = "COALESCE(reconciled_cost_micros,MAX(reserved_cost_micros,COALESCE(estimated_cost_micros,0)))"


class UsageLedger:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings

    def reserve(self, provider_id: str, operation: str, model_id: str, cost: int,
                evidence_mode: str = "live_http", *, input_rate: int = 0, output_rate: int = 0) -> str:
        s = self.settings
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        minute = (now - timedelta(seconds=60)).replace(microsecond=0).isoformat()
        reason = None
        with self.db.session(write=True) as conn:
            if not all(type(x) is int and 0 < x <= 10**15 for x in (
                cost, s.provider_total_budget_micros, s.provider_daily_budget_micros,
                s.provider_max_cost_micros_per_call, s.provider_max_calls_per_day,
                s.provider_max_calls_per_minute, s.provider_max_inflight,
            )) or not safe_reference(s.provider_pricing_reference) or not re.fullmatch(r"[A-Z]{3}", s.provider_currency):
                reason = "BUDGET_NOT_CONFIGURED"
            elif evidence_mode not in {"live_http", "synthetic_http"}:
                reason = "INVALID_EVIDENCE_MODE"
            elif not all(safe_reference(x) for x in (provider_id, operation, model_id)):
                reason = "INVALID_CALL_METADATA"
            elif conn.execute("SELECT paused FROM provider_control WHERE id=1").fetchone()[0]:
                reason = "PROVIDER_PAUSED"
            elif conn.execute("SELECT 1 FROM provider_calls WHERE currency<>? LIMIT 1", (s.provider_currency,)).fetchone():
                reason = "BUDGET_CURRENCY_CHANGED"
            elif cost > s.provider_max_cost_micros_per_call:
                reason = "CALL_COST_LIMIT"
            else:
                total = conn.execute(f"SELECT COALESCE(SUM({_CHARGE}),0) FROM provider_calls").fetchone()[0]
                daily = conn.execute(f"SELECT COUNT(*),COALESCE(SUM({_CHARGE}),0) FROM provider_calls WHERE created_at>=?", (today,)).fetchone()
                recent = conn.execute("SELECT COUNT(*) FROM provider_calls WHERE created_at>=?", (minute,)).fetchone()[0]
                inflight = conn.execute("SELECT COUNT(*) FROM provider_calls WHERE state='reserved'").fetchone()[0]
                if total + cost > s.provider_total_budget_micros:
                    reason = "TOTAL_COST_LIMIT"
                elif daily[1] + cost > s.provider_daily_budget_micros:
                    reason = "DAILY_COST_LIMIT"
                elif daily[0] >= s.provider_max_calls_per_day:
                    reason = "DAILY_CALL_LIMIT"
                elif recent >= s.provider_max_calls_per_minute:
                    reason = "PROVIDER_RATE_LIMIT"
                elif inflight >= s.provider_max_inflight:
                    reason = "PROVIDER_INFLIGHT_LIMIT"
            if reason:
                conn.execute("INSERT INTO provider_denials(reason,count) VALUES (?,1) ON CONFLICT(reason) DO UPDATE SET count=count+1", (reason,))
            else:
                call_id = new_id("provider_call")
                conn.execute(
                    "INSERT INTO provider_calls(id,provider_id,operation,model_id,evidence_mode,currency,pricing_reference,input_rate,output_rate,reserved_cost_micros,state,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (call_id, provider_id, operation, model_id, evidence_mode, s.provider_currency,
                     s.provider_pricing_reference, input_rate, output_rate, cost, "reserved", utc_now()),
                )
        if reason:
            raise ProviderLimit(reason)
        return call_id

    def finish(self, call_id: str, *, state: str, request_id: str | None = None,
               error_code: str | None = None, latency_ms: int = 0,
               prompt_tokens: int | None = None, completion_tokens: int | None = None) -> bool:
        if state not in {"returned", "failed", "unknown"}:
            raise ValueError("invalid call state")
        overrun = False
        with self.db.session(write=True) as conn:
            row = conn.execute("SELECT * FROM provider_calls WHERE id=? AND state='reserved'", (call_id,)).fetchone()
            if not row:
                raise ProviderLimit("CALL_ALREADY_FINISHED")
            usage_valid = all(type(x) is int and 0 <= x <= 10**9 for x in (prompt_tokens, completion_tokens))
            estimate = token_cost(prompt_tokens, completion_tokens, row["input_rate"], row["output_rate"]) if usage_valid else None
            overrun = bool(usage_valid and (
                prompt_tokens > self.settings.model_max_input_tokens
                or completion_tokens > self.settings.model_max_output_tokens
                or estimate > row["reserved_cost_micros"]
            ))
            conn.execute(
                "UPDATE provider_calls SET state=?,request_id=?,error_code=?,latency_ms=?,prompt_tokens=?,completion_tokens=?,estimated_cost_micros=?,finished_at=? WHERE id=?",
                (state, safe_reference(request_id), safe_reference(error_code), max(0, int(latency_ms)),
                 prompt_tokens if usage_valid else None, completion_tokens if usage_valid else None, estimate, utc_now(), call_id),
            )
            if overrun:
                conn.execute("UPDATE provider_control SET paused=1,updated_at=? WHERE id=1", (utc_now(),))
        return overrun

    def set_paused(self, paused: bool) -> None:
        with self.db.session(write=True) as conn:
            conn.execute("UPDATE provider_control SET paused=?,updated_at=? WHERE id=1", (int(paused), utc_now()))

    def reconcile(self, call_id: str, cost: int, currency: str, billing_reference: str, request_id: str) -> dict[str, Any]:
        if type(cost) is not int or not 0 <= cost <= 10**15 or not safe_reference(billing_reference) or not safe_reference(request_id):
            raise ProviderLimit("INVALID_RECONCILIATION")
        with self.db.session(write=True) as conn:
            row = conn.execute("SELECT * FROM provider_calls WHERE id=?", (call_id,)).fetchone()
            if not row:
                raise ProviderLimit("CALL_NOT_FOUND")
            if row["state"] == "reserved":
                raise ProviderLimit("CALL_STILL_RESERVED")
            if row["evidence_mode"] != "live_http":
                raise ProviderLimit("SYNTHETIC_CALL_HAS_NO_INVOICE")
            if currency != row["currency"] or (row["request_id"] and row["request_id"] != request_id):
                raise ProviderLimit("RECONCILIATION_MISMATCH")
            if row["reconciled_cost_micros"] is not None:
                if (row["reconciled_cost_micros"], row["billing_reference"], row["request_id"]) != (cost, billing_reference, request_id):
                    raise ProviderLimit("RECONCILIATION_CONFLICT")
            else:
                conn.execute("UPDATE provider_calls SET state='reconciled',reconciled_cost_micros=?,billing_reference=?,request_id=?,finished_at=? WHERE id=?", (cost, billing_reference, request_id, utc_now(), call_id))
                if cost > row["reserved_cost_micros"]:
                    conn.execute("UPDATE provider_control SET paused=1,updated_at=? WHERE id=1", (utc_now(),))
        return {"call_id": call_id, "status": "reconciled", "billing_evidence": "operator_invoice_reference"}

    def summary(self) -> dict[str, Any]:
        with self.db.session() as conn:
            modes = {row[0]: row[1] for row in conn.execute("SELECT evidence_mode,COUNT(*) FROM provider_calls GROUP BY evidence_mode")}
            states = {row[0]: row[1] for row in conn.execute("SELECT state,COUNT(*) FROM provider_calls GROUP BY state")}
            totals = conn.execute(f"SELECT COALESCE(SUM({_CHARGE}),0),SUM(estimated_cost_micros),SUM(reconciled_cost_micros),SUM(prompt_tokens),SUM(completion_tokens) FROM provider_calls").fetchone()
            pending = conn.execute("SELECT COUNT(*) FROM provider_calls WHERE reconciled_cost_micros IS NULL AND evidence_mode='live_http'").fetchone()[0]
            paused = bool(conn.execute("SELECT paused FROM provider_control WHERE id=1").fetchone()[0])
            denials = {row[0]: row[1] for row in conn.execute("SELECT reason,count FROM provider_denials")}
            currency_row = conn.execute("SELECT currency FROM provider_calls LIMIT 1").fetchone()
        return {
            "tracked": True, "by_evidence_mode": modes, "by_state": states, "paused": paused,
            "currency": currency_row[0] if currency_row else self.settings.provider_currency,
            "configured_currency": self.settings.provider_currency, "budget_charge_micros": totals[0],
            "estimated_cost_micros": totals[1], "reconciled_cost_micros": totals[2],
            "prompt_tokens": totals[3], "completion_tokens": totals[4], "invoice_pending_calls": pending,
            "denials": denials, "cost_basis": "reservation_until_operator_invoice_reconciliation",
            "total_budget_micros": self.settings.provider_total_budget_micros,
            "daily_budget_micros": self.settings.provider_daily_budget_micros,
        }

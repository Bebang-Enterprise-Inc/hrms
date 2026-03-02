"""Inventory risk APIs for stockout visibility workflows (Sprint 20)."""

from __future__ import annotations

from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime


_TEST_RISK_ROWS: list[dict] = []
_TEST_INCIDENTS: list[dict] = []


def set_test_risk_rows(rows: list[dict]) -> None:
    """Inject deterministic risk inputs for tests."""
    global _TEST_RISK_ROWS
    _TEST_RISK_ROWS = [deepcopy(row) for row in rows]


def set_test_incidents(rows: list[dict]) -> None:
    """Inject deterministic incident rows for tests."""
    global _TEST_INCIDENTS
    _TEST_INCIDENTS = [deepcopy(row) for row in rows]


def _risk_level_from_score(risk_score: float) -> str:
    if risk_score >= 80:
        return "Critical"
    if risk_score >= 60:
        return "High"
    if risk_score >= 35:
        return "Moderate"
    return "Low"


def _safe_supplier_score(reliability_score: float) -> float:
    bounded = min(100.0, max(0.0, flt(reliability_score)))
    # Higher reliability lowers risk contribution.
    return round((100.0 - bounded) * 0.1, 2)


def build_risk_snapshot_row(source: dict, horizon_hours: int = 72) -> dict:
    available_qty = max(0.0, flt(source.get("available_qty")))
    avg_daily_demand = max(0.0, flt(source.get("avg_daily_demand")))
    lead_time_days = max(0.0, flt(source.get("lead_time_days")))
    supplier_reliability = flt(source.get("supplier_reliability_score") or 70)

    days_to_stockout = 999.0
    projected_stockout_at = None
    if avg_daily_demand > 0:
        days_to_stockout = round(available_qty / avg_daily_demand, 2)
        projected_stockout_at = add_to_date(
            now_datetime(),
            days=days_to_stockout,
            as_string=True,
        )

    # Deterministic weighted model: stock cover dominates, then lead time, then supplier reliability.
    cover_score = 0.0 if days_to_stockout >= 14 else (14.0 - days_to_stockout) * 5.0
    lead_score = min(20.0, lead_time_days * 2.0)
    supplier_score = _safe_supplier_score(supplier_reliability)
    risk_score = round(min(100.0, max(0.0, cover_score + lead_score + supplier_score)), 2)

    return {
        "item_code": source.get("item_code"),
        "warehouse": source.get("warehouse"),
        "available_qty": available_qty,
        "avg_daily_demand": avg_daily_demand,
        "lead_time_days": lead_time_days,
        "supplier_reliability_score": supplier_reliability,
        "horizon_hours": cint(horizon_hours or 72),
        "days_to_stockout": days_to_stockout,
        "projected_stockout_at": projected_stockout_at,
        "risk_score": risk_score,
        "risk_level": _risk_level_from_score(risk_score),
    }


def _load_risk_inputs() -> list[dict]:
    if _TEST_RISK_ROWS:
        return [deepcopy(row) for row in _TEST_RISK_ROWS]
    return []


def _load_open_incidents() -> list[dict]:
    if not _TEST_INCIDENTS:
        return []
    rows = [deepcopy(row) for row in _TEST_INCIDENTS]
    return [row for row in rows if row.get("status") != "Resolved"]


@frappe.whitelist()
def recompute_risk_snapshots(horizon_hours: int = 72):
    rows = [build_risk_snapshot_row(row, horizon_hours=horizon_hours) for row in _load_risk_inputs()]
    return {
        "success": True,
        "horizon_hours": cint(horizon_hours or 72),
        "recomputed": len(rows),
        "rows": rows,
    }


@frappe.whitelist()
def get_risk_items(limit: int = 50, horizon_hours: int = 72):
    computed = recompute_risk_snapshots(horizon_hours=horizon_hours)
    rows = sorted(computed["rows"], key=lambda row: row.get("risk_score", 0), reverse=True)
    return {
        "items": rows[: max(1, cint(limit or 50))],
        "limit": max(1, cint(limit or 50)),
        "horizon_hours": cint(horizon_hours or 72),
    }


@frappe.whitelist()
def get_risk_dashboard(horizon_hours: int = 72):
    items_payload = get_risk_items(limit=200, horizon_hours=horizon_hours)
    items = items_payload["items"]

    stockouts_next_horizon = [
        row
        for row in items
        if flt(row.get("days_to_stockout")) <= round(cint(horizon_hours or 72) / 24.0, 2)
    ]
    high_risk = [row for row in items if row.get("risk_level") in ("High", "Critical")]
    incidents = _load_open_incidents()

    return {
        "horizon_hours": cint(horizon_hours or 72),
        "summary": {
            "total_items": len(items),
            "high_risk_items": len(high_risk),
            "stockouts_next_72h": len(stockouts_next_horizon),
            "open_incidents": len(incidents),
        },
        "top_risks": items[:10],
    }


@frappe.whitelist()
def get_item_exposure(item_code: str):
    if not item_code:
        frappe.throw(_("item_code is required"))
    return {
        "item_code": item_code,
        "exposure": [],
    }


@frappe.whitelist()
def get_stockout_incidents(status: str | None = None):
    incidents = [deepcopy(row) for row in _TEST_INCIDENTS]
    if status:
        incidents = [row for row in incidents if row.get("status") == status]
    return {
        "status": status,
        "incidents": incidents,
    }


@frappe.whitelist()
def update_stockout_incident(incident_name: str, new_status: str, note: str | None = None):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not new_status:
        frappe.throw(_("new_status is required"))

    for row in _TEST_INCIDENTS:
        if row.get("name") == incident_name:
            row["status"] = new_status
            row["note"] = note or ""
            return {
                "name": incident_name,
                "status": new_status,
                "note": note or "",
            }

    return {
        "name": incident_name,
        "status": new_status,
        "note": note or "",
    }

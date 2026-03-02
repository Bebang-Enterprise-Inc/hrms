"""Inventory risk APIs for stockout visibility workflows (Sprint 20)."""

from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def get_risk_dashboard(horizon_hours: int = 72):
    """Return an empty dashboard payload until risk snapshots are computed."""
    return {
        "horizon_hours": int(horizon_hours or 72),
        "summary": {
            "total_items": 0,
            "high_risk_items": 0,
            "stockouts_next_72h": 0,
            "open_incidents": 0,
        },
        "top_risks": [],
    }


@frappe.whitelist()
def get_risk_items(limit: int = 50):
    return {
        "items": [],
        "limit": int(limit or 50),
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
    return {
        "status": status,
        "incidents": [],
    }


@frappe.whitelist()
def update_stockout_incident(incident_name: str, new_status: str, note: str | None = None):
    if not incident_name:
        frappe.throw(_("incident_name is required"))
    if not new_status:
        frappe.throw(_("new_status is required"))
    return {
        "name": incident_name,
        "status": new_status,
        "note": note or "",
    }


@frappe.whitelist()
def recompute_risk_snapshots(horizon_hours: int = 72):
    return {
        "success": True,
        "horizon_hours": int(horizon_hours or 72),
        "recomputed": 0,
    }

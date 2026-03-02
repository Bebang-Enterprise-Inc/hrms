"""Inventory risk APIs for stockout visibility workflows (Sprint 20)."""

from __future__ import annotations

from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime

_TEST_RISK_ROWS: list[dict] = []
_TEST_INCIDENTS: list[dict] = []
_TEST_INCIDENT_EVENTS: dict[str, list[dict]] = {}
_TEST_EXPOSURE_MAP: dict[str, list[dict]] = {}


def set_test_risk_rows(rows: list[dict]) -> None:
	"""Inject deterministic risk inputs for tests."""
	global _TEST_RISK_ROWS
	_TEST_RISK_ROWS = [deepcopy(row) for row in rows]


def set_test_incidents(rows: list[dict]) -> None:
	"""Inject deterministic incident rows for tests."""
	global _TEST_INCIDENTS
	_TEST_INCIDENTS = [deepcopy(row) for row in rows]


def set_test_exposure_map(exposure_map: dict[str, list[dict]]) -> None:
	"""Inject deterministic exposure payloads keyed by parent item."""
	global _TEST_EXPOSURE_MAP
	_TEST_EXPOSURE_MAP = {key: [deepcopy(row) for row in rows] for key, rows in exposure_map.items()}


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
		row for row in items if flt(row.get("days_to_stockout")) <= round(cint(horizon_hours or 72) / 24.0, 2)
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


def build_ingredient_exposure(
	parent_item_code: str,
	demand_qty: float,
	bom_rows: list[dict],
	stock_map: dict[str, float],
) -> list[dict]:
	exposure_rows: list[dict] = []
	for row in bom_rows:
		ingredient = row.get("ingredient_item_code") or row.get("item_code")
		qty_per_unit = max(0.0, flt(row.get("qty_per_unit") or row.get("qty")))
		required_qty = round(max(0.0, flt(demand_qty)) * qty_per_unit, 2)
		available_qty = max(0.0, flt(stock_map.get(ingredient, 0)))
		shortage_qty = round(max(0.0, required_qty - available_qty), 2)
		daily_requirement = max(0.0, flt(demand_qty) * qty_per_unit)
		days_cover = 999.0 if daily_requirement <= 0 else round(available_qty / daily_requirement, 2)

		if shortage_qty > 0 and available_qty <= 0:
			exposure_status = "Critical"
		elif shortage_qty > 0:
			exposure_status = "Watch"
		else:
			exposure_status = "Normal"

		exposure_rows.append(
			{
				"parent_item_code": parent_item_code,
				"ingredient_item_code": ingredient,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"shortage_qty": shortage_qty,
				"days_cover": days_cover,
				"exposure_status": exposure_status,
			}
		)
	return exposure_rows


@frappe.whitelist()
def get_item_exposure(item_code: str):
	if not item_code:
		frappe.throw(_("item_code is required"))

	exposure_rows = [deepcopy(row) for row in _TEST_EXPOSURE_MAP.get(item_code, [])]
	return {
		"item_code": item_code,
		"exposure": exposure_rows,
	}


def _next_incident_name() -> str:
	return f"S20-INC-{len(_TEST_INCIDENTS) + 1:04d}"


def _resolve_session_user() -> str:
	local_session = getattr(getattr(frappe, "local", None), "session", None)
	if local_session and getattr(local_session, "user", None):
		return str(local_session.user)

	session = getattr(frappe, "session", None)
	if session and getattr(session, "user", None):
		return str(session.user)

	return "Administrator"


def _append_incident_event(incident_name: str, event_type: str, details: str | None = None) -> dict:
	event = {
		"incident": incident_name,
		"event_type": event_type,
		"details": details or "",
		"event_at": add_to_date(now_datetime(), days=0, as_string=True),
		"event_by": _resolve_session_user(),
	}
	_TEST_INCIDENT_EVENTS.setdefault(incident_name, []).append(event)
	return event


def create_stockout_incident(
	item_code: str,
	warehouse: str,
	incident_title: str | None = None,
	owner_user: str | None = None,
) -> dict:
	if not item_code:
		frappe.throw(_("item_code is required"))
	if not warehouse:
		frappe.throw(_("warehouse is required"))

	incident = {
		"name": _next_incident_name(),
		"incident_title": incident_title or f"Stockout risk on {item_code}",
		"item_code": item_code,
		"warehouse": warehouse,
		"status": "Open",
		"owner_user": owner_user,
		"detected_on": add_to_date(now_datetime(), days=0, as_string=True),
		"resolution_notes": "",
	}
	_TEST_INCIDENTS.append(incident)
	_append_incident_event(incident["name"], "Detected", "Incident created")
	return deepcopy(incident)


_STATUS_EVENT_MAP = {
	"Mitigating": "Assigned",
	"Blocked": "Blocked",
	"Resolved": "Resolved",
}


def update_stockout_incident_status(
	incident_name: str,
	new_status: str,
	note: str | None = None,
	resolution_notes: str | None = None,
	owner_user: str | None = None,
) -> dict:
	if not incident_name:
		frappe.throw(_("incident_name is required"))
	if not new_status:
		frappe.throw(_("new_status is required"))

	allowed_status = {"Open", "Mitigating", "Blocked", "Resolved"}
	if new_status not in allowed_status:
		frappe.throw(_("Invalid status"))

	incident = next((row for row in _TEST_INCIDENTS if row.get("name") == incident_name), None)
	if incident is None:
		incident = {
			"name": incident_name,
			"incident_title": incident_name,
			"item_code": None,
			"warehouse": None,
			"status": "Open",
			"owner_user": None,
			"detected_on": add_to_date(now_datetime(), days=0, as_string=True),
			"resolution_notes": "",
		}
		_TEST_INCIDENTS.append(incident)

	if new_status == "Resolved":
		final_notes = (resolution_notes or note or "").strip()
		if not final_notes:
			frappe.throw(_("resolution_notes is required for Resolved status"))
		incident["resolution_notes"] = final_notes

	if owner_user:
		incident["owner_user"] = owner_user

	incident["status"] = new_status
	event_type = _STATUS_EVENT_MAP.get(new_status, "Updated")
	_append_incident_event(incident_name, event_type, note)
	return deepcopy(incident)


@frappe.whitelist()
def get_incident_events(incident_name: str):
	if not incident_name:
		frappe.throw(_("incident_name is required"))
	return [deepcopy(row) for row in _TEST_INCIDENT_EVENTS.get(incident_name, [])]


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
	return update_stockout_incident_status(
		incident_name=incident_name,
		new_status=new_status,
		note=note,
	)

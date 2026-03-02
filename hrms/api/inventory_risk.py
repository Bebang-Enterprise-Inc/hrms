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
_FORCE_TEST_MODE = False

TEST_DATA_TAG = "test-s20-inventory-risk-seed"
_INCIDENT_FIELDS = [
	"name",
	"incident_title",
	"item_code",
	"warehouse",
	"status",
	"owner_user",
	"detected_on",
	"resolution_notes",
]


def set_test_risk_rows(rows: list[dict]) -> None:
	"""Inject deterministic risk inputs for tests."""
	global _TEST_RISK_ROWS, _FORCE_TEST_MODE
	_FORCE_TEST_MODE = True
	_TEST_RISK_ROWS = [deepcopy(row) for row in rows]


def set_test_incidents(rows: list[dict]) -> None:
	"""Inject deterministic incident rows for tests."""
	global _TEST_INCIDENTS, _TEST_INCIDENT_EVENTS, _FORCE_TEST_MODE
	_FORCE_TEST_MODE = True
	_TEST_INCIDENTS = [deepcopy(row) for row in rows]
	_TEST_INCIDENT_EVENTS = {}


def set_test_exposure_map(exposure_map: dict[str, list[dict]]) -> None:
	"""Inject deterministic exposure payloads keyed by parent item."""
	global _TEST_EXPOSURE_MAP, _FORCE_TEST_MODE
	_FORCE_TEST_MODE = True
	_TEST_EXPOSURE_MAP = {key: [deepcopy(row) for row in rows] for key, rows in exposure_map.items()}


def _is_test_mode() -> bool:
	return bool(_FORCE_TEST_MODE)


def _doctype_available(doctype: str) -> bool:
	db = getattr(frappe, "db", None)
	if not db or not hasattr(db, "exists"):
		return False
	try:
		return bool(db.exists("DocType", doctype))
	except Exception:
		return False


def _frappe_get_all(*args, **kwargs):
	get_all_fn = getattr(frappe, "get_all", None)
	if not callable(get_all_fn):
		return []
	return get_all_fn(*args, **kwargs)


def _incident_event_type(status: str) -> str:
	return {
		"Open": "Updated",
		"Mitigating": "Assigned",
		"Blocked": "Blocked",
		"Resolved": "Resolved",
	}.get(status, "Updated")


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
	if _is_test_mode():
		return [deepcopy(row) for row in _TEST_RISK_ROWS]
	if not _doctype_available("BEI Inventory Risk Snapshot"):
		return []

	profiles = _frappe_get_all(
		"BEI Inventory Risk Profile",
		filters={"is_active": 1},
		fields=["item_code", "warehouse", "lead_time_days", "supplier_reliability_score"],
		limit_page_length=2000,
	)
	profile_map = {f"{row.get('item_code')}::{row.get('warehouse')}": row for row in profiles}

	snapshots = _frappe_get_all(
		"BEI Inventory Risk Snapshot",
		fields=["item_code", "warehouse", "available_qty", "avg_daily_demand"],
		order_by="modified desc",
		limit_page_length=2000,
	)

	latest_by_item: dict[tuple[str, str], dict] = {}
	for row in snapshots:
		item_code = str(row.get("item_code") or "").strip()
		warehouse = str(row.get("warehouse") or "").strip()
		if not item_code or not warehouse:
			continue
		key = (item_code, warehouse)
		if key not in latest_by_item:
			latest_by_item[key] = row

	input_rows: list[dict] = []
	for (item_code, warehouse), row in latest_by_item.items():
		profile = profile_map.get(f"{item_code}::{warehouse}") or {}
		input_rows.append(
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"available_qty": flt(row.get("available_qty")),
				"avg_daily_demand": flt(row.get("avg_daily_demand")),
				"lead_time_days": flt(profile.get("lead_time_days") or 2),
				"supplier_reliability_score": flt(profile.get("supplier_reliability_score") or 70),
			}
		)
	return input_rows


def _load_open_incidents() -> list[dict]:
	if _is_test_mode():
		rows = [deepcopy(row) for row in _TEST_INCIDENTS]
		return [row for row in rows if row.get("status") != "Resolved"]
	if not _doctype_available("BEI Stockout Incident"):
		return []
	return _frappe_get_all(
		"BEI Stockout Incident",
		filters=[["status", "!=", "Resolved"]],
		fields=_INCIDENT_FIELDS,
		order_by="modified desc",
		limit_page_length=500,
	)


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

	if _is_test_mode():
		exposure_rows = [deepcopy(row) for row in _TEST_EXPOSURE_MAP.get(item_code, [])]
	elif _doctype_available("BEI Ingredient Risk Exposure"):
		exposure_rows = _frappe_get_all(
			"BEI Ingredient Risk Exposure",
			filters={"parent_item_code": item_code},
			fields=[
				"parent_item_code",
				"ingredient_item_code",
				"required_qty",
				"available_qty",
				"shortage_qty",
				"days_cover",
				"exposure_status",
			],
			order_by="modified desc",
			limit_page_length=500,
		)
	else:
		exposure_rows = []

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


def _serialize_incident_doc(doc) -> dict:
	return {
		"name": doc.name,
		"incident_title": doc.incident_title,
		"item_code": doc.item_code,
		"warehouse": doc.warehouse,
		"status": doc.status,
		"owner_user": doc.owner_user,
		"detected_on": doc.detected_on,
		"resolution_notes": doc.resolution_notes or "",
	}


def _append_incident_event(incident_name: str, event_type: str, details: str | None = None) -> dict:
	event = {
		"incident": incident_name,
		"event_type": event_type,
		"details": details or "",
		"event_at": add_to_date(now_datetime(), days=0, as_string=True),
		"event_by": _resolve_session_user(),
	}
	if _is_test_mode():
		_TEST_INCIDENT_EVENTS.setdefault(incident_name, []).append(event)
		return event

	if _doctype_available("BEI Stockout Incident Event"):
		doc = frappe.get_doc(
			{
				"doctype": "BEI Stockout Incident Event",
				"incident": event["incident"],
				"event_type": event["event_type"],
				"event_at": event["event_at"],
				"event_by": event["event_by"],
				"details": event["details"],
			}
		)
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
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

	if _is_test_mode():
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

	doc = frappe.get_doc(
		{
			"doctype": "BEI Stockout Incident",
			"incident_title": incident_title or f"Stockout risk on {item_code}",
			"item_code": item_code,
			"warehouse": warehouse,
			"status": "Open",
			"owner_user": owner_user,
			"detected_on": add_to_date(now_datetime(), days=0, as_string=True),
		}
	)
	doc.flags.ignore_links = True
	doc.insert(ignore_permissions=True)
	_append_incident_event(doc.name, "Detected", "Incident created")
	return _serialize_incident_doc(doc)


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

	if _is_test_mode():
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
		_append_incident_event(incident_name, _incident_event_type(new_status), note)
		return deepcopy(incident)

	if not _doctype_available("BEI Stockout Incident"):
		frappe.throw(_("BEI Stockout Incident DocType is not available"))
	if not frappe.db.exists("BEI Stockout Incident", incident_name):
		frappe.throw(_("Stockout incident not found"))

	doc = frappe.get_doc("BEI Stockout Incident", incident_name)
	if new_status == "Resolved":
		final_notes = (resolution_notes or note or "").strip()
		if not final_notes:
			frappe.throw(_("resolution_notes is required for Resolved status"))
		doc.resolution_notes = final_notes

	if owner_user:
		doc.owner_user = owner_user

	doc.status = new_status
	doc.flags.ignore_links = True
	doc.save(ignore_permissions=True)
	_append_incident_event(incident_name, _incident_event_type(new_status), note)
	return _serialize_incident_doc(doc)


@frappe.whitelist()
def get_incident_events(incident_name: str):
	if not incident_name:
		frappe.throw(_("incident_name is required"))
	if _is_test_mode():
		return [deepcopy(row) for row in _TEST_INCIDENT_EVENTS.get(incident_name, [])]
	if not _doctype_available("BEI Stockout Incident Event"):
		return []
	return _frappe_get_all(
		"BEI Stockout Incident Event",
		filters={"incident": incident_name},
		fields=["incident", "event_type", "details", "event_at", "event_by"],
		order_by="event_at asc, creation asc",
		limit_page_length=500,
	)


@frappe.whitelist()
def get_stockout_incidents(status: str | None = None):
	if _is_test_mode():
		incidents = [deepcopy(row) for row in _TEST_INCIDENTS]
		if status:
			incidents = [row for row in incidents if row.get("status") == status]
		return {
			"status": status,
			"incidents": incidents,
		}

	if not _doctype_available("BEI Stockout Incident"):
		incidents = []
	else:
		filters = {"status": status} if status else None
		incidents = _frappe_get_all(
			"BEI Stockout Incident",
			filters=filters,
			fields=_INCIDENT_FIELDS,
			order_by="modified desc",
			limit_page_length=500,
		)

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


def _clear_existing_test_dataset() -> dict:
	removed = {
		"risk_profiles_deleted": 0,
		"risk_snapshots_deleted": 0,
		"exposures_deleted": 0,
		"incidents_deleted": 0,
		"incident_events_deleted": 0,
	}
	db = getattr(frappe, "db", None)
	if not db or not hasattr(db, "delete"):
		return removed

	test_incidents = _frappe_get_all(
		"BEI Stockout Incident",
		filters={"incident_title": ["like", "test %"]},
		fields=["name"],
		limit_page_length=2000,
	)
	test_incident_names = [row.get("name") for row in test_incidents if row.get("name")]
	if test_incident_names:
		removed["incident_events_deleted"] = frappe.db.delete(
			"BEI Stockout Incident Event", {"incident": ["in", test_incident_names]}
		)
		removed["incidents_deleted"] = frappe.db.delete("BEI Stockout Incident", {"name": ["in", test_incident_names]})

	removed["exposures_deleted"] = frappe.db.delete(
		"BEI Ingredient Risk Exposure", {"parent_item_code": ["like", "test-%"]}
	)
	removed["risk_snapshots_deleted"] = frappe.db.delete(
		"BEI Inventory Risk Snapshot", {"item_code": ["like", "test-%"]}
	)
	removed["risk_profiles_deleted"] = frappe.db.delete(
		"BEI Inventory Risk Profile", {"item_code": ["like", "test-%"]}
	)
	return removed


def _seed_profile_and_snapshot(item_index: int, horizon_hours: int) -> tuple[str, str]:
	item_code = f"test-item-{item_index:03d}"
	warehouse = "test-warehouse-main"

	if item_index <= 14:
		target_days = 0.6 + (item_index % 3) * 0.4
		demand = 24 + (item_index % 5) * 3
		lead_time = 7
		reliability = 52
	elif item_index <= 30:
		target_days = 1.5 + (item_index % 4) * 0.6
		demand = 18 + (item_index % 6) * 2
		lead_time = 5
		reliability = 62
	elif item_index <= 40:
		target_days = 4.5 + (item_index % 5) * 1.1
		demand = 14 + (item_index % 4) * 2
		lead_time = 3
		reliability = 76
	else:
		target_days = 14.5 + (item_index % 6) * 1.5
		demand = 10 + (item_index % 5) * 1.5
		lead_time = 2
		reliability = 93

	available_qty = round(max(0.0, demand * target_days), 2)
	computed = build_risk_snapshot_row(
		{
			"item_code": item_code,
			"warehouse": warehouse,
			"available_qty": available_qty,
			"avg_daily_demand": demand,
			"lead_time_days": lead_time,
			"supplier_reliability_score": reliability,
		},
		horizon_hours=horizon_hours,
	)

	profile_doc = frappe.get_doc(
		{
			"doctype": "BEI Inventory Risk Profile",
			"item_code": item_code,
			"warehouse": warehouse,
			"supplier": "test-supplier-main",
			"lead_time_days": lead_time,
			"safety_stock_days": 2,
			"supplier_reliability_score": reliability,
			"is_active": 1,
		}
	)
	profile_doc.flags.ignore_links = True
	profile_doc.insert(ignore_permissions=True)

	snapshot_doc = frappe.get_doc(
		{
			"doctype": "BEI Inventory Risk Snapshot",
			"snapshot_date": add_to_date(now_datetime(), days=0, as_string=True).split(" ")[0],
			"item_code": item_code,
			"warehouse": warehouse,
			"available_qty": computed["available_qty"],
			"avg_daily_demand": computed["avg_daily_demand"],
			"days_to_stockout": computed["days_to_stockout"],
			"projected_stockout_at": computed["projected_stockout_at"],
			"risk_score": computed["risk_score"],
			"risk_level": computed["risk_level"],
			"source_reference": f"{TEST_DATA_TAG}-test-dtl",
		}
	)
	snapshot_doc.flags.ignore_links = True
	snapshot_doc.insert(ignore_permissions=True)
	return item_code, snapshot_doc.name


def _seed_exposure_rows(item_code: str, snapshot_name: str, item_index: int) -> int:
	exposure_count = 0
	for ingredient_index in (1, 2):
		ingredient_code = f"test-ingredient-{item_index:03d}-{ingredient_index:02d}"
		required_qty = round(10 + item_index * 0.4 + ingredient_index, 2)

		if item_index <= 14:
			available_qty = 0.0 if ingredient_index == 1 else round(required_qty * 0.35, 2)
		elif item_index <= 30:
			available_qty = round(required_qty * (0.55 if ingredient_index == 1 else 0.75), 2)
		elif item_index <= 40:
			available_qty = round(required_qty * (0.9 if ingredient_index == 1 else 1.05), 2)
		else:
			available_qty = round(required_qty * (1.25 if ingredient_index == 1 else 1.5), 2)

		shortage_qty = round(max(0.0, required_qty - available_qty), 2)
		if shortage_qty > 0 and available_qty <= 0:
			exposure_status = "Critical"
		elif shortage_qty > 0:
			exposure_status = "Watch"
		else:
			exposure_status = "Normal"

		exposure_doc = frappe.get_doc(
			{
				"doctype": "BEI Ingredient Risk Exposure",
				"snapshot": snapshot_name,
				"parent_item_code": item_code,
				"ingredient_item_code": ingredient_code,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"shortage_qty": shortage_qty,
				"days_cover": 999.0 if required_qty <= 0 else round(available_qty / required_qty, 2),
				"exposure_status": exposure_status,
			}
		)
		exposure_doc.flags.ignore_links = True
		exposure_doc.insert(ignore_permissions=True)
		exposure_count += 1

	return exposure_count


def _seed_incidents(item_count: int, incident_count: int) -> dict:
	status_plan = ["Open", "Open", "Open", "Open", "Mitigating", "Mitigating", "Blocked", "Resolved"]
	created = 0
	status_counts = {"Open": 0, "Mitigating": 0, "Blocked": 0, "Resolved": 0}

	for index in range(incident_count):
		status = status_plan[index % len(status_plan)]
		item_code = f"test-item-{(index % item_count) + 1:03d}"
		incident_doc = frappe.get_doc(
			{
				"doctype": "BEI Stockout Incident",
				"incident_title": f"test incident {index + 1:03d} - {status.lower()}",
				"item_code": item_code,
				"warehouse": "test-warehouse-main",
				"status": status,
				"owner_user": "test.warehouse@bebang.ph",
				"detected_on": add_to_date(now_datetime(), days=0, as_string=True),
				"target_resolution_at": add_to_date(now_datetime(), days=2, as_string=True),
				"resolution_notes": "test resolution notes" if status == "Resolved" else "",
			}
		)
		incident_doc.flags.ignore_links = True
		incident_doc.insert(ignore_permissions=True)

		_append_incident_event(incident_doc.name, "Detected", "test incident detected")
		if status != "Open":
			_append_incident_event(incident_doc.name, _incident_event_type(status), f"test status moved to {status}")

		created += 1
		status_counts[status] += 1

	return {"incidents_created": created, "incident_status_counts": status_counts}


def seed_test_inventory_and_dtl_dataset(item_count: int = 50, incident_count: int = 20, horizon_hours: int = 72):
	"""
	Seed persistent S20 test inventory + DTL (days_to_stockout) data.

	All inserted records include the word "test" in item codes, incident titles,
	source references, suppliers, and warehouses.
	"""
	global _FORCE_TEST_MODE
	_FORCE_TEST_MODE = False

	item_count = max(50, cint(item_count or 50))
	incident_count = max(1, cint(incident_count or 20))
	horizon_hours = max(1, cint(horizon_hours or 72))

	if not _doctype_available("BEI Inventory Risk Snapshot"):
		frappe.throw(_("BEI Inventory Risk Snapshot DocType is not available"))

	removed = _clear_existing_test_dataset()

	snapshot_count = 0
	profile_count = 0
	exposure_count = 0
	for item_index in range(1, item_count + 1):
		item_code, snapshot_name = _seed_profile_and_snapshot(item_index=item_index, horizon_hours=horizon_hours)
		snapshot_count += 1
		profile_count += 1
		exposure_count += _seed_exposure_rows(item_code=item_code, snapshot_name=snapshot_name, item_index=item_index)

	incident_results = _seed_incidents(item_count=item_count, incident_count=incident_count)
	frappe.db.commit()

	return {
		"success": True,
		"tag": TEST_DATA_TAG,
		"item_count": item_count,
		"incident_count": incident_count,
		"horizon_hours": horizon_hours,
		"seeded": {
			"risk_profiles": profile_count,
			"risk_snapshots": snapshot_count,
			"exposures": exposure_count,
			"incidents": incident_results["incidents_created"],
			"incident_status_counts": incident_results["incident_status_counts"],
		},
		"removed_previous_test_data": removed,
	}

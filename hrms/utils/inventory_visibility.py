from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe

from hrms.services.sheets_receiver.transforms import INVENTORY_SUMMARY_WAREHOUSE_MAP
from hrms.utils.store_inventory_shadow_sync import load_store_registry
from hrms.utils.supply_chain_contracts import (
	CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
	LEGACY_COMMISSARY_OPERATION_WAREHOUSES,
	TEST_COMMISSARY_OPERATION_WAREHOUSE,
	load_store_buyer_entity_register,
	normalize_lookup_key,
	strip_company_suffix,
)

FACILITY_MODE_WAREHOUSES = "warehouses"
FACILITY_MODE_STORES = "stores"
FACILITY_MODE_ALL = "all"

FACILITY_KIND_WAREHOUSE_OPERATION = "warehouse_operation"
FACILITY_KIND_WAREHOUSE_3PL_HUB = "warehouse_3pl_hub"
FACILITY_KIND_STORE = "store"
FACILITY_KIND_GROUP_NODE = "group_node"
FACILITY_KIND_TEST_FIXTURE = "test_fixture"
FACILITY_KIND_INACTIVE = "inactive"

READ_ONLY_OVERSIGHT_ROLES = {"Area Supervisor", "Regional Manager"}
NETWORK_INVENTORY_ROLES = {
	"Warehouse User",
	"Warehouse Staff",
	"Warehouse Manager",
	"Supply Chain Manager",
	"Logistics Coordinator",
	"System Manager",
	"Administrator",
}
STORE_MODE_ROLES = set(NETWORK_INVENTORY_ROLES)
ALL_MODE_ROLES = set(NETWORK_INVENTORY_ROLES)
STOCK_UPDATE_ROLES = {
	"Warehouse User",
	"Warehouse Staff",
	"Warehouse Manager",
	"Supply Chain Manager",
	"System Manager",
	"Administrator",
}

STORE_STALE_HOURS = 36
STORE_BLOCKED_HOURS = 72

KNOWN_WAREHOUSE_FACILITIES = (
	{
		"kind": FACILITY_KIND_WAREHOUSE_3PL_HUB,
		"display_label": "3MD Logistics – Camangyanan",
		"display_order": 10,
		"aliases": (
			"3MD",
			"3MD Logistics – Camangyanan",
			"3MD Logistics - Camangyanan",
		),
	},
	{
		"kind": FACILITY_KIND_WAREHOUSE_3PL_HUB,
		"display_label": "Jentec Storage Inc.",
		"display_order": 20,
		"aliases": ("JENTEC", "Jentec Storage Inc."),
	},
	{
		"kind": FACILITY_KIND_WAREHOUSE_3PL_HUB,
		"display_label": "Royal Cold Storage – Taytay (RCS)",
		"display_order": 30,
		"aliases": (
			"RCS",
			"Royal Cold Storage – Taytay (RCS)",
			"Royal Cold Storage - Taytay (RCS)",
		),
	},
	{
		"kind": FACILITY_KIND_WAREHOUSE_3PL_HUB,
		"display_label": "Pinnacle Cold Storage Solutions",
		"display_order": 40,
		"aliases": ("PINNACLE", "Pinnacle Cold Storage Solutions"),
	},
	{
		"kind": FACILITY_KIND_WAREHOUSE_OPERATION,
		"display_label": "Shaw BLVD",
		"display_order": 50,
		"aliases": (
			"SHAW",
			"Shaw BLVD",
			CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
			*LEGACY_COMMISSARY_OPERATION_WAREHOUSES,
		),
	},
)


def _lookup_keys(*values: str | None) -> set[str]:
	keys: set[str] = set()
	for value in values:
		normalized = normalize_lookup_key(value)
		if normalized:
			keys.add(normalized)
		stripped = normalize_lookup_key(strip_company_suffix(value))
		if stripped:
			keys.add(stripped)
	return keys


def _parse_dt(value: str | None) -> datetime | None:
	text = str(value or "").strip()
	if not text:
		return None
	candidates = [text]
	if text.endswith("Z"):
		candidates.append(text[:-1] + "+00:00")
	for candidate in candidates:
		try:
			return datetime.fromisoformat(candidate)
		except ValueError:
			continue
	for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
		try:
			return datetime.strptime(text, fmt)
		except ValueError:
			continue
	return None


def _freshness_status(source_mode: str, timestamp: str | None) -> str:
	if source_mode != "mirrored_sheet":
		return "current"

	reference_dt = _parse_dt(timestamp)
	if not reference_dt:
		return "blocked"

	age_hours = (datetime.now() - reference_dt).total_seconds() / 3600.0
	if age_hours >= STORE_BLOCKED_HOURS:
		return "blocked"
	if age_hours >= STORE_STALE_HOURS:
		return "stale"
	return "current"


def _store_lookup() -> dict[str, dict[str, Any]]:
	lookup: dict[str, dict[str, Any]] = {}

	for row in load_store_buyer_entity_register():
		payload = {
			"store_name": row.get("store_name") or strip_company_suffix(row.get("warehouse_docname")),
			"warehouse_docname": row.get("warehouse_docname"),
			"store_type": row.get("store_type") or None,
			"buyer_entity_status": row.get("buyer_entity_status") or None,
			"source_mode": "erp_live",
			"freshness_status": "current",
			"last_sync_at": None,
			"shadow_state": None,
		}
		for key in _lookup_keys(row.get("warehouse_docname"), row.get("store_name")):
			lookup[key] = {**lookup.get(key, {}), **payload}

	for config in load_store_registry():
		state = str(config.state or "shadow_sync").strip() or "shadow_sync"
		source_mode = "mirrored_sheet" if config.sheet_sync_enabled and state == "shadow_sync" else "erp_live"
		last_sync_at = config.last_success_at or config.last_inventory_date or None
		payload = {
			"store_name": config.store_name
			or config.warehouse_name
			or strip_company_suffix(config.warehouse_docname),
			"warehouse_docname": config.warehouse_docname,
			"source_mode": source_mode,
			"freshness_status": _freshness_status(source_mode, last_sync_at),
			"last_sync_at": last_sync_at,
			"shadow_state": state,
			"sheet_sync_enabled": bool(config.sheet_sync_enabled),
		}
		for key in _lookup_keys(config.warehouse_docname, config.warehouse_name, config.store_name):
			lookup[key] = {**lookup.get(key, {}), **payload}

	return lookup


def _warehouse_definition_lookup() -> dict[str, dict[str, Any]]:
	lookup: dict[str, dict[str, Any]] = {}
	for entry in KNOWN_WAREHOUSE_FACILITIES:
		for key in entry["aliases"]:
			lookup[normalize_lookup_key(key)] = entry
	for short_code, label in INVENTORY_SUMMARY_WAREHOUSE_MAP.items():
		lookup[normalize_lookup_key(short_code)] = next(
			entry
			for entry in KNOWN_WAREHOUSE_FACILITIES
			if entry["display_label"] == ("Shaw BLVD" if short_code == "SHAW" else label)
		)
	return lookup


def _area_name_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
	if not getattr(getattr(frappe, "db", None), "has_column", None):
		return {}
	try:
		if not frappe.db.has_column("Warehouse", "custom_area_supervisor"):
			return {}
	except Exception:
		return {}

	user_ids = sorted(
		{
			str(row.get("custom_area_supervisor") or "").strip()
			for row in rows
			if str(row.get("custom_area_supervisor") or "").strip()
		}
	)
	if not user_ids:
		return {}

	try:
		employees = frappe.get_all(
			"Employee",
			filters={"user_id": ["in", user_ids], "status": "Active"},
			fields=["user_id", "employee_name"],
			limit_page_length=max(20, len(user_ids) * 2),
		)
	except Exception:
		return {}

	return {
		str(row.get("user_id") or "").strip(): str(row.get("employee_name") or "").strip()
		for row in employees
		if str(row.get("user_id") or "").strip()
	}


def _resolve_branch_warehouse(branch: str | None) -> str | None:
	if not branch:
		return None
	if frappe.db.exists("Warehouse", branch):
		return branch
	warehouse_with_company = f"{branch} - BEI"
	if frappe.db.exists("Warehouse", warehouse_with_company):
		return warehouse_with_company
	warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": branch}, "name")
	if warehouse:
		return warehouse
	return None


def get_inventory_facility_catalog() -> list[dict[str, Any]]:
	fields = ["name", "warehouse_name", "company", "is_group", "disabled"]
	try:
		if frappe.db.has_column("Warehouse", "custom_area_supervisor"):
			fields.append("custom_area_supervisor")
	except Exception:
		pass

	warehouse_rows = frappe.get_all(
		"Warehouse",
		filters={"disabled": 0},
		fields=fields,
		order_by="warehouse_name asc, name asc",
		limit_page_length=1000,
	)
	store_lookup = _store_lookup()
	warehouse_lookup = _warehouse_definition_lookup()
	area_lookup = _area_name_lookup(warehouse_rows)

	catalog: list[dict[str, Any]] = []
	for row in warehouse_rows:
		warehouse = row.get("name")
		warehouse_name = row.get("warehouse_name") or strip_company_suffix(warehouse)
		keys = _lookup_keys(warehouse, warehouse_name)

		if row.get("is_group"):
			facility_kind = FACILITY_KIND_GROUP_NODE
			display_label = warehouse_name
			display_order = 9000
		elif any(key in _lookup_keys(TEST_COMMISSARY_OPERATION_WAREHOUSE, "test commissary") for key in keys):
			facility_kind = FACILITY_KIND_TEST_FIXTURE
			display_label = warehouse_name
			display_order = 9100
		else:
			store_meta = next((store_lookup[key] for key in keys if key in store_lookup), None)
			warehouse_meta = next((warehouse_lookup[key] for key in keys if key in warehouse_lookup), None)

			if store_meta:
				facility_kind = FACILITY_KIND_STORE
				display_label = store_meta.get("store_name") or warehouse_name
				display_order = 2000
			elif warehouse_meta:
				facility_kind = warehouse_meta["kind"]
				display_label = warehouse_meta["display_label"]
				display_order = warehouse_meta["display_order"]
			else:
				joined_keys = " ".join(sorted(keys))
				if any(
					token in joined_keys
					for token in ("storage", "logistics", "cold", "jentec", "pinnacle", "3md", "rcs")
				):
					facility_kind = FACILITY_KIND_WAREHOUSE_3PL_HUB
					display_label = warehouse_name
					display_order = 800
				elif str(row.get("company") or "").strip() == "Bebang Kitchen Inc.":
					facility_kind = FACILITY_KIND_WAREHOUSE_OPERATION
					display_label = warehouse_name
					display_order = 700
				else:
					facility_kind = FACILITY_KIND_INACTIVE
					display_label = warehouse_name
					display_order = 9999

		if facility_kind in {FACILITY_KIND_GROUP_NODE, FACILITY_KIND_TEST_FIXTURE, FACILITY_KIND_INACTIVE}:
			continue

		store_meta = next((store_lookup[key] for key in keys if key in store_lookup), {})
		source_mode = store_meta.get("source_mode") if facility_kind == FACILITY_KIND_STORE else "erp_live"
		freshness_status = (
			store_meta.get("freshness_status") if facility_kind == FACILITY_KIND_STORE else "current"
		)
		last_sync_at = store_meta.get("last_sync_at") if facility_kind == FACILITY_KIND_STORE else None
		area_user = str(row.get("custom_area_supervisor") or "").strip()
		area_label = area_lookup.get(area_user) or area_user or None

		catalog.append(
			{
				"warehouse": warehouse,
				"warehouse_name": display_label,
				"warehouse_docname": warehouse,
				"source_warehouse_name": warehouse_name,
				"facility_kind": facility_kind,
				"facility_mode": FACILITY_MODE_STORES
				if facility_kind == FACILITY_KIND_STORE
				else FACILITY_MODE_WAREHOUSES,
				"display_order": display_order,
				"company": row.get("company"),
				"area_label": area_label,
				"source_mode": source_mode or "erp_live",
				"freshness_status": freshness_status or "current",
				"last_sync_at": last_sync_at,
				"shadow_state": store_meta.get("shadow_state"),
				"store_type": store_meta.get("store_type"),
				"buyer_entity_status": store_meta.get("buyer_entity_status"),
			}
		)

	mode_rank = {FACILITY_MODE_WAREHOUSES: 0, FACILITY_MODE_STORES: 1}
	catalog.sort(
		key=lambda row: (
			mode_rank.get(row["facility_mode"], 99),
			row["display_order"],
			str(row["warehouse_name"]).lower(),
		)
	)
	return catalog


def get_inventory_scope_context() -> dict[str, Any]:
	user = frappe.session.user
	user_roles = set(frappe.get_roles(user))
	catalog = get_inventory_facility_catalog()
	warehouse_facilities = [row for row in catalog if row["facility_mode"] == FACILITY_MODE_WAREHOUSES]
	store_facilities = [row for row in catalog if row["facility_mode"] == FACILITY_MODE_STORES]

	allowed_modes = [FACILITY_MODE_WAREHOUSES]
	if user_roles.intersection(STORE_MODE_ROLES):
		allowed_modes.append(FACILITY_MODE_STORES)
	if user_roles.intersection(ALL_MODE_ROLES):
		allowed_modes.append(FACILITY_MODE_ALL)

	can_write = bool(user_roles.intersection(STOCK_UPDATE_ROLES))
	can_view_all = bool(user_roles.intersection(NETWORK_INVENTORY_ROLES | READ_ONLY_OVERSIGHT_ROLES))

	employee = frappe.db.get_value(
		"Employee",
		{"user_id": user, "status": "Active"},
		["name", "branch", "employee_name"],
		as_dict=True,
	)
	default_warehouse = _resolve_branch_warehouse(employee.branch) if employee and employee.branch else None
	if default_warehouse and default_warehouse not in {row["warehouse"] for row in warehouse_facilities}:
		default_warehouse = None
	if not default_warehouse and warehouse_facilities:
		default_warehouse = warehouse_facilities[0]["warehouse"]

	if user_roles.intersection(READ_ONLY_OVERSIGHT_ROLES):
		scope_source = "oversight_read_only"
	elif can_write:
		scope_source = "warehouse_operator"
	else:
		scope_source = "inventory_view_only"

	return {
		"user": user,
		"user_roles": sorted(user_roles),
		"can_view_all": can_view_all,
		"can_write": can_write,
		"read_only": not can_write,
		"default_warehouse": default_warehouse,
		"default_mode": FACILITY_MODE_WAREHOUSES,
		"scope_source": scope_source,
		"allowed_modes": allowed_modes,
		"warehouses": warehouse_facilities,
		"warehouse_facilities": warehouse_facilities,
		"store_facilities": store_facilities,
		"facilities": catalog,
		"warehouse_names": {row["warehouse"] for row in warehouse_facilities},
		"mode_contract": {
			"allowed_modes": allowed_modes,
			"default_mode": FACILITY_MODE_WAREHOUSES,
			"read_only": not can_write,
			"store_direct_column_limit": 12,
		},
	}


def _requested_tokens(facility_ids: list[str] | tuple[str, ...] | str | None) -> set[str]:
	if facility_ids is None:
		return set()
	if isinstance(facility_ids, str):
		values = [part.strip() for part in facility_ids.split(",")]
	else:
		values = [str(part or "").strip() for part in facility_ids]
	return {token for value in values for token in _lookup_keys(value) if value}


def resolve_inventory_requested_warehouses(scope: dict[str, Any], warehouse: str | None = None) -> list[str]:
	allowed = sorted(scope.get("warehouse_names") or [])
	if not allowed:
		return []
	if not warehouse:
		return allowed

	requested = _requested_tokens(warehouse)
	for candidate in scope.get("warehouse_facilities", []):
		if requested.intersection(_lookup_keys(candidate.get("warehouse"), candidate.get("warehouse_name"))):
			return [candidate["warehouse"]]

	frappe.throw(
		frappe._("You do not have inventory access to warehouse {0}").format(warehouse),
		frappe.PermissionError,
	)
	return []


def resolve_inventory_requested_facilities(
	scope: dict[str, Any],
	facility_mode: str | None = None,
	facility_ids: list[str] | tuple[str, ...] | str | None = None,
) -> list[dict[str, Any]]:
	mode = (facility_mode or FACILITY_MODE_WAREHOUSES).strip().lower()
	if mode not in scope.get("allowed_modes", []):
		frappe.throw(
			frappe._("You do not have permission to use facility mode {0}").format(mode),
			frappe.PermissionError,
		)

	if mode == FACILITY_MODE_WAREHOUSES:
		base_rows = list(scope.get("warehouse_facilities") or [])
	elif mode == FACILITY_MODE_STORES:
		base_rows = list(scope.get("store_facilities") or [])
	else:
		base_rows = list(scope.get("warehouse_facilities") or []) + list(scope.get("store_facilities") or [])

	requested = _requested_tokens(facility_ids)
	if not requested:
		return base_rows

	selected = [
		row
		for row in base_rows
		if requested.intersection(_lookup_keys(row.get("warehouse"), row.get("warehouse_name")))
	]
	if not selected:
		frappe.throw(
			frappe._("No accessible facilities matched the requested selection."), frappe.PermissionError
		)
	return selected

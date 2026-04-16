from __future__ import annotations

import time
from typing import Any

import frappe


# S200: TTL cache (30 seconds) replaces permanent @lru_cache.
# Changes to Company/Warehouse take effect within 30 seconds — no restart needed.
# on_update hooks (registered in hooks.py) call clear_cache() for immediate effect.
_CACHE_TTL = 30
_mapping_cache: dict[str, dict[str, Any]] = {}
_mapping_cache_ts: float = 0
_mapping_by_id_cache: dict[int, dict[str, Any]] = {}
_mapping_by_id_cache_ts: float = 0


def clear_cache(doc=None, method=None):
	"""Clear the TTL cache + auto-sync Supabase stores table.

	Called by on_update hooks for Company/Warehouse.
	When a Company with mosaic_location_id is saved, auto-upserts the Supabase
	`stores` table so the store appears in Analytics automatically.
	"""
	global _mapping_cache, _mapping_cache_ts, _mapping_by_id_cache, _mapping_by_id_cache_ts
	_mapping_cache = {}
	_mapping_cache_ts = 0
	_mapping_by_id_cache = {}
	_mapping_by_id_cache_ts = 0

	# S200: Auto-sync Supabase stores table when Company has mosaic_location_id
	if doc and getattr(doc, "doctype", None) == "Company":
		_sync_supabase_store(doc)


def _sync_supabase_store(doc):
	"""Upsert Supabase `stores` table when Company has mosaic_location_id.

	Runs in background (enqueue) to avoid blocking the Company save.
	"""
	lid = getattr(doc, "mosaic_location_id", None)
	if not lid:
		return
	entity_cat = getattr(doc, "entity_category", "")
	if entity_cat not in ("Store", "Commissary"):
		return
	try:
		lid_int = int(lid)
	except (TypeError, ValueError):
		return
	store_name = _store_prefix(doc.name)
	frappe.enqueue(
		_do_supabase_store_upsert,
		queue="short",
		location_id=lid_int,
		store_name=store_name,
		company_name=doc.name,
	)


def _do_supabase_store_upsert(location_id: int, store_name: str, company_name: str):
	"""Background job: upsert Supabase stores table.

	The `stores` table has a NOT NULL constraint on `go_live_date`, so we must
	provide all required fields. Uses PostgREST upsert (merge-duplicates) on
	the `location_id` primary key.
	"""
	try:
		from hrms.utils.supabase import supabase_headers, SUPABASE_URL
		import requests as _requests

		url = f"{SUPABASE_URL}/rest/v1/stores"
		headers = supabase_headers(prefer="resolution=merge-duplicates,return=representation")

		# Read Company fields for the upsert payload
		ownership = frappe.db.get_value("Company", company_name, "store_ownership_type") or "Managed Franchise"
		store_type_map = {"JV": "Company-Owned", "Company Owned": "Company-Owned"}
		store_type = store_type_map.get(ownership, "Managed Franchise")

		payload = {
			"location_id": location_id,
			"store_name": store_name,
			"erpnext_company": company_name,
			"legal_entity": company_name.split(" - ", 1)[1] if " - " in company_name else company_name,
			"mosaic_name": company_name.split(" - ", 1)[1] if " - " in company_name else company_name,
			"store_type": store_type,
			"credential_group": "New Store",
			"go_live_date": frappe.utils.today(),
			"is_active": True,
		}
		r = _requests.post(url, headers=headers, json=payload, timeout=15)
		if r.status_code in (200, 201):
			frappe.logger().info(f"S200: Supabase stores upsert OK — LID {location_id} = {store_name}")
		else:
			frappe.log_error(
				title="S200: Supabase stores upsert failed",
				message=f"LID {location_id}, store={store_name}, company={company_name}, status={r.status_code}, body={r.text[:500]}",
			)
	except Exception as e:
		frappe.log_error(
			title="S200: Supabase stores upsert error",
			message=f"LID {location_id}, store={store_name}: {e}",
		)


def normalize_store_key(value: str | None) -> str:
	text = str(value or "").strip().lower().replace("\u2019", "'")
	return " ".join(text.split())


def _warehouse_name_base(value: str | None) -> str:
	text = str(value or "").strip()
	if " - " in text:
		text = text.split(" - ", 1)[0]
	return text


def _store_prefix(company_name: str) -> str:
	"""Extract store display name from Company docname.

	S199 convention: all store Companies are named '<STORE> - <CORP>' in ALL CAPS.
	This function returns the store prefix (everything before ' - ').
	For Companies without ' - ' (shouldn't exist for stores post-S199), returns
	the full name.
	"""
	if " - " in company_name:
		return company_name.split(" - ", 1)[0]
	return company_name


def load_sales_location_mapping() -> dict[str, dict[str, Any]]:
	"""Build store-key -> row mapping from Company.mosaic_location_id + child Warehouses.

	S200: Uses TTL cache (30s) instead of permanent @lru_cache. Derives store
	display name from Company docname prefix (SSOT) instead of Warehouse.warehouse_name.
	Filters by entity_category to exclude holding companies.

	Returns a dict keyed by normalized store names mapping to
	{warehouse_name, warehouse_record_name, company, location_id}.
	"""
	global _mapping_cache, _mapping_cache_ts
	now = time.time()
	if _mapping_cache and (now - _mapping_cache_ts) < _CACHE_TTL:
		return _mapping_cache

	# S200 P1-T5: Only include Store + Commissary Companies, exclude holding/archived
	companies = frappe.get_all(
		"Company",
		filters={
			"mosaic_location_id": ["is", "set"],
			"entity_category": ["in", ["Store", "Commissary"]],
			"operational_status": ["in", ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]],
		},
		fields=["name", "mosaic_location_id"],
	)
	co_location: dict[str, int] = {}
	for co in companies:
		lid = co.get("mosaic_location_id")
		if lid:
			try:
				co_location[co["name"]] = int(lid)
			except (TypeError, ValueError):
				pass

	if not co_location:
		_mapping_cache = {}
		_mapping_cache_ts = now
		return _mapping_cache

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"company": ["in", list(co_location.keys())],
			"is_group": 0,
			"disabled": 0,
		},
		fields=["name", "warehouse_name", "company"],
	)

	# Structural warehouse names that are NOT store-facing (S199 hotfix PR #596)
	_STRUCTURAL_NAMES = {
		"STORES", "FINISHED GOODS", "GOODS IN TRANSIT", "WORK IN PROGRESS",
		"ALL WAREHOUSES", "RAW MATERIALS", "IN TRANSIT",
	}

	mapping: dict[str, dict[str, Any]] = {}
	for wh in warehouses:
		wh_name = (wh.get("warehouse_name") or wh.get("name") or "").strip()
		if wh_name.upper() in _STRUCTURAL_NAMES:
			continue
		company = wh.get("company") or ""
		location_id = co_location.get(company)
		if not location_id:
			continue
		# S200 P1-T2: Use Company store prefix as display name (SSOT)
		store_display = _store_prefix(company)
		payload = {
			"warehouse_name": store_display,
			"warehouse_record_name": wh.get("name") or "",
			"company": company,
			"location_id": location_id,
		}
		for key_src in (
			wh.get("warehouse_name"),
			wh.get("name"),
			_warehouse_name_base(wh.get("name")),
			store_display,
		):
			key = normalize_store_key(key_src)
			if key:
				mapping[key] = payload

	_mapping_cache = mapping
	_mapping_cache_ts = now
	return mapping


def lookup_sales_location(
	warehouse_name: str | None = None,
	warehouse_record_name: str | None = None,
) -> dict[str, Any] | None:
	mapping = load_sales_location_mapping()
	for value in (warehouse_record_name, warehouse_name):
		key = normalize_store_key(value)
		if key and key in mapping:
			return mapping[key]
	return None


def lookup_location_id(
	warehouse_name: str | None = None,
	warehouse_record_name: str | None = None,
) -> int | None:
	match = lookup_sales_location(warehouse_name=warehouse_name, warehouse_record_name=warehouse_record_name)
	return int(match["location_id"]) if match else None


def load_sales_location_mapping_by_id() -> dict[int, dict[str, Any]]:
	global _mapping_by_id_cache, _mapping_by_id_cache_ts
	now = time.time()
	if _mapping_by_id_cache and (now - _mapping_by_id_cache_ts) < _CACHE_TTL:
		return _mapping_by_id_cache

	mapping: dict[int, dict[str, Any]] = {}
	for row in load_sales_location_mapping().values():
		location_id = int(row["location_id"])
		if location_id not in mapping:
			mapping[location_id] = row

	_mapping_by_id_cache = mapping
	_mapping_by_id_cache_ts = now
	return mapping


def lookup_store_name_by_location_id(location_id: int | str | None) -> str | None:
	try:
		key = int(location_id or 0)
	except (TypeError, ValueError):
		return None
	if not key:
		return None
	match = load_sales_location_mapping_by_id().get(key)
	if not match:
		return None
	return str(match.get("warehouse_name") or match.get("warehouse_record_name") or "").strip() or None

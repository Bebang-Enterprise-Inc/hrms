from __future__ import annotations

from functools import lru_cache
from typing import Any

import frappe


def normalize_store_key(value: str | None) -> str:
	text = str(value or "").strip().lower().replace("\u2019", "'")
	return " ".join(text.split())


def _warehouse_name_base(value: str | None) -> str:
	text = str(value or "").strip()
	if " - " in text:
		text = text.split(" - ", 1)[0]
	return text


@lru_cache(maxsize=1)
def load_sales_location_mapping() -> dict[str, dict[str, Any]]:
	"""Build store-key -> row mapping from Company.mosaic_location_id + child Warehouses.

	Returns a dict keyed by normalized store names (warehouse_name, warehouse docname,
	warehouse_name prefix) mapping to {warehouse_name, warehouse_record_name, company,
	location_id}.  This is the Frappe-native replacement for the CSV fixture.
	"""
	companies = frappe.get_all(
		"Company",
		filters={"mosaic_location_id": ["is", "set"]},
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
		return {}

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"company": ["in", list(co_location.keys())],
			"is_group": 0,
			"disabled": 0,
		},
		fields=["name", "warehouse_name", "company"],
	)

	# Structural warehouse names that are NOT store-facing — must be excluded
	# to prevent "Work In Progress", "Finished Goods", etc. from appearing
	# in the Analytics Store Leaderboard.
	_STRUCTURAL_NAMES = {
		"Stores", "Finished Goods", "Goods In Transit", "Work In Progress",
		"All Warehouses", "Raw Materials", "In Transit",
	}

	mapping: dict[str, dict[str, Any]] = {}
	for wh in warehouses:
		wh_name = (wh.get("warehouse_name") or wh.get("name") or "").strip()
		if wh_name in _STRUCTURAL_NAMES:
			continue
		company = wh.get("company") or ""
		location_id = co_location.get(company)
		if not location_id:
			continue
		payload = {
			"warehouse_name": wh.get("warehouse_name") or wh.get("name") or "",
			"warehouse_record_name": wh.get("name") or "",
			"company": company,
			"location_id": location_id,
		}
		for key_src in (
			wh.get("warehouse_name"),
			wh.get("name"),
			_warehouse_name_base(wh.get("name")),
		):
			key = normalize_store_key(key_src)
			if key:
				mapping[key] = payload
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


@lru_cache(maxsize=1)
def load_sales_location_mapping_by_id() -> dict[int, dict[str, Any]]:
	mapping: dict[int, dict[str, Any]] = {}
	for row in load_sales_location_mapping().values():
		location_id = int(row["location_id"])
		if location_id not in mapping:
			mapping[location_id] = row
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

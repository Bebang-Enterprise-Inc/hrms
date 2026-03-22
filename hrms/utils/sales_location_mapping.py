from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

MAPPING_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sales_dashboard_store_mapping.csv"


def normalize_store_key(value: str | None) -> str:
	text = str(value or "").strip().lower().replace("’", "'")
	return " ".join(text.split())


def _record_name_base(value: str | None) -> str:
	text = str(value or "").strip()
	if " - " in text:
		text = text.split(" - ", 1)[0]
	return text


def _candidate_keys(row: dict[str, Any]) -> list[str]:
	keys = [
		row.get("warehouse_name"),
		row.get("warehouse_record_name"),
		_record_name_base(row.get("warehouse_record_name")),
	]
	return [normalize_store_key(key) for key in keys if normalize_store_key(key)]


@lru_cache(maxsize=1)
def load_sales_location_mapping() -> dict[str, dict[str, Any]]:
	mapping: dict[str, dict[str, Any]] = {}
	with MAPPING_PATH.open("r", encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			payload = dict(row)
			payload["location_id"] = int(payload["location_id"])
			for key in _candidate_keys(payload):
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

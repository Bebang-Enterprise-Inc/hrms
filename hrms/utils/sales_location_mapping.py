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


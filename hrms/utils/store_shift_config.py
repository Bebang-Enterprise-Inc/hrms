from __future__ import annotations

from copy import deepcopy

from hrms.utils.supply_chain_contracts import get_preferred_commissary_warehouses

DEFAULT_SHIFT_OPTIONS = [
	{
		"shift_type_name": "Opening",
		"label": "Opening",
		"shift_start": "09:30",
		"shift_end": "18:30",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "blue",
	},
	{
		"shift_type_name": "Mid",
		"label": "Mid",
		"shift_start": "12:00",
		"shift_end": "20:00",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "green",
	},
	{
		"shift_type_name": "Closing",
		"label": "Closing",
		"shift_start": "14:00",
		"shift_end": "22:30",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "orange",
	},
	{
		"shift_type_name": "Off",
		"label": "Off",
		"shift_start": "",
		"shift_end": "",
		"hours": 0,
		"is_off": 1,
		"ends_next_day": 0,
		"color": "gray",
	},
]

COMMISSARY_SHIFT_OPTIONS = [
	{
		"shift_type_name": "Commissary - Dawn",
		"label": "Dawn",
		"shift_start": "03:00",
		"shift_end": "12:00",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "purple",
	},
	{
		"shift_type_name": "Commissary - Morning",
		"label": "Morning",
		"shift_start": "06:00",
		"shift_end": "15:00",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "blue",
	},
	{
		"shift_type_name": "Commissary - Afternoon",
		"label": "Afternoon",
		"shift_start": "14:00",
		"shift_end": "23:00",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 0,
		"color": "green",
	},
	{
		"shift_type_name": "Commissary - Night",
		"label": "Night",
		"shift_start": "22:00",
		"shift_end": "07:00",
		"hours": 8,
		"is_off": 0,
		"ends_next_day": 1,
		"color": "red",
	},
	DEFAULT_SHIFT_OPTIONS[-1],
]

NAIA_SHIFT_OPTIONS = [
	DEFAULT_SHIFT_OPTIONS[0],
	DEFAULT_SHIFT_OPTIONS[2],
	DEFAULT_SHIFT_OPTIONS[3],
]


def _normalized_store_name(store_name: str | None) -> str:
	return (store_name or "").strip().upper()


def _normalized_commissary_keys() -> set[str]:
	keys = {"COMMISSARY", "SHAW BLVD", "SHAW BLVD - BKI"}
	for warehouse in get_preferred_commissary_warehouses(include_legacy=True):
		normalized = _normalized_store_name(warehouse)
		if normalized.startswith("TEST-"):
			continue
		keys.add(normalized)
		keys.add(normalized.replace(" - BEI", "").replace(" - BKI", "").strip())
	return {key for key in keys if key}


def is_commissary_store(store_name: str | None) -> bool:
	normalized = _normalized_store_name(store_name)
	return "COMMISSARY" in normalized or normalized in _normalized_commissary_keys()


def get_shift_options_for_store(store_name: str | None) -> list[dict]:
	normalized = _normalized_store_name(store_name)

	if is_commissary_store(normalized):
		return deepcopy(COMMISSARY_SHIFT_OPTIONS)
	if "NAIA" in normalized:
		return deepcopy(NAIA_SHIFT_OPTIONS)
	return deepcopy(DEFAULT_SHIFT_OPTIONS)

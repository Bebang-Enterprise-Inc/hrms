from __future__ import annotations

from hrms.utils.sales_location_mapping import (
	_warehouse_name_base,
	normalize_store_key,
)


def test_normalize_store_key_collapses_whitespace():
	assert normalize_store_key("  SM  Manila  ") == "sm manila"


def test_normalize_store_key_curly_quote():
	assert normalize_store_key("D\u2019verde Laguna") == "d'verde laguna"


def test_warehouse_name_base_strips_suffix():
	assert _warehouse_name_base("SM Megamall - Bebang Enterprise Inc.") == "SM Megamall"
	assert _warehouse_name_base("NAIA T3") == "NAIA T3"

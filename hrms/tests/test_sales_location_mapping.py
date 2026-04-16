from __future__ import annotations

from hrms.utils.sales_location_mapping import (
	_store_prefix,
	_warehouse_name_base,
	clear_cache,
	normalize_store_key,
)


def test_normalize_store_key_collapses_whitespace():
	assert normalize_store_key("  SM  Manila  ") == "sm manila"


def test_normalize_store_key_curly_quote():
	assert normalize_store_key("D\u2019verde Laguna") == "d'verde laguna"


def test_warehouse_name_base_strips_suffix():
	assert _warehouse_name_base("SM Megamall - Bebang Enterprise Inc.") == "SM Megamall"
	assert _warehouse_name_base("NAIA T3") == "NAIA T3"


def test_store_prefix_extracts_store_name():
	assert _store_prefix("SM MEGAMALL - BEBANG ENTERPRISE INC.") == "SM MEGAMALL"
	assert _store_prefix("NAIA T3 - HALO-HALO TERMINAL FOOD CORP.") == "NAIA T3"
	assert _store_prefix("D'VERDE CALAMBA - TAJ FOOD CORP.") == "D'VERDE CALAMBA"


def test_store_prefix_no_separator():
	# Companies without " - " return the full name
	assert _store_prefix("BEBANG KITCHEN INC.") == "BEBANG KITCHEN INC."


def test_clear_cache_resets_globals():
	import hrms.utils.sales_location_mapping as mod
	mod._mapping_cache = {"test": {}}
	mod._mapping_cache_ts = 999999
	mod._mapping_by_id_cache = {1: {}}
	mod._mapping_by_id_cache_ts = 999999
	clear_cache()
	assert mod._mapping_cache == {}
	assert mod._mapping_cache_ts == 0
	assert mod._mapping_by_id_cache == {}
	assert mod._mapping_by_id_cache_ts == 0

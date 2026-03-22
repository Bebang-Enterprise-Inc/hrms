import importlib.util
import pathlib
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _load_builder_module():
	file_path = ROOT / "hrms" / "utils" / "store_order_demand_snapshot.py"
	spec = importlib.util.spec_from_file_location(
		"store_order_demand_snapshot_under_test",
		file_path,
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_resolve_product_mapping_prefers_explicit_component_recipe_policy():
	builder = _load_builder_module()

	mapping = builder.resolve_product_mapping(
		product_name="Banana Cinnamon Con Yelo",
		product_code="136615",
		fg_display_by_norm={builder.normalize_name("BANANA CINNAMON"): "BANANA CINNAMON"},
		crosswalk_by_norm={builder.normalize_name("Banana Cinnamon Con Yelo"): "BANANA CINNAMON"},
		policies_by_code={},
		policies_by_name={
			builder.normalize_name("Banana Cinnamon Con Yelo"): {
				"product_name": "Banana Cinnamon Con Yelo",
				"product_code": "",
				"policy_type": "component_recipe",
				"target_key": "FULL-BANANA-CINNAMON",
				"note": "explicit test policy",
			}
		},
		component_recipes_by_key={
			"FULL-BANANA-CINNAMON": [
				{
					"component_item_code": "FG020",
					"component_item_name": "FROZEN ICE MILK",
					"qty_per_fg": 0.124,
				}
			]
		},
	)

	assert mapping["status"] == "mapped"
	assert mapping["target_type"] == "component_recipe"
	assert mapping["target_key"] == "FULL-BANANA-CINNAMON"
	assert mapping["mapping_method"] == "explicit_component_recipe"
	assert mapping["component_rows"][0]["component_item_code"] == "FG020"


def test_fetch_pos_web_product_rows_aggregates_duplicates():
	builder = _load_builder_module()

	builder._get_optional_secret = lambda *_args, **_kwargs: ""
	builder._fetch_channel_product_rows_via_rest = lambda **kwargs: [
		{
			"business_date": "2026-03-08",
			"channel": kwargs["channel"],
			"store_name": "Test Store",
			"store_code": "TST",
			"product_code": "136615",
			"product_name": "Banana Cinnamon Con Yelo",
			"qty_sold": 1,
			"net_sales_amount": 100.0,
		},
		{
			"business_date": "2026-03-08",
			"channel": kwargs["channel"],
			"store_name": "Test Store",
			"store_code": "TST",
			"product_code": "136615",
			"product_name": "Banana Cinnamon Con Yelo",
			"qty_sold": 2,
			"net_sales_amount": 200.0,
		},
	]

	rows = builder.fetch_pos_web_product_rows(date(2026, 3, 1), date(2026, 3, 8))

	assert len(rows) == 2
	assert {row["channel"] for row in rows} == {"POS", "Web"}
	assert all(row["qty_sold"] == 3 for row in rows)
	assert all(row["net_sales_amount"] == 300.0 for row in rows)


def test_build_outputs_tracks_explicit_exclusions_separately():
	builder = _load_builder_module()

	builder.load_bom_catalog = lambda: ({}, {}, {})
	builder.load_product_policy_catalog = lambda: (
		{},
		{
			builder.normalize_name("Banana Cinnamon Con Yelo"): {
				"product_name": "Banana Cinnamon Con Yelo",
				"product_code": "",
				"policy_type": "component_recipe",
				"target_key": "FULL-BANANA-CINNAMON",
				"note": "explicit test policy",
			},
			builder.normalize_name("Bottled Water"): {
				"product_name": "Bottled Water",
				"product_code": "",
				"policy_type": "exclude",
				"target_key": "NON_WAREHOUSE_PRODUCT",
				"note": "no mapped stock item",
			},
		},
	)
	builder.load_component_recipe_catalog = lambda: {
		"FULL-BANANA-CINNAMON": [
			{
				"component_item_code": "FG020",
				"component_item_name": "FROZEN ICE MILK",
				"qty_per_fg": 0.124,
			}
		]
	}
	builder.fetch_pos_web_product_rows = lambda *_args: [
		{
			"business_date": "2026-03-08",
			"channel": "POS",
			"store_name": "Test Store",
			"store_code": "TST",
			"product_code": "136615",
			"product_name": "Banana Cinnamon Con Yelo",
			"qty_sold": 2,
			"net_sales_amount": 335.72,
		},
		{
			"business_date": "2026-03-08",
			"channel": "POS",
			"store_name": "Test Store",
			"store_code": "TST",
			"product_code": "999999",
			"product_name": "Bottled Water",
			"qty_sold": 1,
			"net_sales_amount": 20.0,
		},
	]
	builder.load_foodpanda_product_rows = lambda: []

	outputs = builder.build_outputs(snapshot_date=date(2026, 3, 9), lookback_days=7)

	assert len(outputs["product_daily_rows"]) == 1
	assert len(outputs["excluded_rows"]) == 1
	assert len(outputs["unmapped_rows"]) == 0
	assert outputs["excluded_rows"][0]["product_name"] == "Bottled Water"
	assert outputs["item_daily_rows"][0]["item_code"] == "FG020"
	assert outputs["item_daily_rows"][0]["demand_qty"] == 0.248
	assert {row["resolution_status"] for row in outputs["mapping_audit_rows"]} == {
		"excluded",
		"mapped",
	}


def test_live_fixture_maps_pop_lamig_to_component_recipe():
	builder = _load_builder_module()

	policies_by_code, policies_by_name = builder.load_product_policy_catalog()
	component_recipes_by_key = builder.load_component_recipe_catalog()

	mapping = builder.resolve_product_mapping(
		product_name="Pop Lamig",
		product_code="174220",
		fg_display_by_norm={},
		crosswalk_by_norm={},
		policies_by_code=policies_by_code,
		policies_by_name=policies_by_name,
		component_recipes_by_key=component_recipes_by_key,
	)

	assert mapping["status"] == "mapped"
	assert mapping["target_type"] == "component_recipe"
	assert mapping["target_key"] == "POP-LAMIG"
	assert mapping["mapping_method"] == "explicit_component_recipe"

	component_qty_by_code = {
		row["component_item_code"]: row["qty_per_fg"]
		for row in mapping["component_rows"]
	}
	assert component_qty_by_code["PM100"] == 0.006024
	assert component_qty_by_code["PM070"] == 0.000333
	assert component_qty_by_code["RM203"] == 0.026

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_weather_sync_module(alias: str):
	spec = importlib.util.spec_from_file_location(alias, ROOT / "scripts" / "sync_weather_to_supabase.py")
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_business_impact_treats_long_light_showers_as_wet():
	module = _load_weather_sync_module("weather_sync_semantics_light_rain")

	result = module.calculate_business_impact(
		max_temp=29.0,
		total_precipitation=2.0,
		max_hourly_precipitation=1.8,
		rain_hours=7,
		weather_code=80,
		storm_flag=False,
	)

	assert result == "wet"


def test_business_impact_keeps_heavy_sustained_rain_disruptive():
	module = _load_weather_sync_module("weather_sync_semantics_heavy_rain")

	result = module.calculate_business_impact(
		max_temp=28.0,
		total_precipitation=14.0,
		max_hourly_precipitation=4.5,
		rain_hours=6,
		weather_code=63,
		storm_flag=False,
	)

	assert result == "disruptive_rain"

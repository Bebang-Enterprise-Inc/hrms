#!/usr/bin/env python3
"""
Sync weather data from Open-Meteo into Supabase daily and hourly weather tables.

This script:
1. Reads store coordinates from WAREHOUSE_TREE.csv
2. Resolves Mosaic location_id from the shared sales dashboard mapping
3. Groups nearby stores to reduce provider calls
4. Fetches daily + hourly weather for each weather group
5. Upserts into daily_weather and weather_hourly
6. Refreshes the sales_dashboard_weather_daily_features materialized view
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[1]


def _load_lookup_sales_location():
	spec = importlib.util.spec_from_file_location(
		"sales_location_mapping_sync",
		ROOT / "hrms" / "utils" / "sales_location_mapping.py",
	)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module.lookup_sales_location


lookup_sales_location = _load_lookup_sales_location()

MANILA_TZ = ZoneInfo("Asia/Manila")

WEATHER_CODES = {
	0: "Clear sky",
	1: "Mainly clear",
	2: "Partly cloudy",
	3: "Overcast",
	45: "Fog",
	48: "Depositing rime fog",
	51: "Light drizzle",
	53: "Moderate drizzle",
	55: "Dense drizzle",
	61: "Slight rain",
	63: "Moderate rain",
	65: "Heavy rain",
	80: "Slight rain showers",
	81: "Moderate rain showers",
	82: "Violent rain showers",
	95: "Thunderstorm",
	96: "Thunderstorm with slight hail",
	99: "Thunderstorm with heavy hail",
}

STORM_CODES = {95, 96, 99}
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
CREATE_NO_WINDOW = 0x08000000
UPSERT_BATCH_SIZE = 500
INTER_GROUP_DELAY_SECONDS = 0.1
RAIN_LIGHT_PEAK_MM = 2.5
RAIN_DISRUPTIVE_PEAK_MM = 7.5
RAIN_DISRUPTIVE_TOTAL_MM = 20.0
RAIN_SUSTAINED_PEAK_MM = 4.0
RAIN_SUSTAINED_TOTAL_MM = 10.0
RAIN_SUSTAINED_HOURS = 6


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	"""Calculate distance between two coordinates in kilometers."""
	radius_km = 6371
	lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
	dlat = lat2 - lat1
	dlon = lon2 - lon1
	a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
	c = 2 * atan2(sqrt(a), sqrt(1 - a))
	return radius_km * c


def _get_secret(env_name: str, doppler_name: str | None = None) -> str:
	value = os.environ.get(env_name, "").strip()
	if value:
		return value
	doppler_key = doppler_name or env_name
	result = subprocess.run(
		[
			"C:/Users/Sam/bin/doppler.exe",
			"secrets",
			"get",
			doppler_key,
			"--plain",
			"--project",
			"bei-erp",
			"--config",
			"dev",
		],
		capture_output=True,
		text=True,
		timeout=15,
		creationflags=CREATE_NO_WINDOW,
	)
	if result.returncode == 0 and result.stdout.strip():
		return result.stdout.strip()
	raise RuntimeError(f"{env_name} is required and could not be resolved from environment or Doppler")


def get_supabase_client() -> Client:
	service_role_key = _get_secret("SUPABASE_SERVICE_ROLE_KEY")
	return create_client(SUPABASE_URL, service_role_key)


def upsert_batches(client: Client, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
	if not rows:
		return
	for index in range(0, len(rows), UPSERT_BATCH_SIZE):
		batch = rows[index : index + UPSERT_BATCH_SIZE]
		client.table(table).upsert(batch, on_conflict=on_conflict).execute()


def read_store_coordinates(csv_path: str) -> list[dict[str, Any]]:
	"""Read store coordinates and resolve location IDs from the shared mapping."""
	stores: list[dict[str, Any]] = []
	with open(csv_path, "r", encoding="utf-8") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			if row["is_open"] != "True" or not row["latitude"] or not row["longitude"]:
				continue
			if row["node_kind"] == "external_storage_hub":
				continue

			mapping = lookup_sales_location(warehouse_name=row["warehouse_name"])
			if not mapping:
				print(f"[WARN] Skipping {row['warehouse_name']} - no shared sales location mapping")
				continue

			stores.append(
				{
					"warehouse_id": row["warehouse_id"],
					"warehouse_name": row["warehouse_name"],
					"location_id": int(mapping["location_id"]),
					"latitude": float(row["latitude"]),
					"longitude": float(row["longitude"]),
				}
			)
	return stores


def group_nearby_stores(stores: list[dict[str, Any]], max_distance_km: float = 5.0) -> list[list[dict[str, Any]]]:
	"""Group stores within max_distance_km of each other."""
	groups: list[list[dict[str, Any]]] = []
	ungrouped = stores.copy()
	while ungrouped:
		seed = ungrouped.pop(0)
		group = [seed]
		index = 0
		while index < len(ungrouped):
			store = ungrouped[index]
			distance = haversine_distance(
				seed["latitude"],
				seed["longitude"],
				store["latitude"],
				store["longitude"],
			)
			if distance <= max_distance_km:
				group.append(ungrouped.pop(index))
			else:
				index += 1
		groups.append(group)
	return groups


def _value_from_series(series: list[Any] | None, index: int) -> Any:
	if not series or index >= len(series):
		return None
	return series[index]


def calculate_business_impact(
	max_temp: float | None,
	total_precipitation: float | None,
	max_hourly_precipitation: float | None,
	rain_hours: int,
	weather_code: int | None,
	storm_flag: bool,
) -> str:
	"""Legacy business impact label kept for compatibility with existing dashboard payloads."""
	max_temp = float(max_temp or 0)
	total_precipitation = float(total_precipitation or 0)
	max_hourly_precipitation = float(max_hourly_precipitation or 0)
	weather_code = int(weather_code or 0)

	if max_temp >= 33 and total_precipitation == 0 and weather_code < 3:
		return "peak"
	if (
		storm_flag
		or max_hourly_precipitation >= RAIN_DISRUPTIVE_PEAK_MM
		or total_precipitation >= RAIN_DISRUPTIVE_TOTAL_MM
		or (max_hourly_precipitation >= RAIN_SUSTAINED_PEAK_MM and rain_hours >= 4)
		or (rain_hours >= RAIN_SUSTAINED_HOURS and total_precipitation >= RAIN_SUSTAINED_TOTAL_MM)
	):
		return "disruptive_rain"
	if max_hourly_precipitation < RAIN_LIGHT_PEAK_MM and rain_hours <= 2 and total_precipitation > 0:
		return "passing_showers"
	if total_precipitation > 0:
		return "wet"
	if max_temp <= 27:
		return "cool"
	return "normal"


def fetch_weather_bundle(latitude: float, longitude: float, date_str: str) -> dict[str, Any] | None:
	"""Fetch daily and hourly weather data for a single Manila business date."""
	target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
	days_ago = (datetime.now(tz=MANILA_TZ).date() - target_date).days
	use_archive = days_ago > 3
	base_url = "https://archive-api.open-meteo.com/v1/archive" if use_archive else "https://api.open-meteo.com/v1/forecast"

	hourly_fields = [
		"temperature_2m",
		"apparent_temperature",
		"precipitation",
		"weather_code",
		"wind_speed_10m",
		"wind_gusts_10m",
		"cloud_cover",
	]
	if not use_archive:
		hourly_fields.append("precipitation_probability")

	params = {
		"latitude": latitude,
		"longitude": longitude,
		"daily": ",".join(
			[
				"temperature_2m_max",
				"temperature_2m_min",
				"temperature_2m_mean",
				"apparent_temperature_max",
				"relative_humidity_2m_mean",
				"precipitation_sum",
				"weather_code",
				"wind_speed_10m_max",
			]
		),
		"hourly": ",".join(hourly_fields),
		"timezone": "Asia/Manila",
		"start_date": date_str,
		"end_date": date_str,
	}

	try:
		response = requests.get(base_url, params=params, timeout=20)
		response.raise_for_status()
		payload = response.json()
	except Exception as exc:
		print(f"[ERROR] Error fetching weather data: {exc}")
		return None

	daily = payload.get("daily", {})
	hourly = payload.get("hourly", {})
	if not daily.get("time"):
		return None

	hourly_rows: list[dict[str, Any]] = []
	for index, observed_local in enumerate(hourly.get("time") or []):
		local_dt = datetime.fromisoformat(observed_local).replace(tzinfo=MANILA_TZ)
		hourly_rows.append(
			{
				"observed_at_utc": local_dt.astimezone(timezone.utc).isoformat(),
				"observed_at_manila": local_dt.replace(tzinfo=None).isoformat(sep=" "),
				"business_date": local_dt.date().isoformat(),
				"hour_local": local_dt.hour,
				"precipitation": _value_from_series(hourly.get("precipitation"), index),
				"precipitation_probability": _value_from_series(hourly.get("precipitation_probability"), index),
				"weather_code": _value_from_series(hourly.get("weather_code"), index),
				"temperature_2m": _value_from_series(hourly.get("temperature_2m"), index),
				"apparent_temperature": _value_from_series(hourly.get("apparent_temperature"), index),
				"wind_speed_10m": _value_from_series(hourly.get("wind_speed_10m"), index),
				"wind_gusts_10m": _value_from_series(hourly.get("wind_gusts_10m"), index),
				"cloud_cover": _value_from_series(hourly.get("cloud_cover"), index),
			}
		)

	rain_hours = sum(1 for row in hourly_rows if float(row["precipitation"] or 0) > 0)
	max_hourly_precipitation = max((float(row["precipitation"] or 0) for row in hourly_rows), default=0.0)
	avg_hourly_wind = (
		sum(float(row["wind_speed_10m"] or 0) for row in hourly_rows) / len(hourly_rows)
		if hourly_rows
		else None
	)
	storm_flag = any(int(row["weather_code"] or 0) in STORM_CODES for row in hourly_rows)
	daily_weather_code = int(daily["weather_code"][0])

	return {
		"daily": {
			"temperature_max": daily["temperature_2m_max"][0],
			"temperature_min": daily["temperature_2m_min"][0],
			"temperature_mean": daily["temperature_2m_mean"][0],
			"apparent_temperature_max": daily.get("apparent_temperature_max", [None])[0],
			"humidity_mean": daily["relative_humidity_2m_mean"][0],
			"precipitation": daily["precipitation_sum"][0],
			"weather_code": daily_weather_code,
			"wind_speed_avg": avg_hourly_wind,
			"wind_speed_max": daily["wind_speed_10m_max"][0],
			"rain_hours": rain_hours,
			"max_hourly_precipitation": max_hourly_precipitation,
			"storm_flag": storm_flag,
		},
		"hourly": hourly_rows,
	}


def upsert_daily_weather(client: Client, group: list[dict[str, Any]], date_str: str, daily_weather: dict[str, Any]) -> None:
	weather_description = WEATHER_CODES.get(
		int(daily_weather["weather_code"]),
		f"Unknown ({daily_weather['weather_code']})",
	)
	business_impact = calculate_business_impact(
		max_temp=daily_weather.get("temperature_max"),
		total_precipitation=daily_weather.get("precipitation"),
		max_hourly_precipitation=daily_weather.get("max_hourly_precipitation"),
		rain_hours=int(daily_weather.get("rain_hours") or 0),
		weather_code=daily_weather.get("weather_code"),
		storm_flag=bool(daily_weather.get("storm_flag")),
	)

	rows = []
	for store in group:
		rows.append(
			{
				"location_id": store["location_id"],
				"business_date": date_str,
				"max_temperature": daily_weather.get("temperature_max"),
				"min_temperature": daily_weather.get("temperature_min"),
				"avg_temperature": daily_weather.get("temperature_mean"),
				"avg_humidity": daily_weather.get("humidity_mean"),
				"total_precipitation": daily_weather.get("precipitation"),
				"weather_code": daily_weather.get("weather_code"),
				"weather_description": weather_description,
				"avg_wind_speed": daily_weather.get("wind_speed_avg") or daily_weather.get("wind_speed_max"),
				"is_rainy": float(daily_weather.get("precipitation") or 0) > 0,
				"rain_hours": int(daily_weather.get("rain_hours") or 0),
				"business_impact": business_impact,
				"synced_at": datetime.now(timezone.utc).isoformat(),
			}
		)
	upsert_batches(client, "daily_weather", rows, "location_id,business_date")


def upsert_hourly_weather(client: Client, group: list[dict[str, Any]], hourly_rows: list[dict[str, Any]]) -> None:
	rows = []
	for store in group:
		for row in hourly_rows:
			rows.append(
				{
					"location_id": store["location_id"],
					"observed_at_utc": row["observed_at_utc"],
					"observed_at_manila": row["observed_at_manila"],
					"business_date": row["business_date"],
					"hour_local": row["hour_local"],
					"precipitation": row["precipitation"],
					"precipitation_probability": row["precipitation_probability"],
					"weather_code": row["weather_code"],
					"temperature_2m": row["temperature_2m"],
					"apparent_temperature": row["apparent_temperature"],
					"wind_speed_10m": row["wind_speed_10m"],
					"wind_gusts_10m": row["wind_gusts_10m"],
					"cloud_cover": row["cloud_cover"],
					"synced_at": datetime.now(timezone.utc).isoformat(),
				}
			)
	upsert_batches(client, "weather_hourly", rows, "location_id,observed_at_utc")


def refresh_weather_features(client: Client) -> None:
	client.rpc("refresh_sales_dashboard_weather_daily_features").execute()


def sync_weather(client: Client, date_str: str, warehouse_tree_path: str) -> dict[str, Any]:
	print(f"\n{'=' * 60}")
	print(f"Syncing weather data for {date_str}")
	print(f"{'=' * 60}\n")

	print(">> Reading store coordinates...")
	stores = read_store_coordinates(warehouse_tree_path)
	print(f"   Found {len(stores)} stores with coordinates and shared location mapping\n")

	print(">> Grouping nearby stores (within 5km)...")
	groups = group_nearby_stores(stores)
	print(f"   Created {len(groups)} weather fetch groups\n")

	stats = {
		"stores_processed": 0,
		"api_calls": 0,
		"successful_groups": 0,
		"failed_groups": 0,
		"weather_conditions": {},
	}

	for group_index, group in enumerate(groups, start=1):
		seed = group[0]
		print(f"[Group {group_index}/{len(groups)}] Fetching weather at ({seed['latitude']:.4f}, {seed['longitude']:.4f})")
		print(f"   Stores in group: {', '.join(store['warehouse_name'] for store in group)}")

		weather_bundle = fetch_weather_bundle(seed["latitude"], seed["longitude"], date_str)
		stats["api_calls"] += 1
		if not weather_bundle:
			print("   [WARN] Failed to fetch weather data, skipping group\n")
			stats["failed_groups"] += 1
			stats["stores_processed"] += len(group)
			continue

		daily_weather = weather_bundle["daily"]
		business_impact = calculate_business_impact(
			max_temp=daily_weather.get("temperature_max"),
			total_precipitation=daily_weather.get("precipitation"),
			max_hourly_precipitation=daily_weather.get("max_hourly_precipitation"),
			rain_hours=int(daily_weather.get("rain_hours") or 0),
			weather_code=daily_weather.get("weather_code"),
			storm_flag=bool(daily_weather.get("storm_flag")),
		)
		weather_desc = WEATHER_CODES.get(int(daily_weather["weather_code"]), "Unknown")

		print(f"   Temperature: {float(daily_weather['temperature_mean']):.1f}C (max: {float(daily_weather['temperature_max']):.1f}C)")
		print(f"   Precipitation: {float(daily_weather['precipitation']):.1f}mm")
		print(f"   Rain hours: {int(daily_weather['rain_hours'])}")
		print(f"   Conditions: {weather_desc}")
		print(f"   Business impact: {business_impact}")

		try:
			upsert_daily_weather(client, group, date_str, daily_weather)
			upsert_hourly_weather(client, group, weather_bundle["hourly"])
			stats["successful_groups"] += 1
			stats["weather_conditions"][business_impact] = stats["weather_conditions"].get(business_impact, 0) + len(group)
			for store in group:
				print(f"   [OK] {store['warehouse_name']} (location_id: {store['location_id']})")
		except Exception as exc:
			stats["failed_groups"] += 1
			print(f"   [FAIL] Group upsert failed: {exc}")
		finally:
			stats["stores_processed"] += len(group)

		print()
		if group_index < len(groups):
			time.sleep(INTER_GROUP_DELAY_SECONDS)

	return stats


def main() -> None:
	parser = argparse.ArgumentParser(description="Sync weather data to Supabase")
	parser.add_argument("--date", type=str, help="Date to sync (YYYY-MM-DD). Default: yesterday")
	parser.add_argument("--backfill-days", type=int, help="Backfill N days of historical data")
	parser.add_argument("--start-date", type=str, help="Range start date (YYYY-MM-DD)")
	parser.add_argument("--end-date", type=str, help="Range end date (YYYY-MM-DD)")
	parser.add_argument(
		"--warehouse-tree",
		type=str,
		default="data/_FINAL/WAREHOUSE_TREE.csv",
		help="Path to WAREHOUSE_TREE.csv",
	)
	parser.add_argument(
		"--skip-refresh-features",
		action="store_true",
		help="Skip refreshing sales_dashboard_weather_daily_features after sync",
	)
	args = parser.parse_args()

	if args.start_date or args.end_date:
		if not (args.start_date and args.end_date):
			raise SystemExit("--start-date and --end-date must be used together")
		start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
		end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
		if start_date > end_date:
			raise SystemExit("--start-date must be on or before --end-date")
		dates = []
		current = start_date
		while current <= end_date:
			dates.append(current.strftime("%Y-%m-%d"))
			current += timedelta(days=1)
	elif args.backfill_days:
		end_date = datetime.now(tz=MANILA_TZ) - timedelta(days=1)
		start_date = end_date - timedelta(days=args.backfill_days - 1)
		dates = []
		current = start_date
		while current <= end_date:
			dates.append(current.strftime("%Y-%m-%d"))
			current += timedelta(days=1)
	elif args.date:
		dates = [args.date]
	else:
		yesterday = datetime.now(tz=MANILA_TZ) - timedelta(days=1)
		dates = [yesterday.strftime("%Y-%m-%d")]

	print("\nWeather Data Sync")
	print(f"Dates to process: {', '.join(dates)}")
	supabase = get_supabase_client()

	all_stats = {
		"total_stores_processed": 0,
		"total_api_calls": 0,
		"total_successful_groups": 0,
		"total_failed_groups": 0,
		"total_weather_conditions": {},
	}

	for date_str in dates:
		stats = sync_weather(supabase, date_str, args.warehouse_tree)
		all_stats["total_stores_processed"] += stats["stores_processed"]
		all_stats["total_api_calls"] += stats["api_calls"]
		all_stats["total_successful_groups"] += stats["successful_groups"]
		all_stats["total_failed_groups"] += stats["failed_groups"]
		for condition, count in stats["weather_conditions"].items():
			all_stats["total_weather_conditions"][condition] = (
				all_stats["total_weather_conditions"].get(condition, 0) + count
			)

	if not args.skip_refresh_features:
		print(">> Refreshing weather intelligence materialized view...")
		refresh_weather_features(supabase)
		print("   [OK] sales_dashboard_weather_daily_features refreshed")

	print(f"\n{'=' * 60}")
	print("SUMMARY")
	print(f"{'=' * 60}")
	print(f"Dates processed: {len(dates)}")
	print(f"Stores processed: {all_stats['total_stores_processed']}")
	print(f"API calls: {all_stats['total_api_calls']}")
	print(f"Successful groups: {all_stats['total_successful_groups']}")
	print(f"Failed groups: {all_stats['total_failed_groups']}")
	print("\nWeather conditions breakdown:")
	for condition, count in sorted(all_stats["total_weather_conditions"].items()):
		print(f"  {condition}: {count} stores")
	print()


if __name__ == "__main__":
	main()

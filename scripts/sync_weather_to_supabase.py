#!/usr/bin/env python3
"""
Sync weather data from Open-Meteo API to Supabase daily_weather table.

This script:
1. Reads store coordinates from WAREHOUSE_TREE.csv
2. Groups nearby stores (within 5km) to minimize API calls
3. Fetches historical weather data from Open-Meteo API
4. Calculates business impact based on temperature/precipitation
5. Upserts into Supabase daily_weather table

Usage:
    python scripts/sync_weather_to_supabase.py --date 2026-02-13
    python scripts/sync_weather_to_supabase.py --backfill-days 30
"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import requests

# Weather code to description mapping
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

# Store name to Mosaic location_id mapping
LOCATION_ID_MAP = {
	"SM Caloocan": 2464,
	"Ayala Market Market": 2287,
	"SM Megamall": 2338,
	"SM Manila": 2339,
	"Robinsons Antipolo": 2342,
	"SM Valenzuela": 2341,
	"The Terminal": 2319,
	"SM Grand Central": 2218,
	"Ayala Malls Fairview Terraces": 2220,
	"SM East Ortigas": 2184,
	"SM Marikina": 2317,
	"Megaworld Paseo Center": 2177,
	"Megawide PITX": 2179,
	"Megaworld Venice Grand Canal": 2216,
	"Lucky Chinatown": 2311,
	"SM North EDSA": 2284,
	"SM Southmall": 2340,
	"Festival Mall Alabang": 2222,
	"SM Mall Of Asia": 2219,
	"Ever Commonwealth": 2281,
	"The Grid - Rockwell": 2250,
	"BF Homes": 2217,
	"SM Tanza": 2411,
	"SJDM": 2481,
	"SM Sangandaan": 2482,
	"SM Marilao": 2413,
	"SM Bicutan": 2412,
	"Robinson Imus": 2408,
	"SM Pulilan": 2478,
	"Ayala Evo": 2426,
	"Robinson General Trias": 2430,
	"Ayala Vermosa": 2428,
	"Ayala Solenad": 2547,
	"Robinsons Galleria South": 2515,
	"Ayala UPTC": 2425,
	"Vista Mall Taguig": 2556,
	"Sta. Lucia East Grand Mall": 2558,
	"Up Town Mall BGC": 2548,
	"SM Clark": 2646,
	"Araneta Gateway": 2557,
	"CTTM Tomas Morato": 2526,
	"D'verde Laguna": 2766,
}

WAREHOUSE_NAME_ALIASES = {
	"SM  Manila": "SM Manila",
	"Robisons Galleria South": "Robinsons Galleria South",
}

# Supabase configuration
SUPABASE_PROJECT_ID = "csnniykjrychgajfrgua"
SUPABASE_API_TOKEN = os.environ["SUPABASE_MGMT_TOKEN"]
SUPABASE_API_URL = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_ID}/database/query"


def normalize_warehouse_name(name: str) -> str:
	"""Normalize warehouse names so minor label drift does not break the weather join."""
	text = re.sub(r"\s+", " ", (name or "").strip())
	return WAREHOUSE_NAME_ALIASES.get(text, text)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	"""Calculate distance between two coordinates in kilometers."""
	R = 6371  # Earth's radius in kilometers

	lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
	dlat = lat2 - lat1
	dlon = lon2 - lon1

	a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
	c = 2 * atan2(sqrt(a), sqrt(1 - a))

	return R * c


def read_store_coordinates(csv_path: str) -> list[dict]:
	"""Read store coordinates from WAREHOUSE_TREE.csv."""
	stores = []
	csv_file = Path(csv_path).expanduser().resolve()

	with csv_file.open(encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			# Only include open stores with coordinates
			if row["is_open"] == "True" and row["latitude"] and row["longitude"]:
				# Skip external storage hubs
				if row["node_kind"] == "external_storage_hub":
					continue

				warehouse_name = row["warehouse_name"]
				canonical_name = normalize_warehouse_name(warehouse_name)

				# Only include stores with known location_ids
				if canonical_name not in LOCATION_ID_MAP:
					print(f"[WARN] Skipping {warehouse_name} - no location_id mapping")
					continue

				stores.append(
					{
						"warehouse_id": row["warehouse_id"],
						"warehouse_name": canonical_name,
						"location_id": LOCATION_ID_MAP[canonical_name],
						"latitude": float(row["latitude"]),
						"longitude": float(row["longitude"]),
					}
				)

	return stores


def group_nearby_stores(stores: list[dict], max_distance_km: float = 5.0) -> list[list[dict]]:
	"""Group stores within max_distance_km of each other."""
	groups = []
	ungrouped = stores.copy()

	while ungrouped:
		# Start a new group with the first ungrouped store
		seed = ungrouped.pop(0)
		group = [seed]

		# Find all stores within max_distance_km
		i = 0
		while i < len(ungrouped):
			store = ungrouped[i]
			distance = haversine_distance(
				seed["latitude"], seed["longitude"], store["latitude"], store["longitude"]
			)

			if distance <= max_distance_km:
				group.append(ungrouped.pop(i))
			else:
				i += 1

		groups.append(group)

	return groups


def calculate_business_impact(max_temp: float, precipitation: float, weather_code: int) -> str:
	"""
	Calculate business impact based on weather conditions.

	Rules:
	- Hot (>33°C) + Clear (code < 3) = 'peak' (hot weather = halo-halo demand)
	- Heavy rain (>5mm) = 'slow' (heavy rain = slow foot traffic)
	- Moderate rain (>1mm) = 'moderate_rain'
	- Light rain (>0mm) = 'light_rain'
	- Otherwise = 'normal'
	"""
	# Hot and clear = peak demand
	if max_temp > 33 and weather_code < 3:
		return "peak"

	# Rain impacts
	if precipitation > 5:
		return "slow"
	elif precipitation > 1:
		return "moderate_rain"
	elif precipitation > 0:
		return "light_rain"

	return "normal"


def fetch_weather_data(latitude: float, longitude: float, date_str: str) -> dict:
	"""
	Fetch weather data from Open-Meteo API.

	For dates more than 3 days old, uses the archive endpoint.
	"""
	# Determine if we need the archive endpoint
	target_date = datetime.strptime(date_str, "%Y-%m-%d")
	days_ago = (datetime.now() - target_date).days

	if days_ago > 3:
		base_url = "https://archive-api.open-meteo.com/v1/archive"
	else:
		base_url = "https://api.open-meteo.com/v1/forecast"

	params = {
		"latitude": latitude,
		"longitude": longitude,
		"daily": ",".join(
			[
				"temperature_2m_max",
				"temperature_2m_min",
				"temperature_2m_mean",
				"relative_humidity_2m_mean",
				"precipitation_sum",
				"weather_code",
				"wind_speed_10m_max",
			]
		),
		"timezone": "Asia/Manila",
		"start_date": date_str,
		"end_date": date_str,
	}

	try:
		response = requests.get(base_url, params=params, timeout=10)
		response.raise_for_status()
		data = response.json()

		# Extract daily data
		if "daily" not in data or not data["daily"].get("time"):
			return None

		daily = data["daily"]
		idx = 0  # We only requested one day

		return {
			"temperature_max": daily["temperature_2m_max"][idx],
			"temperature_min": daily["temperature_2m_min"][idx],
			"temperature_mean": daily["temperature_2m_mean"][idx],
			"humidity_mean": daily["relative_humidity_2m_mean"][idx],
			"precipitation": daily["precipitation_sum"][idx],
			"weather_code": daily["weather_code"][idx],
			"wind_speed_max": daily["wind_speed_10m_max"][idx],
		}

	except Exception as e:
		print(f"[ERROR] Error fetching weather data: {e}")
		return None


def upsert_to_supabase(location_id: int, date_str: str, weather_data: dict) -> bool:
	"""Upsert weather data into Supabase daily_weather table."""
	# Calculate business impact
	business_impact = calculate_business_impact(
		weather_data["temperature_max"], weather_data["precipitation"], weather_data["weather_code"]
	)

	# Get weather description
	weather_description = WEATHER_CODES.get(
		weather_data["weather_code"], f"Unknown ({weather_data['weather_code']})"
	)

	# Build SQL query
	# Determine is_rainy and rain_hours from weather code
	is_rainy = weather_data["weather_code"] in (51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99)
	rain_hours = (
		8
		if weather_data["precipitation"] > 5
		else (4 if weather_data["precipitation"] > 1 else (1 if weather_data["precipitation"] > 0 else 0))
	)

	sql = f"""
    INSERT INTO daily_weather (
        location_id,
        business_date,
        max_temperature,
        min_temperature,
        avg_temperature,
        avg_humidity,
        total_precipitation,
        weather_code,
        weather_description,
        avg_wind_speed,
        is_rainy,
        rain_hours,
        business_impact,
        synced_at
    ) VALUES (
        {location_id},
        '{date_str}',
        {weather_data["temperature_max"]},
        {weather_data["temperature_min"]},
        {weather_data["temperature_mean"]},
        {weather_data["humidity_mean"]},
        {weather_data["precipitation"]},
        {weather_data["weather_code"]},
        '{weather_description}',
        {weather_data["wind_speed_max"]},
        {"TRUE" if is_rainy else "FALSE"},
        {rain_hours},
        '{business_impact}',
        NOW()
    )
    ON CONFLICT (location_id, business_date)
    DO UPDATE SET
        max_temperature = EXCLUDED.max_temperature,
        min_temperature = EXCLUDED.min_temperature,
        avg_temperature = EXCLUDED.avg_temperature,
        avg_humidity = EXCLUDED.avg_humidity,
        total_precipitation = EXCLUDED.total_precipitation,
        weather_code = EXCLUDED.weather_code,
        weather_description = EXCLUDED.weather_description,
        avg_wind_speed = EXCLUDED.avg_wind_speed,
        is_rainy = EXCLUDED.is_rainy,
        rain_hours = EXCLUDED.rain_hours,
        business_impact = EXCLUDED.business_impact,
        synced_at = NOW();
    """

	headers = {
		"Authorization": f"Bearer {SUPABASE_API_TOKEN}",
		"Content-Type": "application/json",
	}

	payload = {"query": sql}

	try:
		response = requests.post(SUPABASE_API_URL, headers=headers, json=payload, timeout=10)
		response.raise_for_status()
		return True

	except Exception as e:
		print(f"[ERROR] Error upserting to Supabase: {e}")
		if "response" in locals() and hasattr(response, "text"):
			print(f"   Response: {response.text}")
		return False


def sync_weather(date_str: str, warehouse_tree_path: str) -> dict:
	"""Sync weather data for a specific date."""
	print(f"\n{'=' * 60}")
	print(f"Syncing weather data for {date_str}")
	print(f"{'=' * 60}\n")

	# Read store data
	print(">> Reading store coordinates...")
	stores = read_store_coordinates(warehouse_tree_path)
	print(f"   Found {len(stores)} stores with coordinates and location_ids\n")

	# Group nearby stores
	print(">> Grouping nearby stores (within 5km)...")
	groups = group_nearby_stores(stores)
	print(f"   Created {len(groups)} weather fetch groups\n")

	# Track statistics
	stats = {
		"stores_processed": 0,
		"api_calls": 0,
		"successful_upserts": 0,
		"failed_upserts": 0,
		"weather_conditions": {},
	}

	# Process each group
	for group_idx, group in enumerate(groups, 1):
		# Use the first store's coordinates as representative
		seed = group[0]
		print(
			f"[Group {group_idx}/{len(groups)}] Fetching weather at ({seed['latitude']:.4f}, {seed['longitude']:.4f})"
		)
		print(f"   Stores in group: {', '.join(s['warehouse_name'] for s in group)}")

		# Fetch weather data
		weather_data = fetch_weather_data(seed["latitude"], seed["longitude"], date_str)
		stats["api_calls"] += 1

		if not weather_data:
			print("   [WARN] Failed to fetch weather data, skipping group")
			stats["failed_upserts"] += len(group)
			continue

		# Calculate business impact for logging
		business_impact = calculate_business_impact(
			weather_data["temperature_max"], weather_data["precipitation"], weather_data["weather_code"]
		)

		weather_desc = WEATHER_CODES.get(weather_data["weather_code"], "Unknown")

		print(
			f"   Temperature: {weather_data['temperature_mean']:.1f}C (max: {weather_data['temperature_max']:.1f}C)"
		)
		print(f"   Precipitation: {weather_data['precipitation']:.1f}mm")
		print(f"   Conditions: {weather_desc}")
		print(f"   Business impact: {business_impact}")

		# Track weather conditions
		stats["weather_conditions"][business_impact] = stats["weather_conditions"].get(
			business_impact, 0
		) + len(group)

		# Upsert for each store in the group
		for store in group:
			success = upsert_to_supabase(store["location_id"], date_str, weather_data)

			if success:
				stats["successful_upserts"] += 1
				print(f"   [OK] {store['warehouse_name']} (location_id: {store['location_id']})")
			else:
				stats["failed_upserts"] += 1
				print(f"   [FAIL] {store['warehouse_name']} (location_id: {store['location_id']})")

			stats["stores_processed"] += 1

		print()

		# Rate limiting: be nice to the free API
		if group_idx < len(groups):
			time.sleep(0.5)

	return stats


def main():
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

	args = parser.parse_args()

	# Determine date range
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
		end_date = datetime.now() - timedelta(days=1)  # Yesterday
		start_date = end_date - timedelta(days=args.backfill_days - 1)
		dates = []
		current = start_date
		while current <= end_date:
			dates.append(current.strftime("%Y-%m-%d"))
			current += timedelta(days=1)
	elif args.date:
		dates = [args.date]
	else:
		# Default: yesterday
		yesterday = datetime.now() - timedelta(days=1)
		dates = [yesterday.strftime("%Y-%m-%d")]

	print("\nWeather Data Sync")
	print(f"Dates to process: {', '.join(dates)}")

	# Sync each date
	all_stats = {
		"total_stores_processed": 0,
		"total_api_calls": 0,
		"total_successful_upserts": 0,
		"total_failed_upserts": 0,
		"total_weather_conditions": {},
	}

	for date_str in dates:
		stats = sync_weather(date_str, args.warehouse_tree)

		all_stats["total_stores_processed"] += stats["stores_processed"]
		all_stats["total_api_calls"] += stats["api_calls"]
		all_stats["total_successful_upserts"] += stats["successful_upserts"]
		all_stats["total_failed_upserts"] += stats["failed_upserts"]

		for condition, count in stats["weather_conditions"].items():
			all_stats["total_weather_conditions"][condition] = (
				all_stats["total_weather_conditions"].get(condition, 0) + count
			)

	# Print summary
	print(f"\n{'=' * 60}")
	print("SUMMARY")
	print(f"{'=' * 60}")
	print(f"Dates processed: {len(dates)}")
	print(f"Stores processed: {all_stats['total_stores_processed']}")
	print(f"API calls: {all_stats['total_api_calls']}")
	print(f"Successful upserts: {all_stats['total_successful_upserts']}")
	print(f"Failed upserts: {all_stats['total_failed_upserts']}")
	print("\nWeather conditions breakdown:")
	for condition, count in sorted(all_stats["total_weather_conditions"].items()):
		print(f"  {condition}: {count} stores")
	print()


if __name__ == "__main__":
	main()

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Weather Service for BEI Stores

Uses Open-Meteo API (free, no API key required):
- 300,000 API calls/month (10,000/day)
- No rate limiting for reasonable use
- Covers all Philippine locations

Collects weather data 5x daily for sales correlation analysis.
"""

import frappe
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List


# Open-Meteo API (free, no key needed)
BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Weather code mappings
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
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Fetch current weather for a location.

    Args:
        latitude: Location latitude
        longitude: Location longitude

    Returns:
        Dictionary with weather data:
        {
            "temperature": 28.5,
            "feels_like": 32.1,
            "humidity": 75,
            "precipitation": 0.0,
            "weather_code": 2,
            "weather_description": "Partly cloudy",
            "wind_speed": 12.5,
            "is_rainy": False,
            "timestamp": "2026-01-31T10:00:00",
            "success": True
        }
    """
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ],
            "timezone": "Asia/Manila",
        }

        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)

        return {
            "temperature": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation", 0),
            "weather_code": weather_code,
            "weather_description": WEATHER_CODES.get(weather_code, "Unknown"),
            "wind_speed": current.get("wind_speed_10m"),
            "is_rainy": weather_code >= 51,  # Codes 51+ are rain/drizzle
            "timestamp": current.get("time"),
            "success": True,
        }

    except requests.RequestException as e:
        frappe.log_error(f"Weather API error: {str(e)}", "Weather Service")
        return {"success": False, "error": str(e)}


def get_weather_forecast(latitude: float, longitude: float, days: int = 3) -> Dict[str, Any]:
    """
    Fetch weather forecast for a location.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        days: Number of forecast days (1-16)

    Returns:
        Dictionary with hourly and daily forecasts
    """
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "temperature_2m",
                "precipitation_probability",
                "weather_code",
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
            ],
            "timezone": "Asia/Manila",
            "forecast_days": min(days, 16),
        }

        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "hourly": data.get("hourly", {}),
            "daily": data.get("daily", {}),
            "success": True,
        }

    except requests.RequestException as e:
        frappe.log_error(f"Weather forecast error: {str(e)}", "Weather Service")
        return {"success": False, "error": str(e)}


def collect_weather_for_zone(zone_name: str) -> Optional[str]:
    """
    Collect weather data for a weather zone and create a log entry.

    Args:
        zone_name: Name of BEI Weather Zone document

    Returns:
        Name of created BEI Weather Log document, or None on failure
    """
    try:
        zone = frappe.get_doc("BEI Weather Zone", zone_name)

        if not zone.is_active:
            return None

        weather = get_weather(zone.latitude, zone.longitude)

        if not weather.get("success"):
            return None

        # Create weather log entry
        log = frappe.new_doc("BEI Weather Log")
        log.weather_zone = zone_name
        log.collection_time = datetime.now()
        log.temperature = weather.get("temperature")
        log.feels_like = weather.get("feels_like")
        log.humidity = weather.get("humidity")
        log.precipitation = weather.get("precipitation")
        log.weather_code = weather.get("weather_code")
        log.weather_description = weather.get("weather_description")
        log.wind_speed = weather.get("wind_speed")
        log.is_rainy = weather.get("is_rainy")
        log.insert(ignore_permissions=True)

        return log.name

    except Exception as e:
        frappe.log_error(f"Weather collection error for {zone_name}: {str(e)}", "Weather Service")
        return None


def collect_all_weather():
    """
    Collect weather for all active weather zones.
    Called by scheduler every 3 hours (5x daily).
    """
    zones = frappe.get_all(
        "BEI Weather Zone",
        filters={"is_active": 1},
        pluck="name"
    )

    collected = 0
    for zone_name in zones:
        if collect_weather_for_zone(zone_name):
            collected += 1

    frappe.logger("weather_service").info(
        f"Weather collection completed: {collected}/{len(zones)} zones"
    )


def get_weather_for_store(store: str, date: str = None) -> Optional[Dict[str, Any]]:
    """
    Get most recent weather data for a store.

    Args:
        store: Store/Warehouse name
        date: Optional date filter (YYYY-MM-DD)

    Returns:
        Weather data dictionary or None
    """
    try:
        # Find weather zone for this store
        zone = frappe.db.get_value(
            "BEI Weather Zone Store",
            {"store": store},
            "parent"
        )

        if not zone:
            return None

        filters = {"weather_zone": zone}
        if date:
            filters["collection_time"] = ["like", f"{date}%"]

        log = frappe.get_all(
            "BEI Weather Log",
            filters=filters,
            fields=[
                "temperature", "feels_like", "humidity", "precipitation",
                "weather_code", "weather_description", "is_rainy", "collection_time"
            ],
            order_by="collection_time desc",
            limit=1
        )

        if log:
            return log[0]

        return None

    except Exception as e:
        frappe.log_error(f"Get weather for store error: {str(e)}", "Weather Service")
        return None


# ==============================================================================
# FRAPPE API ENDPOINTS
# ==============================================================================

@frappe.whitelist()
def fetch_current_weather(store: str = None, latitude: float = None, longitude: float = None):
    """
    API endpoint to fetch current weather.

    Either provide store name (uses zone coordinates) or lat/long directly.
    """
    if store:
        # Get zone for store
        zone_name = frappe.db.get_value(
            "BEI Weather Zone Store",
            {"store": store},
            "parent"
        )

        if zone_name:
            zone = frappe.get_doc("BEI Weather Zone", zone_name)
            latitude = zone.latitude
            longitude = zone.longitude
        else:
            return {"success": False, "error": f"No weather zone configured for store: {store}"}

    if not latitude or not longitude:
        return {"success": False, "error": "Either store or lat/long coordinates required"}

    return get_weather(float(latitude), float(longitude))


@frappe.whitelist()
def get_store_weather_history(store: str, days: int = 7):
    """
    Get weather history for a store over the past N days.
    """
    from frappe.utils import add_days, nowdate

    zone = frappe.db.get_value(
        "BEI Weather Zone Store",
        {"store": store},
        "parent"
    )

    if not zone:
        return {"success": False, "error": f"No weather zone for store: {store}"}

    start_date = add_days(nowdate(), -int(days))

    logs = frappe.get_all(
        "BEI Weather Log",
        filters={
            "weather_zone": zone,
            "collection_time": [">=", start_date]
        },
        fields=[
            "collection_time", "temperature", "humidity", "precipitation",
            "weather_description", "is_rainy"
        ],
        order_by="collection_time desc"
    )

    return {"success": True, "data": logs}

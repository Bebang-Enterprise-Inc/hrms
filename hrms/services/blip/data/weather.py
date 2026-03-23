"""
Weather Data Module

Fetches weather data from Open-Meteo API (free, no API key required).
Includes BEI store locations for area-specific weather.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Metro Manila default coordinates
METRO_MANILA_LAT = 14.5995
METRO_MANILA_LON = 120.9842

# BEI Store locations with coordinates and area info
STORE_LOCATIONS = {
    # Format: "store_code": {"name": "Full Name", "area": "Area", "lat": x, "lon": y}
    "market_market": {"name": "Market! Market!", "area": "BGC/Taguig", "lat": 14.5494, "lon": 121.0509},
    "sm_megamall": {"name": "SM Megamall", "area": "Ortigas/Mandaluyong", "lat": 14.5847, "lon": 121.0565},
    "sm_north": {"name": "SM North EDSA", "area": "Quezon City", "lat": 14.6566, "lon": 121.0285},
    "trinoma": {"name": "TriNoma", "area": "Quezon City", "lat": 14.6532, "lon": 121.0327},
    "glorietta": {"name": "Glorietta", "area": "Makati", "lat": 14.5514, "lon": 121.0251},
    "greenbelt": {"name": "Greenbelt", "area": "Makati", "lat": 14.5527, "lon": 121.0220},
    "uptown_mall": {"name": "Uptown Mall", "area": "BGC/Taguig", "lat": 14.5535, "lon": 121.0500},
    "high_street": {"name": "High Street BGC", "area": "BGC/Taguig", "lat": 14.5504, "lon": 121.0467},
    "sm_aura": {"name": "SM Aura", "area": "BGC/Taguig", "lat": 14.5468, "lon": 121.0556},
    "eastwood": {"name": "Eastwood Mall", "area": "Quezon City", "lat": 14.6086, "lon": 121.0799},
    "rob_galleria": {"name": "Robinsons Galleria", "area": "Ortigas/Pasig", "lat": 14.5876, "lon": 121.0585},
    "rob_magnolia": {"name": "Robinsons Magnolia", "area": "Quezon City", "lat": 14.6172, "lon": 121.0196},
    "ayala_fairview": {"name": "Ayala Malls Fairview Terraces", "area": "Fairview/QC", "lat": 14.7377, "lon": 121.0574},
    "sm_fairview": {"name": "SM City Fairview", "area": "Fairview/QC", "lat": 14.7279, "lon": 121.0731},
    "gateway": {"name": "Gateway Mall", "area": "Cubao/QC", "lat": 14.6184, "lon": 121.0557},
    "sm_moa": {"name": "SM Mall of Asia", "area": "Pasay", "lat": 14.5351, "lon": 120.9829},
    "festival_mall": {"name": "Festival Mall", "area": "Alabang/Muntinlupa", "lat": 14.4172, "lon": 121.0399},
    "sm_southmall": {"name": "SM Southmall", "area": "Las Piñas", "lat": 14.4489, "lon": 120.9818},
    "alabang_town": {"name": "Alabang Town Center", "area": "Alabang/Muntinlupa", "lat": 14.4220, "lon": 121.0415},
}

# Store name aliases for natural language matching
STORE_ALIASES = {
    # SM Megamall
    "megamall": "sm_megamall", "mega mall": "sm_megamall", "sm mega": "sm_megamall",
    "megamall ortigas": "sm_megamall", "sm megamall": "sm_megamall",
    # Market Market
    "market market": "market_market", "market!market": "market_market", "marketmarket": "market_market",
    "market market bgc": "market_market", "mm bgc": "market_market",
    # SM North
    "sm north": "sm_north", "north edsa": "sm_north", "sm north edsa": "sm_north",
    # Trinoma
    "trinoma": "trinoma", "tri noma": "trinoma",
    # Glorietta
    "glorietta": "glorietta", "gloria": "glorietta", "glorietta makati": "glorietta",
    # Greenbelt
    "greenbelt": "greenbelt", "green belt": "greenbelt", "gb makati": "greenbelt",
    # Uptown
    "uptown": "uptown_mall", "uptown mall": "uptown_mall", "uptown bgc": "uptown_mall",
    # High Street
    "high street": "high_street", "highstreet": "high_street", "high street bgc": "high_street",
    # SM Aura
    "aura": "sm_aura", "sm aura": "sm_aura", "aura bgc": "sm_aura",
    # Eastwood
    "eastwood": "eastwood", "eastwood mall": "eastwood", "eastwood city": "eastwood",
    # Robinsons Galleria
    "galleria": "rob_galleria", "robinsons galleria": "rob_galleria", "rob galleria": "rob_galleria",
    # Robinsons Magnolia
    "magnolia": "rob_magnolia", "robinsons magnolia": "rob_magnolia", "rob magnolia": "rob_magnolia",
    # Fairview
    "fairview": "ayala_fairview", "fairview terraces": "ayala_fairview", "ayala fairview": "ayala_fairview",
    "fairview terrace": "ayala_fairview", "ayala malls fairview": "ayala_fairview",
    # SM Fairview
    "sm fairview": "sm_fairview",
    # Gateway
    "gateway": "gateway", "gateway mall": "gateway", "gateway cubao": "gateway",
    # SM MOA
    "moa": "sm_moa", "mall of asia": "sm_moa", "sm moa": "sm_moa", "sm mall of asia": "sm_moa",
    # Festival
    "festival": "festival_mall", "festival mall": "festival_mall", "filinvest festival": "festival_mall",
    # SM Southmall
    "southmall": "sm_southmall", "sm southmall": "sm_southmall", "south mall": "sm_southmall",
    # Alabang Town Center
    "atc": "alabang_town", "alabang town center": "alabang_town", "alabang town": "alabang_town",
    # Area names
    "bgc": "market_market", "bonifacio global city": "market_market",
    "makati": "glorietta", "ayala makati": "glorietta",
    "ortigas": "sm_megamall", "ortigas center": "sm_megamall",
    "cubao": "gateway", "araneta": "gateway",
    "alabang": "alabang_town", "muntinlupa": "alabang_town",
}


def resolve_store(store_hint: str) -> Tuple[str, dict]:
    """
    Resolve a store name/alias to its full details.

    Args:
        store_hint: User's store name (may be alias or partial)

    Returns:
        Tuple of (store_code, store_details) or (None, None) if not found
    """
    if not store_hint:
        return None, None

    hint_lower = store_hint.lower().strip()

    # Direct match in aliases
    if hint_lower in STORE_ALIASES:
        code = STORE_ALIASES[hint_lower]
        return code, STORE_LOCATIONS.get(code)

    # Direct match in store codes
    if hint_lower.replace(" ", "_") in STORE_LOCATIONS:
        code = hint_lower.replace(" ", "_")
        return code, STORE_LOCATIONS[code]

    # Fuzzy match - check if any alias contains the hint
    for alias, code in STORE_ALIASES.items():
        if hint_lower in alias or alias in hint_lower:
            return code, STORE_LOCATIONS.get(code)

    return None, None


# Weather code descriptions
WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

# Business impact based on weather - BEBANG HALO-HALO CHAIN
# Hot weather = GREAT (people want cold desserts), Cold/Rain = SLOW
WEATHER_IMPACT = {
    0: "🔥 PEAK SALES DAY! Presidential & Mango Graham will fly. Stock up on ice!",
    1: "🔥 Excellent halo-halo weather! Push Presidential, expect high traffic",
    2: "☀️ Good sales day - sunny enough for steady halo-halo demand",
    3: "⛅ Moderate traffic - push add-ons (leche flan, ube) to boost ticket",
    45: "🌫️ Foggy morning - slow start, picks up if sun breaks through",
    48: "🌫️ Expect slower traffic - prep for lighter sales",
    51: "🌧️ Light rain hurts walk-ins. Focus on GrabFood/FoodPanda",
    53: "🌧️ Rainy day - lower demand for cold desserts. Push delivery",
    55: "🌧️ Heavy drizzle - expect 30-40% dip. Minimal staffing OK",
    61: "🌧️ Rain = slow halo-halo day. Consider delivery promotions",
    63: "🌧️ Moderate rain - 40-50% traffic drop. Push online orders",
    65: "⚠️ Heavy rain - expect very slow day. Check staff safety first",
    66: "⚠️ Bad weather - minimal walk-ins expected",
    67: "⚠️ Severe weather - prioritize safety over sales",
    80: "🌦️ Showers - unpredictable traffic. Keep ice stocked for sunny breaks",
    81: "🌧️ Rain showers - delivery focus, expect 30% walk-in drop",
    82: "⛈️ Heavy showers - very slow for halo-halo. Safety first",
    95: "⛈️ STORM - Check store protocols! Safety > sales",
    96: "⛈️ SEVERE WEATHER - Follow emergency procedures",
    99: "🚨 EXTREME WEATHER - Store safety check required"
}


async def get_weather_forecast(entities: dict) -> dict:
    """
    Get weather forecast for a specific store/area or Metro Manila.

    Args:
        entities: Parsed entities (may include store, area, date)

    Returns:
        Weather data dict with pre-formatted response
    """
    # Resolve store location from entities
    store_hint = entities.get("store") or entities.get("area") or entities.get("location")
    store_code, store_info = resolve_store(store_hint) if store_hint else (None, None)

    # Use store coordinates or default to Metro Manila
    if store_info:
        lat = store_info["lat"]
        lon = store_info["lon"]
        location_name = f"{store_info['name']} ({store_info['area']})"
    else:
        lat = METRO_MANILA_LAT
        lon = METRO_MANILA_LON
        location_name = "Metro Manila"

    logger.info(f"Fetching weather for {location_name} at ({lat}, {lon})")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,sunrise,sunset",
                    "timezone": "Asia/Manila",
                    "forecast_days": 3
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

        # Parse current weather
        current = data.get("current", {})
        current_code = current.get("weather_code", 0)
        temp = current.get("temperature_2m", 0)
        feels_like = current.get("apparent_temperature", 0)
        humidity = current.get("relative_humidity_2m", 0)
        condition = WEATHER_DESCRIPTIONS.get(current_code, "Unknown")
        impact = WEATHER_IMPACT.get(current_code, "Normal conditions")

        # Parse daily forecast
        daily = data.get("daily", {})
        forecast_lines = []

        today = datetime.now().date()
        for i, date_str in enumerate(daily.get("time", [])[:3]):
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            code = daily["weather_code"][i]

            day_label = "Today" if date == today else (
                "Tomorrow" if date == today + timedelta(days=1) else
                date.strftime("%A")
            )

            day_condition = WEATHER_DESCRIPTIONS.get(code, "Unknown")
            temp_min = daily["temperature_2m_min"][i]
            temp_max = daily["temperature_2m_max"][i]
            rain_chance = daily["precipitation_probability_max"][i]

            # Rain emoji based on chance
            rain_icon = "🌧️" if rain_chance > 50 else ("🌦️" if rain_chance > 20 else "")

            forecast_lines.append(
                f"• {day_label}: {day_condition}, {temp_min:.0f}°-{temp_max:.0f}°C {rain_icon}{f' ({rain_chance}% rain)' if rain_chance > 0 else ''}"
            )

        # Weather emoji based on condition
        if current_code in [0, 1]:
            weather_emoji = "☀️"
        elif current_code in [2, 3]:
            weather_emoji = "⛅"
        elif current_code in [45, 48]:
            weather_emoji = "🌫️"
        elif current_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            weather_emoji = "🌧️"
        elif current_code in [95, 96, 99]:
            weather_emoji = "⛈️"
        else:
            weather_emoji = "🌤️"

        # Build friendly formatted response
        formatted_response = f"""{weather_emoji} **Weather at {location_name}**

**Right Now:** {condition}, {temp:.1f}°C (feels like {feels_like:.1f}°C)
Humidity: {humidity}%

**3-Day Forecast:**
{chr(10).join(forecast_lines)}

**💼 Business Impact:** {impact}"""

        return {
            "type": "weather",
            "formatted_response": formatted_response,
            "location": location_name,
            "store_code": store_code,
        }

    except httpx.HTTPError as e:
        logger.error(f"Weather API error: {e}")
        return {"error": "Could not fetch weather data", "details": str(e)}
    except Exception as e:
        logger.exception(f"Weather error: {e}")
        return {"error": "Weather service unavailable", "details": str(e)}

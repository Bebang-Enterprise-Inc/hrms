"""
Google Maps API integration for route planning.
Provides Directions API calls with route polylines and traffic-adjusted ETAs.
"""

import frappe
from frappe import _

from hrms.utils.sentry import set_backend_observability_context


def _get_api_key():
	"""Get Google Maps API key from environment, site config, or BEI HR Settings."""
	import os
	key = os.environ.get("GOOGLE_MAPS_API_KEY")
	if not key:
		key = frappe.conf.get("google_maps_api_key")
	if not key:
		try:
			key = frappe.db.get_single_value("BEI HR Settings", "google_maps_api_key")
		except Exception:
			pass
	if not key:
		frappe.throw(_("Google Maps API key not configured. Set GOOGLE_MAPS_API_KEY env var, google_maps_api_key in site_config.json, or BEI HR Settings."))
	return key


@frappe.whitelist()
def get_directions(origin_lat, origin_lng, waypoints_json, departure_time=None):
	"""
	Call Google Maps Directions API with waypoints.

	Args:
		origin_lat: Hub latitude
		origin_lng: Hub longitude
		waypoints_json: JSON array of {lat, lng, name} for each stop in order
		departure_time: ISO datetime for traffic estimation (optional)

	Returns:
		dict with polyline, legs (per-stop duration/distance), total_distance_km, total_duration_min
	"""
	import json
	import requests

	set_backend_observability_context(module="scm", action="get_directions")

	api_key = _get_api_key()
	waypoints = json.loads(waypoints_json) if isinstance(waypoints_json, str) else waypoints_json

	if not waypoints:
		frappe.throw(_("At least one waypoint is required"))

	origin = f"{origin_lat},{origin_lng}"

	# Last waypoint is destination, middle ones are waypoints
	destination = f"{waypoints[-1]['lat']},{waypoints[-1]['lng']}"
	intermediate = []
	for wp in waypoints[:-1]:
		intermediate.append(f"{wp['lat']},{wp['lng']}")

	params = {
		"origin": origin,
		"destination": destination,
		"key": api_key,
		"mode": "driving",
	}

	if intermediate:
		params["waypoints"] = "|".join(intermediate)

	if departure_time:
		from datetime import datetime
		import calendar
		dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
		params["departure_time"] = int(calendar.timegm(dt.timetuple()))

	resp = requests.get(
		"https://maps.googleapis.com/maps/api/directions/json",
		params=params,
		timeout=15,
	)
	data = resp.json()

	if data.get("status") != "OK":
		error_msg = data.get("error_message", data.get("status", "Unknown error"))
		frappe.throw(_(f"Google Directions API error: {error_msg}"))

	route = data["routes"][0]
	overview_polyline = route["overview_polyline"]["points"]

	legs = []
	total_distance_m = 0
	total_duration_s = 0

	for i, leg in enumerate(route["legs"]):
		total_distance_m += leg["distance"]["value"]
		duration_s = leg.get("duration_in_traffic", leg["duration"])["value"]
		total_duration_s += duration_s

		legs.append({
			"store": waypoints[i]["name"] if i < len(waypoints) else "Hub",
			"distance_km": round(leg["distance"]["value"] / 1000, 1),
			"duration_min": round(duration_s / 60, 1),
			"distance_text": leg["distance"]["text"],
			"duration_text": leg.get("duration_in_traffic", leg["duration"])["text"],
		})

	return {
		"polyline": overview_polyline,
		"legs": legs,
		"total_distance_km": round(total_distance_m / 1000, 1),
		"total_duration_min": round(total_duration_s / 60, 1),
		"waypoint_order": route.get("waypoint_order", list(range(len(intermediate)))),
	}


def decode_polyline(encoded):
	"""Decode a Google Maps encoded polyline into a list of [lat, lng] pairs."""
	points = []
	index = lat = lng = 0

	while index < len(encoded):
		for field in range(2):
			shift = result = 0
			while True:
				b = ord(encoded[index]) - 63
				index += 1
				result |= (b & 0x1F) << shift
				shift += 5
				if b < 0x20:
					break
			delta = ~(result >> 1) if (result & 1) else (result >> 1)
			if field == 0:
				lat += delta
			else:
				lng += delta

		points.append([lat / 1e5, lng / 1e5])

	return points

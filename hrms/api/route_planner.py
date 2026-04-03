"""
SCM Route Planner API — Smart Delivery Optimizer (S139)

Accepts store orders, calculates optimized route options with cost estimates,
and returns results with Google Maps polylines for map display.
"""

import json
import math
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from hrms.utils.sentry import set_backend_observability_context

# ── Seed data embedded in Python module (no filesystem dependency) ──
from hrms.api.route_planner_data import (
	SKU_MASTER,
	TRUCK_PROFILES,
	PROVIDER_RATES,
	STORE_DATA,
	DISTANCE_MATRIX,
	STORE_PAIRS,
)

_SEED = {
	"sku_master": SKU_MASTER,
	"truck_profiles": TRUCK_PROFILES,
	"provider_rates": PROVIDER_RATES,
	"store_data": STORE_DATA,
	"distance_matrix": DISTANCE_MATRIX,
	"store_pairs": STORE_PAIRS,
}


def _load_seed(name):
	"""Return embedded seed data by name."""
	if name not in _SEED:
		frappe.throw(_(f"Unknown seed data: {name}"))
	return _SEED[name]


def _get_sku_weights():
	"""Return dict of item -> weight_kg."""
	items = _load_seed("sku_master")
	return {i["item"]: i["weight_kg"] for i in items}


def _get_truck_profiles():
	"""Return list of truck profiles sorted by kg_limit ascending."""
	return sorted(_load_seed("truck_profiles"), key=lambda t: t["kg_limit"])


def _get_provider_rates():
	return _load_seed("provider_rates")


def _get_store_data():
	"""Return dict of store_name -> store info."""
	stores = _load_seed("store_data")
	return {s["name"]: s for s in stores}


def _get_distance_matrix():
	return _load_seed("distance_matrix")


def _get_store_pairs():
	return _load_seed("store_pairs")


# ── Truck Recommender ─────────────────────────────────────────────────────

def recommend_truck(total_kg, total_m3=None, truck_restriction=None):
	"""
	Recommend smallest truck that fits the load.
	Checks BOTH weight AND volume (when available).
	Respects per-store truck restrictions.
	"""
	profiles = _get_truck_profiles()
	warnings = []

	weight_truck = None
	volume_truck = None

	for t in profiles:
		if truck_restriction == "4W_only" and t["axle"] != "4W":
			continue
		if weight_truck is None and t["kg_limit"] >= total_kg:
			weight_truck = t
		if total_m3 is not None and volume_truck is None and t["m3_limit"] >= total_m3:
			volume_truck = t

	# If no truck fits, use the largest
	if weight_truck is None:
		weight_truck = profiles[-1]
		warnings.append(f"Load exceeds largest truck capacity ({profiles[-1]['kg_limit']}kg). Split required.")

	if total_m3 is not None and volume_truck is None:
		volume_truck = profiles[-1]
		warnings.append(f"Volume exceeds largest truck ({profiles[-1]['m3_limit']}m³). Split required.")

	# Pick the bigger of the two recommendations
	if volume_truck and volume_truck["kg_limit"] > weight_truck["kg_limit"]:
		recommended = volume_truck
		if weight_truck["type"] != volume_truck["type"]:
			warnings.append(
				f"Volume-constrained: needs {volume_truck['type']} by volume but only "
				f"{weight_truck['type']} by weight. Bulky items (cups/lids) take more space."
			)
	else:
		recommended = weight_truck

	utilization_weight = round(total_kg / recommended["kg_limit"], 2) if recommended["kg_limit"] > 0 else 0
	utilization_volume = round(total_m3 / recommended["m3_limit"], 2) if total_m3 and recommended["m3_limit"] > 0 else None

	if utilization_weight < 0.30:
		warnings.append(f"Low weight utilization ({utilization_weight:.0%}). Consider combining with nearby stores.")

	return {
		"truck": recommended,
		"utilization_weight": utilization_weight,
		"utilization_volume": utilization_volume,
		"warnings": warnings,
	}


# ── Route Sequencing (Nearest Neighbor) ───────────────────────────────────

def _haversine_km(lat1, lng1, lat2, lng2):
	R = 6371
	dlat = math.radians(lat2 - lat1)
	dlng = math.radians(lng2 - lng1)
	a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
	return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def sequence_stores(hub, stores_with_items, store_data):
	"""
	Nearest-neighbor sequencing: start from hub, pick closest unvisited store, repeat.
	Returns ordered list of stops.
	"""
	hub_info = store_data.get(hub, {})
	hub_lat = hub_info.get("lat", 14.5)
	hub_lng = hub_info.get("lng", 121.0)

	remaining = list(stores_with_items)
	ordered = []
	current_lat, current_lng = hub_lat, hub_lng

	while remaining:
		best_dist = float("inf")
		best_idx = 0
		for i, s in enumerate(remaining):
			si = store_data.get(s["store"], {})
			d = _haversine_km(current_lat, current_lng, si.get("lat", 14.5), si.get("lng", 121.0))
			if d < best_dist:
				best_dist = d
				best_idx = i

		stop = remaining.pop(best_idx)
		si = store_data.get(stop["store"], {})
		current_lat = si.get("lat", 14.5)
		current_lng = si.get("lng", 121.0)
		ordered.append(stop)

	return ordered


# ── Cost Calculator ───────────────────────────────────────────────────────

def _classify_route(hub, stores, store_data):
	"""Classify a route into a route region for provider rate lookup."""
	dm = _get_distance_matrix()
	max_dist = 0
	for s in stores:
		key = f"{hub}_{s}"
		entry = dm.get(key, {})
		d = entry.get("distance_km", 0)
		if d > max_dist:
			max_dist = d

	if hub == "3MD Marilao":
		if max_dist <= 30:
			return "north_a"
		elif max_dist <= 50:
			return "north_b"
		else:
			return "metro"
	else:  # Pinnacle Calamba
		if max_dist <= 30:
			return "south_a"
		elif max_dist <= 50:
			return "south_b"
		else:
			return "south_c"


def calculate_cost(hub, stores, truck_type, goods_type, provider=None):
	"""Calculate delivery cost for a route option."""
	rates = _get_provider_rates()
	results = []

	for prov_key, prov in rates.items():
		if provider and prov_key != provider:
			continue
		if prov["rate_type"] == "per_trip":
			type_rates = prov.get(goods_type)
			if not type_rates:
				continue
			route_region = _classify_route(hub, stores, _get_store_data())
			region_rates = type_rates.get(route_region)
			if not region_rates:
				# Try metro as fallback
				region_rates = type_rates.get("metro", {})
			rate = region_rates.get(truck_type, 0)
			if rate:
				results.append({"provider": prov_key, "name": prov["name"], "cost": rate, "breakdown": f"Trip rate: P{rate:,}"})

		elif prov["rate_type"] == "flat_plus_stops":
			type_rate = prov.get(goods_type)
			if not type_rate:
				continue
			num_stops = len(stores)
			extra = max(0, num_stops - type_rate["included_stops"])
			cost = type_rate["base_rate"] + extra * type_rate["extra_stop"]
			results.append({
				"provider": prov_key, "name": prov["name"], "cost": cost,
				"breakdown": f"Base P{type_rate['base_rate']:,} + {extra} extra stops × P{type_rate['extra_stop']:,}"
			})

		elif prov["rate_type"] == "per_store":
			type_rates = prov.get(goods_type)
			if not type_rates:
				continue
			cost = sum(type_rates.get(s, 0) for s in stores)
			matched = [s for s in stores if s in type_rates]
			if matched:
				results.append({
					"provider": prov_key, "name": prov["name"], "cost": cost,
					"breakdown": f"Per-store rates for {len(matched)} stores"
				})

	return sorted(results, key=lambda x: x["cost"])


# ── Multi-Option Generator ────────────────────────────────────────────────

def _generate_option(label, hub, stops, total_kg, total_m3, goods_type, truck_rec,
                     store_data, dm, optimize_for="cost"):
	"""Generate a single route option."""
	store_names = [s["store"] for s in stops]
	costs = calculate_cost(hub, store_names, truck_rec["truck"]["type"], goods_type)

	if not costs:
		# Fallback: use Coolitz metro rate
		cost_info = {"provider": "coolitz", "name": "Four Coolitz Corporation", "cost": 6160, "breakdown": "Fallback rate"}
	elif optimize_for == "cost":
		cost_info = costs[0]  # cheapest
	else:
		cost_info = costs[0]

	# Build ETA estimates from distance matrix
	hub_info = store_data.get(hub, {})
	total_distance = 0
	total_duration = 0
	formatted_stops = []

	# Use 5:00 AM default departure for cold, 8:00 AM for dry
	base_hour = 5 if goods_type == "cold" else 8
	now = datetime.now()
	current_time = datetime(now.year, now.month, now.day, base_hour, 0)

	for seq, stop in enumerate(stops):
		key = f"{hub}_{stop['store']}"
		entry = dm.get(key, {})
		leg_duration = entry.get("traffic_duration_min", entry.get("duration_min", 30))
		leg_distance = entry.get("distance_km", 20)

		if seq == 0:
			current_time += timedelta(minutes=leg_duration)
		else:
			# Inter-store travel: estimate 15 min + 10 min unloading
			current_time += timedelta(minutes=25)

		total_distance += leg_distance
		total_duration += leg_duration if seq == 0 else 25

		si = store_data.get(stop["store"], {})
		formatted_stops.append({
			"store": stop["store"],
			"sequence": seq + 1,
			"eta": current_time.strftime("%H:%M"),
			"kg": stop.get("total_kg", 0),
			"m3": stop.get("total_m3"),
			"items": stop.get("item_count", 0),
			"lat": si.get("lat"),
			"lng": si.get("lng"),
		})

	return {
		"label": label,
		"truck_type": truck_rec["truck"]["type"],
		"truck_label": truck_rec["truck"]["label"],
		"provider": cost_info["provider"],
		"provider_name": cost_info["name"],
		"estimated_cost": cost_info["cost"],
		"cost_breakdown": cost_info["breakdown"],
		"total_kg": round(total_kg, 1),
		"total_m3": round(total_m3, 1) if total_m3 else None,
		"truck_utilization_weight": truck_rec["utilization_weight"],
		"truck_utilization_volume": truck_rec["utilization_volume"],
		"stops": formatted_stops,
		"total_distance_km": round(total_distance, 1),
		"total_duration_min": round(total_duration),
		"hub": hub,
	}


# ── Main API Endpoints ───────────────────────────────────────────────────

@frappe.whitelist()
def optimize_route(stores_json, goods_type="cold", departure_time=None):
	"""
	Main optimization endpoint.

	Args:
		stores_json: JSON array of {store, items: [{sku, qty}]}
		goods_type: 'cold' or 'dry'
		departure_time: 'HH:MM' format (default: 05:00 for cold, 08:00 for dry)

	Returns:
		dict with options (3 ranked options), warnings
	"""
	set_backend_observability_context(module="scm", action="optimize_route", mutation_type="read")

	stores = json.loads(stores_json) if isinstance(stores_json, str) else stores_json
	if not stores:
		frappe.throw(_("No stores provided"))

	sku_weights = _get_sku_weights()
	store_data = _get_store_data()
	dm = _get_distance_matrix()
	warnings = []

	# Calculate per-store totals
	# S155/INT4: Accept projected_kg directly when stores come from schedule
	# (no item-level data). Falls back to item-based weight calculation.
	stores_with_totals = []
	for s in stores:
		projected = s.get("projected_kg")
		if projected is not None and not s.get("items"):
			# Schedule-sourced store with projected load from BOM demand
			stores_with_totals.append({
				"store": s["store"],
				"items": [],
				"total_kg": round(float(projected), 1),
				"total_m3": None,
				"item_count": s.get("item_count", 0),
			})
		else:
			store_kg = 0
			item_count = 0
			for item in s.get("items", []):
				w = sku_weights.get(item["sku"], 1.0)
				qty = float(item.get("qty", 0))
				store_kg += w * qty
				item_count += 1
			stores_with_totals.append({
				"store": s["store"],
				"items": s.get("items", []),
				"total_kg": round(store_kg, 1),
				"total_m3": None,
				"item_count": item_count,
			})

	total_kg = sum(s["total_kg"] for s in stores_with_totals)
	total_m3 = None  # Mode 1

	# Determine hub
	hub_votes = {}
	for s in stores_with_totals:
		si = store_data.get(s["store"], {})
		h = si.get("hub", "3MD Marilao")
		hub_votes[h] = hub_votes.get(h, 0) + 1
	hub = max(hub_votes, key=hub_votes.get) if hub_votes else "3MD Marilao"

	# Check truck restrictions
	for s in stores_with_totals:
		si = store_data.get(s["store"], {})
		restriction = si.get("truck_restriction")
		if restriction == "4W_only":
			warnings.append(f"{s['store']}: 4-wheeler trucks only (no 4T/6W)")
		elif restriction == "delivery_window_14_17":
			warnings.append(f"{s['store']}: delivery window 2-5 PM only")

	# Sequence stores using nearest-neighbor
	ordered_stops = sequence_stores(hub, stores_with_totals, store_data)

	# Check for split requirement
	profiles = _get_truck_profiles()
	max_truck = profiles[-1]
	needs_split = total_kg > max_truck["kg_limit"]

	if needs_split:
		warnings.append(f"Total load ({total_kg:.0f}kg) exceeds largest truck ({max_truck['kg_limit']}kg). Splitting into 2 routes.")

	# Generate 3 options
	options = []

	# Any store with 4W_only restriction?
	has_4w_restriction = any(
		store_data.get(s["store"], {}).get("truck_restriction") == "4W_only"
		for s in stores_with_totals
	)
	truck_restriction = "4W_only" if has_4w_restriction else None

	# Option A: Best Cost — smallest truck, cheapest provider
	truck_a = recommend_truck(total_kg, total_m3, truck_restriction)
	option_a = _generate_option("Best Cost", hub, ordered_stops, total_kg, total_m3,
	                            goods_type, truck_a, store_data, dm, "cost")
	option_a["rank"] = 1
	option_a["warnings"] = truck_a["warnings"]
	options.append(option_a)

	# Option B: Fastest — optimize for shortest delivery time
	# Re-sequence by distance from hub (closest first for fastest delivery)
	fast_stops = sorted(stores_with_totals, key=lambda s: (
		dm.get(f"{hub}_{s['store']}", {}).get("traffic_duration_min", 999)
	))
	truck_b = recommend_truck(total_kg, total_m3, truck_restriction)
	option_b = _generate_option("Fastest", hub, fast_stops, total_kg, total_m3,
	                            goods_type, truck_b, store_data, dm, "speed")
	option_b["rank"] = 2
	option_b["warnings"] = truck_b["warnings"]
	options.append(option_b)

	# Option C: Fewest Trucks — pack maximum stops, may use bigger truck
	# Use next size up if utilization > 80%
	if truck_a["utilization_weight"] > 0.80 and not needs_split:
		bigger_idx = min(len(profiles) - 1,
		                 next((i for i, t in enumerate(profiles) if t["type"] == truck_a["truck"]["type"]), 0) + 1)
		truck_c_profile = profiles[bigger_idx]
		truck_c = {
			"truck": truck_c_profile,
			"utilization_weight": round(total_kg / truck_c_profile["kg_limit"], 2),
			"utilization_volume": None,
			"warnings": [],
		}
	else:
		truck_c = truck_a

	option_c = _generate_option("Fewest Trucks", hub, ordered_stops, total_kg, total_m3,
	                            goods_type, truck_c, store_data, dm, "cost")
	option_c["rank"] = 3
	option_c["trucks_needed"] = 1 if not needs_split else 2
	option_c["warnings"] = truck_c["warnings"]
	options.append(option_c)

	return {
		"options": options,
		"warnings": warnings,
		"hub": hub,
		"total_kg": round(total_kg, 1),
		"total_m3": total_m3,
		"total_stores": len(stores),
		"goods_type": goods_type,
	}


@frappe.whitelist()
def get_store_orders_for_date(date=None):
	"""
	Pull today's approved store orders from BEI Store Order DocType.
	Returns per-store item list with qty.
	"""
	set_backend_observability_context(module="scm", action="get_store_orders_for_date", mutation_type="read")

	if not date:
		date = nowdate()

	# Check if BEI Store Order DocType exists
	if not frappe.db.exists("DocType", "BEI Store Order"):
		return {"stores": [], "message": "BEI Store Order DocType not found. Use manual entry."}

	orders = frappe.get_all(
		"BEI Store Order",
		filters={
			"delivery_date": date,
			"docstatus": 1,  # Submitted/approved
		},
		fields=["name", "store", "store_name"],
	)

	if not orders:
		return {"stores": [], "message": f"No approved orders for {date}"}

	stores = []
	for order in orders:
		items = frappe.get_all(
			"BEI Store Order Item",
			filters={"parent": order["name"]},
			fields=["item_code", "item_name", "qty", "uom", "cargo_category"],
		)
		stores.append({
			"store": order.get("store_name") or order["store"],
			"order_name": order["name"],
			"items": [
				{"sku": item["item_name"] or item["item_code"], "qty": float(item["qty"])}
				for item in items
			],
			"cargo_category": items[0].get("cargo_category") if items else None,
		})

	return {"stores": stores, "date": date, "count": len(stores)}


# ── S155: Schedule → Route Planner Integration ─────────────────────────────


def _normalize_warehouse_to_store_key(warehouse_name):
	"""Convert Frappe warehouse name to STORE_DATA display name.

	E.g. 'ARANETA CITY - BEI' → 'Araneta City'
	     'UP TOWN CENTER - BEBANG ENTERPRISE INC.' → 'UP Town Center'
	"""
	name = (warehouse_name or "").strip()
	for suffix in (" - BEBANG ENTERPRISE INC.", " - BEI", " - BKI"):
		if name.upper().endswith(suffix):
			name = name[: len(name) - len(suffix)].strip()
			break
	return name.title()


@frappe.whitelist()
def get_stores_for_delivery_date(date=None, goods_type="cold"):
	"""S155/INT1: Return stores scheduled for delivery on a given date.

	Reads from the published BEI Delivery Schedule to find which stores
	have deliveries on the given date + goods_type. Falls back to
	get_store_orders_for_date if no schedule exists.
	"""
	set_backend_observability_context(
		module="scm", action="get_stores_for_delivery_date", mutation_type="read",
	)

	if not date:
		date = nowdate()

	target_date = getdate(date)
	day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
	day_of_week = day_names[target_date.weekday()]

	# Find the Monday of this week
	monday = add_days(target_date, -target_date.weekday())

	# Look up published schedule
	week_name = frappe.db.get_value(
		"BEI Delivery Schedule Week",
		{"week_start": str(monday), "published": 1},
		"name",
	)

	if not week_name:
		# No published schedule — fall back to approved orders
		return get_store_orders_for_date(date)

	# Map goods_type to delivery_type filter
	delivery_type_filter = "COLD" if goods_type == "cold" else "DRY"

	entries = frappe.get_all(
		"BEI Delivery Schedule Entry",
		filters={
			"parent": week_name,
			"day_of_week": day_of_week,
			"delivery_type": delivery_type_filter,
		},
		fields=["store"],
	)

	if not entries:
		return {
			"stores": [],
			"date": date,
			"goods_type": goods_type,
			"source": "schedule",
			"message": f"No {goods_type} deliveries scheduled for {day_of_week}",
		}

	store_data = _get_store_data()
	stores = []
	for entry in entries:
		display_name = _normalize_warehouse_to_store_key(entry.store)
		si = store_data.get(display_name, {})
		stores.append({
			"store": display_name,
			"warehouse": entry.store,
			"lat": si.get("lat"),
			"lng": si.get("lng"),
			"hub": si.get("hub", "3MD Marilao"),
			"truck_restriction": si.get("truck_restriction"),
		})

	return {
		"stores": stores,
		"date": date,
		"goods_type": goods_type,
		"day_of_week": day_of_week,
		"source": "schedule",
		"count": len(stores),
	}


@frappe.whitelist()
def get_projected_load_for_store(store, date=None):
	"""S155/INT2: Get projected delivery load for a store from BOM demand snapshots.

	Queries BEI Inventory Risk Snapshot for the store and sums projected
	weight using the existing _get_sku_weights() lookup.
	"""
	set_backend_observability_context(
		module="scm", action="get_projected_load_for_store", mutation_type="read",
	)

	if not date:
		date = nowdate()

	# The store param may be a display name or warehouse name
	warehouse = store
	# If it looks like a display name (no ' - ' suffix), try to find the warehouse
	if " - " not in store:
		# Try to find matching warehouse
		wh = frappe.db.get_value(
			"Warehouse",
			{"name": ["like", f"%{store}%"], "is_group": 0, "disabled": 0},
			"name",
		)
		if wh:
			warehouse = wh

	# Query latest snapshots for this warehouse
	snapshots = frappe.get_all(
		"BEI Inventory Risk Snapshot",
		filters={
			"warehouse": warehouse,
			"snapshot_date": ["<=", str(date)],
		},
		fields=["item_code", "avg_daily_demand", "coverage_window_days"],
		order_by="snapshot_date desc",
		limit_page_length=500,
	)

	if not snapshots:
		return {
			"store": store,
			"warehouse": warehouse,
			"total_kg": 0,
			"total_m3": None,
			"item_count": 0,
			"items": [],
		}

	# Deduplicate: keep latest snapshot per item
	seen_items = set()
	unique_snapshots = []
	for snap in snapshots:
		if snap.item_code not in seen_items:
			seen_items.add(snap.item_code)
			unique_snapshots.append(snap)

	sku_weights = _get_sku_weights()
	total_kg = 0
	items = []
	for snap in unique_snapshots:
		demand = snap.avg_daily_demand or 0
		coverage = snap.coverage_window_days or 3
		projected_qty = demand * coverage
		weight_per_unit = sku_weights.get(snap.item_code, 1.0)
		item_kg = projected_qty * weight_per_unit
		total_kg += item_kg
		if projected_qty > 0:
			items.append({
				"item_code": snap.item_code,
				"projected_qty": round(projected_qty, 1),
				"weight_kg": round(item_kg, 1),
				"avg_daily_demand": round(demand, 2),
				"coverage_days": coverage,
			})

	return {
		"store": store,
		"warehouse": warehouse,
		"total_kg": round(total_kg, 1),
		"total_m3": None,
		"item_count": len(items),
		"items": items,
	}


@frappe.whitelist()
def load_orders_from_schedule(date=None, goods_type="cold"):
	"""S155/INT3: Load stores from schedule + their projected demand.

	Combines get_stores_for_delivery_date + get_projected_load_for_store
	for all scheduled stores. Returns data ready for optimize_route.
	"""
	set_backend_observability_context(
		module="scm", action="load_orders_from_schedule", mutation_type="read",
	)

	schedule_result = get_stores_for_delivery_date(date, goods_type)
	schedule_stores = schedule_result.get("stores", [])

	if not schedule_stores:
		return {
			"stores": [],
			"date": date or nowdate(),
			"goods_type": goods_type,
			"source": schedule_result.get("source", "schedule"),
			"message": schedule_result.get("message", "No stores scheduled"),
			"total_kg": 0,
		}

	stores_with_load = []
	total_kg = 0
	for s in schedule_stores:
		load = get_projected_load_for_store(s.get("warehouse") or s["store"], date)
		store_entry = {
			"store": s["store"],
			"warehouse": s.get("warehouse", ""),
			"projected_kg": load["total_kg"],
			"projected_m3": load.get("total_m3"),
			"item_count": load["item_count"],
			"lat": s.get("lat"),
			"lng": s.get("lng"),
			"hub": s.get("hub", "3MD Marilao"),
			"truck_restriction": s.get("truck_restriction"),
			"items": load.get("items", []),
		}
		stores_with_load.append(store_entry)
		total_kg += load["total_kg"]

	return {
		"stores": stores_with_load,
		"date": date or nowdate(),
		"goods_type": goods_type,
		"source": "schedule",
		"count": len(stores_with_load),
		"total_kg": round(total_kg, 1),
	}


@frappe.whitelist()
def get_route_options(stores_json, goods_type="cold", departure_time=None, include_directions=False):
	"""
	Wrapper: calls optimize_route + optionally Google Directions for polylines.

	Args:
		stores_json: JSON array of {store, items: [{sku, qty}]}
		goods_type: 'cold' or 'dry'
		departure_time: 'HH:MM'
		include_directions: If true, calls Google Directions API for polylines

	Returns:
		Full response with options, polylines, warnings
	"""
	set_backend_observability_context(module="scm", action="get_route_options", mutation_type="read")

	result = optimize_route(stores_json, goods_type, departure_time)

	if include_directions and result.get("options"):
		from hrms.api.google_maps import get_directions
		store_data = _get_store_data()

		for option in result["options"]:
			hub_info = store_data.get(option["hub"], {})
			if not hub_info.get("lat"):
				continue

			waypoints = []
			for stop in option["stops"]:
				if stop.get("lat") and stop.get("lng"):
					waypoints.append({
						"lat": stop["lat"],
						"lng": stop["lng"],
						"name": stop["store"],
					})

			if waypoints:
				try:
					directions = get_directions(
						hub_info["lat"], hub_info["lng"],
						json.dumps(waypoints),
						departure_time,
					)
					option["polyline"] = directions.get("polyline")
					option["total_distance_km"] = directions.get("total_distance_km", option["total_distance_km"])
					option["total_duration_min"] = directions.get("total_duration_min", option["total_duration_min"])

					# Update ETAs from actual directions
					for i, leg in enumerate(directions.get("legs", [])):
						if i < len(option["stops"]):
							option["stops"][i]["duration_text"] = leg.get("duration_text")
				except Exception as e:
					option["polyline"] = None
					option["directions_error"] = str(e)

	return result


@frappe.whitelist()
def get_available_stores():
	"""Return list of all stores with geocode data for the store selector."""
	set_backend_observability_context(module="scm", action="get_available_stores", mutation_type="read")

	store_data = _get_store_data()
	stores = [
		{
			"name": s["name"],
			"lat": s["lat"],
			"lng": s["lng"],
			"hub": s.get("hub"),
			"truck_restriction": s.get("truck_restriction"),
		}
		for s in store_data.values()
		if s["type"] == "store"
	]
	return sorted(stores, key=lambda s: (s.get("hub", ""), s["name"]))


@frappe.whitelist()
def get_sku_list():
	"""Return list of all SKUs with weights for item entry autocomplete."""
	set_backend_observability_context(module="scm", action="get_sku_list", mutation_type="read")

	items = _load_seed("sku_master")
	return [{"item": i["item"], "uom": i["uom"], "weight_kg": i["weight_kg"]} for i in items]

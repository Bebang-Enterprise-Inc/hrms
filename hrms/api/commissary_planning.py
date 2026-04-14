# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary Production Planning APIs (S136).
Recommendation engine, target setting, CEO audit view, and store demand aggregation.
"""

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime, today

from hrms.api.commissary import (
	PRODUCT_THRESHOLDS,
	DEFAULT_THRESHOLD,
	get_commissary_warehouse,
	get_product_threshold,
	resolve_outsourced_item_flag,
)
from hrms.api.commissary_dashboard import (
	_get_item_default_supplier_map,
	_hydrate_item_outsourcing_meta,
	_item_has_column,
	_normalize_outsourced_flag,
)
from hrms.utils.sentry import set_backend_observability_context

# Daily capacity estimate from MANCOM data: ~950 kg/day practical
DAILY_CAPACITY_KG = 950


# ============================================================
# P0-1: PRODUCTION RECOMMENDATIONS
# ============================================================


@frappe.whitelist()
def get_production_recommendations():
	"""
	Demand-driven production recommendation engine.
	Replaces hardcoded target=100 from get_production_suggestions().

	For each active FG item:
	- Uses product-specific target DI from PRODUCT_THRESHOLDS
	- Applies shelf life overproduction cap for short-life items
	- Applies wastage factor from 7-day production/wastage data
	- Detects outsourced items (Order vs Produce)
	- Checks BOM feasibility for in-house items
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_production_recommendations",
		mutation_type="read",
	)
	commissary_warehouse = get_commissary_warehouse()
	today_date = today()
	date_7_days_ago = add_days(today_date, -7)

	# Get all active FG items with current stock (same SQL pattern as get_days_inventory)
	items = frappe.db.sql(
		"""
		SELECT
			b.item_code,
			i.item_name,
			i.item_group,
			i.stock_uom as uom,
			IFNULL(b.actual_qty, 0) as current_stock,
			bom.name as bom_name,
			bom.quantity as bom_yield
		FROM `tabBin` b
		JOIN `tabItem` i ON i.name = b.item_code
		LEFT JOIN `tabBOM` bom
			ON bom.item = i.name
			AND bom.is_active = 1
			AND bom.is_default = 1
			AND bom.docstatus = 1
		WHERE b.warehouse = %s
		AND i.disabled = 0
		AND i.is_stock_item = 1
		AND (i.item_group = 'Finished Goods' OR i.item_code LIKE 'FG%%')
		ORDER BY i.item_name
		""",
		commissary_warehouse,
		as_dict=True,
	)

	# Also get FG items with zero stock (no Bin entry) but with active BOMs
	items_with_bom_no_stock = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.item_name,
			i.item_group,
			i.stock_uom as uom,
			0 as current_stock,
			bom.name as bom_name,
			bom.quantity as bom_yield
		FROM `tabItem` i
		JOIN `tabBOM` bom
			ON bom.item = i.name
			AND bom.is_active = 1
			AND bom.is_default = 1
			AND bom.docstatus = 1
		WHERE i.disabled = 0
		AND i.is_stock_item = 1
		AND (i.item_group = 'Finished Goods' OR i.name LIKE 'FG%%')
		AND i.name NOT IN (
			SELECT b2.item_code FROM `tabBin` b2
			WHERE b2.warehouse = %s AND b2.actual_qty > 0
		)
		ORDER BY i.item_name
		""",
		commissary_warehouse,
		as_dict=True,
	)

	# Merge, dedup by item_code
	seen = {item["item_code"] for item in items}
	for item in items_with_bom_no_stock:
		if item["item_code"] not in seen:
			items.append(item)
			seen.add(item["item_code"])

	# Batch: get 7-day consumption for all items
	consumption_map = _get_7day_consumption_map(commissary_warehouse, date_7_days_ago, today_date)

	# Batch: get 7-day wastage (Material Issue SLE) for all items
	wastage_map = _get_7day_wastage_map(commissary_warehouse, date_7_days_ago, today_date)

	# Batch: get 7-day production (Manufacture SLE) for all items
	production_map = _get_7day_production_map(commissary_warehouse, date_7_days_ago, today_date)

	# Batch: get pending Material Request demand for all items
	pending_demand_map = _get_pending_demand_map()

	# Batch: get last production date/qty for all items
	last_produced_map = _get_last_produced_map(commissary_warehouse)

	# Outsourced item metadata
	item_codes = [item["item_code"] for item in items]
	default_supplier_map = _get_item_default_supplier_map(item_codes)

	# BOM feasibility: batch get RM stock
	rm_stock_map = _get_rm_stock_map(commissary_warehouse)

	result = []
	for item in items:
		item_code = item["item_code"]
		current_stock = flt(item.get("current_stock", 0))

		# Step 2: 7-day consumption
		total_consumption = flt(consumption_map.get(item_code, 0))
		avg_daily = flt(total_consumption / 7, 2) if total_consumption > 0 else 0

		# Step 4: Days inventory
		days_inventory = flt(current_stock / avg_daily, 1) if avg_daily > 0 else (999 if current_stock > 0 else 0)

		# Step 5: Product-specific thresholds
		threshold = get_product_threshold(item_code)
		target_di = threshold["target_di"]
		shelf_life = threshold["shelf_life"]

		# Step 6-7: Target stock and raw recommended
		target_stock = flt(avg_daily * target_di, 2)
		pending_demand = flt(pending_demand_map.get(item_code, 0))
		raw_recommended = max(0, target_stock - current_stock + pending_demand)

		# Step 8: Shelf life cap for short-life items
		shelf_life_cap_applied = False
		if shelf_life <= 30 and avg_daily > 0:
			max_before_expiry = (shelf_life - days_inventory) * avg_daily
			if max_before_expiry <= 0:
				recommended_qty = 0
				shelf_life_cap_applied = True
			elif raw_recommended > max_before_expiry:
				recommended_qty = flt(max_before_expiry, 2)
				shelf_life_cap_applied = True
			else:
				recommended_qty = flt(raw_recommended, 2)
		elif avg_daily == 0:
			recommended_qty = 0
		else:
			recommended_qty = flt(raw_recommended, 2)

		# Step 9: Wastage factor
		wastage_7d = flt(wastage_map.get(item_code, 0))
		production_7d = flt(production_map.get(item_code, 0))
		wastage_factor = flt(1 + (wastage_7d / production_7d), 4) if production_7d > 0 else 1
		recommended_qty = flt(recommended_qty * wastage_factor, 2)

		# Step 10: Priority (only critical/high if there IS consumption demand)
		if avg_daily > 0 and (days_inventory == 0 or days_inventory < 1):
			priority = "critical"
		elif avg_daily > 0 and days_inventory < target_di * 0.5:
			priority = "high"
		else:
			priority = "normal"

		# Step 11: Outsourced detection
		item_meta = _hydrate_item_outsourcing_meta(
			dict(item), default_supplier_map
		)
		item_meta = _normalize_outsourced_flag(item_meta)
		is_outsourced = bool(item_meta.get("is_outsourced_item"))

		# BOM feasibility (only for in-house items with BOM)
		has_bom = bool(item.get("bom_name"))
		max_producible = None
		bottleneck_rm = None
		if has_bom and not is_outsourced and recommended_qty > 0:
			feasibility = _check_bom_feasibility_batch(
				item_code, item["bom_name"], flt(item.get("bom_yield", 1)),
				recommended_qty, rm_stock_map
			)
			max_producible = feasibility["max_producible"]
			bottleneck_rm = feasibility.get("bottleneck_rm")

		# Supplier info for outsourced items
		supplier_lead_time_days = None
		default_supplier = None
		if is_outsourced:
			default_supplier = item_meta.get("default_supplier") or item_meta.get("outsourced_supplier")
			supplier_lead_time_days = 14  # Default lead time

		# Last produced
		last_info = last_produced_map.get(item_code, {})

		action = "order" if is_outsourced else "produce"

		result.append({
			"item_code": item_code,
			"item_name": item.get("item_name", ""),
			"current_stock": current_stock,
			"uom": item.get("uom", "KG"),
			"avg_daily_consumption": avg_daily,
			"days_inventory": days_inventory if days_inventory < 999 else None,
			"target_di": target_di,
			"shelf_life_days": shelf_life,
			"target_stock": target_stock,
			"pending_demand": pending_demand,
			"recommended_qty": recommended_qty,
			"wastage_factor": wastage_factor,
			"shelf_life_cap_applied": shelf_life_cap_applied,
			"priority": priority,
			"is_outsourced": is_outsourced,
			"action": action,
			"has_bom": has_bom,
			"bom_name": item.get("bom_name"),
			"max_producible": max_producible,
			"bottleneck_rm": bottleneck_rm,
			"last_produced": last_info.get("date"),
			"last_produced_qty": last_info.get("qty"),
			"default_supplier": default_supplier,
			"supplier_lead_time_days": supplier_lead_time_days,
		})

	# Sort by priority
	priority_order = {"critical": 0, "high": 1, "normal": 2}
	result.sort(key=lambda x: (priority_order.get(x["priority"], 99), x["item_name"]))

	# Capacity check
	total_recommended_kg = sum(
		r["recommended_qty"] for r in result
		if r["action"] == "produce" and r["uom"] == "KG"
	)

	return {
		"success": True,
		"data": result,
		"summary": {
			"total_items": len(result),
			"in_house_items": sum(1 for r in result if r["action"] == "produce"),
			"outsourced_items": sum(1 for r in result if r["action"] == "order"),
			"critical_count": sum(1 for r in result if r["priority"] == "critical"),
			"high_count": sum(1 for r in result if r["priority"] == "high"),
			"total_recommended_kg": flt(total_recommended_kg, 2),
			"daily_capacity_kg": DAILY_CAPACITY_KG,
			"capacity_utilization_pct": flt(total_recommended_kg / DAILY_CAPACITY_KG * 100, 1) if DAILY_CAPACITY_KG > 0 else 0,
		},
		"calculation_period": f"{date_7_days_ago} to {today_date}",
	}


# ============================================================
# P0-2: SET PRODUCTION TARGETS
# ============================================================


@frappe.whitelist()
def set_production_targets(production_date=None, targets=None):
	"""
	Supervisor sets daily production targets. Logged immutably.
	recommended_qty is re-fetched server-side to prevent manipulation.
	"""
	set_backend_observability_context(
		module="commissary",
		action="set_production_targets",
		mutation_type="create",
	)
	if isinstance(targets, str):
		targets = json.loads(targets)
	if not targets:
		frappe.throw(_("No targets provided"))

	production_date = production_date or today()
	production_date = getdate(production_date)

	# Validate role
	user_roles = frappe.get_roles()
	if not any(r in user_roles for r in ["Commissary User", "Commissary Manager", "Commissary Supervisor", "System Manager"]):
		frappe.throw(_("You do not have permission to set production targets"))

	# Re-fetch recommendations server-side (anti-manipulation)
	recs_response = get_production_recommendations()
	recs_data = recs_response.get("data", [])
	rec_map = {r["item_code"]: r for r in recs_data}

	saved = []
	failed = []

	try:
		frappe.db.savepoint("set_targets")

		# Get or create the BEI Production Target doc for this date
		existing = frappe.db.exists(
			"BEI Production Target",
			{"production_date": production_date},
		)

		if existing:
			target_doc = frappe.get_doc("BEI Production Target", existing)
		else:
			target_doc = frappe.new_doc("BEI Production Target")
			target_doc.production_date = production_date
			target_doc.status = "Set"

		# Build item map for existing items
		existing_items = {row.item_code: row for row in target_doc.get("items", [])}

		for t in targets:
			item_code = t.get("item_code")
			target_qty = flt(t.get("target_qty", 0))
			reason = t.get("reason", "")

			if not item_code:
				failed.append({"item_code": item_code, "error": "Missing item_code"})
				continue

			try:
				rec = rec_map.get(item_code, {})
				recommended_qty = flt(rec.get("recommended_qty", 0))

				# Compute deviation
				deviation_pct = flt(
					(target_qty - recommended_qty) / recommended_qty * 100, 1
				) if recommended_qty > 0 else 0

				# Get previous target for log
				previous_target = 0
				if item_code in existing_items:
					previous_target = flt(existing_items[item_code].target_qty)

				# Determine action type for log
				if item_code in existing_items:
					action_type = "adjusted" if previous_target != target_qty else "set"
					# Update existing row
					row = existing_items[item_code]
					row.recommended_qty = recommended_qty
					row.target_qty = target_qty
					row.reason = reason
				else:
					action_type = "set"
					# Add new row
					row = target_doc.append("items", {
						"item_code": item_code,
						"recommended_qty": recommended_qty,
						"target_qty": target_qty,
						"reason": reason,
						"actual_produced": 0,
					})

				# Create immutable log entry
				log_entry = frappe.new_doc("BEI Production Target Log")
				log_entry.production_date = production_date
				log_entry.item_code = item_code
				log_entry.action = action_type
				log_entry.recommended_qty = recommended_qty
				log_entry.previous_target = previous_target
				log_entry.new_target = target_qty
				log_entry.reason = reason
				log_entry.changed_by = frappe.session.user
				log_entry.changed_at = now_datetime()
				log_entry.insert(ignore_permissions=True)

				saved.append({
					"item_code": item_code,
					"recommended_qty": recommended_qty,
					"target_qty": target_qty,
					"deviation_pct": deviation_pct,
				})
			except Exception as e:
				failed.append({"item_code": item_code, "error": str(e)})

		# Save the target doc
		target_doc.set_by = frappe.session.user
		target_doc.set_at = now_datetime()
		target_doc.save(ignore_permissions=True)

		frappe.db.release_savepoint("set_targets")

		if failed and not saved:
			return {"success": False, "saved": [], "failed": failed, "error": "All items failed"}

		return {
			"success": True,
			"saved": saved,
			"failed": failed,
			"target_name": target_doc.name,
		}

	except Exception as e:
		frappe.db.rollback(save_point="set_targets")
		frappe.log_error("set_production_targets failed", str(e))
		return {"success": False, "saved": [], "failed": failed, "error": str(e)}


# ============================================================
# P0-3: GET PRODUCTION TARGETS
# ============================================================


@frappe.whitelist()
def get_production_targets(production_date=None):
	"""
	Returns current targets for a date, with recommended vs target comparison.
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_production_targets",
		mutation_type="read",
	)
	production_date = getdate(production_date or today())

	existing = frappe.db.exists(
		"BEI Production Target",
		{"production_date": production_date},
	)

	if not existing:
		return {
			"success": True,
			"production_date": str(production_date),
			"items": [],
			"summary": {
				"total_recommended": 0,
				"total_targeted": 0,
				"total_produced": 0,
				"overall_deviation_pct": 0,
				"overall_completion_pct": 0,
			},
			"has_targets": False,
		}

	target_doc = frappe.get_doc("BEI Production Target", existing)

	items = []
	total_recommended = 0
	total_targeted = 0
	total_produced = 0

	for row in target_doc.get("items", []):
		recommended_qty = flt(row.recommended_qty)
		target_qty = flt(row.target_qty)
		actual_produced = flt(row.actual_produced)

		deviation_pct = flt(
			(target_qty - recommended_qty) / recommended_qty * 100, 1
		) if recommended_qty > 0 else 0

		completion_pct = flt(
			actual_produced / target_qty * 100, 1
		) if target_qty > 0 else (100 if target_qty == 0 else 0)

		total_recommended += recommended_qty
		total_targeted += target_qty
		total_produced += actual_produced

		items.append({
			"item_code": row.item_code,
			"recommended_qty": recommended_qty,
			"target_qty": target_qty,
			"deviation_pct": deviation_pct,
			"actual_produced": actual_produced,
			"completion_pct": completion_pct,
			"set_by": target_doc.set_by,
			"set_at": str(target_doc.set_at) if target_doc.set_at else None,
			"reason": row.reason or "",
		})

	overall_deviation = flt(
		(total_targeted - total_recommended) / total_recommended * 100, 1
	) if total_recommended > 0 else 0

	overall_completion = flt(
		total_produced / total_targeted * 100, 1
	) if total_targeted > 0 else (100 if total_targeted == 0 else 0)

	return {
		"success": True,
		"production_date": str(production_date),
		"items": items,
		"summary": {
			"total_recommended": flt(total_recommended, 2),
			"total_targeted": flt(total_targeted, 2),
			"total_produced": flt(total_produced, 2),
			"overall_deviation_pct": overall_deviation,
			"overall_completion_pct": overall_completion,
		},
		"has_targets": True,
		"target_name": target_doc.name,
		"status": target_doc.status,
	}


# ============================================================
# P0-4: RM REQUIREMENTS FOR PLAN
# ============================================================


@frappe.whitelist()
def get_rm_requirements_for_plan(targets=None):
	"""
	Given target quantities, explode BOMs to show total RM needed.
	Extends check_production_feasibility() to multi-item planning.
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_rm_requirements_for_plan",
		mutation_type="read",
	)
	if isinstance(targets, str):
		targets = json.loads(targets)
	if not targets:
		return {"success": True, "rm_requirements": [], "feasibility": {"all_feasible": True, "bottlenecks": [], "items_blocked": []}}

	commissary_warehouse = get_commissary_warehouse()
	rm_stock_map = _get_rm_stock_map(commissary_warehouse)

	# Aggregate RM requirements across all target items
	rm_requirements: dict[str, dict] = {}  # rm_code -> {total_required, consumed_by, ...}
	items_blocked = []

	for t in targets:
		item_code = t.get("item_code")
		qty = flt(t.get("qty", 0))
		if qty <= 0:
			continue

		# Get BOM
		bom = frappe.db.get_value(
			"BOM",
			{"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
			["name", "quantity"],
			as_dict=True,
		)
		if not bom:
			continue

		bom_items = frappe.get_all(
			"BOM Item",
			filters={"parent": bom.name},
			fields=["item_code", "item_name", "qty", "stock_uom"],
		)

		scale_factor = qty / flt(bom.quantity) if flt(bom.quantity) > 0 else 0
		item_has_deficit = False

		for mat in bom_items:
			rm_code = mat.item_code
			required_qty = flt(mat.qty) * scale_factor

			if rm_code not in rm_requirements:
				rm_requirements[rm_code] = {
					"rm_code": rm_code,
					"rm_name": mat.item_name,
					"uom": mat.stock_uom,
					"total_required": 0,
					"current_stock": flt(rm_stock_map.get(rm_code, 0)),
					"consumed_by": [],
				}

			rm_requirements[rm_code]["total_required"] += required_qty
			rm_requirements[rm_code]["consumed_by"].append({
				"item_code": item_code,
				"qty_needed": flt(required_qty, 2),
			})

	# Calculate surplus/deficit
	bottlenecks = []
	rm_list = []
	for rm_code, rm in rm_requirements.items():
		rm["total_required"] = flt(rm["total_required"], 2)
		surplus_deficit = flt(rm["current_stock"] - rm["total_required"], 2)
		rm["surplus_deficit"] = surplus_deficit
		rm["status"] = "sufficient" if surplus_deficit >= 0 else "deficit"

		if surplus_deficit < 0:
			bottlenecks.append(f"{rm_code} {rm['rm_name']}: need {rm['total_required']}, have {rm['current_stock']}")
			# Find which items are blocked by this deficit
			for cb in rm["consumed_by"]:
				if cb["item_code"] not in items_blocked:
					items_blocked.append(cb["item_code"])

		rm_list.append(rm)

	# Sort: deficits first
	rm_list.sort(key=lambda x: (0 if x["status"] == "deficit" else 1, x["rm_name"]))

	return {
		"success": True,
		"rm_requirements": rm_list,
		"feasibility": {
			"all_feasible": len(bottlenecks) == 0,
			"bottlenecks": bottlenecks,
			"items_blocked": items_blocked,
		},
	}


# ============================================================
# P3-1: PRODUCTION AUDIT TRAIL (CEO)
# ============================================================


@frappe.whitelist()
def get_production_audit_trail(date_from=None, date_to=None, item_code=None):
	"""
	Returns all target changes with recommended vs target comparison.
	For CEO anti-manipulation monitoring.
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_production_audit_trail",
		mutation_type="read",
	)
	date_from = getdate(date_from or add_days(today(), -7))
	date_to = getdate(date_to or today())

	# Get all target docs in range
	filters = {
		"production_date": ["between", [date_from, date_to]],
	}
	target_docs = frappe.get_all(
		"BEI Production Target",
		filters=filters,
		fields=["name", "production_date", "status"],
		order_by="production_date desc",
	)

	entries = []
	for td in target_docs:
		target_doc = frappe.get_doc("BEI Production Target", td.name)

		for row in target_doc.get("items", []):
			if item_code and row.item_code != item_code:
				continue

			recommended_qty = flt(row.recommended_qty)
			target_qty = flt(row.target_qty)
			actual_produced = flt(row.actual_produced)

			deviation_pct = flt(
				(target_qty - recommended_qty) / recommended_qty * 100, 1
			) if recommended_qty > 0 else 0

			completion_pct = flt(
				actual_produced / target_qty * 100, 1
			) if target_qty > 0 else (100 if target_qty == 0 else 0)

			# Get adjustment logs for this item+date
			logs = frappe.get_all(
				"BEI Production Target Log",
				filters={
					"production_date": td.production_date,
					"item_code": row.item_code,
				},
				fields=["action", "previous_target", "new_target", "reason", "changed_by", "changed_at"],
				order_by="changed_at asc",
				limit_page_length=50,
			)

			adjustments = [
				{
					"action": log.action,
					"previous": flt(log.previous_target),
					"new": flt(log.new_target),
					"reason": log.reason or "",
					"by": log.changed_by,
					"at": str(log.changed_at) if log.changed_at else None,
				}
				for log in logs
			]

			# Get item_name
			item_name = frappe.db.get_value("Item", row.item_code, "item_name") or row.item_code

			entries.append({
				"production_date": str(td.production_date),
				"item_code": row.item_code,
				"item_name": item_name,
				"recommended_qty": recommended_qty,
				"final_target_qty": target_qty,
				"actual_produced": actual_produced,
				"deviation_pct": deviation_pct,
				"completion_pct": completion_pct,
				"adjustments": adjustments,
			})

	# Summary
	if entries:
		avg_deviation = flt(sum(abs(e["deviation_pct"]) for e in entries) / len(entries), 1)
		items_over = sum(1 for e in entries if e["deviation_pct"] > 10)
		items_under = sum(1 for e in entries if e["deviation_pct"] < -10)
		items_on = sum(1 for e in entries if abs(e["deviation_pct"]) <= 10)
		total_targeted = sum(e["final_target_qty"] for e in entries)
		total_produced = sum(e["actual_produced"] for e in entries)
		overall_completion = flt(total_produced / total_targeted * 100, 1) if total_targeted > 0 else 0
	else:
		avg_deviation = 0
		items_over = items_under = items_on = 0
		overall_completion = 0

	return {
		"success": True,
		"entries": entries,
		"summary": {
			"avg_deviation_pct": avg_deviation,
			"items_over_target": items_over,
			"items_under_target": items_under,
			"items_on_target": items_on,
			"overall_completion_pct": overall_completion,
		},
	}


# ============================================================
# P3-2: PRODUCTION PERFORMANCE SUMMARY (CEO)
# ============================================================


@frappe.whitelist()
def get_production_performance_summary(period="week", date=None):
	"""
	Weekly/monthly rollup for CEO reporting.
	Includes alerts for manipulation detection.
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_production_performance_summary",
		mutation_type="read",
	)
	ref_date = getdate(date or today())

	if period == "month":
		# Current month
		date_from = ref_date.replace(day=1)
		if ref_date.month == 12:
			date_to = ref_date.replace(year=ref_date.year + 1, month=1, day=1)
		else:
			date_to = ref_date.replace(month=ref_date.month + 1, day=1)
		date_to = add_days(date_to, -1)
		period_label = ref_date.strftime("%Y-%m")
	else:
		# Current week (Monday to Sunday)
		weekday = ref_date.weekday()
		date_from = add_days(ref_date, -weekday)
		date_to = add_days(date_from, 6)
		iso = ref_date.isocalendar()
		period_label = f"{iso[0]}-W{iso[1]:02d}"

	# Get all target docs in range
	target_docs = frappe.get_all(
		"BEI Production Target",
		filters={"production_date": ["between", [date_from, date_to]]},
		fields=["name", "production_date"],
		order_by="production_date asc",
	)

	daily_breakdown = []
	item_agg: dict[str, dict] = {}
	alerts = []

	# Track consecutive deviation/underproduction per item
	item_consecutive_over: dict[str, int] = {}
	item_consecutive_under: dict[str, int] = {}

	for td in target_docs:
		doc = frappe.get_doc("BEI Production Target", td.name)
		day_rec = day_tgt = day_prod = 0

		for row in doc.get("items", []):
			rec = flt(row.recommended_qty)
			tgt = flt(row.target_qty)
			act = flt(row.actual_produced)
			day_rec += rec
			day_tgt += tgt
			day_prod += act

			# Item aggregation
			if row.item_code not in item_agg:
				item_agg[row.item_code] = {
					"item_code": row.item_code,
					"total_recommended": 0,
					"total_targeted": 0,
					"total_produced": 0,
					"days_count": 0,
					"deviations": [],
					"completions": [],
				}
			ia = item_agg[row.item_code]
			ia["total_recommended"] += rec
			ia["total_targeted"] += tgt
			ia["total_produced"] += act
			ia["days_count"] += 1

			dev = flt((tgt - rec) / rec * 100, 1) if rec > 0 else 0
			comp = flt(act / tgt * 100, 1) if tgt > 0 else 100
			ia["deviations"].append(dev)
			ia["completions"].append(comp)

			# Track consecutive patterns for alerts
			if dev > 30:
				item_consecutive_over[row.item_code] = item_consecutive_over.get(row.item_code, 0) + 1
			else:
				item_consecutive_over[row.item_code] = 0

			if comp < 50:
				item_consecutive_under[row.item_code] = item_consecutive_under.get(row.item_code, 0) + 1
			else:
				item_consecutive_under[row.item_code] = 0

		day_dev = flt((day_tgt - day_rec) / day_rec * 100, 1) if day_rec > 0 else 0
		day_comp = flt(day_prod / day_tgt * 100, 1) if day_tgt > 0 else 0

		daily_breakdown.append({
			"date": str(td.production_date),
			"total_recommended": flt(day_rec, 2),
			"total_targeted": flt(day_tgt, 2),
			"total_produced": flt(day_prod, 2),
			"deviation_pct": day_dev,
			"completion_pct": day_comp,
		})

	# Build item breakdown
	item_breakdown = []
	for ic, ia in item_agg.items():
		item_name = frappe.db.get_value("Item", ic, "item_name") or ic
		avg_dev = flt(sum(abs(d) for d in ia["deviations"]) / len(ia["deviations"]), 1) if ia["deviations"] else 0
		avg_comp = flt(sum(ia["completions"]) / len(ia["completions"]), 1) if ia["completions"] else 0

		# Trend: compare first half vs second half
		devs = ia["deviations"]
		if len(devs) >= 2:
			first_half = sum(devs[:len(devs)//2]) / max(len(devs)//2, 1)
			second_half = sum(devs[len(devs)//2:]) / max(len(devs) - len(devs)//2, 1)
			trend = "increasing" if second_half > first_half + 5 else ("decreasing" if second_half < first_half - 5 else "stable")
		else:
			trend = "stable"

		item_breakdown.append({
			"item_code": ic,
			"item_name": item_name,
			"total_recommended": flt(ia["total_recommended"], 2),
			"total_targeted": flt(ia["total_targeted"], 2),
			"total_produced": flt(ia["total_produced"], 2),
			"avg_deviation_pct": avg_dev,
			"avg_completion_pct": avg_comp,
			"trend": trend,
		})

	# Generate alerts
	for ic, count in item_consecutive_over.items():
		if count >= 3:
			item_name = frappe.db.get_value("Item", ic, "item_name") or ic
			alerts.append(f"{ic} ({item_name}): Target consistently 40%+ above recommended ({count} days)")

	for ic, count in item_consecutive_under.items():
		if count >= 3:
			item_name = frappe.db.get_value("Item", ic, "item_name") or ic
			alerts.append(f"{ic} ({item_name}): Chronic under-production (completion < 50% for {count} days)")

	# Check for chronic deviation in period
	for ib in item_breakdown:
		if ib["avg_deviation_pct"] > 25:
			alerts.append(f"{ib['item_code']} ({ib['item_name']}): Average deviation {ib['avg_deviation_pct']}% for the period")

	return {
		"success": True,
		"period": period_label,
		"date_from": str(date_from),
		"date_to": str(date_to),
		"daily_breakdown": daily_breakdown,
		"item_breakdown": sorted(item_breakdown, key=lambda x: -x["avg_deviation_pct"]),
		"alerts": alerts,
	}


# ============================================================
# P4-1: STORE DEMAND FOR COMMISSARY
# ============================================================


@frappe.whitelist()
def get_store_demand_for_commissary():
	"""
	Aggregates store-level demand that the commissary needs to fulfill.
	Data sources: pending Material Requests + per-store DTL.
	"""
	set_backend_observability_context(
		module="commissary",
		action="get_store_demand_for_commissary",
		mutation_type="read",
	)
	commissary_warehouse = get_commissary_warehouse()
	today_date = today()
	date_7_days_ago = add_days(today_date, -7)

	# Get pending Material Request items grouped by item+warehouse
	pending_mrs = frappe.db.sql(
		"""
		SELECT
			mri.item_code,
			i.item_name,
			mr.set_warehouse as store_warehouse,
			SUM(mri.qty - IFNULL(mri.ordered_qty, 0)) as pending_qty
		FROM `tabMaterial Request Item` mri
		JOIN `tabMaterial Request` mr ON mr.name = mri.parent
		JOIN `tabItem` i ON i.name = mri.item_code
		WHERE mr.docstatus = 1
		AND mr.status IN ('Pending', 'Partially Ordered')
		AND (i.item_group = 'Finished Goods' OR mri.item_code LIKE 'FG%%')
		AND (mri.qty - IFNULL(mri.ordered_qty, 0)) > 0
		GROUP BY mri.item_code, mr.set_warehouse
		ORDER BY mri.item_code, mr.set_warehouse
		""",
		as_dict=True,
	)

	# Build demand_by_item structure
	demand_map: dict[str, dict] = {}

	for mr in pending_mrs:
		item_code = mr.item_code
		if item_code not in demand_map:
			demand_map[item_code] = {
				"item_code": item_code,
				"item_name": mr.item_name,
				"total_pending_orders": 0,
				"total_projected_demand": 0,
				"stores_ordering": 0,
				"stores_at_risk": 0,
				"store_breakdown": [],
			}

		dm = demand_map[item_code]
		pending_qty = flt(mr.pending_qty)
		dm["total_pending_orders"] += pending_qty
		dm["stores_ordering"] += 1

		# Get store DI for this item
		store_warehouse = mr.store_warehouse
		store_stock = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": item_code, "warehouse": store_warehouse},
				"actual_qty",
			) or 0
		)

		# 7-day consumption at store level
		store_consumption = flt(
			frappe.db.sql(
				"""
				SELECT IFNULL(SUM(ABS(sed.qty)), 0)
				FROM `tabStock Entry` se
				JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
				WHERE se.docstatus = 1
				AND se.posting_date BETWEEN %s AND %s
				AND sed.s_warehouse = %s
				AND sed.item_code = %s
				""",
				(date_7_days_ago, today_date, store_warehouse, item_code),
			)[0][0] or 0
		)
		store_avg_daily = flt(store_consumption / 7, 2) if store_consumption > 0 else 0
		store_di = flt(store_stock / store_avg_daily, 1) if store_avg_daily > 0 else (999 if store_stock > 0 else 0)

		if store_di < 3:
			status = "critical"
			dm["stores_at_risk"] += 1
		elif store_di < 7:
			status = "low"
			dm["stores_at_risk"] += 1
		else:
			status = "ok"

		# Store name from warehouse
		store_name = store_warehouse.split(" - ")[0] if store_warehouse else store_warehouse

		dm["store_breakdown"].append({
			"store": store_name,
			"warehouse": store_warehouse,
			"pending": flt(pending_qty, 2),
			"current_stock": flt(store_stock, 2),
			"di": store_di if store_di < 999 else None,
			"avg_daily": store_avg_daily,
			"status": status,
		})

	# Calculate projected demand (pending + stores at risk)
	for dm in demand_map.values():
		dm["total_projected_demand"] = flt(
			dm["total_pending_orders"] + sum(
				s["avg_daily"] * 3  # 3-day projected need for at-risk stores
				for s in dm["store_breakdown"]
				if s["status"] in ("critical", "low")
			), 2
		)

	demand_list = sorted(demand_map.values(), key=lambda x: -x["total_projected_demand"])

	return {
		"success": True,
		"demand_by_item": demand_list,
		"summary": {
			"total_items_in_demand": len(demand_list),
			"total_stores_at_risk": sum(d["stores_at_risk"] for d in demand_list),
			"total_pending_order_qty": flt(sum(d["total_pending_orders"] for d in demand_list), 2),
		},
	}


# ============================================================
# STOCK ENTRY HOOKS (P1-3)
# ============================================================


def on_stock_entry_submit(doc, method=None):
	"""Hook: after Stock Entry submit, update production actuals if Manufacture type."""
	if doc.stock_entry_type != "Manufacture":
		return
	_update_production_actuals_from_se(doc, multiplier=1)


def on_stock_entry_cancel(doc, method=None):
	"""Hook: after Stock Entry cancel, decrement production actuals."""
	if doc.stock_entry_type != "Manufacture":
		return
	_update_production_actuals_from_se(doc, multiplier=-1)


def _update_production_actuals_from_se(doc, multiplier=1):
	"""
	Update BEI Production Target actual_produced for items in this Stock Entry.
	Idempotency: track SE name in the target doc's remarks to prevent double-counting.
	"""
	posting_date = getdate(doc.posting_date)

	existing = frappe.db.exists(
		"BEI Production Target",
		{"production_date": posting_date},
	)
	if not existing:
		return  # No target set for this date — nothing to update

	target_doc = frappe.get_doc("BEI Production Target", existing)

	# Idempotency check: store processed SE names
	processed_ses = (target_doc.get("processed_stock_entries") or "").split(",")
	se_name = doc.name

	if multiplier > 0 and se_name in processed_ses:
		return  # Already processed
	if multiplier < 0 and se_name not in processed_ses:
		return  # Never processed, nothing to undo

	# Get produced items from SE (t_warehouse = commissary = FG produced)
	commissary_warehouse = get_commissary_warehouse()
	item_map = {row.item_code: row for row in target_doc.get("items", [])}
	updated = False

	for sed in doc.get("items", []):
		if sed.t_warehouse == commissary_warehouse and sed.item_code in item_map:
			row = item_map[sed.item_code]
			row.actual_produced = flt(row.actual_produced, 2) + flt(sed.qty, 2) * multiplier
			if row.actual_produced < 0:
				row.actual_produced = 0
			updated = True

	if updated:
		# Update processed SE list
		if multiplier > 0:
			processed_ses.append(se_name)
		else:
			processed_ses = [s for s in processed_ses if s != se_name]

		target_doc.processed_stock_entries = ",".join(s for s in processed_ses if s)
		target_doc.save(ignore_permissions=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _get_7day_consumption_map(warehouse, date_from, date_to):
	"""Batch query: get total outgoing qty per item in the last 7 days."""
	rows = frappe.db.sql(
		"""
		SELECT sed.item_code, IFNULL(SUM(ABS(sed.qty)), 0) as total_out
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		AND se.posting_date BETWEEN %s AND %s
		AND sed.s_warehouse = %s
		GROUP BY sed.item_code
		""",
		(date_from, date_to, warehouse),
		as_dict=True,
	)
	return {r.item_code: flt(r.total_out) for r in rows}


def _get_7day_wastage_map(warehouse, date_from, date_to):
	"""Batch query: get wastage (Material Issue) qty per FG item in last 7 days."""
	rows = frappe.db.sql(
		"""
		SELECT sed.item_code, IFNULL(SUM(ABS(sed.qty)), 0) as total_wastage
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		AND se.stock_entry_type = 'Material Issue'
		AND se.posting_date BETWEEN %s AND %s
		AND sed.s_warehouse = %s
		AND (sed.item_code LIKE 'FG%%')
		GROUP BY sed.item_code
		""",
		(date_from, date_to, warehouse),
		as_dict=True,
	)
	return {r.item_code: flt(r.total_wastage) for r in rows}


def _get_7day_production_map(warehouse, date_from, date_to):
	"""Batch query: get production (Manufacture) qty per FG item in last 7 days."""
	rows = frappe.db.sql(
		"""
		SELECT sed.item_code, IFNULL(SUM(sed.qty), 0) as total_produced
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		AND se.stock_entry_type = 'Manufacture'
		AND se.posting_date BETWEEN %s AND %s
		AND sed.t_warehouse = %s
		AND (sed.item_code LIKE 'FG%%')
		GROUP BY sed.item_code
		""",
		(date_from, date_to, warehouse),
		as_dict=True,
	)
	return {r.item_code: flt(r.total_produced) for r in rows}


def _get_pending_demand_map():
	"""Batch query: get total pending Material Request qty per FG item."""
	rows = frappe.db.sql(
		"""
		SELECT
			mri.item_code,
			SUM(mri.qty - IFNULL(mri.ordered_qty, 0)) as pending_qty
		FROM `tabMaterial Request Item` mri
		JOIN `tabMaterial Request` mr ON mr.name = mri.parent
		WHERE mr.docstatus = 1
		AND mr.status IN ('Pending', 'Partially Ordered')
		AND (mri.item_code LIKE 'FG%%')
		AND (mri.qty - IFNULL(mri.ordered_qty, 0)) > 0
		GROUP BY mri.item_code
		""",
		as_dict=True,
	)
	return {r.item_code: flt(r.pending_qty) for r in rows}


def _get_last_produced_map(warehouse):
	"""Batch query: get last production date+qty per FG item."""
	rows = frappe.db.sql(
		"""
		SELECT sed.item_code, se.posting_date as last_date, sed.qty as last_qty
		FROM `tabStock Entry` se
		JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
		AND se.stock_entry_type = 'Manufacture'
		AND sed.t_warehouse = %s
		AND (sed.item_code LIKE 'FG%%')
		ORDER BY se.posting_date DESC
		""",
		warehouse,
		as_dict=True,
	)
	result = {}
	for r in rows:
		if r.item_code not in result:
			result[r.item_code] = {"date": str(r.last_date), "qty": flt(r.last_qty)}
	return result


def _get_rm_stock_map(warehouse):
	"""Batch query: get current stock for all RM items in commissary."""
	rows = frappe.db.sql(
		"""
		SELECT b.item_code, IFNULL(b.actual_qty, 0) as qty
		FROM `tabBin` b
		JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.warehouse = %s
		AND i.disabled = 0
		AND i.is_stock_item = 1
		AND (i.item_group = 'Raw Materials' OR i.item_code LIKE 'RM%%')
		""",
		warehouse,
		as_dict=True,
	)
	return {r.item_code: flt(r.qty) for r in rows}


def _check_bom_feasibility_batch(item_code, bom_name, bom_yield, target_qty, rm_stock_map):
	"""Check if target_qty is producible given RM stock. Returns max_producible and bottleneck."""
	bom_items = frappe.get_all(
		"BOM Item",
		filters={"parent": bom_name},
		fields=["item_code", "item_name", "qty"],
	)

	if not bom_items or flt(bom_yield) <= 0:
		return {"max_producible": 0, "bottleneck_rm": None}

	scale_factor = target_qty / flt(bom_yield)
	max_producible = float("inf")
	bottleneck_rm = None

	for mat in bom_items:
		available = flt(rm_stock_map.get(mat.item_code, 0))
		if flt(mat.qty) > 0:
			can_make = (available / flt(mat.qty)) * flt(bom_yield)
			if can_make < max_producible:
				max_producible = can_make
				if can_make < target_qty:
					bottleneck_rm = f"{mat.item_code} {mat.item_name}"

	if max_producible == float("inf"):
		max_producible = 0

	return {
		"max_producible": flt(max_producible, 2),
		"bottleneck_rm": bottleneck_rm,
	}

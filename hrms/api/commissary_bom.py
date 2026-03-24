# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Commissary BOM Management & Production Feasibility APIs.
Split from commissary.py (P0-11) for maintainability.
"""

import json
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import flt

from hrms.api.commissary import get_commissary_warehouse
from hrms.utils.bei_config import get_company
from hrms.utils.sentry import set_backend_observability_context


@contextmanager
def _run_as_system_user(user: str = "Administrator"):
	session = getattr(frappe, "session", None)
	if session is None:
		session = getattr(getattr(frappe, "local", None), "session", None)
	original_user = getattr(session, "user", None)
	try:
		if session and user:
			session.user = user
		yield
	finally:
		if session and original_user:
			session.user = original_user


# ============================================================
# BOM MANAGEMENT
# ============================================================


@frappe.whitelist()
def create_bom(item_code, materials, quantity=1, uom=None, remarks=None):
	"""
	Create a Bill of Materials for a Finished Good item.

	Args:
	    item_code: FG item code (e.g. FG007)
	    materials: JSON array of {item_code, qty, uom}
	    quantity: Yield quantity for this BOM (default 1)
	    uom: Unit of measure for yield (defaults to item's stock_uom)
	    remarks: Optional notes
	"""
	set_backend_observability_context(module="commissary", action="create_bom", mutation_type="create")
	if isinstance(materials, str):
		materials = json.loads(materials)

	if not materials:
		frappe.throw(_("BOM must have at least one material"))

	item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom"], as_dict=True)
	if not item:
		return {"success": False, "error": f"Item {item_code} not found"}

	# Check if active BOM already exists
	existing = frappe.db.get_value(
		"BOM", {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
	)
	if existing:
		return {
			"success": False,
			"error": f"Active default BOM already exists: {existing}. Use update_bom() or deactivate first.",
		}

	bom = frappe.new_doc("BOM")
	bom.item = item_code
	bom.quantity = flt(quantity) or 1
	bom.uom = uom or item.stock_uom
	bom.is_active = 1
	bom.is_default = 1
	bom.company = get_company()
	bom.with_operations = 0

	if remarks:
		bom.remarks = remarks

	for mat in materials:
		mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
		if not mat_item:
			return {"success": False, "error": f"Material {mat['item_code']} not found in Item master"}

		bom.append(
			"items",
			{
				"item_code": mat["item_code"],
				"item_name": mat_item.item_name,
				"qty": flt(mat["qty"]),
				"uom": mat.get("uom") or mat_item.stock_uom,
				"stock_uom": mat_item.stock_uom,
				"rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
			},
		)

	bom.insert()
	with _run_as_system_user("Administrator"):
		bom.submit()

	return {
		"success": True,
		"message": f"BOM {bom.name} created for {item_code}",
		"data": {
			"name": bom.name,
			"item": bom.item,
			"quantity": bom.quantity,
			"materials_count": len(bom.items),
			"is_default": bom.is_default,
		},
	}


@frappe.whitelist()
def update_bom(bom_name, materials=None, quantity=None, remarks=None):
	"""
	Update a BOM by creating a new version (amend).
	Frappe BOMs are immutable once submitted - amendments create new versions.

	Args:
	    bom_name: Existing BOM name to amend
	    materials: New materials list (optional, keeps existing if not provided)
	    quantity: New yield quantity (optional)
	    remarks: Optional notes
	"""
	set_backend_observability_context(module="commissary", action="update_bom", mutation_type="update")
	if materials and isinstance(materials, str):
		materials = json.loads(materials)

	old_bom = frappe.get_doc("BOM", bom_name)

	if old_bom.docstatus != 1:
		return {"success": False, "error": "Can only amend submitted BOMs"}

	# Deactivate old BOM (use db.set_value since doc is submitted)
	frappe.db.set_value(
		"BOM",
		bom_name,
		{
			"is_active": 0,
			"is_default": 0,
		},
	)

	# Create new BOM
	new_bom = frappe.new_doc("BOM")
	new_bom.item = old_bom.item
	new_bom.quantity = flt(quantity) or old_bom.quantity
	new_bom.uom = old_bom.uom
	new_bom.is_active = 1
	new_bom.is_default = 1
	new_bom.company = old_bom.company
	new_bom.with_operations = 0
	new_bom.amended_from = old_bom.name

	if remarks:
		new_bom.remarks = remarks

	if materials:
		for mat in materials:
			mat_item = frappe.db.get_value("Item", mat["item_code"], ["item_name", "stock_uom"], as_dict=True)
			if not mat_item:
				return {"success": False, "error": f"Material {mat['item_code']} not found"}

			new_bom.append(
				"items",
				{
					"item_code": mat["item_code"],
					"item_name": mat_item.item_name,
					"qty": flt(mat["qty"]),
					"uom": mat.get("uom") or mat_item.stock_uom,
					"stock_uom": mat_item.stock_uom,
					"rate": frappe.db.get_value("Item", mat["item_code"], "valuation_rate") or 0,
				},
			)
	else:
		# Copy materials from old BOM
		for old_item in old_bom.items:
			new_bom.append(
				"items",
				{
					"item_code": old_item.item_code,
					"item_name": old_item.item_name,
					"qty": old_item.qty,
					"uom": old_item.uom,
					"stock_uom": old_item.stock_uom,
					"rate": old_item.rate,
				},
			)

	new_bom.insert()
	with _run_as_system_user("Administrator"):
		new_bom.submit()

	return {
		"success": True,
		"message": f"BOM updated: {old_bom.name} -> {new_bom.name}",
		"data": {
			"old_bom": old_bom.name,
			"new_bom": new_bom.name,
			"item": new_bom.item,
			"quantity": new_bom.quantity,
			"materials_count": len(new_bom.items),
		},
	}


@frappe.whitelist()
def get_bom_detail(item_code):
	"""
	Get the default active BOM for an item with full materials breakdown.

	Args:
	    item_code: Item to look up BOM for
	"""
	set_backend_observability_context(module="commissary", action="get_bom_detail", mutation_type="read")
	bom = frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
		["name", "quantity", "uom", "total_cost", "operating_cost", "raw_material_cost"],
		as_dict=True,
	)

	if not bom:
		return {"success": False, "error": f"No active default BOM for {item_code}"}

	bom_doc = frappe.get_doc("BOM", bom.name)

	materials = []
	for item in bom_doc.items:
		materials.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"uom": item.uom,
				"rate": item.rate,
				"amount": item.amount,
				"stock_qty": item.stock_qty,
				"stock_uom": item.stock_uom,
			}
		)

	return {
		"success": True,
		"data": {
			"name": bom.name,
			"item_code": item_code,
			"quantity": bom.quantity,
			"uom": bom.uom,
			"total_cost": bom.total_cost,
			"raw_material_cost": bom.raw_material_cost,
			"materials": materials,
			"materials_count": len(materials),
		},
	}


# ============================================================
# PRODUCTION FEASIBILITY CHECK
# ============================================================


@frappe.whitelist()
def check_production_feasibility(item_code, qty):
	"""
	Check if we can produce a given quantity of an FG item.
	Validates raw material availability against BOM requirements.

	Args:
	    item_code: FG item to check
	    qty: Desired production quantity
	"""
	set_backend_observability_context(
		module="commissary", action="check_production_feasibility", mutation_type="read"
	)
	qty = flt(qty)
	if qty <= 0:
		return {"success": False, "error": "Quantity must be greater than 0"}

	commissary_warehouse = get_commissary_warehouse()

	# Get default BOM
	bom = frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
		["name", "quantity"],
		as_dict=True,
	)

	if not bom:
		return {"success": False, "error": f"No active BOM for {item_code}. Cannot check feasibility."}

	# Get BOM materials
	bom_items = frappe.get_all(
		"BOM Item", filters={"parent": bom.name}, fields=["item_code", "item_name", "qty", "stock_uom"]
	)

	# Calculate required quantities (scale by production qty / BOM yield)
	scale_factor = qty / flt(bom.quantity)
	shortfall = []
	max_batches = float("inf")

	for mat in bom_items:
		required_qty = flt(mat.qty) * scale_factor
		available_qty = (
			flt(
				frappe.db.get_value(
					"Bin", {"item_code": mat.item_code, "warehouse": commissary_warehouse}, "actual_qty"
				)
			)
			or 0
		)

		deficit = required_qty - available_qty

		# How many batches can this material support?
		if mat.qty > 0:
			batches_possible = (
				available_qty / (flt(mat.qty) * (qty / flt(bom.quantity)) / qty) if qty > 0 else 0
			)
			# Simpler: how many times can we make the BOM yield?
			batches_possible = (available_qty / flt(mat.qty)) * flt(bom.quantity)
			max_batches = min(max_batches, batches_possible)

		if deficit > 0:
			shortfall.append(
				{
					"item_code": mat.item_code,
					"item_name": mat.item_name,
					"required_qty": round(required_qty, 3),
					"available_qty": round(available_qty, 3),
					"deficit": round(deficit, 3),
					"uom": mat.stock_uom,
				}
			)

	can_produce = len(shortfall) == 0
	max_producible = round(max_batches, 2) if max_batches != float("inf") else 0

	return {
		"success": True,
		"data": {
			"item_code": item_code,
			"requested_qty": qty,
			"can_produce": can_produce,
			"max_producible_qty": max_producible,
			"bom_name": bom.name,
			"bom_yield": bom.quantity,
			"shortfall": shortfall,
			"shortfall_count": len(shortfall),
		},
	}


@frappe.whitelist()
def get_bom_runtime_deduction_proof(item_code, produced_qty, warehouse=None):
	"""
	Return line-level runtime proof for BOM raw-material deduction.

	This endpoint is read-only proof data used by execute/evidence gates.
	"""
	set_backend_observability_context(
		module="commissary", action="get_bom_runtime_deduction_proof", mutation_type="read"
	)
	produced_qty = flt(produced_qty)
	if produced_qty <= 0:
		return {"success": False, "error": "produced_qty must be greater than 0"}

	target_warehouse = warehouse or get_commissary_warehouse()
	bom = frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
		["name", "quantity"],
		as_dict=True,
	)
	if not bom:
		return {"success": False, "error": f"No active default BOM for {item_code}"}

	bom_yield = flt(bom.quantity) or 1
	scale_factor = produced_qty / bom_yield

	bom_items = frappe.get_all(
		"BOM Item", filters={"parent": bom.name}, fields=["item_code", "item_name", "qty", "stock_uom"]
	)

	proof_lines = []
	for bom_item in bom_items:
		qty_before = (
			flt(
				frappe.db.get_value(
					"Bin", {"item_code": bom_item.item_code, "warehouse": target_warehouse}, "actual_qty"
				)
			)
			or 0
		)
		qty_required = flt(bom_item.qty) * scale_factor
		qty_after = qty_before - qty_required

		proof_lines.append(
			{
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"uom": bom_item.stock_uom,
				"qty_required": round(qty_required, 3),
				"qty_before": round(qty_before, 3),
				"qty_after": round(qty_after, 3),
				"delta": round(qty_after - qty_before, 3),
			}
		)

	return {
		"success": True,
		"data": {
			"item_code": item_code,
			"produced_qty": produced_qty,
			"warehouse": target_warehouse,
			"bom_name": bom.name,
			"bom_yield": bom_yield,
			"proof_lines": proof_lines,
			"proof_line_count": len(proof_lines),
		},
	}

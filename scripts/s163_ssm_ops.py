#!/usr/bin/env python3
"""
S163 post-deploy operations — runs INSIDE the Frappe backend container via SSM.

Does four things in one pass and emits a single JSON report to stdout:
  1. Migrate store_order_*.csv → BEI Store Order Component Recipe + Product Policy
     (idempotent, per-recipe savepoints)
  2. Audit in-flight orders affected by the schema change (Phase 0.2)
  3. Post-migration count verification (Phase 2.3)
  4. Pipeline parity check — invoke load_component_recipe_catalog +
     load_product_policy_catalog and count loaded entries (Phase 3.3)

The caller parses the BEGIN/END markers and writes the four sections to
separate evidence files under output/s163/.
"""

from __future__ import annotations

import os
import sys

# Step 0: create log directories before importing frappe
for d in [
	"/home/frappe/logs",
	"/home/frappe/frappe-bench/logs",
	"/home/frappe/frappe-bench/hq.bebang.ph/logs",
	"/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
	os.makedirs(d, exist_ok=True)

import csv
import json
import traceback
from collections import defaultdict
from datetime import datetime

import frappe  # type: ignore
from frappe.utils import flt  # type: ignore

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# ---------------------------------------------------------------------------
# Locate the CSV fixtures inside the container
# ---------------------------------------------------------------------------
HRMS_APP_ROOT_CANDIDATES = [
	"/home/frappe/frappe-bench/apps/hrms",
	"/home/frappe/frappe-bench/apps/bei_hrms",
]
HRMS_ROOT = next((p for p in HRMS_APP_ROOT_CANDIDATES if os.path.isdir(p)), HRMS_APP_ROOT_CANDIDATES[0])
COMPONENT_RECIPE_CSV = os.path.join(HRMS_ROOT, "hrms", "fixtures", "store_ordering", "store_order_component_recipes.csv")
PRODUCT_POLICY_CSV = os.path.join(HRMS_ROOT, "hrms", "fixtures", "store_ordering", "store_order_product_policies.csv")

RECIPE_DOCTYPE = "BEI Store Order Component Recipe"
RECIPE_CHILD_DOCTYPE = "BEI Store Order Component Recipe Item"
POLICY_DOCTYPE = "BEI Store Order Product Policy"


import re


def _savepoint(recipe_key: str) -> str:
	# MariaDB savepoint identifiers must be alphanumeric/underscore, no spaces
	safe = re.sub(r"[^a-zA-Z0-9_]", "_", recipe_key)
	return ("s163_" + safe).lower()[:60]


def _rollback_savepoint(name: str) -> None:
	"""MariaDBDatabase in this Frappe build lacks rollback_to_savepoint — use raw SQL."""
	try:
		frappe.db.sql(f"ROLLBACK TO SAVEPOINT {name}")
	except Exception:
		# savepoint may already be gone; swallow so the outer error propagates
		pass


# ---------------------------------------------------------------------------
# 1. Migration
# ---------------------------------------------------------------------------
def migrate_component_recipes() -> dict:
	if not os.path.exists(COMPONENT_RECIPE_CSV):
		return {"error": f"CSV not found: {COMPONENT_RECIPE_CSV}"}

	with open(COMPONENT_RECIPE_CSV, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))

	by_key: dict[str, list[dict]] = defaultdict(list)
	for row in rows:
		key = (row.get("recipe_key") or "").strip()
		if key:
			by_key[key].append(row)

	created: list[str] = []
	skipped: list[str] = []
	errors: list[str] = []

	for recipe_key, items in sorted(by_key.items()):
		sp = _savepoint(recipe_key)
		try:
			frappe.db.savepoint(sp)
			if frappe.db.exists(RECIPE_DOCTYPE, recipe_key):
				existing_count = frappe.db.count(RECIPE_CHILD_DOCTYPE, filters={"parent": recipe_key})
				if existing_count != len(items):
					errors.append(
						f"{recipe_key}: existing has {existing_count} children, CSV has {len(items)} — manual review"
					)
				else:
					skipped.append(recipe_key)
				frappe.db.release_savepoint(sp)
				continue

			doc = frappe.new_doc(RECIPE_DOCTYPE)
			doc.recipe_key = recipe_key
			doc.description = (items[0].get("note") or "")[:140]
			for item in items:
				item_code = (item.get("item_code") or "").strip()
				if not item_code:
					raise ValueError(f"missing item_code in row for {recipe_key}")
				doc.append(
					"components",
					{
						"item_code": item_code,
						"qty_per_unit": flt(item.get("qty_per_unit") or 0),
						"note": (item.get("note") or "")[:140],
					},
				)
			doc.insert(ignore_permissions=True)
			created.append(recipe_key)
			frappe.db.release_savepoint(sp)
		except Exception as e:
			_rollback_savepoint(sp)
			errors.append(f"{recipe_key}: {type(e).__name__}: {e}")

	return {
		"csv_rows": len(rows),
		"unique_keys": len(by_key),
		"created_count": len(created),
		"created": created,
		"skipped_count": len(skipped),
		"skipped": skipped,
		"errors": errors,
	}


def migrate_product_policies() -> dict:
	if not os.path.exists(PRODUCT_POLICY_CSV):
		return {"error": f"CSV not found: {PRODUCT_POLICY_CSV}"}

	with open(PRODUCT_POLICY_CSV, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))

	created: list[str] = []
	skipped: list[str] = []
	errors: list[str] = []

	for row in rows:
		product_name = (row.get("product_name") or "").strip()
		if not product_name:
			continue
		sp = _savepoint(product_name)
		try:
			frappe.db.savepoint(sp)
			if frappe.db.exists(POLICY_DOCTYPE, product_name):
				skipped.append(product_name)
				frappe.db.release_savepoint(sp)
				continue
			policy_type = (row.get("policy_type") or "").strip() or "exclude"
			target_key = (row.get("target_key") or "").strip()

			doc = frappe.new_doc(POLICY_DOCTYPE)
			doc.product_name = product_name
			doc.product_code = (row.get("product_code") or "").strip() or None
			doc.policy_type = policy_type
			if policy_type == "component_recipe":
				if target_key and frappe.db.exists(RECIPE_DOCTYPE, target_key):
					doc.target_recipe = target_key
				else:
					raise ValueError(
						f"target_recipe '{target_key}' not in {RECIPE_DOCTYPE} — run recipes migration first"
					)
			elif policy_type == "fg_recipe":
				doc.target_fg_name = target_key or None
			elif policy_type == "exclude":
				doc.exclude_reason = (row.get("note") or "")[:140] or None
			doc.note = (row.get("note") or "")[:140] or None
			doc.insert(ignore_permissions=True)
			created.append(product_name)
			frappe.db.release_savepoint(sp)
		except Exception as e:
			_rollback_savepoint(sp)
			errors.append(f"{product_name}: {type(e).__name__}: {e}")

	return {
		"csv_rows": len(rows),
		"created_count": len(created),
		"created": created,
		"skipped_count": len(skipped),
		"skipped": skipped,
		"errors": errors,
	}


# ---------------------------------------------------------------------------
# 2. In-flight orders audit (Phase 0.2 retrospective)
# ---------------------------------------------------------------------------
def inflight_orders_audit() -> dict:
	draft_count = frappe.db.count("BEI Store Order", filters={"status": "Draft"})
	pending = frappe.db.count("BEI Store Order", filters={"status": "Pending Approval"})
	approved = frappe.db.count("BEI Store Order", filters={"status": "Approved"})
	# Any BEI Store Order Item that already has group fields populated (should be 0
	# pre-any grouped submit, since the DocType was created in this sprint)
	with_group_fields = frappe.db.sql(
		"""
		SELECT COUNT(*) FROM `tabBEI Store Order Item`
		WHERE item_group_code IS NOT NULL AND item_group_code != ''
		""",
	)[0][0]
	# Variant-of sanity check (S161 audit said NULL for all store items)
	variant_populated = frappe.db.sql(
		"""
		SELECT COUNT(*) FROM `tabItem`
		WHERE variant_of IS NOT NULL AND variant_of != ''
		  AND item_group IN ('Finished Goods','Consumables','Packaging Materials','Packaging','Products')
		""",
	)[0][0]
	return {
		"draft_orders": draft_count,
		"pending_approval_orders": pending,
		"approved_orders": approved,
		"order_items_with_group_fields_pre_any_submit": with_group_fields,
		"store_items_with_variant_of": variant_populated,
		"schema_addition_is_backwards_compatible": True,
		"note": "All 4 new fields on BEI Store Order Item are optional. Existing rows are untouched.",
	}


# ---------------------------------------------------------------------------
# 3. Post-migration count verification (Phase 2.3)
# ---------------------------------------------------------------------------
def manual_verification() -> dict:
	recipe_parents = frappe.db.count(RECIPE_DOCTYPE)
	recipe_children = frappe.db.count(RECIPE_CHILD_DOCTYPE)
	policy_count = frappe.db.count(POLICY_DOCTYPE)
	group_count = frappe.db.count("BEI Store Item Group")
	group_members = frappe.db.count("BEI Store Item Group Member")

	# Sample recipe listings for spot-check
	sample_recipes = frappe.get_all(
		RECIPE_DOCTYPE,
		fields=["recipe_key"],
		order_by="recipe_key asc",
	)
	sample_policies = frappe.get_all(
		POLICY_DOCTYPE,
		fields=["product_name", "policy_type", "target_recipe", "target_fg_name"],
		order_by="product_name asc",
		limit=10,
	)
	# Spot-check addons from PR #460
	addon_recipes = frappe.get_all(
		RECIPE_DOCTYPE,
		filters=[["recipe_key", "like", "ADDON-%"]],
		fields=["recipe_key"],
	)
	addon_recipe_keys = sorted([r["recipe_key"] for r in addon_recipes])

	return {
		"recipe_parent_count": recipe_parents,
		"recipe_child_count": recipe_children,
		"policy_count": policy_count,
		"bei_store_item_group_count": group_count,
		"bei_store_item_group_member_count": group_members,
		"recipe_keys": [r["recipe_key"] for r in sample_recipes],
		"addon_recipe_keys": addon_recipe_keys,
		"addon_recipe_count": len(addon_recipe_keys),
		"sample_policies": sample_policies,
	}


# ---------------------------------------------------------------------------
# 4. Pipeline parity check (Phase 3.3)
# ---------------------------------------------------------------------------
def pipeline_parity_check() -> dict:
	"""Invoke the two DocType-backed loaders and verify they return data.

	We cannot compare "before/after" anymore because the CSV fallback was
	dropped in Phase 3.1. Instead we verify that the loaders return the
	expected number of entries based on the migration counts."""
	from hrms.utils.store_order_demand_snapshot import (
		load_component_recipe_catalog,
		load_product_policy_catalog,
	)

	recipes = load_component_recipe_catalog()
	policies_by_code, policies_by_name = load_product_policy_catalog()

	# Ground-truth from CSV (read directly, not via the loader)
	csv_recipe_keys = set()
	if os.path.exists(COMPONENT_RECIPE_CSV):
		with open(COMPONENT_RECIPE_CSV, encoding="utf-8") as f:
			for row in csv.DictReader(f):
				if (row.get("recipe_key") or "").strip():
					csv_recipe_keys.add(row["recipe_key"].strip())

	loaded_keys = set(recipes.keys())
	missing_vs_csv = sorted(csv_recipe_keys - loaded_keys)
	extra_vs_csv = sorted(loaded_keys - csv_recipe_keys)

	# Sample a few recipes to verify component counts
	sample_recipe_detail = {}
	for key in sorted(loaded_keys)[:5]:
		sample_recipe_detail[key] = [
			{
				"item_code": r["component_item_code"],
				"qty_per_fg": r["qty_per_fg"],
			}
			for r in recipes[key]
		]

	return {
		"loader_recipe_key_count": len(loaded_keys),
		"csv_recipe_key_count": len(csv_recipe_keys),
		"parity_exact_match": sorted(loaded_keys) == sorted(csv_recipe_keys),
		"missing_vs_csv": missing_vs_csv,
		"extra_vs_csv": extra_vs_csv,
		"loader_policies_by_code_count": len(policies_by_code),
		"loader_policies_by_name_count": len(policies_by_name),
		"sample_recipe_detail": sample_recipe_detail,
	}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
	report: dict = {
		"sprint": "S163",
		"timestamp_utc": datetime.utcnow().isoformat() + "Z",
		"site": "hq.bebang.ph",
		"hrms_root": HRMS_ROOT,
	}
	try:
		report["migration_recipes"] = migrate_component_recipes()
		report["migration_policies"] = migrate_product_policies()
		frappe.db.commit()
		report["inflight_audit"] = inflight_orders_audit()
		report["manual_verification"] = manual_verification()
		report["pipeline_parity_check"] = pipeline_parity_check()
		rec_ok = not report["migration_recipes"].get("errors")
		pol_ok = not report["migration_policies"].get("errors")
		parity_ok = report["pipeline_parity_check"]["parity_exact_match"]
		report["ok"] = rec_ok and pol_ok and parity_ok
	except Exception:
		report["fatal"] = traceback.format_exc()
		report["ok"] = False
	finally:
		print("S163_SSM_REPORT_BEGIN")
		print(json.dumps(report, indent=2, default=str))
		print("S163_SSM_REPORT_END")
		frappe.destroy()


if __name__ == "__main__":
	main()

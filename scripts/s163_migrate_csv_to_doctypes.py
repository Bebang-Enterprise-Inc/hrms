"""
S163 — Migrate store ordering CSVs to Frappe DocTypes.

Reads:
  hrms/fixtures/store_ordering/store_order_component_recipes.csv
  hrms/fixtures/store_ordering/store_order_product_policies.csv

Writes:
  BEI Store Order Component Recipe (parent + child)
  BEI Store Order Product Policy

Idempotent: re-running this script does nothing if records already exist.
Per-recipe savepoint: a single bad row never leaves a half-baked parent.

Execution: SSM-deployed to the Frappe container.
  python scripts/s163_migrate_csv_to_doctypes.py

Output: prints a JSON summary that the caller redirects to
        output/s163/migration_evidence.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from typing import Any

import frappe  # type: ignore
from frappe.utils import flt  # type: ignore

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENT_RECIPE_CSV = os.path.join(
	REPO_ROOT, "hrms", "fixtures", "store_ordering", "store_order_component_recipes.csv"
)
PRODUCT_POLICY_CSV = os.path.join(
	REPO_ROOT, "hrms", "fixtures", "store_ordering", "store_order_product_policies.csv"
)

RECIPE_DOCTYPE = "BEI Store Order Component Recipe"
RECIPE_CHILD_DOCTYPE = "BEI Store Order Component Recipe Item"
POLICY_DOCTYPE = "BEI Store Order Product Policy"


def _safe_savepoint_name(recipe_key: str) -> str:
	return "s163_" + recipe_key.replace("-", "_").replace(".", "_").lower()


def migrate_component_recipes(csv_path: str) -> dict[str, Any]:
	"""Insert one parent per recipe_key, with a child row per component."""
	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"Component recipe CSV not found: {csv_path}")

	with open(csv_path, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))

	by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
	for row in rows:
		key = (row.get("recipe_key") or "").strip()
		if not key:
			continue
		by_key[key].append(row)

	created: list[str] = []
	skipped: list[str] = []
	errors: list[str] = []

	for recipe_key, items in sorted(by_key.items()):
		savepoint = _safe_savepoint_name(recipe_key)
		try:
			frappe.db.savepoint(savepoint)

			if frappe.db.exists(RECIPE_DOCTYPE, recipe_key):
				existing_count = frappe.db.count(
					RECIPE_CHILD_DOCTYPE, filters={"parent": recipe_key}
				)
				if existing_count != len(items):
					errors.append(
						f"{recipe_key}: existing has {existing_count} children, CSV has {len(items)} — manual review"
					)
				else:
					skipped.append(recipe_key)
				frappe.db.release_savepoint(savepoint)
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
			frappe.db.release_savepoint(savepoint)
		except Exception as e:
			frappe.db.rollback_to_savepoint(savepoint)
			errors.append(f"{recipe_key}: {e}")

	return {
		"csv_rows": len(rows),
		"unique_keys": len(by_key),
		"created": created,
		"skipped": skipped,
		"errors": errors,
	}


def migrate_product_policies(csv_path: str) -> dict[str, Any]:
	"""Insert one BEI Store Order Product Policy per CSV row."""
	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"Product policy CSV not found: {csv_path}")

	with open(csv_path, encoding="utf-8") as f:
		rows = list(csv.DictReader(f))

	created: list[str] = []
	skipped: list[str] = []
	errors: list[str] = []

	for row in rows:
		product_name = (row.get("product_name") or "").strip()
		if not product_name:
			continue

		savepoint = _safe_savepoint_name(product_name)
		try:
			frappe.db.savepoint(savepoint)

			if frappe.db.exists(POLICY_DOCTYPE, product_name):
				skipped.append(product_name)
				frappe.db.release_savepoint(savepoint)
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
			frappe.db.release_savepoint(savepoint)
		except Exception as e:
			frappe.db.rollback_to_savepoint(savepoint)
			errors.append(f"{product_name}: {e}")

	return {
		"csv_rows": len(rows),
		"created": created,
		"skipped": skipped,
		"errors": errors,
	}


def run() -> dict[str, Any]:
	site = os.environ.get("FRAPPE_SITE", "hq.bebang.ph")
	if not getattr(frappe, "db", None):
		frappe.init(site=site)
		frappe.connect()

	report: dict[str, Any] = {
		"sprint": "S163",
		"site": site,
		"recipes": migrate_component_recipes(COMPONENT_RECIPE_CSV),
		"policies": migrate_product_policies(PRODUCT_POLICY_CSV),
	}
	frappe.db.commit()
	report["ok"] = not (report["recipes"]["errors"] or report["policies"]["errors"])
	return report


if __name__ == "__main__":
	result = run()
	print(json.dumps(result, indent=2, default=str))
	sys.exit(0 if result["ok"] else 1)

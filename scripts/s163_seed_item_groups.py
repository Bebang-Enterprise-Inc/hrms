#!/usr/bin/env python3
"""
S163 — Seed BEI Store Item Group records on hq.bebang.ph.

Runs INSIDE the Frappe backend container via SSM. Idempotent:
re-running checks frappe.db.exists before creating, skips duplicates.

Seeds 6 of the 9 groups from S161 product_group_audit. The other 3
(BANANA-CINNAMON, FROZEN-ICE-MILK, THERMAL) are intentionally skipped
because they have mixed UOMs and need SCM to confirm conversion factors
before seeding — using conversion_to_display=1.0 would silently break
aggregated stock math.

Groups seeded:
  GRP-FROZEN-MANGO       (plan-specified: RM010-A p1, RM030 p2, KG, Frozen)
  GRP-FRESH-RIPE-MANGO   (FG011 p1, RM010 p2, KG, Frozen)
  GRP-SAGO               (FG009 p1, FG050 p2, KG, Frozen)
  GRP-RAG                (7 CS* colored rags, PIECE, Dry)
  GRP-CUP-HOLDER         (PM004 x4 p1, PM005 x6 p2, PIECE, Dry)
  GRP-LECHE-FLAN-X       (FG001-A x12 p1, FG001-B x16 p2, PIECE, Frozen)

All members use conversion_to_display=1.0 because all members within
each of these 6 groups share the same stock UOM.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime

for d in [
	"/home/frappe/logs",
	"/home/frappe/frappe-bench/logs",
	"/home/frappe/frappe-bench/hq.bebang.ph/logs",
	"/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
	os.makedirs(d, exist_ok=True)

import frappe  # type: ignore

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

GROUPS: list[dict] = [
	{
		"group_code": "GRP-FROZEN-MANGO",
		"display_name": "Frozen Mango",
		"display_uom": "KG",
		"delivery_lane": "Frozen",
		"note": "S163 vertical slice: Frozen Mango dedup (RM010-A vs RM030).",
		"members": [
			{"item_code": "RM010-A", "priority": 1, "conversion_to_display": 1.0},
			{"item_code": "RM030", "priority": 2, "conversion_to_display": 1.0},
		],
	},
	{
		"group_code": "GRP-FRESH-RIPE-MANGO",
		"display_name": "Fresh Ripe Mango",
		"display_uom": "KG",
		"delivery_lane": "Frozen",
		"note": "S163: dedup Fresh Ripe Mango across FG011 and RM010.",
		"members": [
			{"item_code": "FG011", "priority": 1, "conversion_to_display": 1.0},
			{"item_code": "RM010", "priority": 2, "conversion_to_display": 1.0},
		],
	},
	{
		"group_code": "GRP-SAGO",
		"display_name": "Sago",
		"display_uom": "KG",
		"delivery_lane": "Frozen",
		"note": "S163: dedup Sago across FG009 (Finished Goods) and FG050 (Products).",
		"members": [
			{"item_code": "FG009", "priority": 1, "conversion_to_display": 1.0},
			{"item_code": "FG050", "priority": 2, "conversion_to_display": 1.0},
		],
	},
	{
		"group_code": "GRP-RAG",
		"display_name": "Rag",
		"display_uom": "PIECE",
		"delivery_lane": "Dry",
		"note": "S163: dedup 7 colored rags (CS013-CS019). All PIECE, same function.",
		"members": [
			{"item_code": "CS013", "priority": 1, "conversion_to_display": 1.0},  # WHITE
			{"item_code": "CS014", "priority": 2, "conversion_to_display": 1.0},  # BLUE
			{"item_code": "CS019", "priority": 3, "conversion_to_display": 1.0},  # CYAN
			{"item_code": "CS016", "priority": 4, "conversion_to_display": 1.0},  # GREEN
			{"item_code": "CS017", "priority": 5, "conversion_to_display": 1.0},  # PINK
			{"item_code": "CS015", "priority": 6, "conversion_to_display": 1.0},  # RED
			{"item_code": "CS018", "priority": 7, "conversion_to_display": 1.0},  # YELLOW
		],
	},
	{
		"group_code": "GRP-CUP-HOLDER",
		"display_name": "Cup Holder",
		"display_uom": "PIECE",
		"delivery_lane": "Dry",
		"note": "S163: dedup Cup Holder (PM004 x4, PM005 x6). Both PIECE.",
		"members": [
			{"item_code": "PM004", "priority": 1, "conversion_to_display": 1.0},  # x4
			{"item_code": "PM005", "priority": 2, "conversion_to_display": 1.0},  # x6
		],
	},
	{
		"group_code": "GRP-LECHE-FLAN-X",
		"display_name": "Leche Flan",
		"display_uom": "PIECE",
		"delivery_lane": "Frozen",
		"note": "S163: dedup Leche Flan (FG001-A x12, FG001-B x16). Both PIECE.",
		"members": [
			{"item_code": "FG001-A", "priority": 1, "conversion_to_display": 1.0},  # x12
			{"item_code": "FG001-B", "priority": 2, "conversion_to_display": 1.0},  # x16
		],
	},
]


def validate_items(group: dict) -> list[str]:
	"""Verify every member item exists in tabItem before creating the group."""
	errors = []
	for m in group["members"]:
		code = m["item_code"]
		if not frappe.db.exists("Item", code):
			errors.append(f"Item {code} does not exist")
	return errors


def seed_one(group: dict) -> dict:
	result: dict = {"group_code": group["group_code"]}
	try:
		item_errors = validate_items(group)
		if item_errors:
			result["status"] = "skipped_missing_items"
			result["errors"] = item_errors
			return result

		if frappe.db.exists("BEI Store Item Group", group["group_code"]):
			# Idempotent: verify member count matches
			existing_members = frappe.db.count(
				"BEI Store Item Group Member", filters={"parent": group["group_code"]}
			)
			result["status"] = "already_exists"
			result["existing_member_count"] = existing_members
			result["expected_member_count"] = len(group["members"])
			return result

		# Verify display_uom exists (UOMs are a DocType)
		if not frappe.db.exists("UOM", group["display_uom"]):
			result["status"] = "skipped_missing_uom"
			result["errors"] = [f"UOM {group['display_uom']} does not exist"]
			return result

		doc = frappe.new_doc("BEI Store Item Group")
		doc.group_code = group["group_code"]
		doc.display_name = group["display_name"]
		doc.display_uom = group["display_uom"]
		doc.delivery_lane = group["delivery_lane"]
		doc.disabled = 0
		doc.note = group.get("note") or ""
		for m in group["members"]:
			doc.append(
				"members",
				{
					"item_code": m["item_code"],
					"conversion_to_display": m["conversion_to_display"],
					"priority": m["priority"],
				},
			)
		doc.insert(ignore_permissions=True)
		result["status"] = "created"
		result["member_count"] = len(group["members"])
	except Exception as e:
		result["status"] = "error"
		result["error"] = f"{type(e).__name__}: {e}"
		result["traceback"] = traceback.format_exc()
	return result


def main() -> None:
	report: dict = {
		"sprint": "S163",
		"task": "seed BEI Store Item Group",
		"timestamp_utc": datetime.utcnow().isoformat() + "Z",
		"groups": [],
	}
	try:
		for g in GROUPS:
			result = seed_one(g)
			report["groups"].append(result)
			frappe.db.commit()
		# Post-seed counts
		report["post_seed_group_count"] = frappe.db.count("BEI Store Item Group")
		report["post_seed_member_count"] = frappe.db.count("BEI Store Item Group Member")
		report["all_groups_in_db"] = frappe.get_all(
			"BEI Store Item Group",
			fields=["group_code", "display_name", "display_uom", "delivery_lane", "disabled"],
			order_by="group_code",
		)
		report["ok"] = all(
			r.get("status") in {"created", "already_exists"} for r in report["groups"]
		)
	except Exception:
		report["fatal"] = traceback.format_exc()
		report["ok"] = False
	finally:
		print("S163_SEED_REPORT_BEGIN")
		print(json.dumps(report, indent=2, default=str))
		print("S163_SEED_REPORT_END")
		frappe.destroy()


if __name__ == "__main__":
	main()

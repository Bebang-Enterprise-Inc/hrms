#!/usr/bin/env python3
"""
S163 — Clean up test BEI Store Orders created during L3 testing.

Runs INSIDE the Frappe backend container via SSM.

Test orders: BEI-ORD-2026-00240 through BEI-ORD-2026-00247 (8 orders)
Plus any Material Requests that reference them (should be 0 — dual approval
chain never completed, so no MR was created in L3 tests).
Plus any BEI Approval Queue entries tied to them.

Follows Recipe 3 pattern from frappe-bulk-edits skill:
  ORM cancel + delete first, SQL fallback for stubborn rows.
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

TEST_ORDERS = [
	"BEI-ORD-2026-00240",
	"BEI-ORD-2026-00241",
	"BEI-ORD-2026-00242",
	"BEI-ORD-2026-00243",
	"BEI-ORD-2026-00244",
	"BEI-ORD-2026-00245",
	"BEI-ORD-2026-00246",
	"BEI-ORD-2026-00247",
]


def main() -> None:
	report: dict = {
		"sprint": "S163",
		"task": "cleanup L3 test orders",
		"timestamp_utc": datetime.utcnow().isoformat() + "Z",
		"target_orders": TEST_ORDERS,
		"before": {},
		"actions": [],
		"after": {},
	}
	try:
		# ---- BEFORE snapshot ----
		existing = frappe.get_all(
			"BEI Store Order",
			filters={"name": ("in", TEST_ORDERS)},
			fields=["name", "store", "status", "docstatus", "cargo_category"],
		)
		report["before"]["existing_orders"] = existing
		report["before"]["existing_order_count"] = len(existing)

		existing_items = frappe.db.count(
			"BEI Store Order Item",
			filters={"parent": ("in", TEST_ORDERS)},
		)
		report["before"]["order_item_count"] = existing_items

		# Material Requests that reference these orders
		mr_rows = frappe.get_all(
			"Material Request",
			filters={"custom_store_order": ("in", TEST_ORDERS)},
			fields=["name", "status", "docstatus"],
		)
		report["before"]["material_requests"] = mr_rows

		# Approval queue entries
		aq_filters = [["reference_name", "in", TEST_ORDERS]]
		try:
			aq_rows = frappe.get_all(
				"BEI Approval Queue",
				filters=aq_filters,
				fields=["name", "status"],
			)
		except Exception:
			aq_rows = []
		report["before"]["approval_queue_entries"] = aq_rows

		# ---- 1. Cancel + delete Material Requests first (downstream) ----
		for mr in mr_rows:
			try:
				if mr["docstatus"] == 1:
					doc = frappe.get_doc("Material Request", mr["name"])
					doc.cancel()
					frappe.db.commit()
					report["actions"].append(f"MR cancelled: {mr['name']}")
			except Exception as e:
				report["actions"].append(f"MR cancel failed {mr['name']}: {e}")
			try:
				frappe.delete_doc("Material Request", mr["name"], force=True, ignore_permissions=True)
				frappe.db.commit()
				report["actions"].append(f"MR deleted: {mr['name']}")
			except Exception as e:
				report["actions"].append(f"MR delete failed {mr['name']}: {e}")

		# ---- 2. Delete BEI Approval Queue entries ----
		for aq in aq_rows:
			try:
				frappe.delete_doc("BEI Approval Queue", aq["name"], force=True, ignore_permissions=True)
				frappe.db.commit()
				report["actions"].append(f"Approval queue deleted: {aq['name']}")
			except Exception as e:
				report["actions"].append(f"AQ delete failed {aq['name']}: {e}")

		# Close any ToDo assignments tied to these orders
		try:
			todo_rows = frappe.get_all(
				"ToDo",
				filters={"reference_type": "BEI Store Order", "reference_name": ("in", TEST_ORDERS)},
				fields=["name"],
			)
			for td in todo_rows:
				try:
					frappe.delete_doc("ToDo", td["name"], force=True, ignore_permissions=True)
					report["actions"].append(f"ToDo deleted: {td['name']}")
				except Exception as e:
					report["actions"].append(f"ToDo delete failed {td['name']}: {e}")
			frappe.db.commit()
		except Exception as e:
			report["actions"].append(f"ToDo sweep failed: {e}")

		# ---- 3. Cancel + delete BEI Store Orders ----
		for order_name in TEST_ORDERS:
			if not frappe.db.exists("BEI Store Order", order_name):
				report["actions"].append(f"Order not found (skip): {order_name}")
				continue
			try:
				doc = frappe.get_doc("BEI Store Order", order_name)
				if doc.docstatus == 1:
					try:
						doc.cancel()
						frappe.db.commit()
						report["actions"].append(f"Order cancelled: {order_name}")
					except Exception as e:
						report["actions"].append(f"Order cancel failed {order_name}: {e}")
				# Force delete
				frappe.delete_doc(
					"BEI Store Order",
					order_name,
					force=True,
					ignore_permissions=True,
				)
				frappe.db.commit()
				report["actions"].append(f"Order deleted (ORM): {order_name}")
			except Exception as e:
				report["actions"].append(f"ORM delete failed {order_name}: {e}")

		# ---- 4. SQL fallback for anything ORM missed ----
		remaining_orders = frappe.db.sql(
			"SELECT name FROM `tabBEI Store Order` WHERE name IN %(names)s",
			{"names": tuple(TEST_ORDERS) if len(TEST_ORDERS) > 1 else (TEST_ORDERS[0], TEST_ORDERS[0])},
			as_dict=True,
		)
		if remaining_orders:
			names_str = ",".join([f"'{r['name']}'" for r in remaining_orders])
			frappe.db.sql(f"DELETE FROM `tabBEI Store Order Item` WHERE parent IN ({names_str})")
			frappe.db.sql(f"DELETE FROM `tabBEI Store Order` WHERE name IN ({names_str})")
			frappe.db.commit()
			report["actions"].append(
				f"SQL fallback: force-deleted {len(remaining_orders)} stubborn orders"
			)

		# Orphaned child rows
		orphan_children = frappe.db.sql(
			"SELECT COUNT(*) FROM `tabBEI Store Order Item` WHERE parent IN %(names)s",
			{"names": tuple(TEST_ORDERS) if len(TEST_ORDERS) > 1 else (TEST_ORDERS[0], TEST_ORDERS[0])},
		)[0][0]
		if orphan_children:
			names_str = ",".join([f"'{n}'" for n in TEST_ORDERS])
			frappe.db.sql(f"DELETE FROM `tabBEI Store Order Item` WHERE parent IN ({names_str})")
			frappe.db.commit()
			report["actions"].append(f"SQL: deleted {orphan_children} orphaned order items")

		# ---- AFTER snapshot ----
		report["after"]["remaining_orders"] = frappe.db.count(
			"BEI Store Order", filters={"name": ("in", TEST_ORDERS)}
		)
		report["after"]["remaining_order_items"] = frappe.db.count(
			"BEI Store Order Item", filters={"parent": ("in", TEST_ORDERS)}
		)
		report["after"]["remaining_mrs"] = frappe.db.count(
			"Material Request", filters={"custom_store_order": ("in", TEST_ORDERS)}
		)
		report["ok"] = (
			report["after"]["remaining_orders"] == 0
			and report["after"]["remaining_order_items"] == 0
			and report["after"]["remaining_mrs"] == 0
		)
	except Exception:
		report["fatal"] = traceback.format_exc()
		report["ok"] = False
	finally:
		print("S163_CLEANUP_REPORT_BEGIN")
		print(json.dumps(report, indent=2, default=str))
		print("S163_CLEANUP_REPORT_END")
		frappe.destroy()


if __name__ == "__main__":
	main()

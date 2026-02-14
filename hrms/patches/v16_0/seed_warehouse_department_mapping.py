# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Seed BEI Warehouse Department Mapping from BEI Store Type records."""
	if not frappe.db.table_exists("tabBEI Warehouse Department Mapping"):
		return

	store_types = frappe.get_all("BEI Store Type",
		fields=["store", "store_type"],
		filters={"store": ["is", "set"]}
	)

	for st in store_types:
		# Find warehouse linked to this department/store
		warehouses = frappe.get_all("Warehouse",
			filters={"department": st.store},
			fields=["name"],
			limit=5
		)

		for wh in warehouses:
			if not frappe.db.exists("BEI Warehouse Department Mapping", wh.name):
				doc = frappe.new_doc("BEI Warehouse Department Mapping")
				doc.warehouse = wh.name
				doc.department = st.store
				doc.store_type = st.store_type
				doc.is_active = 1
				doc.insert(ignore_permissions=True)

	frappe.db.commit()

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe

from hrms.hr.doctype.bei_store_type.bei_store_type import resolve_store_type

TABLE_TARGETS = (
	("BEI Store Type", "tabBEI Store Type"),
	("BEI Billing Schedule", "tabBEI Billing Schedule"),
	("BEI Statement of Account", "tabBEI Statement of Account"),
	("BEI Warehouse Department Mapping", "tabBEI Warehouse Department Mapping"),
)


def _normalize_table_store_type(doctype, table_name):
	"""Normalize legacy/canonical store type fields on one table."""
	if not frappe.db.table_exists(table_name):
		return 0

	columns = set(frappe.db.get_table_columns(table_name) or [])
	has_store_type = "store_type" in columns
	has_legacy_store_type = "store_type_category" in columns

	if not has_store_type and not has_legacy_store_type:
		return 0

	fields = ["name"]
	if has_store_type:
		fields.append("store_type")
	if has_legacy_store_type:
		fields.append("store_type_category")

	select_fields = ", ".join(f"`{field}`" for field in fields)
	rows = frappe.db.sql(f"SELECT {select_fields} FROM `{table_name}`", as_dict=True)

	updated_rows = 0
	for row in rows:
		canonical_store_type = resolve_store_type(
			store_type=row.get("store_type"),
			store_type_category=row.get("store_type_category"),
		)
		if not canonical_store_type:
			continue

		target_field = "store_type" if has_store_type else "store_type_category"
		if row.get(target_field) == canonical_store_type:
			continue

		frappe.db.set_value(
			doctype,
			row["name"],
			target_field,
			canonical_store_type,
			update_modified=False,
		)
		updated_rows += 1

	return updated_rows


def execute():
	"""Backfill canonical store_type from legacy store_type_category where needed."""
	total_updates = 0
	for doctype, table_name in TABLE_TARGETS:
		total_updates += _normalize_table_store_type(doctype, table_name)

	if total_updates:
		frappe.db.commit()

	return total_updates

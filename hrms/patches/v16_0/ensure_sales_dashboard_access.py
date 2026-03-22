from __future__ import annotations

import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.utils import get_module_path

ROLE_NAME = "Sales Stakeholder"


def _import_standard_doctype(docname: str) -> None:
	path = os.path.join(get_module_path("hr"), "doctype", docname, f"{docname}.json")
	original_in_fixtures = getattr(frappe.flags, "in_fixtures", False)

	try:
		frappe.flags.in_patch = True
		frappe.flags.in_fixtures = True
		import_file_by_path(path, force=True)
	finally:
		frappe.flags.in_fixtures = original_in_fixtures


def _ensure_role() -> None:
	if frappe.db.exists("Role", ROLE_NAME):
		return

	doc = frappe.new_doc("Role")
	doc.role_name = ROLE_NAME
	doc.desk_access = 0
	doc.insert(ignore_permissions=True)


def execute():
	_import_standard_doctype("bei_sales_dashboard_store_access")
	_ensure_role()
	frappe.clear_cache()

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import annotations

import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.utils import get_module_path


def _import_standard_doctype(docname: str) -> None:
	path = os.path.join(get_module_path("hr"), "doctype", docname, f"{docname}.json")
	original_in_fixtures = getattr(frappe.flags, "in_fixtures", False)

	try:
		frappe.flags.in_patch = True
		frappe.flags.in_fixtures = True
		import_file_by_path(path, force=True)
	finally:
		frappe.flags.in_fixtures = original_in_fixtures


def execute():
	"""Ensure the SOA parent/child DocTypes exist after older deploys missed the parent registry row."""
	_import_standard_doctype("bei_soa_line_item")
	_import_standard_doctype("bei_statement_of_account")
	frappe.clear_cache()

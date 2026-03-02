import frappe


def execute():
	"""Backfill Warehouse.custom_area_supervisor using role-validated inference."""
	try:
		from hrms.api.store import _collect_store_area_supervisor_mapping

		result = _collect_store_area_supervisor_mapping(
			apply_fixes=True,
			include_disabled=False,
			max_rows=0,
		)
		frappe.logger("hrms").info(
			"Store area-supervisor mapping backfill complete: "
			f"updated={result.get('updated_mappings', 0)} "
			f"invalid={result.get('invalid_role_mappings', 0)} "
			f"unmapped={result.get('unmapped_after_resolution', 0)}"
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Store Area Supervisor Mapping Backfill Failed")

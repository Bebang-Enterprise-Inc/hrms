import frappe

from hrms.utils.supply_chain_contracts import (
	CANONICAL_COMMISSARY_GROUP_WAREHOUSE,
	CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
)


def _strip_suffix(warehouse_name: str) -> str:
	return warehouse_name.replace(" - BKI", "").replace(" - BEI", "").strip()


def _ensure_warehouse(warehouse_name: str, *, is_group: int, parent_warehouse: str | None = None) -> None:
	if frappe.db.exists("Warehouse", warehouse_name):
		doc = frappe.get_doc("Warehouse", warehouse_name)
		changed = False
		if doc.company != "Bebang Kitchen Inc.":
			doc.company = "Bebang Kitchen Inc."
			changed = True
		if int(doc.is_group or 0) != int(is_group):
			doc.is_group = is_group
			changed = True
		if (doc.parent_warehouse or "") != (parent_warehouse or ""):
			doc.parent_warehouse = parent_warehouse
			changed = True
		if int(doc.disabled or 0) != 0:
			doc.disabled = 0
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return

	doc = frappe.new_doc("Warehouse")
	doc.warehouse_name = _strip_suffix(warehouse_name)
	doc.company = "Bebang Kitchen Inc."
	doc.is_group = is_group
	doc.parent_warehouse = parent_warehouse
	doc.disabled = 0
	doc.insert(ignore_permissions=True)


def execute():
	"""Create the canonical BKI commissary group + operational warehouse if missing."""
	if not frappe.db.exists("Company", "Bebang Kitchen Inc."):
		return

	_ensure_warehouse(CANONICAL_COMMISSARY_GROUP_WAREHOUSE, is_group=1)
	_ensure_warehouse(
		CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
		is_group=0,
		parent_warehouse=CANONICAL_COMMISSARY_GROUP_WAREHOUSE,
	)
	frappe.db.commit()

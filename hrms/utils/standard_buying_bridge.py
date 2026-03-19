import frappe

from hrms.utils.bei_config import get_company


def _strip_company_suffix(value: str | None) -> str:
	return str(value or "").replace(" - BEI", "").replace(" - BKI", "").strip()


def resolve_active_buying_warehouse(
	warehouse_name_or_label: str | None,
	*,
	company: str | None = None,
) -> str | None:
	"""Resolve a warehouse label/docname to an active leaf warehouse for buying flows."""
	candidate = str(warehouse_name_or_label or "").strip()
	if not candidate:
		return None

	active_exact = frappe.db.get_value(
		"Warehouse",
		{"name": candidate, "disabled": 0, "is_group": 0},
		"name",
	)
	if active_exact:
		return active_exact

	warehouse_label = frappe.db.get_value("Warehouse", candidate, "warehouse_name") or _strip_company_suffix(
		candidate
	)

	if warehouse_label:
		preferred_company = company or get_company()
		active_company_match = frappe.db.get_value(
			"Warehouse",
			{"warehouse_name": warehouse_label, "company": preferred_company, "disabled": 0, "is_group": 0},
			"name",
		)
		if active_company_match:
			return active_company_match

		active_any = frappe.db.get_value(
			"Warehouse",
			{"warehouse_name": warehouse_label, "disabled": 0, "is_group": 0},
			"name",
		)
		if active_any:
			return active_any

	if frappe.db.exists("Warehouse", candidate):
		frappe.throw(
			frappe._("Warehouse {0} is disabled and has no active buying-route mapping.").format(candidate)
		)

	return candidate


def doctype_has_field(doctype: str, fieldname: str) -> bool:
	"""Return True when a DocType currently exposes *fieldname*."""
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def apply_standard_buying_context(doc, *, store_label: str | None = None, legal_entity: str | None = None) -> None:
	"""Populate BEI-required bridge fields only when they exist on the target DocType."""
	resolved_store_label = (store_label or "").strip() or "Stores - BEI"
	resolved_legal_entity = legal_entity or get_company()

	if doctype_has_field(doc.doctype, "bei_legal_entity"):
		doc.set("bei_legal_entity", resolved_legal_entity)

	if doctype_has_field(doc.doctype, "bei_store_label"):
		doc.set("bei_store_label", resolved_store_label)

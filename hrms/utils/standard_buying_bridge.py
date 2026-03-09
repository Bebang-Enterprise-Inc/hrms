import frappe

from hrms.utils.bei_config import get_company


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

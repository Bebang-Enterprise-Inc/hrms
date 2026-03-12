from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import frappe

REQUEST_SOURCE_STORE_ORDER = "store_order"
REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL = "commissary_raw_material_request"
REQUEST_SOURCE_COMMISSARY_FG_TRANSFER = "commissary_fg_transfer"
REQUEST_SOURCE_SUPPLIER_PO_RECEIPT = "supplier_po_receipt"
REQUEST_SOURCE_STORE_RETURN = "store_return"
REQUEST_SOURCE_STORE_DISPOSAL = "store_disposal"

FINANCE_TREATMENT_SAME_COMPANY = "same_company"
FINANCE_TREATMENT_INTERCOMPANY = "intercompany"

BUYER_ENTITY_STATUS_CONFIRMED = "confirmed_legal_entity"
BUYER_ENTITY_STATUS_CONFIRMED_TYPE_PENDING = "entity_confirmed_store_type_pending"
BUYER_ENTITY_STATUS_PROVISIONAL = "provisional_entity_from_pos_master"
BUYER_ENTITY_STATUS_EXCLUDED = "entity_known_but_non_operating_or_not_registered"
BUYER_ENTITY_STATUS_MISSING = "missing_register_row"

BUYER_ENTITY_BILLING_HOLD_POLICIES = {
    "DRAFT_ONLY__BILLING_HOLD_PENDING_LEGAL_ENTITY",
    "EXCLUDED__DO_NOT_DISPATCH_OR_BILL",
}

JV_MARKUP_RATE = 0.025
FRANCHISE_MARKUP_RATE = 0.08

REQUEST_SOURCE_LABELS = {
    REQUEST_SOURCE_STORE_ORDER: "Store Order",
    REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL: "Commissary Raw Materials",
    REQUEST_SOURCE_COMMISSARY_FG_TRANSFER: "Commissary FG Transfer",
    REQUEST_SOURCE_SUPPLIER_PO_RECEIPT: "Supplier PO Receipt",
    REQUEST_SOURCE_STORE_RETURN: "Store Return",
    REQUEST_SOURCE_STORE_DISPOSAL: "Store Disposal",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


BUYER_ENTITY_REGISTER_PATH = (
    _project_root()
    / "data"
    / "_CLEANROOM"
    / "2026-03-12-s037-store-buyer-entity-register"
    / "store_buyer_entity_register_2026-03-12.csv"
)


def has_column(doctype: str, fieldname: str) -> bool:
    checker = getattr(getattr(frappe, "db", None), "has_column", None)
    if not callable(checker):
        return False
    try:
        return bool(checker(doctype, fieldname))
    except Exception:
        return False


def set_if_column(doc: Any, fieldname: str, value: Any) -> None:
    doctype = getattr(doc, "doctype", None)
    if not doctype or not has_column(doctype, fieldname):
        return
    setattr(doc, fieldname, value)


def get_field(record: Any, fieldname: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(fieldname, default)
    return getattr(record, fieldname, default)


def normalize_request_source(value: str | None) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "store_order": REQUEST_SOURCE_STORE_ORDER,
        "commissary_raw_material_request": REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL,
        "commissary_raw_materials": REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL,
        "commissary_fg_transfer": REQUEST_SOURCE_COMMISSARY_FG_TRANSFER,
        "supplier_po_receipt": REQUEST_SOURCE_SUPPLIER_PO_RECEIPT,
        "store_return": REQUEST_SOURCE_STORE_RETURN,
        "store_disposal": REQUEST_SOURCE_STORE_DISPOSAL,
    }
    return aliases.get(raw, raw)


def get_request_source_label(value: str | None) -> str:
    normalized = normalize_request_source(value)
    return REQUEST_SOURCE_LABELS.get(normalized, normalized.replace("_", " ").title() or "Unclassified")


def infer_finance_treatment(source_company: str | None, target_company: str | None) -> str:
    if source_company and target_company and source_company != target_company:
        return FINANCE_TREATMENT_INTERCOMPANY
    return FINANCE_TREATMENT_SAME_COMPANY


def strip_company_suffix(value: str | None) -> str:
    return str(value or "").replace(" - BEI", "").replace(" - BKI", "").strip()


def normalize_lookup_key(value: str | None) -> str:
    raw = strip_company_suffix(value).lower()
    normalized = "".join(ch if ch.isalnum() else " " for ch in raw)
    return " ".join(normalized.split())


def resolve_warehouse_company(warehouse_name: str | None) -> str | None:
    if not warehouse_name:
        return None
    try:
        company = frappe.db.get_value("Warehouse", warehouse_name, "company")
        if company:
            return company
    except Exception:
        pass

    warehouse_label = str(warehouse_name).upper()
    if " - BKI" in warehouse_label or warehouse_label.endswith(" BKI"):
        return "Bebang Kitchen Inc."
    if " - BEI" in warehouse_label or warehouse_label.endswith(" BEI"):
        return "Bebang Enterprise Inc."
    return None


@lru_cache(maxsize=1)
def load_store_buyer_entity_register() -> list[dict[str, str]]:
    if not BUYER_ENTITY_REGISTER_PATH.exists():
        return []

    with BUYER_ENTITY_REGISTER_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row["_store_name_key"] = normalize_lookup_key(row.get("store_name"))
        row["_warehouse_docname_key"] = normalize_lookup_key(row.get("warehouse_docname"))
        row["_buyer_entity_status"] = str(row.get("buyer_entity_status") or "").strip()
        row["_billing_post_policy"] = str(row.get("billing_post_policy") or "").strip()
        row["_active_fulfillment_status"] = str(row.get("active_fulfillment_status") or "").strip()

    return rows


def resolve_store_buyer_entity(
    *,
    warehouse_docname: str | None = None,
    store_name: str | None = None,
) -> dict[str, Any]:
    rows = load_store_buyer_entity_register()
    warehouse_key = normalize_lookup_key(warehouse_docname)
    store_key = normalize_lookup_key(store_name or warehouse_docname)

    for row in rows:
        if warehouse_key and warehouse_key == row["_warehouse_docname_key"]:
            return row
    for row in rows:
        if store_key and store_key == row["_store_name_key"]:
            return row

    return {
        "store_name": store_name or strip_company_suffix(warehouse_docname),
        "buyer_entity_name": "",
        "buyer_entity_status": BUYER_ENTITY_STATUS_MISSING,
        "buyer_entity_source": "",
        "billing_policy": "",
        "billing_post_policy": "DRAFT_ONLY__BILLING_HOLD_PENDING_REGISTER",
        "store_type": "",
        "store_type_status": "",
        "store_allocation_required": 0,
        "markup_rule_mode": "CONFIG_PENDING_REGISTER",
        "markup_rule_source": "store_buyer_entity_register_missing",
        "active_fulfillment_status": "blocked_missing_register",
        "warehouse_docname": warehouse_docname or "",
        "evidence_primary": "",
        "evidence_secondary": "",
        "notes": "No canonical buyer-entity register row found",
    }


def buyer_entity_requires_billing_hold(entity_row: dict[str, Any]) -> bool:
    status = str(entity_row.get("buyer_entity_status") or "").strip()
    post_policy = str(entity_row.get("billing_post_policy") or "").strip()
    active_status = str(entity_row.get("active_fulfillment_status") or "").strip()
    return (
        status in {BUYER_ENTITY_STATUS_PROVISIONAL, BUYER_ENTITY_STATUS_EXCLUDED, BUYER_ENTITY_STATUS_MISSING}
        or post_policy in BUYER_ENTITY_BILLING_HOLD_POLICIES
        or active_status.startswith("active_with_billing_hold")
        or active_status.startswith("blocked")
        or active_status == "excluded"
    )


def resolve_markup_percent(store_type: str | None) -> float:
    normalized = str(store_type or "").strip().lower()
    if normalized == "jv":
        return JV_MARKUP_RATE
    if normalized in {"managed franchise", "full franchise"}:
        return FRANCHISE_MARKUP_RATE
    return 0.0


def stamp_billing_schedule_contract(
    doc: Any,
    *,
    entity_row: dict[str, Any],
    markup_percent: float,
    warehouse_docname: str | None = None,
) -> None:
    set_if_column(doc, "custom_buyer_entity_name", entity_row.get("buyer_entity_name"))
    set_if_column(doc, "custom_buyer_entity_status", entity_row.get("buyer_entity_status"))
    set_if_column(doc, "custom_buyer_entity_source", entity_row.get("buyer_entity_source"))
    set_if_column(doc, "custom_billing_policy", entity_row.get("billing_policy"))
    set_if_column(doc, "custom_billing_post_policy", entity_row.get("billing_post_policy"))
    set_if_column(doc, "custom_store_allocation_required", cint_bool(entity_row.get("store_allocation_required")))
    set_if_column(doc, "custom_markup_percent", markup_percent * 100)
    set_if_column(doc, "custom_store_warehouse", warehouse_docname or entity_row.get("warehouse_docname"))


def cint_bool(value: Any) -> int:
    return 1 if str(value or "").strip() in {"1", "true", "True", "yes", "Yes"} else 0


def resolve_route_source_warehouse(store_warehouse: str | None, cargo_type: str | None) -> str | None:
    normalized_cargo = str(cargo_type or "").strip().upper()
    if not store_warehouse or not normalized_cargo:
        return None
    if not frappe.db.exists("DocType", "BEI Route") or not frappe.db.exists("DocType", "BEI Route Stop"):
        return None

    exact = frappe.db.sql(
        """
        SELECT r.source_warehouse
        FROM `tabBEI Route` r
        JOIN `tabBEI Route Stop` s ON s.parent = r.name
        WHERE COALESCE(r.active, 1) = 1
          AND r.cargo_type = %(cargo_type)s
          AND s.store = %(store)s
        ORDER BY r.modified DESC, s.stop_order ASC
        LIMIT 1
        """,
        {"cargo_type": normalized_cargo, "store": store_warehouse},
        as_dict=True,
    )
    if exact:
        return exact[0].source_warehouse

    fallback = frappe.db.sql(
        """
        SELECT DISTINCT r.source_warehouse
        FROM `tabBEI Route` r
        WHERE COALESCE(r.active, 1) = 1
          AND r.cargo_type = %(cargo_type)s
          AND IFNULL(r.source_warehouse, '') != ''
        ORDER BY r.source_warehouse
        """,
        {"cargo_type": normalized_cargo},
        as_dict=True,
    )
    if len(fallback) == 1:
        return fallback[0].source_warehouse

    return None


def stamp_material_request_contract(
    doc: Any,
    *,
    request_source: str,
    cargo_lane: str | None = None,
    source_warehouse: str | None = None,
    source_company: str | None = None,
    target_company: str | None = None,
    finance_treatment: str | None = None,
) -> None:
    source_company = source_company or resolve_warehouse_company(source_warehouse)
    target_company = target_company or resolve_warehouse_company(getattr(doc, "set_warehouse", None))
    resolved_treatment = finance_treatment or infer_finance_treatment(source_company, target_company)
    set_if_column(doc, "custom_request_source", normalize_request_source(request_source))
    set_if_column(doc, "custom_cargo_lane", cargo_lane)
    set_if_column(doc, "custom_source_warehouse", source_warehouse)
    set_if_column(doc, "custom_source_company", source_company)
    set_if_column(doc, "custom_target_company", target_company)
    set_if_column(doc, "custom_finance_treatment", resolved_treatment)


def stamp_stock_entry_contract(
    doc: Any,
    *,
    request_source: str,
    cargo_lane: str | None = None,
    source_company: str | None = None,
    target_company: str | None = None,
    finance_treatment: str | None = None,
) -> None:
    source_company = source_company or resolve_warehouse_company(
        getattr(doc, "from_warehouse", None) or getattr(doc, "source_warehouse", None)
    )
    target_company = target_company or resolve_warehouse_company(
        getattr(doc, "to_warehouse", None) or getattr(doc, "target_warehouse", None)
    )
    resolved_treatment = finance_treatment or infer_finance_treatment(source_company, target_company)
    set_if_column(doc, "custom_request_source", normalize_request_source(request_source))
    set_if_column(doc, "custom_cargo_lane", cargo_lane)
    set_if_column(doc, "custom_source_company", source_company)
    set_if_column(doc, "custom_target_company", target_company)
    set_if_column(doc, "custom_finance_treatment", resolved_treatment)


def resolve_material_request_contract(material_request: Any, commissary_warehouse: str | None = None) -> dict[str, Any]:
    request_source = normalize_request_source(get_field(material_request, "custom_request_source"))
    if not request_source:
        if get_field(material_request, "custom_store_order"):
            request_source = REQUEST_SOURCE_STORE_ORDER
        elif commissary_warehouse and get_field(material_request, "set_warehouse") == commissary_warehouse:
            request_source = REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL
        elif "raw material requisition" in str(get_field(material_request, "remarks", "")).lower():
            request_source = REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL

    source_warehouse = get_field(material_request, "custom_source_warehouse")
    destination_warehouse = get_field(material_request, "set_warehouse")
    first_item_warehouse = None
    for item in get_field(material_request, "items", []) or []:
        first_item_warehouse = get_field(item, "from_warehouse") or first_item_warehouse
        destination_warehouse = destination_warehouse or get_field(item, "warehouse")
        if source_warehouse and destination_warehouse:
            break
        source_warehouse = source_warehouse or first_item_warehouse

    source_company = get_field(material_request, "custom_source_company") or resolve_warehouse_company(source_warehouse)
    target_company = get_field(material_request, "custom_target_company") or resolve_warehouse_company(
        destination_warehouse
    )
    finance_treatment = get_field(material_request, "custom_finance_treatment") or infer_finance_treatment(
        source_company, target_company
    )

    return {
        "request_source": request_source,
        "request_source_label": get_request_source_label(request_source),
        "cargo_lane": get_field(material_request, "custom_cargo_lane"),
        "source_warehouse": source_warehouse,
        "destination_warehouse": destination_warehouse,
        "destination_label": strip_company_suffix(destination_warehouse),
        "source_company": source_company,
        "target_company": target_company,
        "finance_treatment": finance_treatment,
    }

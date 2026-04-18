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

CANONICAL_COMMISSARY_GROUP_WAREHOUSE = "Commissary - BKI"
CANONICAL_COMMISSARY_OPERATION_WAREHOUSE = "Shaw BLVD - BKI"
TEST_COMMISSARY_OPERATION_WAREHOUSE = "TEST-COMMISSARY - BKI"
LEGACY_COMMISSARY_OPERATION_WAREHOUSES = ("TEST-COMMISSARY - BEI", "Commissary - BEI")

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


def get_preferred_commissary_warehouses(include_legacy: bool = True) -> tuple[str, ...]:
	preferred = (
		TEST_COMMISSARY_OPERATION_WAREHOUSE,
		CANONICAL_COMMISSARY_OPERATION_WAREHOUSE,
	)
	if include_legacy:
		return preferred + LEGACY_COMMISSARY_OPERATION_WAREHOUSES
	return preferred


def _project_root() -> Path:
	return Path(__file__).resolve().parents[2]


RUNTIME_BUYER_ENTITY_REGISTER_RELATIVE_PATH = (
	Path("hrms") / "fixtures" / "store_buyer_entity_register" / "store_buyer_entity_register.csv"
)

CLEANROOM_BUYER_ENTITY_REGISTER_RELATIVE_PATH = (
	Path("data")
	/ "_CLEANROOM"
	/ "2026-03-12-s037-store-buyer-entity-register"
	/ "store_buyer_entity_register_2026-03-12.csv"
)


def _candidate_project_roots() -> tuple[Path, ...]:
	current_root = _project_root()
	candidates = [current_root]

	# Worktrees in this repo commonly live beside the canonical workspace root
	# (for example: `BEI-ERP-s037-handoff` -> `BEI-ERP`). Search that root too
	# so local execution never silently falls back to "missing register" state.
	canonical_sibling = current_root.parent / "BEI-ERP"
	if canonical_sibling != current_root:
		candidates.append(canonical_sibling)

	unique: list[Path] = []
	for candidate in candidates:
		if candidate not in unique:
			unique.append(candidate)
	return tuple(unique)


def _candidate_register_paths() -> tuple[Path, ...]:
	paths: list[Path] = []
	for root in _candidate_project_roots():
		for relative_path in (
			RUNTIME_BUYER_ENTITY_REGISTER_RELATIVE_PATH,
			CLEANROOM_BUYER_ENTITY_REGISTER_RELATIVE_PATH,
		):
			candidate = root / relative_path
			if candidate not in paths:
				paths.append(candidate)
	return tuple(paths)


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
	"""S190: Resolve warehouse → Company via Warehouse.company Link field only.

	No suffix guessing (" - BEI" / " - BKI"). If Warehouse.company is not set,
	returns None. Callers MUST handle None per the S190 callsite contract:
	- submit_order: THROW
	- _create_mr_for_store_order: reads order.company (never calls this)
	- stamp_material_request_contract: THROW if both source and target are None
	- build_bki_store_sale_invoice: fall back to CSV
	- _create_fee_sales_invoice_for_billing: fall back to CSV
	"""
	if not warehouse_name:
		return None
	try:
		company = frappe.db.get_value("Warehouse", warehouse_name, "company")
		if company:
			return company
	except Exception:
		pass
	# S190: No suffix guessing — Warehouse.company is mandatory
	return None


def load_store_buyer_entity_register() -> list[dict[str, str]]:
	"""S190 Phase 5: CSV register RETIRED. Company Master is the only source of truth.

	If any caller still invokes this, they must be migrated to read Warehouse.company
	and Company DocType fields directly.
	"""
	raise NotImplementedError(
		"S190 Phase 5: store_buyer_entity_register CSV has been retired. "
		"Use Warehouse.company + Company Master fields. "
		"See hrms/utils/supply_chain_contracts.py::resolve_store_buyer_entity "
		"for the Company-first resolution pattern."
	)


def _build_company_first_entity_row(
	company_name: str, warehouse_name: str, store_name: str | None = None,
) -> dict[str, Any]:
	"""S190: Build a 14-key entity_row from Company Master fields.

	CRITICAL (B1 fix): buyer_entity_requires_billing_hold() checks
	buyer_entity_status — if missing, returns True → billing hold on ALL stores.
	Every key that callers read MUST be present.
	"""
	store_ownership_type = ""
	try:
		store_ownership_type = frappe.db.get_value(
			"Company", company_name, "store_ownership_type"
		) or ""
	except Exception:
		pass

	return {
		"store_name": store_name or strip_company_suffix(warehouse_name),
		"buyer_entity_name": company_name,
		"buyer_entity_status": BUYER_ENTITY_STATUS_CONFIRMED,
		"buyer_entity_source": "company_master",
		"billing_policy": "BKI_TO_STORE_INTERCOMPANY",
		"billing_post_policy": "standard",
		"store_type": store_ownership_type or "Company Owned",
		"store_type_status": "active",
		"store_allocation_required": "no",
		"markup_rule_mode": "standard",
		"markup_rule_source": "company_master",
		"active_fulfillment_status": "active",
		"warehouse_docname": warehouse_name,
		"evidence_primary": "company_master",
	}


def _resolve_buyer_customer_for_company(company: str) -> tuple[str | None, str | None]:
	"""S204: Resolve the Customer that should be billed for a given Company.

	Returns (customer_name_used, matched_company) — the customer_name_used
	becomes buyer_entity_name on the entity_row, and matched_company is the
	Company the customer was found under (for audit).

	Resolution order (each step is a data-driven lookup, no hardcoded maps):
	  1. Customer.customer_name == company  (parent-entity warehouses like
	     "BEBANG MEGA INC." — exact match works for legacy stores).
	  2. Customer.represents_company == company  (Frappe's native internal
	     customer linkage — handles manually-seeded store-first customers).
	  3. Follow Company.parent_company → Customer.customer_name == parent
	     (S199 store-first companies like "SM MEGAMALL - BEBANG ENTERPRISE
	     INC." → parent_company=BEBANG ENTERPRISE INC. → Customer exists).
	  4. Strip trailing " - <legal suffix>" from the company name → Customer
	     whose customer_name matches the stripped part (unblocks stores whose
	     Company has NULL parent_company but whose legal suffix names a
	     Customer — e.g. "THE GRID ROCKWELL - TASTECARTEL CORP." → strip to
	     "TASTECARTEL CORP." → Customer exists).
	"""
	import re as _re

	# Step 1: exact name match
	exact = frappe.db.get_value("Customer", {"customer_name": company}, "name")
	if exact:
		return exact, company

	# Step 2: represents_company link
	internal = frappe.db.get_value(
		"Customer", {"represents_company": company}, "name"
	)
	if internal:
		return internal, company

	# Step 3: parent_company fallback
	parent_company = frappe.db.get_value("Company", company, "parent_company")
	if parent_company:
		via_parent = frappe.db.get_value(
			"Customer", {"customer_name": parent_company}, "name"
		) or frappe.db.get_value(
			"Customer", {"represents_company": parent_company}, "name"
		)
		if via_parent:
			return via_parent, parent_company

	# Step 4: strip trailing " - <legal suffix>" (INC./CORP./OPC/HOLDINGS OPC)
	# Matches the tail used by S199 store-first names. Safe regex: only anchored
	# to end of string, only matches explicit legal suffixes so we don't
	# accidentally chop a store-specific name.
	stripped = _re.sub(
		r"\s+-\s+.+?(?:\s+INC\.|\s+CORP\.|\s+OPC|\s+HOLDINGS\s+OPC)$",
		"",
		company,
	).strip()
	if stripped and stripped != company:
		via_stripped = frappe.db.get_value(
			"Customer", {"customer_name": stripped}, "name"
		) or frappe.db.get_value(
			"Customer", {"represents_company": stripped}, "name"
		)
		if via_stripped:
			return via_stripped, stripped

	# Also try the opposite direction — the legal-suffix tail (after the dash)
	# e.g. "THE GRID ROCKWELL - TASTECARTEL CORP." → "TASTECARTEL CORP."
	tail_match = _re.search(
		r"\s+-\s+(.+?(?:INC\.|CORP\.|OPC|HOLDINGS\s+OPC))$",
		company,
	)
	if tail_match:
		tail = tail_match.group(1).strip()
		via_tail = frappe.db.get_value(
			"Customer", {"customer_name": tail}, "name"
		) or frappe.db.get_value(
			"Customer", {"represents_company": tail}, "name"
		)
		if via_tail:
			return via_tail, tail

	return None, None


def resolve_store_buyer_entity(
	*,
	warehouse_docname: str | None = None,
	store_name: str | None = None,
) -> dict[str, Any]:
	"""S190 Phase 5 + S204: Company Master is source of truth with principled
	fallbacks (parent_company link + legal-suffix strip).

	Resolution:
	1. Resolve warehouse → Company (via Warehouse.company Link)
	2. Resolve Company → Customer via a 4-step data-driven lookup:
	     a. exact customer_name match
	     b. represents_company link
	     c. Company.parent_company → Customer
	     d. stripped legal suffix → Customer
	3. If no Company or no Customer across all steps, return the "missing" dict
	   with billing hold (fail-safe — billing halts cleanly instead of
	   throwing/guessing).
	"""
	if warehouse_docname:
		company = resolve_warehouse_company(warehouse_docname)
		if company:
			customer_name, matched_company = _resolve_buyer_customer_for_company(company)
			if customer_name:
				# Use matched_company (the company whose name the customer actually
				# matches) as buyer_entity_name. For parent-fallback cases, this
				# ensures the SI lists the parent as buyer — the legal pay-er.
				return _build_company_first_entity_row(
					matched_company, warehouse_docname, store_name
				)

	# No Company or no Customer → fail-safe hold (caller's billing_hold check fires).
	return {
		"store_name": store_name or strip_company_suffix(warehouse_docname),
		"buyer_entity_name": "",
		"buyer_entity_status": BUYER_ENTITY_STATUS_MISSING,
		"buyer_entity_source": "",
		"billing_policy": "",
		"billing_post_policy": "DRAFT_ONLY__BILLING_HOLD_PENDING_COMPANY_MASTER",
		"store_type": "",
		"store_type_status": "",
		"store_allocation_required": 0,
		"markup_rule_mode": "CONFIG_PENDING_COMPANY_MASTER",
		"markup_rule_source": "company_master_missing",
		"active_fulfillment_status": "blocked_missing_company_master",
		"warehouse_docname": warehouse_docname or "",
		"evidence_primary": "",
		"evidence_secondary": "",
		"notes": "No Warehouse.company or no Customer for that company. Fix Company Master.",
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


def _coerce_percent(value: Any) -> float | None:
	try:
		numeric = float(value)
	except (TypeError, ValueError):
		return None
	if numeric <= 0:
		return None
	return numeric / 100 if numeric > 1 else numeric


def _get_store_type_delivery_markup_percent(store_name: str | None) -> float | None:
	if not store_name or not getattr(getattr(frappe, "db", None), "get_value", None):
		return None
	try:
		row = frappe.db.get_value(
			"BEI Store Type",
			{"store": store_name},
			["price_list_multiplier", "store_type"],
			as_dict=True,
		)
	except Exception:
		return None
	if not row:
		return None
	return _coerce_percent(get_field(row, "price_list_multiplier"))


def resolve_markup_percent(
	store_type: str | None,
	*,
	store_name: str | None = None,
	entity_row: dict[str, Any] | None = None,
) -> float:
	if entity_row:
		store_name = store_name or entity_row.get("store_name")

	configured_markup = _get_store_type_delivery_markup_percent(store_name)
	if configured_markup is not None:
		return configured_markup

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
	set_if_column(
		doc, "custom_store_allocation_required", cint_bool(entity_row.get("store_allocation_required"))
	)
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
	destination_warehouse: str | None = None,
	source_company: str | None = None,
	target_company: str | None = None,
	finance_treatment: str | None = None,
) -> None:
	source_company = source_company or resolve_warehouse_company(source_warehouse)
	destination_warehouse = destination_warehouse or getattr(doc, "set_warehouse", None)
	target_company = target_company or resolve_warehouse_company(destination_warehouse)
	# S190 B4: if both companies are None, log error — finance treatment will be wrong
	if not source_company and not target_company:
		frappe.log_error(
			f"S190: stamp_material_request_contract — both source and target company are None "
			f"(source_wh={source_warehouse}, dest_wh={destination_warehouse}). "
			f"Finance treatment will default to same_company which may be incorrect.",
			"S190 Missing Company Warning",
		)
	resolved_treatment = finance_treatment or infer_finance_treatment(source_company, target_company)
	set_if_column(doc, "custom_request_source", normalize_request_source(request_source))
	set_if_column(doc, "custom_cargo_lane", cargo_lane)
	set_if_column(doc, "custom_source_warehouse", source_warehouse)
	set_if_column(doc, "custom_destination_warehouse", destination_warehouse)
	set_if_column(doc, "custom_source_company", source_company)
	set_if_column(doc, "custom_target_company", target_company)
	set_if_column(doc, "custom_finance_treatment", resolved_treatment)


def stamp_stock_entry_contract(
	doc: Any,
	*,
	request_source: str,
	cargo_lane: str | None = None,
	destination_warehouse: str | None = None,
	source_company: str | None = None,
	target_company: str | None = None,
	finance_treatment: str | None = None,
) -> None:
	source_company = source_company or resolve_warehouse_company(
		getattr(doc, "from_warehouse", None) or getattr(doc, "source_warehouse", None)
	)
	destination_warehouse = (
		destination_warehouse or getattr(doc, "to_warehouse", None) or getattr(doc, "target_warehouse", None)
	)
	target_company = target_company or resolve_warehouse_company(destination_warehouse)
	resolved_treatment = finance_treatment or infer_finance_treatment(source_company, target_company)
	set_if_column(doc, "custom_request_source", normalize_request_source(request_source))
	set_if_column(doc, "custom_cargo_lane", cargo_lane)
	set_if_column(doc, "custom_destination_warehouse", destination_warehouse)
	set_if_column(doc, "custom_source_company", source_company)
	set_if_column(doc, "custom_target_company", target_company)
	set_if_column(doc, "custom_finance_treatment", resolved_treatment)


def resolve_material_request_contract(
	material_request: Any, commissary_warehouse: str | None = None
) -> dict[str, Any]:
	request_source = normalize_request_source(get_field(material_request, "custom_request_source"))
	if not request_source:
		if get_field(material_request, "custom_store_order"):
			request_source = REQUEST_SOURCE_STORE_ORDER
		elif commissary_warehouse and get_field(material_request, "set_warehouse") == commissary_warehouse:
			request_source = REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL
		elif "raw material requisition" in str(get_field(material_request, "remarks", "")).lower():
			request_source = REQUEST_SOURCE_COMMISSARY_RAW_MATERIAL

	source_warehouse = get_field(material_request, "custom_source_warehouse")
	destination_warehouse = get_field(material_request, "custom_destination_warehouse") or get_field(
		material_request, "set_warehouse"
	)
	first_item_warehouse = None
	for item in get_field(material_request, "items", []) or []:
		first_item_warehouse = get_field(item, "from_warehouse") or first_item_warehouse
		destination_warehouse = destination_warehouse or get_field(item, "warehouse")
		if source_warehouse and destination_warehouse:
			break
		source_warehouse = source_warehouse or first_item_warehouse

	if request_source == REQUEST_SOURCE_STORE_ORDER and not destination_warehouse:
		linked_store_order = get_field(material_request, "custom_store_order")
		if linked_store_order and getattr(getattr(frappe, "db", None), "get_value", None):
			try:
				destination_warehouse = frappe.db.get_value("BEI Store Order", linked_store_order, "store")
			except Exception:
				destination_warehouse = destination_warehouse

	source_company = get_field(material_request, "custom_source_company") or resolve_warehouse_company(
		source_warehouse
	)
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

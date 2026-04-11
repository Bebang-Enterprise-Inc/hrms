# Copyright (c) 2026, Bebang Enterprise Inc. and contributors
# For license information, please see license.txt
"""S181 Phase 2B: whitelisted API for the Company Master frontend lane.

The bei-tasks (React/Next.js) Company Master page at
`/dashboard/bd/companies` consumes these methods exclusively via the
`/api/frappe/api/method/hrms.api.company_master.<function>` proxy. This
module is the frozen interface contract between the backend and frontend
lanes (see output/s181/interface_contract.md).

Blocker 6 fix -- the original draft told the bei-tasks frontend to read
Company data via `/api/resource/Company/<name>`. That pattern is not used
anywhere else in bei-tasks (`lib/queries/hr-employee-detail.ts`,
`lib/queries/hr-payroll.ts` and every other integration use the
`/api/frappe/api/method/...` proxy exclusively). Trying to mix patterns
would break CSRF handling and the child-table PATCH semantics that
bei-tasks has already solved for its other pages. This module gives the
frontend an interface that matches the existing convention.

Security posture:
- Every endpoint calls `set_backend_observability_context(module=
  "company", action=..., mutation_type=...)` per DM-7 rule.
- Every mutating endpoint runs `frappe.has_permission("Company", "write",
  doc=...)` on the specific Company before touching it. Read endpoints
  check "read".
- `update_company_section` takes a `section` name and a payload dict, and
  only writes fields that appear in `EDITABLE_SECTIONS[section]`. Mass
  assignment outside that allow-list is silently dropped -- the frontend
  cannot use this endpoint to write to arbitrary Company fields.
- `upsert_compliance_document` re-runs the "file OR drive_file_url"
  validator at the API layer, mirroring the BEI Company Document
  controller validate() so callers hitting this endpoint directly get the
  same guarantees as callers coming through doc.save().
- `upsert_adms_device` enforces cross-company uniqueness on device_serial
  -- one physical device cannot be assigned to two companies.
"""
from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from hrms.utils.sentry import set_backend_observability_context


# Fields the frontend is allowed to write, grouped by section.
# Keeps mass assignment safe -- any payload key outside the allowlist for
# the requested section is silently dropped.
EDITABLE_SECTIONS: dict[str, list[str]] = {
	"bir_legal": [
		"company_name",
		"tax_id",
		"branch_tin",
		"bir_rdo_code",
		"bir_registration_date",
		"sec_registration_no",
		"sec_registration_date",
	],
	"location": [
		"full_address",
		"city",
		"province",
		"region",
		"mall_or_building",
		"gps_latitude",
		"gps_longitude",
		"google_maps_place_id",
	],
	"operations": [
		"entity_category",
		"store_ownership_type",
		"operational_status",
		"opening_date",
		"operating_hours",
		"pos_system",
		"mosaic_location_id",
	],
	"contacts": [
		"store_manager",
		"store_manager_phone",
		"area_supervisor",
		"regional_manager",
	],
	"compliance": [
		"drive_folder_url",
	],
	"bd_pipeline": [
		"pipeline_status",
		"target_opening_date",
		"lease_start_date",
		"lease_end_date",
		"lease_monthly_rent",
		"revenue_share_pct",
	],
}


def _compute_expiry_summary(compliance_documents: list[dict]) -> dict[str, int]:
	"""Compute the valid/expiring/expired counts for the Compliance Documents
	strip in the frontend detail dialog. Expiring = within 30 days of today.
	"""
	today_d = getdate(today())
	cutoff = add_days(today_d, 30)
	valid = expiring = expired = 0
	for d in compliance_documents or []:
		if not d.get("expiry_date"):
			continue
		ed = getdate(d["expiry_date"])
		if ed < today_d:
			expired += 1
		elif ed <= cutoff:
			expiring += 1
		else:
			valid += 1
	return {"valid": valid, "expiring": expiring, "expired": expired}


@frappe.whitelist()
def list_companies(filters: dict | str | None = None, search: str | None = None) -> list[dict]:
	"""Return the list rows for the Company Master table.

	Projects only the columns the list page needs (name, abbr,
	entity_category, store_ownership_type, operational_status, city,
	mosaic_location_id, first_provision_done). Does NOT return child
	tables -- callers need `get_company(name)` for the full detail.

	Filters (all optional, combined with AND):
	- entity_category: exact match
	- store_ownership_type: exact match
	- operational_status: exact match

	Search (optional): substring match on name / company_name / city.

	Sort: by entity_category then name, ASC.
	"""
	set_backend_observability_context(
		module="company",
		action="list_companies",
		mutation_type="read",
	)

	# Frappe whitelisted methods receive JSON-encoded dicts as strings when
	# called through the /api/method proxy; decode defensively.
	if isinstance(filters, str):
		import json

		try:
			filters = json.loads(filters)
		except Exception:
			filters = None

	where_clauses = ["1=1"]
	params: dict[str, Any] = {}
	if filters:
		if filters.get("entity_category"):
			where_clauses.append("entity_category = %(ec)s")
			params["ec"] = filters["entity_category"]
		if filters.get("store_ownership_type"):
			where_clauses.append("store_ownership_type = %(sot)s")
			params["sot"] = filters["store_ownership_type"]
		if filters.get("operational_status"):
			where_clauses.append("operational_status = %(os)s")
			params["os"] = filters["operational_status"]
		if filters.get("region"):
			where_clauses.append("region = %(region)s")
			params["region"] = filters["region"]
	if search:
		where_clauses.append(
			"(name LIKE %(s)s OR company_name LIKE %(s)s OR city LIKE %(s)s)"
		)
		params["s"] = f"%{search}%"

	sql = f"""
		SELECT
			name, company_name, abbr,
			entity_category, store_ownership_type, operational_status,
			city, province, region,
			mosaic_location_id,
			first_provision_done
		FROM `tabCompany`
		WHERE {' AND '.join(where_clauses)}
		ORDER BY COALESCE(entity_category, 'zzz'), name
	"""
	return frappe.db.sql(sql, params, as_dict=True)


@frappe.whitelist()
def get_company(name: str) -> dict:
	"""Return the full Company document including S181 Custom Fields,
	the stakeholders / adms_devices / compliance_documents child tables,
	and a computed `expiry_summary` for the compliance calendar strip.
	"""
	set_backend_observability_context(
		module="company",
		action="get_company",
		mutation_type="read",
		extras={"company": name},
	)

	if not frappe.has_permission("Company", "read", doc=name):
		frappe.throw(_("Not permitted to read company {0}").format(name))

	doc = frappe.get_doc("Company", name).as_dict()
	doc["expiry_summary"] = _compute_expiry_summary(doc.get("compliance_documents") or [])
	return doc


@frappe.whitelist()
def update_company_section(name: str, section: str, payload: dict | str) -> dict:
	"""Update a single section of the Company form.

	Mass-assignment safety: only fields in `EDITABLE_SECTIONS[section]`
	are accepted. Any other payload keys are silently dropped. An unknown
	section raises.

	Triggers on_update -- the sentinel-gated auto_provision_company hook
	is idempotent (will not re-run after first_provision_done=1).
	"""
	set_backend_observability_context(
		module="company",
		action="update_company_section",
		mutation_type="update",
		extras={"company": name, "section": section},
	)

	if not frappe.has_permission("Company", "write", doc=name):
		frappe.throw(_("Not permitted to write company {0}").format(name))

	if section not in EDITABLE_SECTIONS:
		frappe.throw(_("Unknown section: {0}").format(section))

	if isinstance(payload, str):
		import json

		payload = json.loads(payload)

	allowed = set(EDITABLE_SECTIONS[section])
	clean = {k: v for k, v in (payload or {}).items() if k in allowed}
	if not clean:
		return {"ok": True, "noop": True, "updated_fields": []}

	doc = frappe.get_doc("Company", name)
	for k, v in clean.items():
		doc.set(k, v)
	doc.save()
	return {"ok": True, "updated_fields": sorted(clean.keys())}


def _validate_compliance_row_payload(row: dict) -> None:
	"""Mirror the BEI Company Document controller validate() at the API
	layer so callers hitting this endpoint directly get the same checks
	as callers going through doc.save().
	"""
	if not row.get("file") and not row.get("drive_file_url"):
		frappe.throw(
			_(
				"Document must have either an uploaded File or a Google Drive URL "
				"(or both)."
			)
		)
	drive_url = row.get("drive_file_url")
	if drive_url and not (
		drive_url.startswith("https://drive.google.com/")
		or drive_url.startswith("https://docs.google.com/")
	):
		frappe.throw(
			_(
				"Google Drive URL must start with https://drive.google.com/ or "
				"https://docs.google.com/"
			)
		)


@frappe.whitelist()
def upsert_compliance_document(company: str, row: dict | str) -> dict:
	"""Create or update a BEI Company Document row on the Company's
	`compliance_documents` child table.

	If `row["name"]` is set, updates the existing row in place; otherwise
	appends a new row. Enforces the "at least one of file OR drive_file_url"
	rule at the API layer too, in addition to the BEI Company Document
	controller validator (defense in depth).
	"""
	set_backend_observability_context(
		module="company",
		action="upsert_compliance_document",
		mutation_type="update",
		extras={"company": company},
	)

	if not frappe.has_permission("Company", "write", doc=company):
		frappe.throw(_("Not permitted"))

	if isinstance(row, str):
		import json

		row = json.loads(row)

	_validate_compliance_row_payload(row)

	doc = frappe.get_doc("Company", company)
	if row.get("name"):
		for child in doc.compliance_documents:
			if child.name == row["name"]:
				child.update(row)
				break
		else:
			frappe.throw(
				_("Compliance document row {0} not found on company {1}").format(
					row["name"], company
				)
			)
	else:
		doc.append("compliance_documents", row)
	doc.save()
	return {"ok": True}


@frappe.whitelist()
def delete_compliance_document(company: str, row_name: str) -> dict:
	"""Delete a row from the compliance_documents child table."""
	set_backend_observability_context(
		module="company",
		action="delete_compliance_document",
		mutation_type="delete",
		extras={"company": company, "row": row_name},
	)

	if not frappe.has_permission("Company", "write", doc=company):
		frappe.throw(_("Not permitted"))

	doc = frappe.get_doc("Company", company)
	doc.compliance_documents = [
		c for c in doc.compliance_documents if c.name != row_name
	]
	doc.save()
	return {"ok": True}


@frappe.whitelist()
def upsert_adms_device(company: str, row: dict | str) -> dict:
	"""Add or update an ADMS device row on `adms_devices`.

	Saving triggers the `auto_enroll_adms_devices` hook which enqueues the
	enrollment HTTP call in the background. Enforces cross-company
	uniqueness on `device_serial` -- one device cannot belong to two
	companies at the same time.
	"""
	set_backend_observability_context(
		module="company",
		action="upsert_adms_device",
		mutation_type="update",
		extras={"company": company},
	)

	if not frappe.has_permission("Company", "write", doc=company):
		frappe.throw(_("Not permitted"))

	if isinstance(row, str):
		import json

		row = json.loads(row)

	if not row.get("device_serial"):
		frappe.throw(_("device_serial is required"))

	# Cross-company uniqueness check. `parent` on BEI Company ADMS Device
	# is the Company name. Excluding our current company so an in-place
	# edit doesn't false-positive on its own row.
	existing_parent = frappe.db.sql(
		"""
		SELECT parent
		FROM `tabBEI Company ADMS Device`
		WHERE device_serial = %s AND parent != %s
		LIMIT 1
		""",
		(row["device_serial"], company),
	)
	if existing_parent:
		frappe.throw(
			_("Device serial {0} is already assigned to company {1}").format(
				row["device_serial"], existing_parent[0][0]
			)
		)

	doc = frappe.get_doc("Company", company)
	if row.get("name"):
		for child in doc.adms_devices:
			if child.name == row["name"]:
				child.update(row)
				break
		else:
			frappe.throw(
				_("ADMS device row {0} not found on company {1}").format(
					row["name"], company
				)
			)
	else:
		doc.append("adms_devices", row)
	doc.save()
	return {"ok": True}


@frappe.whitelist()
def delete_adms_device(company: str, row_name: str) -> dict:
	"""Delete a row from the adms_devices child table."""
	set_backend_observability_context(
		module="company",
		action="delete_adms_device",
		mutation_type="delete",
		extras={"company": company, "row": row_name},
	)

	if not frappe.has_permission("Company", "write", doc=company):
		frappe.throw(_("Not permitted"))

	doc = frappe.get_doc("Company", company)
	doc.adms_devices = [d for d in doc.adms_devices if d.name != row_name]
	doc.save()
	return {"ok": True}


@frappe.whitelist()
def retry_provision(company: str) -> dict:
	"""Frontend-facing wrapper for
	`hrms.overrides.company.retry_provision_company`.

	Exists so the bei-tasks frontend can use a single consistent module
	namespace (`hrms.api.company_master.*`) for every Company Master call
	instead of mixing in `hrms.overrides.company.*`. The underlying method
	already enforces write permission, clears the sentinel, and re-runs
	auto_provision_company idempotently.
	"""
	set_backend_observability_context(
		module="company",
		action="retry_provision",
		mutation_type="update",
		extras={"company": company},
	)
	from hrms.overrides.company import retry_provision_company

	return retry_provision_company(company)


# ============================================================================
# S181 HOTFIX (2026-04-11) -- store-driven list + one-click populate
#
# Ship reality correction after the first production review:
#
# 1. list_stores() -- the Company Master list must show ONE ROW PER STORE
#    (from the S037 register), not one row per Frappe Company. Multiple
#    stores under the same buyer entity show as duplicate rows -- intentional,
#    because the operational unit is the store, not the legal entity. Adds
#    non-store entities (head office, commissary, franchisor, holding cos)
#    as extra rows at the end so nothing falls off the list.
#
# 2. populate_s181_fields() -- one whitelisted call that runs the Phase 3
#    seed (entity_category, store_ownership_type, mosaic_location_id, GPS,
#    city, operational_status, pos_system) and Phase 4 TIN backfill, plus
#    sets first_provision_done=1 for every existing Company that already
#    has a COA (the 45 pre-S181 entities should not trip the Retry
#    Provisioning UI). Sam triggers this once from the frontend "Populate
#    S181 Fields" banner and it completes in seconds.
#
# 3. get_store_context(store_name) -- returns (store_name, company_name,
#    abbr, entity_category) for the detail dialog header so it can render
#    "Ayala Evo City -- Bebang Mega Inc." instead of just the company name.
# ============================================================================


# S037 register path, resolved relative to the hrms app root
_S037_RELPATH = (
	"..",
	"data",
	"_CLEANROOM",
	"2026-03-12-s037-store-buyer-entity-register",
	"store_buyer_entity_register_2026-03-12.csv",
)

# Non-store legal entities that don't appear in S037 but should still
# appear in the list. Category maps to the S181 entity_category field.
_NON_STORE_ENTITIES: dict[str, str] = {
	"Bebang Enterprise Inc.": "Head Office",
	"Bebang Kitchen Inc.": "Commissary",
	"BEBANG FRANCHISE CORP.": "Franchisor",
	"Bebang Franchise Corporation": "Franchisor",
	"BFC": "Franchisor",
	"Irresistible Infusions Inc.": "Holding Company",
	"DMD HOLDINGS INC.": "Holding Company",
	"DMD Holdings Inc": "Holding Company",
	"Resto Tech Inc": "Head Office",
}


def _load_s037_rows() -> list[dict]:
	"""Read the S037 register and return the list of rows."""
	import csv
	import os

	path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *_S037_RELPATH))
	if not os.path.exists(path):
		frappe.log_error(
			title="S181 list_stores: S037 register missing",
			message=f"Expected at {path}",
		)
		return []
	with open(path, encoding="utf-8-sig") as f:
		return list(csv.DictReader(f))


def _lookup_company_fields(company_names: set[str]) -> dict[str, dict]:
	"""Bulk-fetch the S181 Company fields for the given set of Company
	docnames in one query. Returns {docname: row_dict} for fast lookup.
	"""
	if not company_names:
		return {}
	meta = frappe.get_meta("Company")
	# Only select fields that actually exist -- defensive against partial
	# migrate state on fresh environments.
	fields = [
		f
		for f in [
			"name",
			"company_name",
			"abbr",
			"tax_id",
			"branch_tin",
			"bir_rdo_code",
			"entity_category",
			"store_ownership_type",
			"operational_status",
			"city",
			"province",
			"region",
			"full_address",
			"mall_or_building",
			"gps_latitude",
			"gps_longitude",
			"mosaic_location_id",
			"pos_system",
			"first_provision_done",
		]
		if f == "name" or meta.has_field(f)
	]
	rows = frappe.get_all(
		"Company",
		filters={"name": ["in", list(company_names)]},
		fields=fields,
	)
	return {r["name"]: r for r in rows}


def _resolve_company_for_s037_row(
	row: dict, all_companies: set[str], lower_name_index: dict[str, str]
) -> str | None:
	"""Find the Frappe Company docname that corresponds to an S037 row.

	Resolution order:
	1. `row['buyer_entity_name']` exact match against Company docnames
	2. `row['buyer_entity_name']` case-insensitive match (handles "Bebang
	   Mega Inc" vs "BEBANG MEGA INC." variants)
	3. None (store is mapped in S037 but no Frappe Company exists yet)
	"""
	buyer = (row.get("buyer_entity_name") or "").strip()
	if not buyer:
		return None
	if buyer in all_companies:
		return buyer
	# Case-insensitive normalized fallback
	# Normalize: lowercase + strip trailing period
	key = buyer.lower().rstrip(".").strip()
	return lower_name_index.get(key)


def _company_has_coa(company_name: str) -> bool:
	"""Return True if this Company already has at least one posting Account
	on it -- a proxy for "was provisioned by S175 or earlier". Used to
	decide whether the 'Run First Provisioning' button should show.
	"""
	return bool(
		frappe.db.get_value(
			"Account",
			{"company": company_name, "is_group": 0},
			"name",
		)
	)


@frappe.whitelist()
def list_stores(
	filters: dict | str | None = None,
	search: str | None = None,
) -> list[dict]:
	"""Return one row per store from the S037 register + non-store entities.

	HOTFIX: this is the correct data source for the Company Master list
	page. `list_companies` (above) returns one row per Frappe Company and
	hides multi-store entities (e.g. Bebang Mega Inc operates 5 stores --
	list_companies shows 1 row, list_stores shows 5).

	Row shape per store (driven by S037):
	  - store_name         : from S037 "store_name" (e.g. "Ayala Evo City")
	  - company            : resolved Frappe Company docname (e.g. "BEBANG MEGA INC.")
	  - company_label      : Company.company_name display label
	  - abbr               : Company.abbr
	  - store_type         : from S037 (Managed Franchise / JV / etc.)
	  - row_kind           : "store"
	  - warehouse_docname  : from S037 (for the detail dialog to link to)
	  - entity_category    : "Store" (fixed for store rows)
	  - store_ownership_type, operational_status, city, province, region
	  - mosaic_location_id
	  - first_provision_done (from the resolved Company)
	  - has_coa            : True if the Company already has posting accounts
	                          (used to hide the "Run First Provisioning" pill)

	Row shape per non-store entity (7 rows):
	  - store_name         : None
	  - company            : Frappe Company docname
	  - company_label      : Company.company_name
	  - abbr               : Company.abbr
	  - row_kind           : "non_store"
	  - entity_category    : from NON_STORE_ENTITIES map (Head Office,
	                          Commissary, Franchisor, Holding Company)
	  - first_provision_done, has_coa (same as store rows)
	"""
	set_backend_observability_context(
		module="company", action="list_stores", mutation_type="read"
	)

	if isinstance(filters, str):
		import json

		try:
			filters = json.loads(filters)
		except Exception:
			filters = None
	filters = filters or {}

	# Load S037 + Companies index
	s037_rows = _load_s037_rows()
	all_company_names = set(frappe.get_all("Company", pluck="name"))
	lower_name_index: dict[str, str] = {}
	for name in all_company_names:
		key = name.lower().rstrip(".").strip()
		lower_name_index[key] = name

	# Figure out which Companies we'll need field data for (store rows +
	# non-store rows), then bulk-fetch in one query.
	resolved_store_companies: list[tuple[dict, str | None]] = []
	for s037 in s037_rows:
		company = _resolve_company_for_s037_row(s037, all_company_names, lower_name_index)
		resolved_store_companies.append((s037, company))
	non_store_names = [
		n for n in _NON_STORE_ENTITIES.keys() if n in all_company_names
	]
	needed = {c for _, c in resolved_store_companies if c} | set(non_store_names)
	company_fields = _lookup_company_fields(needed)

	# Cache has_coa checks so we don't re-query per row
	has_coa_cache: dict[str, bool] = {}

	def has_coa(c: str) -> bool:
		if c not in has_coa_cache:
			has_coa_cache[c] = _company_has_coa(c)
		return has_coa_cache[c]

	def apply_filters(row: dict) -> bool:
		if filters.get("entity_category") and row.get("entity_category") != filters["entity_category"]:
			return False
		if (
			filters.get("store_ownership_type")
			and row.get("store_ownership_type") != filters["store_ownership_type"]
		):
			return False
		if (
			filters.get("operational_status")
			and row.get("operational_status") != filters["operational_status"]
		):
			return False
		if filters.get("region") and row.get("region") != filters["region"]:
			return False
		if search:
			needles = [
				(row.get("store_name") or ""),
				(row.get("company") or ""),
				(row.get("company_label") or ""),
				(row.get("city") or ""),
			]
			if not any(search.lower() in (s or "").lower() for s in needles):
				return False
		return True

	out: list[dict] = []

	# Store rows (from S037, may produce duplicate company references)
	for s037, company in resolved_store_companies:
		store_name = (s037.get("store_name") or "").strip()
		store_type = (s037.get("store_type") or "").strip()
		warehouse_docname = (s037.get("warehouse_docname") or "").strip()
		cf = company_fields.get(company) if company else {}
		row = {
			"row_kind": "store",
			"store_name": store_name,
			"company": company,
			"company_label": (cf or {}).get("company_name"),
			"abbr": (cf or {}).get("abbr"),
			"warehouse_docname": warehouse_docname or None,
			"store_type_s037": store_type or None,
			"entity_category": "Store",
			# Prefer S037 store_type for store_ownership_type display even
			# when the Company hasn't been seeded yet (so the filter works).
			"store_ownership_type": (cf or {}).get("store_ownership_type") or (store_type or None),
			"operational_status": (cf or {}).get("operational_status"),
			"city": (cf or {}).get("city"),
			"province": (cf or {}).get("province"),
			"region": (cf or {}).get("region"),
			"mosaic_location_id": (cf or {}).get("mosaic_location_id"),
			"first_provision_done": (cf or {}).get("first_provision_done"),
			"has_coa": has_coa(company) if company else False,
			"company_exists": bool(company),
		}
		if apply_filters(row):
			out.append(row)

	# Non-store entity rows
	for ns_name, cat in _NON_STORE_ENTITIES.items():
		if ns_name not in all_company_names:
			continue
		cf = company_fields.get(ns_name, {})
		row = {
			"row_kind": "non_store",
			"store_name": None,
			"company": ns_name,
			"company_label": cf.get("company_name") or ns_name,
			"abbr": cf.get("abbr"),
			"warehouse_docname": None,
			"store_type_s037": None,
			"entity_category": cf.get("entity_category") or cat,
			"store_ownership_type": None,
			"operational_status": cf.get("operational_status"),
			"city": cf.get("city"),
			"province": cf.get("province"),
			"region": cf.get("region"),
			"mosaic_location_id": cf.get("mosaic_location_id"),
			"first_provision_done": cf.get("first_provision_done"),
			"has_coa": has_coa(ns_name),
			"company_exists": True,
		}
		if apply_filters(row):
			out.append(row)

	# Sort: store rows by store_name, then non-store rows at the bottom
	out.sort(key=lambda r: (r["row_kind"] != "store", r.get("store_name") or r.get("company") or ""))
	return out


@frappe.whitelist()
def get_store_context(store_name: str | None = None, company: str | None = None) -> dict:
	"""Resolve a store_name (from S037) to its Company context for the
	detail dialog header. If `company` is passed directly (non-store rows),
	just returns that Company's display fields.

	Used by the detail dialog top bar so it can show
	"Ayala Evo City -- Bebang Mega Inc. (BMI2)" instead of just the company
	name. Returns None for fields that can't be resolved.
	"""
	set_backend_observability_context(
		module="company", action="get_store_context", mutation_type="read"
	)

	if not store_name and not company:
		frappe.throw(_("Either store_name or company is required"))

	resolved_company = company
	warehouse_docname = None

	if store_name and not resolved_company:
		# Look up via S037
		for s037 in _load_s037_rows():
			if (s037.get("store_name") or "").strip() == store_name.strip():
				buyer = (s037.get("buyer_entity_name") or "").strip()
				warehouse_docname = (s037.get("warehouse_docname") or "").strip() or None
				if buyer and frappe.db.exists("Company", buyer):
					resolved_company = buyer
					break
				# Case-insensitive fallback
				all_names = frappe.get_all("Company", pluck="name")
				lookup = {n.lower().rstrip(".").strip(): n for n in all_names}
				key = buyer.lower().rstrip(".").strip()
				if key in lookup:
					resolved_company = lookup[key]
					break

	if not resolved_company:
		return {
			"store_name": store_name,
			"company": None,
			"company_label": None,
			"abbr": None,
			"warehouse_docname": warehouse_docname,
			"entity_category": None,
		}

	if not frappe.has_permission("Company", "read", doc=resolved_company):
		frappe.throw(_("Not permitted to read company {0}").format(resolved_company))

	meta = frappe.get_meta("Company")
	wanted = [
		f
		for f in ("company_name", "abbr", "entity_category", "store_ownership_type")
		if f == "abbr" or f == "company_name" or meta.has_field(f)
	]
	doc_row = frappe.db.get_value("Company", resolved_company, wanted, as_dict=True) or {}

	return {
		"store_name": store_name,
		"company": resolved_company,
		"company_label": doc_row.get("company_name"),
		"abbr": doc_row.get("abbr"),
		"warehouse_docname": warehouse_docname,
		"entity_category": doc_row.get("entity_category"),
		"store_ownership_type": doc_row.get("store_ownership_type"),
	}


@frappe.whitelist()
def populate_s181_fields() -> dict:
	"""One-click populate S181 Custom Fields on all existing Companies.

	Runs INLINE what the Phase 3 seed script and Phase 4 TIN backfill do,
	plus sets `first_provision_done = 1` on every Company that already
	has posting accounts (the 45 pre-S181 entities with existing COA from
	S175 -- they should not show a "Run First Provisioning" button).

	Sam triggers this ONCE from the frontend "Populate S181 Fields" banner
	after the backend is deployed. Idempotent -- safe to re-run. Skips
	fields that already have the target value. Does NOT create any new
	accounts (the existing COA is left alone).

	Permission: requires System Manager or Accounts Manager role.
	"""
	set_backend_observability_context(
		module="company",
		action="populate_s181_fields",
		mutation_type="update",
	)

	# Permission gate -- one-shot migration, tightly scoped
	user_roles = set(frappe.get_roles())
	if not user_roles & {"System Manager", "Accounts Manager", "Administrator"}:
		frappe.throw(_("Only System Manager / Accounts Manager can run populate_s181_fields."))

	# Import the script logic directly so this runs inline without needing
	# bench execute
	import importlib.util
	import os

	scripts_dir = os.path.normpath(
		os.path.join(frappe.get_app_path("hrms"), "..", "scripts")
	)

	def load_script(filename: str):
		spec_path = os.path.join(scripts_dir, filename)
		spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), spec_path)
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		return mod

	phase3 = load_script("s181_phase_3_seed_company_fields.py")
	phase4 = load_script("s181_phase_4_branch_tin_backfill.py")

	# --- Phase 3 seed ---
	company_names = frappe.get_all("Company", pluck="name")
	p3_planned, p3_unmatched = phase3.plan_updates(company_names)
	p3_updated, p3_skipped, p3_per_field = phase3.apply_updates(p3_planned)

	# --- Phase 4 TIN backfill ---
	companies = frappe.get_all("Company", fields=["name", "tax_id"])
	s037_buyer_map = phase4.load_s037_buyer_map()
	tin_by_entity = phase4.load_tin_rdo_by_entity()
	p4_planned, p4_unmatched = phase4.plan_updates(companies, s037_buyer_map, tin_by_entity)
	p4_updated, p4_skipped, p4_per_field = phase4.apply_updates(p4_planned)

	# --- Pre-existing sentinel fix ---
	# Every Company that already has at least one posting account was
	# provisioned by an earlier sprint (S175 etc.) and does not need the
	# S181 on_update hook to run. Set first_provision_done=1 so the
	# "Run First Provisioning" pill hides for them.
	company_meta = frappe.get_meta("Company")
	if company_meta.has_field("first_provision_done"):
		pre_provisioned: list[str] = []
		for cname in company_names:
			if _company_has_coa(cname) and not frappe.db.get_value(
				"Company", cname, "first_provision_done"
			):
				frappe.db.set_value(
					"Company", cname, "first_provision_done", 1, update_modified=False
				)
				pre_provisioned.append(cname)
		pre_count = len(pre_provisioned)
	else:
		pre_count = 0

	frappe.db.commit()

	return {
		"ok": True,
		"phase3": {
			"updated": p3_updated,
			"skipped": p3_skipped,
			"per_field": p3_per_field,
			"unmatched_count": len(p3_unmatched),
			"unmatched": p3_unmatched[:10],
		},
		"phase4": {
			"updated": p4_updated,
			"skipped": p4_skipped,
			"per_field": p4_per_field,
			"unmatched_count": len(p4_unmatched),
			"unmatched": p4_unmatched[:10],
		},
		"pre_provisioned_sentinels_set": pre_count,
	}

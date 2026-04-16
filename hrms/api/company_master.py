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

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from hrms.utils.sentry import set_backend_observability_context


# Module-level name normalizer used by list_stores company resolution AND
# populate_s181_fields CSV matching. Strips Inc/Corp/OPC suffixes, removes
# punctuation, lowercases, collapses whitespace.
_STRIP_RE = re.compile(r"\b(inc\.?|corp\.?|corporation|opc|company|co\.?)\b", re.I)
_PUNCT_RE = re.compile(r"[.,'\"!\(\)\[\]]")
_WS_RE = re.compile(r"\s+")


def _norm_name(s: str) -> str:
	"""Normalize a company/store name for fuzzy comparison."""
	if not s:
		return ""
	s = s.lower()
	s = _STRIP_RE.sub("", s)
	s = _PUNCT_RE.sub(" ", s)
	return _WS_RE.sub(" ", s).strip()


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


# S037 register path. HOTFIX 2026-04-11: lives inside the hrms Python
# package at `hrms/data_seed/` so the file ships in the Frappe Docker
# image. The original first hotfix pointed at `data/_CLEANROOM/...` at
# the repo root, but that directory is gitignored — those files are
# never cloned by GitHub Actions when it builds the bench image, so
# `_load_s037_rows()` returned an empty list and the entire feature
# silently produced 0 store rows. L3 testing caught this on first run.
_S037_RELPATH = ("data_seed", "store_entity_mapping_2026-04-13.csv")

# Non-store legal entities that don't appear in S037 but should still
# appear in the list. Category maps to the S181 entity_category field.
_NON_STORE_ENTITIES: dict[str, str] = {
	# S199: ALL CAPS Company names. Only entities that are NOT stores.
	"BEBANG ENTERPRISE INC.": "Head Office",
	"BEBANG KITCHEN INC.": "Commissary",
	"BEBANG FRANCHISE CORP.": "Franchisor",
	"IRRESISTIBLE INFUSIONS INC.": "Holding Company",
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

	Resolution order (S188 per-store model):
	1. Check if a per-store child company exists for this specific store
	2. `row['buyer_entity_name']` exact match against Company docnames
	3. `row['buyer_entity_name']` case-insensitive match
	4. None (store is mapped in S037 but no Frappe Company exists yet)
	"""
	buyer = (row.get("buyer_entity_name") or "").strip()
	store_name = (row.get("store_name") or "").strip()
	if not buyer:
		return None

	# S188: per-store child company lookup — check if a child company
	# exists for this specific store before falling back to the parent
	_STORE_TO_CHILD: dict[str, str] = {
		# S199: ALL CAPS store-first Company names
		"SM Megamall": "SM MEGAMALL - BEBANG ENTERPRISE INC.",
		"SM Manila": "SM MANILA - BEBANG ENTERPRISE INC.",
		"SM Southmall": "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
		"Robinsons Place Antipolo": "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
		"Ayala Evo City": "AYALA EVO CITY - BEBANG MEGA INC.",
		"Ayala Vermosa": "AYALA VERMOSA - BEBANG MEGA INC.",
		"Robinsons Place Gen. Trias": "ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.",
		"Robinsons Place Imus": "ROBINSONS IMUS - BEBANG MEGA INC.",
		"SM Tanza": "SM TANZA - BEBANG MEGA INC.",
		"Sta. Lucia East Grand Mall": "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
		"D'Verde Calamba": "D'VERDE CALAMBA - TAJ FOOD CORP.",
		"Food Express (Gateway Mall)": "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
		"SM Caloocan": "SM CALOOCAN - TAJ FOOD CORP.",
		"SM Sangandaan": "SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC",
		"Robinsons Galleria South": "ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC",
	}
	if store_name and store_name in _STORE_TO_CHILD:
		child = _STORE_TO_CHILD[store_name]
		if child in all_companies:
			return child

	if buyer in all_companies:
		return buyer
	key = _norm_name(buyer)
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
		key = _norm_name(name)
		if key:
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
				# Normalized fallback (strips Inc/Corp/OPC + lowercase)
				all_names = frappe.get_all("Company", pluck="name")
				lookup = {_norm_name(n): n for n in all_names if _norm_name(n)}
				key = _norm_name(buyer)
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

	# S190: Also resolve warehouse → Company for the direct Warehouse.company Link
	warehouse_company = None
	if warehouse_docname:
		from hrms.utils.supply_chain_contracts import resolve_warehouse_company
		warehouse_company = resolve_warehouse_company(warehouse_docname)

	return {
		"store_name": store_name,
		"company": resolved_company,
		"company_label": doc_row.get("company_name"),
		"abbr": doc_row.get("abbr"),
		"warehouse_docname": warehouse_docname,
		"warehouse_company": warehouse_company,
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

	# HOTFIX4 2026-04-12: fully self-contained seed logic. No importlib from
	# scripts/ (which doesn't ship in the Docker image). All CSV reads go
	# through data_seed/ inside the hrms Python package.
	import csv
	import os
	import re

	data_seed = os.path.join(frappe.get_app_path("hrms"), "data_seed")
	company_meta = frappe.get_meta("Company")

	def _csv(filename: str) -> list[dict]:
		path = os.path.join(data_seed, filename)
		if not os.path.exists(path):
			frappe.log_error(title="S181 populate: missing CSV", message=path)
			return []
		with open(path, encoding="utf-8-sig") as f:
			return list(csv.DictReader(f))

	def _norm(s: str) -> str:
		"""Alias for the module-level _norm_name."""
		return _norm_name(s)

	def _set(docname: str, field: str, value):
		"""Set a Company field if it exists on the DocType and differs from current.
		Wraps set_value in try/except so one bad value (e.g. a malformed date)
		does not crash the entire populate batch."""
		if not company_meta.has_field(field):
			return False
		current = frappe.db.get_value("Company", docname, field)
		if current == value:
			return False
		try:
			frappe.db.set_value("Company", docname, field, value, update_modified=False)
			return True
		except Exception as e:
			frappe.log_error(
				title=f"S181 populate: set {field} on {docname}",
				message=f"value={value!r}, error={e}",
			)
			return False

	def _parse_date(raw: str) -> str | None:
		"""Normalize any date string to YYYY-MM-DD or return None.
		Handles: 2025-09-28, 2025-09-28 00:00:00, 14-May-2025, 09/28/2025, etc."""
		if not raw:
			return None
		raw = raw.strip().split(" ")[0]  # strip time portion
		from datetime import datetime
		for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
			try:
				return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
			except ValueError:
				continue
		return None

	def _fuzzy_get(index: dict[str, dict], key: str) -> dict | None:
		"""Look up a normalized key in an index. Tries in order:
		1. Exact normalized match
		2. key starts-with an index key (or vice versa), minimum 6 chars overlap
		This handles 'Ayala Evo' (Mosaic) vs 'Ayala Evo City' (S037)."""
		if not key:
			return None
		nk = _norm(key)
		if not nk:
			return None
		if nk in index:
			return index[nk]
		best = None
		best_len = 0
		for idx_key, idx_val in index.items():
			if len(idx_key) < 6 or len(nk) < 6:
				continue
			if nk.startswith(idx_key) or idx_key.startswith(nk):
				overlap = min(len(nk), len(idx_key))
				if overlap > best_len:
					best = idx_val
					best_len = overlap
		return best

	# Explicit name bridge: maps S037 store_name to the exact name used in
	# Mosaic, Locations, and dim_store CSVs for cases where algorithmic
	# matching (normalization + starts-with) fails due to totally different
	# naming conventions (abbreviations, reordering, missing words).
	# Built by manual cross-reference on 2026-04-12.
	_BRIDGE: dict[str, str] = {
		# S037 store_name -> canonical name used in Mosaic/Locations/dim_store
		"Ayala Fairview Terraces": "Ayala Malls Fairview Terraces",
		"Ayala UP Town Center": "Ayala UPTC",
		"Food Express (Gateway Mall)": "Araneta Gateway",
		"Lucky China Town": "Lucky Chinatown",
		"Ortigas Estancia": "Ortigas Land Estancia",
		"Ortigas Greenhills": "Ortigas Greenhills",  # no Mosaic entry exists
		"NAIA T3 (Departure)": "NAIA T3",
		"PITX Terminal": "Megawide PITX",
		"Paseo Center": "Megaworld Paseo Center",
		"SM San Jose Del Monte": "SM SJDM",
		"SM Center Pulilan": "SM Pulilan",
		"Tomas Morato (CTTM Square)": "CTTM Tomas Morato",
		"Venice Grand Canal": "Megaworld Venice Grand Canal",
		"Uptown Mall": "Up Town Mall BGC",
		"Robinsons Place Gen. Trias": "Robinson General Trias",
		"Robinsons Place Imus": "Robinson Imus",
		"Robinsons Galleria South": "ROBINSONS GALLERIA SOUTH",  # S199: typo fixed + ALL CAPS
		"Robinsons Place Antipolo": "Robinsons Antipolo",
		"Robinsons Place Dasmarinas": "Robinsons Place Dasmarinas",  # may not be in Mosaic
		"The Terminal Exchange": "The Terminal",
		"SM North EDSA": "SM North EDSA",
		"SM Sta. Rosa": "SM Sta. Rosa",
		"The Grid - Rockwell": "The Grid - Rockwell",
		"Ever Commonwealth": "Ever Commonwealth",
		"D'Verde Calamba": "D'Verde Calamba",
	}

	# Also bridge for dim_store where names differ further
	_BRIDGE_DIMSTORE: dict[str, str] = {
		"Ever Commonwealth": "Ever Gotesco Commonwealth",
		"Paseo Center": "Megaworld Paseo de Roxas",
		"PITX Terminal": "PITX",
		"D'Verde Calamba": "Dverde Calamba",
		"SM Mall of Asia": "SM Mall of Asia",
		"Uptown Mall": "Uptown Mall BGC",
		"The Terminal Exchange": "The Terminal Alabang",
		"Sta. Lucia East Grand Mall": "Sta. Lucia Grand Mall",
		"The Grid - Rockwell": "The Grid Rockwell",
		"Ayala UP Town Center": "UP Town Center",
		"Lucky China Town": "Lucky Chinatown",
		"Food Express (Gateway Mall)": "Araneta Gateway",
		"Robinsons Place Gen. Trias": "Robinsons General Trias",
		"Robinsons Place Imus": "Robinsons Imus",
		"NAIA T3 (Departure)": "NAIA T3",
		"SM North EDSA": "SM North Edsa",
		"Tomas Morato (CTTM Square)": "CTTM Tomas Morato",
		"Robinsons Galleria South": "Robinsons Galleria South",
		"Venice Grand Canal": "Venice Grand Canal",
	}

	def _bridged_lookup(index: dict[str, dict], store_name: str, bridge: dict[str, str] | None = None) -> dict | None:
		"""Try: exact _norm match → bridge mapping → _fuzzy_get fallback."""
		if not store_name:
			return None
		# Direct
		result = _fuzzy_get(index, store_name)
		if result:
			return result
		# Bridge
		if bridge:
			bridged = bridge.get(store_name)
			if bridged:
				result = _fuzzy_get(index, bridged)
				if result:
					return result
		# Also try the global _BRIDGE
		bridged = _BRIDGE.get(store_name)
		if bridged and bridged != store_name:
			result = _fuzzy_get(index, bridged)
			if result:
				return result
		return None

	# Load all reference CSVs
	s037_rows = _csv("store_buyer_entity_register_2026-03-12.csv")
	mosaic_rows = _csv("MOSAIC_POS_API_KEYS.csv")
	locations_rows = _csv("Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv")
	tin_rows = _csv("ENTITY_TIN_RDO_2026-02-27.csv")
	adms_rows = _csv("BIOMETRIC_MACHINE_MAPPING_ALL_2026-01-14.csv")
	dimstore_rows = _csv("dim_store.csv")

	# Build lookup indices
	all_company_names = set(frappe.get_all("Company", pluck="name"))
	lower_idx: dict[str, str] = {n.lower().rstrip(".").strip(): n for n in all_company_names}

	# S037 by warehouse_docname + by normalized buyer_entity_name
	s037_by_docname: dict[str, dict] = {}
	s037_by_norm: dict[str, dict] = {}
	for row in s037_rows:
		docname = (row.get("warehouse_docname") or "").strip()
		if docname:
			s037_by_docname[docname] = row
		buyer = (row.get("buyer_entity_name") or "").strip()
		if buyer:
			s037_by_norm[_norm(buyer)] = row

	# Mosaic by normalized store name
	mosaic_by_norm: dict[str, dict] = {}
	for row in mosaic_rows:
		n = (row.get("Store Name") or "").strip()
		if n:
			mosaic_by_norm[_norm(n)] = row

	# Locations by normalized store name
	loc_by_norm: dict[str, dict] = {}
	for row in locations_rows:
		n = (row.get("store_name") or "").strip()
		if n:
			loc_by_norm[_norm(n)] = row

	# TIN/RDO by normalized entity name
	tin_by_norm: dict[str, dict] = {}
	for row in tin_rows:
		n = (row.get("Entity Name") or "").strip()
		if n:
			tin_by_norm[_norm(n)] = row

	# dim_store by normalized store name (for opening_date, region)
	dimstore_by_norm: dict[str, dict] = {}
	for row in dimstore_rows:
		n = (row.get("store_name") or "").strip()
		if n:
			dimstore_by_norm[_norm(n)] = row

	# ADMS devices by normalized location name
	adms_by_norm: dict[str, dict] = {}
	for row in adms_rows:
		n = (row.get("canonical_location_name") or "").strip()
		if n:
			adms_by_norm[_norm(n)] = row

	# Non-store entity category map
	non_store_categories: dict[str, str] = {
		# S199: ALL CAPS Company names
		"BEBANG ENTERPRISE INC.": "Head Office",
		"BEBANG KITCHEN INC.": "Commissary",
		"BEBANG FRANCHISE CORP.": "Franchisor",
		"IRRESISTIBLE INFUSIONS INC.": "Holding Company",
	}

	# Companies not in S037 that are Stores — Sam confirmed 2026-04-13.
	# These get entity_category=Store + TIN/RDO directly.
	_STORE_OVERRIDES: dict[str, dict] = {
		# S199: ALL CAPS store-first Company names as keys
		"THE GRID ROCKWELL - TASTECARTEL CORP.": {"store": "The Grid - Rockwell", "tin": "672-270-879-00000", "rdo": "049"},
		"SM SAN JOSE DEL MONTE - JL TRADE OPC": {"store": "SM San Jose Del Monte", "tin": "775-842-763-00003", "rdo": "045"},
		"EVER COMMONWEALTH - DLS DESSERT CRAFT INC.": {"store": "Ever Gotesco Commonwealth", "tin": "671-219-097-00001", "rdo": "028"},
		"AYALA MALLS FAIRVIEW TERRACES - BEBANG FT INC.": {"store": "Ayala Fairview Terraces"},
		"SM CALOOCAN - TAJ FOOD CORP.": {"store": "SM Caloocan"},
		"SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC": {"store": "SM Sangandaan"},
		"ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC": {"store": "Robinsons Galleria South"},
		"SM STA. ROSA - SWEET HARMONY FOOD CORP.": {"store": "SM Sta. Rosa"},
	}

	# ------------ Phase 3: entity_category + mosaic + GPS + city + status + pos -----------
	p3_updated = 0
	p3_per_field: dict[str, int] = {}
	for company_name in all_company_names:
		# Resolve S037 row for this Company
		s037 = None
		for r in s037_rows:
			buyer = (r.get("buyer_entity_name") or "").strip()
			if buyer and _norm(buyer) == _norm(company_name):
				s037 = r
				break
			if buyer:
				key = buyer.lower().rstrip(".").strip()
				if key in lower_idx and lower_idx[key] == company_name:
					s037 = r
					break

		# Resolve store name for Mosaic + Locations lookup
		store_name_for_lookup = None
		if s037:
			store_name_for_lookup = (s037.get("store_name") or "").strip()
		elif company_name in _STORE_OVERRIDES:
			store_name_for_lookup = _STORE_OVERRIDES[company_name].get("store")

		mosaic = _bridged_lookup(mosaic_by_norm, store_name_for_lookup or "")
		if not mosaic:
			prefix = company_name.split(" - ")[0] if " - " in company_name else company_name
			mosaic = _bridged_lookup(mosaic_by_norm, prefix)

		loc = _bridged_lookup(loc_by_norm, store_name_for_lookup or "")
		if not loc:
			prefix = company_name.split(" - ")[0] if " - " in company_name else company_name
			loc = _bridged_lookup(loc_by_norm, prefix)

		dimstore = _bridged_lookup(dimstore_by_norm, store_name_for_lookup or "", _BRIDGE_DIMSTORE)
		if not dimstore:
			prefix = company_name.split(" - ")[0] if " - " in company_name else company_name
			dimstore = _bridged_lookup(dimstore_by_norm, prefix, _BRIDGE_DIMSTORE)

		changed = False
		# entity_category + store_ownership_type
		if s037:
			if _set(company_name, "entity_category", "Store"):
				p3_per_field["entity_category"] = p3_per_field.get("entity_category", 0) + 1
				changed = True
			st = (s037.get("store_type") or "").strip()
			ownership = st if st in ("JV", "Managed Franchise", "Full Franchise", "Company Owned") else "Company Owned"
			if _set(company_name, "store_ownership_type", ownership):
				p3_per_field["store_ownership_type"] = p3_per_field.get("store_ownership_type", 0) + 1
				changed = True
			active = (s037.get("active_status") or s037.get("active_fulfillment_status") or "").strip().lower()
			status = "Active" if active == "active" else "Temporarily Closed"
			if _set(company_name, "operational_status", status):
				p3_per_field["operational_status"] = p3_per_field.get("operational_status", 0) + 1
				changed = True
		elif company_name in non_store_categories:
			if _set(company_name, "entity_category", non_store_categories[company_name]):
				p3_per_field["entity_category"] = p3_per_field.get("entity_category", 0) + 1
				changed = True
			if _set(company_name, "operational_status", "Active"):
				p3_per_field["operational_status"] = p3_per_field.get("operational_status", 0) + 1
				changed = True
		elif company_name in _STORE_OVERRIDES:
			# Companies not in S037 but confirmed as Stores by Sam
			override = _STORE_OVERRIDES[company_name]
			if _set(company_name, "entity_category", "Store"):
				p3_per_field["entity_category"] = p3_per_field.get("entity_category", 0) + 1
				changed = True
			if _set(company_name, "operational_status", "Active"):
				p3_per_field["operational_status"] = p3_per_field.get("operational_status", 0) + 1
				changed = True
			if _set(company_name, "store_ownership_type", "Company Owned"):
				p3_per_field["store_ownership_type"] = p3_per_field.get("store_ownership_type", 0) + 1
				changed = True
			if override.get("tin"):
				if _set(company_name, "branch_tin", override["tin"]):
					p3_per_field["branch_tin"] = p3_per_field.get("branch_tin", 0) + 1
					changed = True
			if override.get("rdo"):
				if _set(company_name, "bir_rdo_code", override["rdo"]):
					p3_per_field["bir_rdo_code"] = p3_per_field.get("bir_rdo_code", 0) + 1
					changed = True

		# mosaic_location_id + pos_system
		if mosaic:
			loc_id = (mosaic.get("Mosaic Location ID") or "").strip()
			if loc_id and _set(company_name, "mosaic_location_id", loc_id):
				p3_per_field["mosaic_location_id"] = p3_per_field.get("mosaic_location_id", 0) + 1
				changed = True
			if loc_id and _set(company_name, "pos_system", "Mosaic"):
				p3_per_field["pos_system"] = p3_per_field.get("pos_system", 0) + 1
				changed = True

		# GPS (prefer locations CSV, fall back to Mosaic)
		lat = lng = None
		if loc:
			try:
				lat = float(loc["latitude"]) if loc.get("latitude") else None
				lng = float(loc["longitude"]) if loc.get("longitude") else None
			except (ValueError, TypeError):
				pass
		if (lat is None or lng is None) and mosaic:
			try:
				if mosaic.get("Latitude"):
					lat = float(mosaic["Latitude"])
				if mosaic.get("Longitude"):
					lng = float(mosaic["Longitude"])
			except (ValueError, TypeError):
				pass
		if lat is not None and _set(company_name, "gps_latitude", lat):
			p3_per_field["gps_latitude"] = p3_per_field.get("gps_latitude", 0) + 1
			changed = True
		if lng is not None and _set(company_name, "gps_longitude", lng):
			p3_per_field["gps_longitude"] = p3_per_field.get("gps_longitude", 0) + 1
			changed = True

		# City (prefer locations, fall back to Mosaic)
		city = None
		if loc and loc.get("city"):
			city = loc["city"].strip()
		elif mosaic and mosaic.get("City"):
			city = mosaic["City"].strip()
		if city and _set(company_name, "city", city):
			p3_per_field["city"] = p3_per_field.get("city", 0) + 1
			changed = True

		# full_address
		addr = None
		if loc and loc.get("address"):
			addr = loc["address"].strip()
		elif mosaic and mosaic.get("Address"):
			addr = mosaic["Address"].strip()
		if addr and _set(company_name, "full_address", addr):
			p3_per_field["full_address"] = p3_per_field.get("full_address", 0) + 1
			changed = True

		# opening_date + region from dim_store
		if dimstore:
			od = _parse_date((dimstore.get("opening_date") or "").strip())
			if od:
				if _set(company_name, "opening_date", od):
					p3_per_field["opening_date"] = p3_per_field.get("opening_date", 0) + 1
					changed = True
			reg = (dimstore.get("region") or "").strip()
			if reg:
				# Map dim_store region codes to S181 Select options
				reg_map = {"NCR": "NCR", "4-A": "Luzon", "3": "Luzon", "CALABARZON": "Luzon"}
				mapped = reg_map.get(reg, "Luzon")
				if _set(company_name, "region", mapped):
					p3_per_field["region"] = p3_per_field.get("region", 0) + 1
					changed = True

		if changed:
			p3_updated += 1

	# ------------ Phase 4: branch_tin + bir_rdo_code -----------
	p4_updated = 0
	p4_per_field: dict[str, int] = {}
	for company_name in all_company_names:
		current_tax_id = (frappe.db.get_value("Company", company_name, "tax_id") or "").strip() or None
		# Resolve entity via S037 buyer_entity_name or direct match
		entity = None
		# Path 1: S037-bridged lookup
		for r in s037_rows:
			wh = (r.get("warehouse_docname") or "").strip()
			buyer = (r.get("buyer_entity_name") or "").strip()
			if wh == company_name or (buyer and _norm(buyer) == _norm(company_name)):
				entity = tin_by_norm.get(_norm(buyer))
				if entity:
					break
		# Path 2: direct match
		if not entity:
			for candidate in [company_name, company_name.rsplit(" - ", 1)[-1] if " - " in company_name else company_name]:
				entity = tin_by_norm.get(_norm(candidate))
				if entity:
					break
		if not entity:
			continue

		changed = False
		resolved_tin = (entity.get("TIN") or "").strip() or None
		resolved_rdo = (entity.get("RDO Code") or "").strip() or None
		if resolved_tin and resolved_tin != current_tax_id:
			if _set(company_name, "branch_tin", resolved_tin):
				p4_per_field["branch_tin"] = p4_per_field.get("branch_tin", 0) + 1
				changed = True
		if resolved_rdo:
			if _set(company_name, "bir_rdo_code", resolved_rdo):
				p4_per_field["bir_rdo_code"] = p4_per_field.get("bir_rdo_code", 0) + 1
				changed = True
		if changed:
			p4_updated += 1

	# ------------ ADMS device seeding -----------
	# Uses DEVICE_TO_STORE from hrms/utils/device_mapping.py — the AUTHORITATIVE
	# source of truth for all 48 ZKTeco MB10-VL devices across all BEI locations.
	# This is inside the hrms Python package, so it ships in the Docker image.
	# The old CSV-based lookup only matched ~9 devices; this covers all 48.
	adms_seeded = 0
	if company_meta.has_field("adms_devices"):
		from hrms.utils.device_mapping import DEVICE_TO_STORE

		# Build reverse index: normalized ADMS location → [(serial, location_name)]
		adms_by_location: dict[str, list[tuple[str, str]]] = {}
		for serial_key, loc_name in DEVICE_TO_STORE.items():
			key = _norm(loc_name)
			if key not in adms_by_location:
				adms_by_location[key] = []
			adms_by_location[key].append((serial_key, loc_name))

		# Bridge: ADMS canonical location name → S037 store_name
		# Built by manual cross-reference of DEVICE_TO_STORE keys vs S037 store names
		_ADMS_TO_S037: dict[str, str] = {
			"ARANETA GATEWAY": "Food Express (Gateway Mall)",
			"AYALA EVO": "Ayala Evo City",
			"AYALA FAIRVIEW": "Ayala Fairview Terraces",
			"AYALA SOLENAD": "Ayala Solenad 2",
			"AYALA UP TOWN CENTER": "Ayala UP Town Center",
			"AYALA VERMOSA": "Ayala Vermosa",
			"BF HOMES": "BF Homes Paranaque (Aguirre Ave.)",
			"BGC CAPITAL HOUSE": "_HEAD_OFFICE_",
			"BRITTANY OFFICE": "_HEAD_OFFICE_",
			"CTTM TOMAS MORATO": "Tomas Morato (CTTM Square)",
			"D VERDE CALAMBA": "D'Verde Calamba",
			"FESTIVAL MALL": "Festival Mall Alabang",
			"GREENHILLS": "Ortigas Greenhills",
			"LCT": "Lucky China Town",
			"MARKET MARKET": "Ayala Market! Market!",
			"MYTOWN": "Ever Commonwealth",
			"NAIA T3": "NAIA T3 (Departure)",
			"PASEO": "Paseo Center",
			"PITX": "PITX Terminal",
			"ROBINSON ANTIPOLO": "Robinsons Place Antipolo",
			"ROBINSON GENERAL TRIAS": "Robinsons Place Gen. Trias",
			"ROBINSONS GALLERIA SOUTH": "Robinsons Galleria South",
			"ROBINSONS IMUS": "Robinsons Place Imus",
			"SHAW COMMISSARY": "_COMMISSARY_",
			"SM BICUTAN": "SM Bicutan",
			"SM CALOOCAN": "SM Caloocan",
			"SM CLARK": "SM Clark",
			"SM EAST ORTIGAS": "SM East Ortigas",
			"SM GRAND CENTRAL": "SM Grand Central",
			"SM MANILA": "SM Manila",
			"SM MARIKINA": "SM Marikina",
			"SM MARILAO": "SM Marilao",
			"SM MEGAMALL": "SM Megamall",
			"SM MOA": "SM Mall of Asia",
			"SM NORTH EDSA": "SM North EDSA",
			"SM PULILAN": "SM Center Pulilan",
			"SM SANGANDAAN": "SM Sangandaan",
			"SM SJDM": "SM San Jose Del Monte",
			"SM SOUTHMALL": "SM Southmall",
			"SM STA. ROSA": "SM Sta. Rosa",
			"SM TANZA": "SM Tanza",
			"SM TAYTAY": "SM Taytay",
			"SM VALENZUELA": "SM Valenzuela",
			"STA LUCIA GRAND MALL": "Sta. Lucia East Grand Mall",
			"THE TERMINAL": "The Terminal Exchange",
			"UPTOWN BGC": "Uptown Mall",
			"VENICE GRAND CANAL": "Venice Grand Canal",
			"VISTA MALL TAGUIG": "Vista Mall Taguig",
		}

		# Reverse bridge: S037 store_name → ADMS location name
		_S037_TO_ADMS: dict[str, str] = {v: k for k, v in _ADMS_TO_S037.items() if not v.startswith("_")}

		# For head office / commissary, map Company docname directly
		_COMPANY_TO_ADMS: dict[str, list[str]] = {
			"Bebang Enterprise Inc.": ["BRITTANY OFFICE", "BGC CAPITAL HOUSE"],
			"Bebang Kitchen Inc.": ["SHAW COMMISSARY"],
		}

		for company_name in all_company_names:
			# Strategy 1: explicit Company → ADMS location(s) map (head office, commissary)
			adms_locations = _COMPANY_TO_ADMS.get(company_name)
			if adms_locations:
				for adms_loc in adms_locations:
					devs = adms_by_location.get(_norm(adms_loc), [])
					for serial_val, loc_label in devs:
						existing = frappe.db.get_value(
							"BEI Company ADMS Device",
							{"parent": company_name, "device_serial": serial_val},
							"name",
						)
						if existing:
							continue
						try:
							doc = frappe.get_doc("Company", company_name)
							doc.append("adms_devices", {
								"device_serial": serial_val,
								"device_name": loc_label,
							})
							doc.flags.ignore_permissions = True
							doc.flags.ignore_mandatory = True
							doc.save()
							adms_seeded += 1
						except Exception as e:
							frappe.log_error(title=f"S181 ADMS seed: {company_name}", message=str(e))
				continue

			# Strategy 2: S037 store_name → reverse bridge → ADMS location
			prefix = company_name.split(" - ")[0] if " - " in company_name else company_name
			matched_adms_loc = None

			# Try via S037 bridge: Company → S037 buyer_entity_name → S037 store_name → _S037_TO_ADMS
			for r in s037_rows:
				buyer = (r.get("buyer_entity_name") or "").strip()
				if buyer and (_norm(buyer) == _norm(company_name) or buyer == company_name):
					sn_s037 = (r.get("store_name") or "").strip()
					adms_loc = _S037_TO_ADMS.get(sn_s037)
					if adms_loc:
						matched_adms_loc = adms_loc
						break

			# Strategy 3: fuzzy match company prefix → ADMS location
			if not matched_adms_loc:
				nk = _norm(prefix)
				for loc_key in adms_by_location:
					if len(loc_key) >= 4 and len(nk) >= 4:
						if nk.startswith(loc_key) or loc_key.startswith(nk):
							# Reverse-lookup the original name
							for serial_val, loc_label in adms_by_location[loc_key]:
								matched_adms_loc = loc_label
								break
							break

			if not matched_adms_loc:
				continue

			devs = adms_by_location.get(_norm(matched_adms_loc), [])
			for serial_val, loc_label in devs:
				existing = frappe.db.get_value(
					"BEI Company ADMS Device",
					{"parent": company_name, "device_serial": serial_val},
					"name",
				)
				if existing:
					continue
				try:
					doc = frappe.get_doc("Company", company_name)
					doc.append("adms_devices", {
						"device_serial": serial_val,
						"device_name": loc_label,
					})
					doc.flags.ignore_permissions = True
					doc.flags.ignore_mandatory = True
					doc.save()
					adms_seeded += 1
				except Exception as e:
					frappe.log_error(title=f"S181 ADMS seed: {company_name}", message=str(e))

	# ------------ Store supervisor from Employee master -----------
	supervisors_set = 0
	if company_meta.has_field("store_manager"):
		# Query live Employee data for Store Supervisors / Area Supervisors
		sup_employees = frappe.get_all(
			"Employee",
			filters={"designation": ["in", ["Store Supervisor", "STORE SUPERVISOR"]], "status": "Active"},
			fields=["name", "employee_name", "company"],
		)
		for emp in sup_employees:
			if emp.company and emp.company in all_company_names:
				current = frappe.db.get_value("Company", emp.company, "store_manager")
				if not current:
					frappe.db.set_value("Company", emp.company, "store_manager", emp.name, update_modified=False)
					supervisors_set += 1

		area_sups = frappe.get_all(
			"Employee",
			filters={"designation": ["in", ["Area Supervisor", "AREA SUPERVISOR"]], "status": "Active"},
			fields=["name", "employee_name", "company"],
		)
		for emp in area_sups:
			if emp.company and emp.company in all_company_names:
				current = frappe.db.get_value("Company", emp.company, "area_supervisor")
				if not current:
					frappe.db.set_value("Company", emp.company, "area_supervisor", emp.name, update_modified=False)

	# ------------ Pre-existing sentinel fix -----------
	pre_count = 0
	if company_meta.has_field("first_provision_done"):
		for cname in all_company_names:
			if _company_has_coa(cname) and not frappe.db.get_value(
				"Company", cname, "first_provision_done"
			):
				frappe.db.set_value(
					"Company", cname, "first_provision_done", 1, update_modified=False
				)
				pre_count += 1

	# ------------ S184: Bank Account seeding -----------
	bank_accounts_seeded = 0
	bank_accounts_skipped = 0
	bank_accounts_unmatched = 0
	bank_csv_path = os.path.join(data_seed, "bank_accounts_2026-04-10.csv")
	if os.path.exists(bank_csv_path):
		bank_rows = _csv("bank_accounts_2026-04-10.csv")

		# Step 0: ensure Bank master records exist (Frappe Bank Account requires a
		# Bank Link field pointing to the Bank DocType — without these records,
		# every Bank Account insert fails with "Could not find Bank: X").
		_BANK_NAMES = {
			"BDO": "BDO Unibank",
			"BPI": "Bank of the Philippine Islands",
			"UB": "Union Bank of the Philippines",
			"PNB": "Philippine National Bank",
			"AUB": "Asia United Bank",
		}
		for csv_code, full_name in _BANK_NAMES.items():
			# Try the full name first, then the CSV abbreviation
			if not frappe.db.exists("Bank", full_name):
				if not frappe.db.exists("Bank", csv_code):
					try:
						bank_doc = frappe.get_doc({"doctype": "Bank", "bank_name": full_name})
						bank_doc.flags.ignore_permissions = True
						bank_doc.insert()
					except Exception as e:
						frappe.log_error(title=f"S184 Bank master create: {full_name}", message=str(e))

		# Build bank-name resolution map: CSV code → Frappe Bank docname
		_bank_resolve: dict[str, str] = {}
		for csv_code, full_name in _BANK_NAMES.items():
			if frappe.db.exists("Bank", full_name):
				_bank_resolve[csv_code] = full_name
			elif frappe.db.exists("Bank", csv_code):
				_bank_resolve[csv_code] = csv_code

		for brow in bank_rows:
			acct_name = (brow.get("account_name") or "").strip()
			gl_desc = (brow.get("gl_description") or "").strip()
			acct_number = (brow.get("account_number") or "").strip()
			bank_code = (brow.get("bank") or "").strip()
			branch = (brow.get("branch_of_account") or "").strip()

			if not acct_name or not gl_desc:
				continue

			# Resolve Bank docname from CSV abbreviation
			resolved_bank = _bank_resolve.get(bank_code)
			if not resolved_bank:
				continue

			# Resolve Company from account_name using _norm matching
			matched_company = None
			norm_acct = _norm(acct_name)
			for cname in all_company_names:
				if _norm(cname) == norm_acct:
					matched_company = cname
					break
			# Fallback: account_name contains a parenthetical store hint
			# e.g. "BEBANG MEGA INC (SM TANZA)" -> try matching "BEBANG MEGA INC"
			if not matched_company and "(" in acct_name:
				base = acct_name.split("(")[0].strip()
				norm_base = _norm(base)
				for cname in all_company_names:
					if _norm(cname) == norm_base:
						matched_company = cname
						break

			if not matched_company:
				# Try direct lower-case index
				key = acct_name.lower().rstrip(".").strip()
				matched_company = lower_idx.get(key)

			if not matched_company:
				bank_accounts_unmatched += 1
				continue

			# Build unique account label: "GL_DESC - COMPANY"
			ba_name = f"{gl_desc} - {matched_company}"

			# Check if Bank Account already exists
			existing = frappe.db.exists("Bank Account", {"account_name": ba_name})
			if existing:
				bank_accounts_skipped += 1
				continue

			try:
				ba = frappe.get_doc({
					"doctype": "Bank Account",
					"account_name": ba_name,
					"bank": resolved_bank,
					"company": matched_company,
					"bank_account_no": acct_number or "",
					"is_company_account": 1,
				})
				ba.flags.ignore_permissions = True
				ba.flags.ignore_mandatory = True
				ba.insert()
				bank_accounts_seeded += 1
			except Exception as e:
				frappe.log_error(
					title=f"S184 bank account seed: {ba_name}",
					message=str(e),
				)

	# ------------ S184: GPS sync from Superadmin API -----------
	gps_synced = 0
	gps_failed = 0
	superadmin_stores = _s184_fetch_superadmin_stores()
	if superadmin_stores:
		# Build index: normalized store_name -> store data
		sa_by_norm: dict[str, dict] = {}
		for st in superadmin_stores:
			sn = (st.get("store_name") or "").strip()
			if sn:
				sa_by_norm[_norm(sn)] = st

		# Direct Frappe Company → Superadmin API store name for cases where
		# S037 buyer_entity_name doesn't match the Company docname.
		# Sam confirmed these mappings 2026-04-13.
		_COMPANY_TO_SA_STORE: dict[str, str] = {
			# S199: ALL CAPS store-first Company names as keys
			"THE GRID ROCKWELL - TASTECARTEL CORP.": "The Grid - Rockwell",
			"SM SAN JOSE DEL MONTE - JL TRADE OPC": "SM SJDM",
			"EVER COMMONWEALTH - DLS DESSERT CRAFT INC.": "Ever Commonwealth",
			"BF HOMES - BEBANG BF HOMES INC.": "BF Homes",
			"AYALA MALLS FAIRVIEW TERRACES - BEBANG FT INC.": "Ayala Malls Fairview Terraces",
			"SM CALOOCAN - TAJ FOOD CORP.": "SM Caloocan",
			"SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC": "SM Sangandaan",
			"ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC": "Robinsons Galleria South",
			"SM STA. ROSA - SWEET HARMONY FOOD CORP.": "SM Sta. Rosa",
			"AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.": "Ayala Solenad",
			"AYALA MARKET MARKET - BEBANG MARKET MARKET INC.": "Ayala Market Market",
			"SM PULILAN - BEBANG SMM INC.": "SM Manila",
			"SM MALL OF ASIA - BEBANG SMOA INC.": "SM Mall Of Asia",
			"BEIFRANCHISE FOOD OPC": "Ortigas Land Greenhills",
			"TAJ FOOD CORP.": "D'Verde Calamba",
			"Bebang Kitchen Inc.": "Shaw BLVD",
			# S199: per-store child companies (ALL CAPS)
			"SM MEGAMALL - BEBANG ENTERPRISE INC.": "SM Megamall",
			"SM MANILA - BEBANG ENTERPRISE INC.": "SM Manila",
			"SM SOUTHMALL - BEBANG ENTERPRISE INC.": "SM Southmall",
			"ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.": "Robinsons Antipolo",
			"AYALA EVO CITY - BEBANG MEGA INC.": "Ayala Evo",
			"AYALA VERMOSA - BEBANG MEGA INC.": "Ayala Vermosa",
			"ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.": "Robinson General Trias",
			"ROBINSONS IMUS - BEBANG MEGA INC.": "Robinson Imus",
			"SM TANZA - BEBANG MEGA INC.": "SM Tanza",
			"STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.": "Sta. Lucia East Grand Mall",
			"D'VERDE CALAMBA - TAJ FOOD CORP.": "D'Verde Calamba",
			"ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC": "Araneta Gateway",
		}

		for company_name in all_company_names:
			# Skip if already has GPS
			current_lat = frappe.db.get_value("Company", company_name, "gps_latitude")
			if current_lat:
				continue

			# Strategy 1: direct Company → SA store map
			sa = None
			direct_sa_name = _COMPANY_TO_SA_STORE.get(company_name)
			if direct_sa_name:
				sa = _bridged_lookup(sa_by_norm, direct_sa_name)

			# Strategy 2: S037 buyer → store_name → bridge → SA
			if not sa:
				store_name_for_lookup = None
				for r in s037_rows:
					buyer = (r.get("buyer_entity_name") or "").strip()
					if buyer and (_norm(buyer) == _norm(company_name)):
						store_name_for_lookup = (r.get("store_name") or "").strip()
						break
					if buyer:
						key = buyer.lower().rstrip(".").strip()
						if key in lower_idx and lower_idx[key] == company_name:
							store_name_for_lookup = (r.get("store_name") or "").strip()
							break

				if store_name_for_lookup:
					sa = _bridged_lookup(sa_by_norm, store_name_for_lookup)

			if not sa:
				gps_failed += 1
				continue

			try:
				sa_lat = float(sa.get("latitude", 0))
				sa_lng = float(sa.get("longitude", 0))
			except (ValueError, TypeError):
				gps_failed += 1
				continue

			if sa_lat and sa_lng:
				_set(company_name, "gps_latitude", sa_lat)
				_set(company_name, "gps_longitude", sa_lng)
				sa_addr = (sa.get("address") or "").strip()
				if sa_addr:
					_set(company_name, "full_address", sa_addr)
				sa_city = (sa.get("city") or "").strip()
				if sa_city:
					_set(company_name, "city", sa_city)
				gps_synced += 1

	frappe.db.commit()

	return {
		"ok": True,
		"phase3": {
			"updated": p3_updated,
			"per_field": p3_per_field,
		},
		"phase4": {
			"updated": p4_updated,
			"per_field": p4_per_field,
		},
		"adms_devices_seeded": adms_seeded,
		"supervisors_set": supervisors_set,
		"pre_provisioned_sentinels_set": pre_count,
		"bank_accounts_seeded": bank_accounts_seeded,
		"bank_accounts_skipped": bank_accounts_skipped,
		"bank_accounts_unmatched": bank_accounts_unmatched,
		"gps_synced": gps_synced,
		"gps_failed": gps_failed,
	}


# ============================================================================
# S184 helpers
# ============================================================================


def _s184_fetch_superadmin_stores() -> list[dict]:
	"""Fetch store list from Superadmin API. Returns [] on failure."""
	import os
	import requests

	# Try multiple sources for the API key:
	# 1. Frappe site_config.json
	# 2. Environment variable (set by Docker/Doppler)
	# 3. Doppler CLI fallback (local dev only)
	api_key = (
		frappe.conf.get("superadmin_stores_api_key")
		or os.environ.get("SUPERADMIN_STORES_API_KEY")
		or os.environ.get("SUPERADMIN_API_KEY")
		or ""
	)
	if not api_key:
		import subprocess
		import sys

		try:
			result = subprocess.run(
				["doppler", "secrets", "get", "SUPERADMIN_STORES_API_KEY",
				 "--plain", "--project", "bei-erp", "--config", "dev"],
				capture_output=True, text=True, timeout=10,
				creationflags=0x08000000 if sys.platform == "win32" else 0,
			)
			if result.returncode == 0 and result.stdout.strip():
				api_key = result.stdout.strip()
		except (FileNotFoundError, subprocess.TimeoutExpired):
			pass

	if not api_key:
		frappe.log_error(
			title="S184 GPS sync: no API key",
			message="Checked: frappe.conf.superadmin_stores_api_key, "
			"env SUPERADMIN_STORES_API_KEY, env SUPERADMIN_API_KEY, doppler CLI. "
			"None available. Add the key to site_config.json: "
			'bench set-config superadmin_stores_api_key "bebang_..."',
		)
		return []

	try:
		resp = requests.get(
			"https://superadmin.bebang.ph/api/stores",
			headers={"x-api-key": api_key},
			timeout=30,
		)
		resp.raise_for_status()
		data = resp.json()
		return data if isinstance(data, list) else data.get("data", [])
	except Exception as e:
		frappe.log_error(title="S184 GPS sync: API call failed", message=str(e))
		return []


# ============================================================================
# S184 Phase 3: Connected data endpoints
# ============================================================================


@frappe.whitelist()
def get_headcount(company: str) -> dict:
	"""Return live employee headcount for a Company, grouped by designation.

	S184 Task 3.1 — always queries live tabEmployee data.
	"""
	set_backend_observability_context(
		module="company",
		action="get_headcount",
		mutation_type="read",
	)

	frappe.has_permission("Company", "read", doc=company, throw=True)

	rows = frappe.db.sql(
		"""
		SELECT designation, COUNT(*) as cnt
		FROM tabEmployee
		WHERE company = %s AND status = 'Active'
		GROUP BY designation
		ORDER BY cnt DESC
		""",
		(company,),
		as_dict=True,
	)

	by_designation = {r["designation"]: r["cnt"] for r in rows if r.get("designation")}
	total_active = sum(r["cnt"] for r in rows)

	# Recent hires (last 90 days)
	recent = frappe.get_all(
		"Employee",
		filters={
			"company": company,
			"status": "Active",
			"date_of_joining": [">=", add_days(today(), -90)],
		},
		fields=["employee_name", "designation", "date_of_joining"],
		order_by="date_of_joining DESC",
		limit=5,
	)

	return {
		"total_active": total_active,
		"by_designation": by_designation,
		"recent_hires": [
			{
				"name": r.employee_name,
				"designation": r.designation,
				"date_of_joining": str(r.date_of_joining),
			}
			for r in recent
		],
	}


@frappe.whitelist()
def get_bank_accounts(company: str) -> list[dict]:
	"""Return all Bank Account records linked to a Company.

	S184 Task 3.2.
	"""
	set_backend_observability_context(
		module="company",
		action="get_bank_accounts",
		mutation_type="read",
	)

	frappe.has_permission("Company", "read", doc=company, throw=True)

	accounts = frappe.get_all(
		"Bank Account",
		filters={"company": company},
		fields=[
			"name", "bank", "account_name", "bank_account_no",
			"is_company_account", "branch_code",
		],
		order_by="bank ASC, account_name ASC",
	)

	return [
		{
			"name": a.name,
			"bank": a.bank,
			"account_name": a.account_name,
			"bank_account_no": a.bank_account_no or "",
			"is_company_account": a.is_company_account,
			"branch_code": a.get("branch_code") or "",
		}
		for a in accounts
	]


@frappe.whitelist()
def get_bki_billing(company: str) -> dict:
	"""Return BKI billing summary for a Company.

	S184 Task 3.3 — follows the S037 register → Customer → Sales Invoice chain.
	"""
	set_backend_observability_context(
		module="company",
		action="get_bki_billing",
		mutation_type="read",
	)

	frappe.has_permission("Company", "read", doc=company, throw=True)

	import csv
	import os

	data_seed = os.path.join(frappe.get_app_path("hrms"), "data_seed")
	s037_path = os.path.join(data_seed, "store_buyer_entity_register_2026-03-12.csv")

	buyer_entity_name = None
	warehouse_docname = None
	if os.path.exists(s037_path):
		with open(s037_path, encoding="utf-8-sig") as f:
			for row in csv.DictReader(f):
				buyer = (row.get("buyer_entity_name") or "").strip()
				if buyer and _norm_name(buyer) == _norm_name(company):
					buyer_entity_name = buyer
					warehouse_docname = (row.get("warehouse_docname") or "").strip()
					break

	if not buyer_entity_name:
		return {
			"buyer_entity_name": None,
			"billing_status": "Not linked",
			"outstanding_count": 0,
			"outstanding_total": 0,
			"last_delivery_date": None,
		}

	# Check if Customer exists
	customer_exists = frappe.db.exists("Customer", buyer_entity_name)
	if not customer_exists:
		return {
			"buyer_entity_name": buyer_entity_name,
			"billing_status": "Customer not created",
			"outstanding_count": 0,
			"outstanding_total": 0,
			"last_delivery_date": None,
		}

	# Outstanding invoices
	outstanding = frappe.db.sql(
		"""
		SELECT COUNT(*) as cnt, COALESCE(SUM(outstanding_amount), 0) as total
		FROM `tabSales Invoice`
		WHERE customer = %s AND outstanding_amount > 0 AND docstatus = 1
		""",
		(buyer_entity_name,),
		as_dict=True,
	)

	# Last delivery date (most recent submitted Sales Invoice)
	last_inv = frappe.db.sql(
		"""
		SELECT posting_date
		FROM `tabSales Invoice`
		WHERE customer = %s AND docstatus = 1
		ORDER BY posting_date DESC
		LIMIT 1
		""",
		(buyer_entity_name,),
		as_dict=True,
	)

	out = outstanding[0] if outstanding else {"cnt": 0, "total": 0}

	return {
		"buyer_entity_name": buyer_entity_name,
		"billing_status": "Active" if customer_exists else "Not linked",
		"outstanding_count": out["cnt"],
		"outstanding_total": float(out["total"]),
		"last_delivery_date": str(last_inv[0]["posting_date"]) if last_inv else None,
	}


@frappe.whitelist()
def get_warehouse_stock(company: str) -> dict:
	"""Return warehouse stock summary for a Company.

	S184 Task 3.4 — follows Company → Warehouse → tabBin chain.
	"""
	set_backend_observability_context(
		module="company",
		action="get_warehouse_stock",
		mutation_type="read",
	)

	frappe.has_permission("Company", "read", doc=company, throw=True)

	# Find the Company's primary warehouse
	abbr = frappe.db.get_value("Company", company, "abbr") or ""
	wh_name = f"{company} - {abbr}" if abbr else company

	# Check if warehouse exists
	wh_exists = frappe.db.exists("Warehouse", wh_name)
	if not wh_exists:
		# Try S037 warehouse_docname match
		import csv
		import os

		data_seed = os.path.join(frappe.get_app_path("hrms"), "data_seed")
		s037_path = os.path.join(data_seed, "store_buyer_entity_register_2026-03-12.csv")
		if os.path.exists(s037_path):
			with open(s037_path, encoding="utf-8-sig") as f:
				for row in csv.DictReader(f):
					buyer = (row.get("buyer_entity_name") or "").strip()
					if buyer and _norm_name(buyer) == _norm_name(company):
						wh_name = (row.get("warehouse_docname") or "").strip()
						wh_exists = frappe.db.exists("Warehouse", wh_name) if wh_name else False
						break

	if not wh_exists:
		return {
			"warehouse_name": None,
			"item_count": 0,
			"stock_value": 0,
			"is_open": False,
		}

	# Query tabBin for stock data
	stock = frappe.db.sql(
		"""
		SELECT COUNT(*) as item_count, COALESCE(SUM(stock_value), 0) as stock_value
		FROM tabBin
		WHERE warehouse = %s AND actual_qty > 0
		""",
		(wh_name,),
		as_dict=True,
	)

	st = stock[0] if stock else {"item_count": 0, "stock_value": 0}

	return {
		"warehouse_name": wh_name,
		"item_count": st["item_count"],
		"stock_value": float(st["stock_value"]),
		"is_open": True,
	}


# ====================================================================
# S196: canonical helpers for orderable-store-universe lookups
# ====================================================================


def get_orderable_companies(include_commissary: bool = True) -> list[str]:
	"""Return list of Company docnames that are orderable (stores + optionally commissary).

	S196 helper — single source of truth for "what Companies appear on the Delivery
	Schedule grid and the ordering surfaces".

	Filter semantics (Audit v3 CR-7 ALLOWLIST):
	  - `entity_category in ("Store", "Commissary")` (or only "Store" if include_commissary=False)
	  - `operational_status in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")`
	    — NULL `operational_status` is EXCLUDED (no pass-through) to prevent misconfigured
	    new Companies from leaking onto the grid.

	Defensive checks:
	  - If `entity_category` Custom Field is missing from Company DocType (pre-S181),
	    return [] and log via frappe.log_error.
	  - Runs a drift assertion (W-5): every key in `_NON_STORE_ENTITIES` must have
	    entity_category != Store/Commissary. Raises on drift so mis-classified
	    Holding/Head-Office/Franchisor Companies don't leak through.

	Does NOT use `_load_s037_rows()` — Company DocType is the SSOT, not the S037 CSV.
	"""
	meta = frappe.get_meta("Company")
	if not meta.has_field("entity_category"):
		frappe.log_error(
			title="S196: Company.entity_category field missing",
			message="get_orderable_companies called but entity_category Custom Field not on Company DocType. Check S181 fixtures.",
		)
		return []

	target_categories = ["Store", "Commissary"] if include_commissary else ["Store"]
	# CR-7 allowlist (NOT `not in ("Permanently Closed",)` — NULL must be excluded)
	allowed_statuses = ["Active", "Pre-Opening", "Temporarily Closed", "Pipeline"]

	# W-5 drift assertion — keys in _NON_STORE_ENTITIES must NOT be in orderable result
	# (module-level constant defined earlier in this file at ~line 503)
	_drift_check_non_store_entities()

	return frappe.get_all(
		"Company",
		filters={
			"entity_category": ["in", target_categories],
			"operational_status": ["in", allowed_statuses],
		},
		pluck="name",
		order_by="name",
	)


def _drift_check_non_store_entities():
	"""S196 W-5 — assert every key in _NON_STORE_ENTITIES has entity_category != Store/Commissary.

	Catches drift where someone adds a Store-category Company to _NON_STORE_ENTITIES
	(or forgets to update it when creating a new Holding/Head Office). Logs + raises.
	"""
	for co_name in _NON_STORE_ENTITIES.keys():
		if not frappe.db.exists("Company", co_name):
			continue
		ec = frappe.db.get_value("Company", co_name, "entity_category")
		# Commissary IS allowed in non-store entities (BKI orders raw materials
		# from warehouse but should NOT appear on the store grid/delivery schedule)
		if ec == "Store":
			msg = (
				f"S196 drift: Company {co_name!r} is in _NON_STORE_ENTITIES "
				f"(expected non-store) but has entity_category={ec!r}. "
				"Update the map OR the Company's entity_category."
			)
			frappe.log_error(title="S196 _NON_STORE_ENTITIES drift", message=msg)
			raise frappe.ValidationError(msg)


def get_orderable_store_warehouses(include_commissary: bool = True) -> list[dict]:
	"""Return one orderable Warehouse per orderable Company.

	S196 primary helper consumed by `get_weekly_schedule` and other SCM surfaces.

	Algorithm:
	  1. orderable = get_orderable_companies(include_commissary)
	  2. G1 short-circuit: if not orderable, return [] (MariaDB `IN ()` is invalid)
	  3. Query Warehouse filtered by company in orderable, is_group=0, disabled=0
	  4. Apply `_is_orderable_store()` (lazy-imported from hrms.api.store)
	  5. Group surviving warehouses by Company
	  6. G3 deterministic tie-break for >1 orderable wh per Company:
	     sorted(key=(route_map_membership, name)) — locale-independent
	  7. Return one row per Company with canonical warehouse.

	Shape per row:
	  {"company": str, "warehouse": str, "warehouse_meta": {...raw fields...}}
	"""
	orderable = get_orderable_companies(include_commissary=include_commissary)
	if not orderable:
		return []

	# Lazy import to avoid circular dep (hrms.api.store imports from this module)
	from hrms.api.store import (
		_is_orderable_store,
		_CENTRAL_WAREHOUSE_ROUTE_MAP,
		_normalize_store_name_for_route,
	)

	whs = frappe.get_all(
		"Warehouse",
		filters={
			"company": ["in", orderable],
			"is_group": 0,
			"disabled": 0,
		},
		fields=[
			"name",
			"company",
			"warehouse_name",
			"warehouse_type",
			"parent_warehouse",
		],
	)

	# Apply orderable-store filter
	filtered = [w for w in whs if _is_orderable_store(w)]

	# Group by Company
	by_company: dict[str, list[dict]] = {}
	for w in filtered:
		by_company.setdefault(w["company"], []).append(w)

	# Deterministic tie-break (G3): prefer route-map membership, then locale-pinned str sort
	def sort_key(w):
		normalized = _normalize_store_name_for_route(w["name"])
		route_map_hit = 0 if normalized in _CENTRAL_WAREHOUSE_ROUTE_MAP else 1
		return (route_map_hit, w["name"])

	result = []
	for company, group in by_company.items():
		if len(group) > 1:
			# Log warning — multi-wh should be rare after S196 Phase 2 cleanup
			chosen = sorted(group, key=sort_key)[0]
			others = [w["name"] for w in group if w["name"] != chosen["name"]]
			frappe.log_error(
				title="S196: multi-warehouse Company",
				message=(
					f"Company {company!r} has {len(group)} orderable warehouses. "
					f"Chose {chosen['name']!r}; runners-up: {others}"
				),
			)
		else:
			chosen = group[0]
		result.append({
			"company": company,
			"warehouse": chosen["name"],
			"warehouse_meta": chosen,
		})

	return result

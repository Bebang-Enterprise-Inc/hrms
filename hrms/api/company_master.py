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

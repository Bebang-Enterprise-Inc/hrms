# Copyright (c) 2026, Bebang Enterprise Inc.
# License: MIT
"""S233: canonical Create-New-Store helper.

Creates the 4 canonical records for a new BEI store atomically:
  1. Per-store Company (entity_category="Store", parent linked)
  2. Warehouse (docname == company name; company == per-store Company)
  3. Billing Customer (customer_name == company name; is_internal_customer=0)
  4. Internal Customer (name = "<store_label> (Internal)"; represents_company == per-store Company; is_internal_customer=1)

Plus appends one row to the S037 register CSV (atomic file write
post-savepoint per v2 A3).

v2 A1: this file lives in hrms/api/ (NOT scripts/canonical/) so it
imports cleanly from Frappe's HTTP request handler. HOTFIX4 at
company_master.py:939 documents the `from scripts/...` trap.

Wraps:
- v2 A2: release_savepoint inside try, no manual commit (Frappe HTTP cycle commits)
- v2 A3: CSV write AFTER savepoint released (no DB↔file split-brain)
- v2 A4: Customer inserts set customer_type/customer_group/territory (mandatory ERPNext fields)
- v3 A18: abbr regex enforced in _validate_preconditions (savepoint name SQL safety)
- v3 A16: imports STORE_ENTITY_MAPPING_RELPATH from hrms.utils.bei_config (no circular import)
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import tempfile
from typing import Optional

import frappe
from frappe import _

# v3 A18: abbr regex — uppercase letters and digits only, 3-6 chars.
# Prevents savepoint-name SQL injection (hyphenated abbr like "SM-T" would
# produce invalid SAVEPOINT identifier per MariaDB syntax) AND aligns with
# the UI label "Abbreviation (3-6 chars)".
ABBR_PATTERN = re.compile(r"^[A-Z0-9]{3,6}$")

# Canonical operational status values per Company custom field options
ALLOWED_OPERATIONAL_STATUSES = {"Pre-Opening"}  # only Pre-Opening on create — operator transitions later

# Canonical store_ownership_type values per BEI design
ALLOWED_OWNERSHIP_TYPES = {"JV", "Managed Franchise", "Full Franchise", "Company Owned"}

# Per-store-Company entity_category — always "Store" for net-new stores
STORE_ENTITY_CATEGORY = "Store"


def _validate_preconditions(
	store_label: str,
	parent_company: str,
	abbr: str,
	store_ownership_type: str,
	operational_status: str,
) -> str:
	"""Validate all preconditions BEFORE any DB write.

	Returns the canonical company_name on success.
	Raises frappe.ValidationError with a specific message on any failure.
	"""
	# v3 A18 — cheapest check first
	if not isinstance(abbr, str) or not ABBR_PATTERN.match(abbr):
		frappe.throw(_("Abbreviation must be 3-6 uppercase letters or digits (got: {0})").format(abbr or ""))

	if not store_label or not store_label.strip():
		frappe.throw(_("Store Label is required"))
	if " - " in store_label:
		frappe.throw(_("Store Label cannot contain ' - ' (it conflicts with the canonical naming convention)"))

	if store_ownership_type not in ALLOWED_OWNERSHIP_TYPES:
		frappe.throw(_("Ownership Type must be one of: {0}").format(", ".join(sorted(ALLOWED_OWNERSHIP_TYPES))))
	if operational_status not in ALLOWED_OPERATIONAL_STATUSES:
		frappe.throw(_("Operational Status must be 'Pre-Opening' on create (got: {0})").format(operational_status))

	# Parent company existence + canonical-parent shape
	parent = frappe.db.get_value(
		"Company", parent_company,
		["is_group", "entity_category", "tax_id"], as_dict=True,
	)
	if not parent:
		frappe.throw(_("Parent Company {0!r} does not exist").format(parent_company))
	if not parent.get("is_group"):
		frappe.throw(_("Parent Company {0!r} must be a group company (is_group=1) to host child stores").format(parent_company))
	allowed_parent_categories = {"Head Office", "Holding Company", "Franchisor", "Commissary"}
	if parent.get("entity_category") not in allowed_parent_categories:
		frappe.throw(_(
			"Parent Company {0!r} entity_category is {1!r}; must be one of: {2}"
		).format(parent_company, parent.get("entity_category") or "(unset)", ", ".join(sorted(allowed_parent_categories))))

	# Abbr uniqueness
	if frappe.db.exists("Company", {"abbr": abbr}):
		frappe.throw(_("Abbreviation {0!r} is already used by another Company").format(abbr))

	# Canonical company_name uniqueness (must not already exist)
	company_name = f"{store_label} - {parent_company}"
	if frappe.db.exists("Company", company_name):
		frappe.throw(_("Company {0!r} already exists").format(company_name))

	return company_name


def _append_s037_row(
	store_label: str,
	parent_company: str,
	store_ownership_type: str,
	company_name: str,
) -> None:
	"""Append one row to the S037 register CSV. Atomic via tempfile + os.replace.

	v3 A16: imports STORE_ENTITY_MAPPING_RELPATH from hrms.utils.bei_config
	(NOT from hrms.api.company_master — circular import trap).
	"""
	from hrms.utils.bei_config import STORE_ENTITY_MAPPING_RELPATH
	s037_path = os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *STORE_ENTITY_MAPPING_RELPATH))
	with open(s037_path, encoding="utf-8-sig", newline="") as f:
		rows = list(csv.reader(f))
	rows.append([
		store_label,
		parent_company,
		store_ownership_type,
		company_name,
		"BKI_TO_STORE_INTERCOMPANY",
		"active",
	])
	fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(s037_path), text=True)
	os.close(fd)
	with open(tmp_path, "w", encoding="utf-8", newline="") as f:
		csv.writer(f).writerows(rows)
	os.replace(tmp_path, s037_path)


def create_new_store(
	store_label: str,
	parent_company: str,
	abbr: str,
	store_ownership_type: str,
	tax_id: Optional[str] = None,
	operational_status: str = "Pre-Opening",
	region: Optional[str] = None,
	province: Optional[str] = None,
	city: Optional[str] = None,
) -> dict:
	"""Create the 4 canonical records for a new BEI store atomically.

	Returns:
		{
			"company": "<store_label> - <parent_company>",
			"warehouse": "<store_label> - <parent_company>",
			"billing_customer": "<store_label> - <parent_company>",
			"internal_customer": "<store_label> (Internal)",
			"s037_row_added": True | False,
			"first_provision_done": 0,
		}

	Raises:
		frappe.ValidationError: any precondition failure
		Any DB exception after savepoint entry: triggers rollback of all 4
		records; the caller observes a clean failure (zero orphans).
	"""
	company_name = _validate_preconditions(
		store_label=store_label,
		parent_company=parent_company,
		abbr=abbr,
		store_ownership_type=store_ownership_type,
		operational_status=operational_status,
	)

	parent_tax_id = frappe.db.get_value("Company", parent_company, "tax_id")
	resolved_tax_id = tax_id or parent_tax_id  # may still be None for standalone OPCs

	sp = "create_new_store_" + abbr.lower()  # safe per v3 A18 regex (alnum only)
	frappe.db.savepoint(sp)
	s037_row_added = False
	try:
		# 1. Per-store Company — defect handling for ERPNext CoA importer + auto_provision
		#    bypass via flags (v2 A1 + S231 known traps)
		frappe.local.flags.ignore_chart_of_accounts = True
		frappe.flags.in_install = True  # skip auto_provision_company on first save
		try:
			co = frappe.new_doc("Company")
			co.company_name = company_name
			co.abbr = abbr
			co.country = "Philippines"
			co.default_currency = "PHP"
			co.tax_id = resolved_tax_id
			co.parent_company = parent_company
			co.entity_category = STORE_ENTITY_CATEGORY
			co.store_ownership_type = store_ownership_type
			co.operational_status = operational_status
			co.is_group = 0
			if region:
				co.region = region
			if province:
				co.province = province
			if city:
				co.city = city
			co.flags.ignore_permissions = True
			co.insert()
		finally:
			frappe.local.flags.ignore_chart_of_accounts = False
			frappe.flags.in_install = False

		# 2. Warehouse — docname = company_name, warehouse_name = store_label
		wh = frappe.new_doc("Warehouse")
		wh.warehouse_name = store_label
		wh.company = company_name  # links to per-store Company (NOT parent)
		wh.is_group = 0
		wh.disabled = 0
		wh.flags.ignore_permissions = True
		wh.insert()
		# Frappe may auto-rename to add suffix; force the canonical docname.
		# v3 hotfix #720 + #721: must call frappe.model.rename_doc.rename_doc directly
		# because the top-level frappe.rename_doc wrapper has a strict typing
		# decorator that doesn't accept `ignore_permissions` (raises TypeError at
		# runtime). The internal rename_doc accepts both `force` (bypass cancelled-doc
		# check) and `ignore_permissions` (bypass source-doc write-perm in
		# validate_rename — required because wh.flags.ignore_permissions=True set
		# before insert does NOT propagate to the rename validation, which loads a
		# fresh doc from DB).
		from frappe.model.rename_doc import rename_doc as _rename_doc_internal
		if wh.name != company_name:
			_rename_doc_internal("Warehouse", wh.name, company_name, force=True, ignore_permissions=True)

		# 3. Billing Customer (v2 A4: mandatory ERPNext fields)
		bc = frappe.new_doc("Customer")
		bc.customer_name = company_name
		bc.customer_type = "Company"
		bc.customer_group = "BKI Store"      # canonical pattern from company.py:574
		bc.territory = "All Territories"      # v3 hotfix #722: matches existing canonical Customers; "Philippines" doesn't exist in production tabTerritory
		bc.tax_id = resolved_tax_id
		bc.is_internal_customer = 0
		bc.flags.ignore_permissions = True
		bc.insert()
		if bc.name != company_name:
			_rename_doc_internal("Customer", bc.name, company_name, force=True, ignore_permissions=True)

		# 4. Internal Customer (S206 labor cost-sharing; v2 A4: same mandatory fields)
		ic = frappe.new_doc("Customer")
		ic.customer_name = f"{store_label} (Internal)"
		ic.customer_type = "Company"
		ic.customer_group = "BKI Store"
		ic.territory = "All Territories"  # v3 hotfix #722: matches existing canonical Internal Customers
		ic.represents_company = company_name
		ic.is_internal_customer = 1
		ic.tax_id = None  # internal — no TIN
		ic.flags.ignore_permissions = True
		ic.insert()

		# v2 A2: release savepoint INSIDE try, BEFORE returning. Do NOT call
		# frappe.db.commit() here — Frappe's HTTP request handler commits on
		# successful return. Calling commit() here would end the transaction
		# before release_savepoint and make the except-block rollback ineffective.
		frappe.db.release_savepoint(sp)
	except Exception:
		# v2 A2: rollback is reachable because we did NOT manually commit
		frappe.db.rollback(save_point=sp)
		raise

	# v2 A3: CSV write happens AFTER savepoint released. Filesystem I/O is
	# non-transactional — keeping it inside the savepoint creates a DB↔file
	# split-brain on commit failure. DB-atomic + CSV-best-effort:
	# if CSV write fails here, surface the exception (DB is already
	# consistent; operator runs scripts/canonical/repair_s037_for_company.py).
	try:
		_append_s037_row(
			store_label=store_label,
			parent_company=parent_company,
			store_ownership_type=store_ownership_type,
			company_name=company_name,
		)
		s037_row_added = True
	except Exception as csv_exc:
		frappe.log_error(
			title="S233: Company created but S037 CSV append failed",
			message=(
				f"Company {company_name!r} created in DB but CSV append failed: {csv_exc}\n"
				f"Operator must run scripts/canonical/repair_s037_for_company.py "
				f"--company-name '{company_name}' to fix."
			),
		)
		raise

	return {
		"company": company_name,
		"warehouse": company_name,
		"billing_customer": company_name,
		"internal_customer": f"{store_label} (Internal)",
		"s037_row_added": s037_row_added,
		"first_provision_done": 0,  # operator clicks "Run First Provisioning" pill afterwards
	}


# CLI wrapper for SSM use (bench execute or direct standalone)
if __name__ == "__main__":  # pragma: no cover — CLI only
	p = argparse.ArgumentParser(description="S233 canonical create-new-store helper")
	p.add_argument("--store-label", required=True)
	p.add_argument("--parent-company", required=True)
	p.add_argument("--abbr", required=True)
	p.add_argument(
		"--store-ownership-type",
		required=True,
		choices=["JV", "Managed Franchise", "Full Franchise", "Company Owned"],
	)
	p.add_argument("--tax-id", default=None)
	p.add_argument("--operational-status", default="Pre-Opening")
	p.add_argument("--region", default=None)
	p.add_argument("--province", default=None)
	p.add_argument("--city", default=None)
	args = p.parse_args()
	# Frappe init expected (script run via bench execute or from container)
	out = create_new_store(
		store_label=args.store_label,
		parent_company=args.parent_company,
		abbr=args.abbr,
		store_ownership_type=args.store_ownership_type,
		tax_id=args.tax_id,
		operational_status=args.operational_status,
		region=args.region,
		province=args.province,
		city=args.city,
	)
	print(json.dumps(out, indent=2))
	sys.exit(0)

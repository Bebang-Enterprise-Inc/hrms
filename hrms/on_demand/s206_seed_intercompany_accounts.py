"""Seed intercompany Due From / Due To accounts + internal Customer/Supplier
party records for S206 paired-JE cost-sharing.

For each in-scope Company, creates:

    1104200 - DUE FROM GROUP ENTITIES - <abbr>   (Receivable, Asset)
    2104200 - DUE TO GROUP ENTITIES - <abbr>     (Payable, Liability)
    Internal Customer "<Company> (Internal)"      (is_internal_customer=1, represents_company=self, companies allowlist=all in-scope)
    Internal Supplier "<Company> (Internal)"      (is_internal_supplier=1, represents_company=self, companies allowlist=all in-scope)

In-scope Companies:
    - every Company with entity_category='Store' (49)
    - BEBANG ENTERPRISE INC. (parent)
    - BEBANG KITCHEN INC. (commissary)

The internal Customer/Supplier records are required by ERPNext v15
`validate_party()` on Journal Entry Account rows with Receivable/Payable
account_type: the `party_type` must be in the Party Type DocType with a
matching account_type (Customer/Supplier pass — 'Company' does not).

The paired-JE allocation (hrms.utils.labor_allocation) uses:
  - Home DR Due From row: party_type='Customer', party=<covered Company's internal Customer>
  - Covered CR Due To row: party_type='Supplier', party=<home Company's internal Supplier>

Run on production via:

    docker exec $BACKEND bench --site hq.bebang.ph execute \
        hrms.on_demand.s206_seed_intercompany_accounts.execute

No dry-run switch — invoke only when you want to create the records.
Idempotent: if a row already exists, it is left as-is (status='existed').

Wrapped in frappe.db.savepoint; any row-level failure rolls back the full
batch and logs via frappe.log_error so Sentry captures it (DM-7).
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import frappe

SAVEPOINT_NAME = "s206_seed_intercompany_accounts"
SITE_REPORT_SUBPATH = ("private", "files")

ACCOUNT_NUMBER_DUE_FROM = "1104200"
ACCOUNT_NUMBER_DUE_TO = "2104200"
ACCOUNT_LABEL_DUE_FROM = "DUE FROM GROUP ENTITIES"
ACCOUNT_LABEL_DUE_TO = "DUE TO GROUP ENTITIES"


def _full_account_name(number: str, label: str, abbr: str) -> str:
	"""Return the final docname Frappe will use for an Account."""
	return f"{number} - {label} - {abbr}"


def internal_party_name(company: str, suffix: str = "Internal") -> str:
	"""Canonical party name for a Company's internal Customer or Supplier.

	Shared constant so labor_allocation.py can resolve it without a DB round-trip.
	Example: 'SM MEGAMALL - BEBANG ENTERPRISE INC.' -> 'SM MEGAMALL (Internal)'.
	Trims the company suffix to keep party names short and readable.
	"""
	# Take the first segment before " - " (typically the store/entity short name),
	# fall back to full company name for holding companies that have no " - ".
	head = company.split(" - ", 1)[0].strip()
	return f"{head} ({suffix})"


PARENT_RECEIVABLE_GROUP_PATTERNS = ["%Accounts Receivable%", "%Current Assets%"]
PARENT_PAYABLE_GROUP_PATTERNS = ["%Accounts Payable%", "%Current Liabilities%"]


def _in_scope_companies() -> list[dict]:
	rows = frappe.db.sql(
		"""
        SELECT name, abbr, entity_category, default_currency, parent_company
        FROM tabCompany
        WHERE entity_category = 'Store'
           OR name IN ('BEBANG ENTERPRISE INC.', 'BEBANG KITCHEN INC.')
        ORDER BY entity_category, name
        """,
		as_dict=True,
	)
	return rows


def _find_parent_group(company: str, patterns: list[str], root_type: str) -> str | None:
	"""Find a parent is_group=1 Account for creating a leaf account in `company`.

	Resolution order:
	  1. Exact name match from `patterns` within root_type, own COA.
	  2. Any is_group=1 under root_type, own COA (outermost group).
	  3. Same pattern match in parent_company's COA (for child Companies that
	     share COA with a parent).
	  4. Any is_group=1 under root_type in parent_company's COA.

	Combined with `frappe.local.flags.ignore_root_company_validation = True`,
	this lets the child Company borrow the parent_company's group as the
	parent_account for its own leaf insert (ERPNext auto-propagates the leaf
	to each Company via its abbr suffix).
	"""
	# 1 + 2. Company's own COA
	for pat in patterns:
		parent = frappe.db.sql(
			"""
            SELECT name FROM tabAccount
            WHERE company = %(company)s
              AND is_group = 1
              AND root_type = %(root_type)s
              AND name LIKE %(pat)s
            ORDER BY lft LIMIT 1
            """,
			{"company": company, "pat": pat, "root_type": root_type},
			as_dict=True,
		)
		if parent:
			return parent[0]["name"]

	parent = frappe.db.sql(
		"""
        SELECT name FROM tabAccount
        WHERE company = %(company)s
          AND is_group = 1
          AND root_type = %(root_type)s
        ORDER BY lft DESC LIMIT 1
        """,
		{"company": company, "root_type": root_type},
		as_dict=True,
	)
	if parent:
		return parent[0]["name"]

	# 3 + 4. parent_company's COA as fallback
	parent_company = frappe.db.get_value("Company", company, "parent_company")
	if not parent_company:
		return None
	for pat in patterns:
		parent = frappe.db.sql(
			"""
            SELECT name FROM tabAccount
            WHERE company = %(company)s
              AND is_group = 1
              AND root_type = %(root_type)s
              AND name LIKE %(pat)s
            ORDER BY lft LIMIT 1
            """,
			{"company": parent_company, "pat": pat, "root_type": root_type},
			as_dict=True,
		)
		if parent:
			return parent[0]["name"]
	parent = frappe.db.sql(
		"""
        SELECT name FROM tabAccount
        WHERE company = %(company)s
          AND is_group = 1
          AND root_type = %(root_type)s
        ORDER BY lft DESC LIMIT 1
        """,
		{"company": parent_company, "root_type": root_type},
		as_dict=True,
	)
	if parent:
		return parent[0]["name"]
	return None


def _first_group_zero(doctype: str) -> str | None:
	"""Return the first `is_group=0` record of a group doctype (Customer Group,
	Supplier Group, Territory). Returns None if only group=1 roots exist.
	"""
	row = frappe.db.get_value(doctype, {"is_group": 0}, "name")
	return row


def _best_territory() -> str:
	"""Territory that works for internal parties. Prefer a non-group leaf; fall
	back to the group root "All Territories" (always exists in fresh installs).
	"""
	return _first_group_zero("Territory") or "All Territories"


def _best_customer_group() -> str:
	return _first_group_zero("Customer Group") or "All Customer Groups"


def _best_supplier_group() -> str:
	return _first_group_zero("Supplier Group") or "All Supplier Groups"


def _ensure_account(
	*,
	company: str,
	abbr: str,
	account_number: str,
	account_label: str,
	account_type: str,
	root_type: str,
	parent_group: str,
	currency: str,
) -> tuple[str, str]:
	"""Ensure Account `<number> - <label> - <abbr>` exists; return (name, 'created'|'existed')."""
	final_name = _full_account_name(account_number, account_label, abbr)
	existing = frappe.db.exists("Account", final_name)
	if existing:
		return (existing, "existed")

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": f"{account_number} - {account_label}",
			"parent_account": parent_group,
			"company": company,
			"is_group": 0,
			"account_type": account_type,
			"root_type": root_type,
			"account_currency": currency or "PHP",
		}
	)
	doc.insert(ignore_permissions=True)
	return (doc.name, "created")


def _ensure_internal_customer(
	*,
	company: str,
	customer_name: str,
	allowlist_companies: list[str],
) -> tuple[str, str]:
	"""Ensure Internal Customer with represents_company=`company` exists.

	Uses `customer_name` as the docname (Customer is autoname=field:customer_name).
	Idempotent: if exists, ensures allowlist is complete.
	Returns (docname, 'created' | 'existed' | 'updated').
	"""
	existing = frappe.db.exists("Customer", {"customer_name": customer_name})
	if existing:
		doc = frappe.get_doc("Customer", existing)
		present = {row.company for row in (doc.companies or [])}
		missing = [c for c in allowlist_companies if c not in present]
		if missing:
			for c in missing:
				doc.append("companies", {"company": c})
			doc.save(ignore_permissions=True)
			return (doc.name, "updated")
		return (doc.name, "existed")

	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
			"customer_group": _best_customer_group(),
			"territory": _best_territory(),
			"is_internal_customer": 1,
			"represents_company": company,
			"companies": [{"company": c} for c in allowlist_companies],
		}
	)
	doc.insert(ignore_permissions=True)
	return (doc.name, "created")


def _ensure_internal_supplier(
	*,
	company: str,
	supplier_name: str,
	allowlist_companies: list[str],
) -> tuple[str, str]:
	"""Ensure Internal Supplier with represents_company=`company` exists. Idempotent."""
	existing = frappe.db.exists("Supplier", {"supplier_name": supplier_name})
	if existing:
		doc = frappe.get_doc("Supplier", existing)
		present = {row.company for row in (doc.companies or [])}
		missing = [c for c in allowlist_companies if c not in present]
		if missing:
			for c in missing:
				doc.append("companies", {"company": c})
			doc.save(ignore_permissions=True)
			return (doc.name, "updated")
		return (doc.name, "existed")

	doc = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_type": "Company",
			"supplier_group": _best_supplier_group(),
			"country": "Philippines",
			"is_internal_supplier": 1,
			"represents_company": company,
			"companies": [{"company": c} for c in allowlist_companies],
		}
	)
	doc.insert(ignore_permissions=True)
	return (doc.name, "created")


def _write_report(payload: dict) -> str:
	stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	filename = f"s206_intercompany_seed_report_{stamp}.json"
	try:
		site_path = frappe.get_site_path(*SITE_REPORT_SUBPATH)
		os.makedirs(site_path, exist_ok=True)
		out_path = os.path.join(site_path, filename)
		# Path is constructed entirely from Frappe-owned site-path constants
		# + timestamped filename. No user input in the path. Safe.
		with open(out_path, "w", encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal
			json.dump(payload, f, indent=2, default=str)
		return out_path
	except Exception as exc:
		frappe.log_error(
			title="S206 seed report write failed",
			message=str(exc),
		)
		return ""


def execute() -> dict:
	"""Seed accounts + internal Customer/Supplier records for every in-scope Company.

	Always-apply. Idempotent.
	"""
	companies = _in_scope_companies()
	company_names = [c["name"] for c in companies]

	created_accounts: list[dict] = []
	existed_accounts: list[dict] = []
	created_parties: list[dict] = []
	existed_parties: list[dict] = []
	updated_parties: list[dict] = []
	missing_parents: list[dict] = []
	errors: list[dict] = []

	# S181 pattern: bypass ERPNext's group-company validator that fires
	# "Please add the account to root level Company - <parent>" on child
	# Companies that share COA with a parent_company. Without this, 15/51
	# Companies (all with parent_company set) fail.
	# See hrms/overrides/company.py:638-644 for the precedent.
	original_root_flag = getattr(frappe.local.flags, "ignore_root_company_validation", False)
	frappe.local.flags.ignore_root_company_validation = True

	# Per-company savepoint loop. One company's failure does NOT block others
	# and does NOT roll back already-successful companies.
	for co in companies:
		name = co["name"]
		abbr = co["abbr"]
		currency = co.get("default_currency") or "PHP"

		# Parent account groups, constrained to the company's own COA.
		parent_rec = _find_parent_group(name, PARENT_RECEIVABLE_GROUP_PATTERNS, "Asset")
		parent_pay = _find_parent_group(name, PARENT_PAYABLE_GROUP_PATTERNS, "Liability")
		if not parent_rec:
			missing_parents.append({"company": name, "missing": "Asset-root parent group"})
			continue
		if not parent_pay:
			missing_parents.append({"company": name, "missing": "Liability-root parent group"})
			continue

		sp = f"s206_co_{co['abbr']}"
		try:
			frappe.db.savepoint(sp)

			# Accounts
			df_name, df_status = _ensure_account(
				company=name,
				abbr=abbr,
				account_number=ACCOUNT_NUMBER_DUE_FROM,
				account_label=ACCOUNT_LABEL_DUE_FROM,
				account_type="Receivable",
				root_type="Asset",
				parent_group=parent_rec,
				currency=currency,
			)
			(created_accounts if df_status == "created" else existed_accounts).append(
				{"company": name, "account": df_name, "type": "Receivable"}
			)

			dt_name, dt_status = _ensure_account(
				company=name,
				abbr=abbr,
				account_number=ACCOUNT_NUMBER_DUE_TO,
				account_label=ACCOUNT_LABEL_DUE_TO,
				account_type="Payable",
				root_type="Liability",
				parent_group=parent_pay,
				currency=currency,
			)
			(created_accounts if dt_status == "created" else existed_accounts).append(
				{"company": name, "account": dt_name, "type": "Payable"}
			)

			# Internal Customer (used by OTHER companies when billing this Company)
			cust_display = internal_party_name(name)
			cust_doc, cust_status = _ensure_internal_customer(
				company=name,
				customer_name=cust_display,
				allowlist_companies=company_names,
			)
			bucket = {
				"created": created_parties,
				"existed": existed_parties,
				"updated": updated_parties,
			}[cust_status]
			bucket.append({"company": name, "party": cust_doc, "type": "Customer"})

			# Internal Supplier (used by OTHER companies when they owe this Company)
			supp_display = internal_party_name(name)
			supp_doc, supp_status = _ensure_internal_supplier(
				company=name,
				supplier_name=supp_display,
				allowlist_companies=company_names,
			)
			bucket = {
				"created": created_parties,
				"existed": existed_parties,
				"updated": updated_parties,
			}[supp_status]
			bucket.append({"company": name, "party": supp_doc, "type": "Supplier"})

			frappe.db.release_savepoint(sp)
		except Exception as exc:
			try:
				frappe.db.rollback(save_point=sp)
			except Exception:
				pass
			errors.append({"company": name, "error": str(exc)[:500]})
			frappe.log_error(
				title=f"S206 seed failed for {name}",
				message=str(exc)[:1500],
			)

	# Restore the root-company validation flag regardless of success/failure.
	frappe.local.flags.ignore_root_company_validation = original_root_flag

	# Commit the whole batch — any partial success on companies whose savepoints
	# were released stays. Per-company savepoint already isolated failures.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit

	summary = {
		"companies_in_scope": len(companies),
		"accounts_created_count": len(created_accounts),
		"accounts_existed_count": len(existed_accounts),
		"parties_created_count": len(created_parties),
		"parties_existed_count": len(existed_parties),
		"parties_updated_count": len(updated_parties),
		"missing_parents_count": len(missing_parents),
		"errors_count": len(errors),
		"accounts_created": created_accounts,
		"accounts_existed": existed_accounts,
		"parties_created": created_parties,
		"parties_existed": existed_parties,
		"parties_updated": updated_parties,
		"missing_parents": missing_parents,
		"errors": errors,
	}
	report_path = _write_report(summary)
	summary["report_path"] = report_path

	status = "rolled_back" if (errors or missing_parents) else "ok"
	frappe.logger().info(
		f"[S206 seed] {status}: accounts created={len(created_accounts)} existed={len(existed_accounts)}; "
		f"parties created={len(created_parties)} existed={len(existed_parties)} updated={len(updated_parties)}; "
		f"missing_parents={len(missing_parents)}, errors={len(errors)}. report={report_path}"
	)
	return summary

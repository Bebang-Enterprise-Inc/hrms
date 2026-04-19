"""Paired-JE cost-sharing generator (S206 Phase 2).

For each in-scope Salary Slip, compute shift-share across stores and generate
PAIRED Journal Entries via Frappe native `inter_company_journal_entry_reference`:

    Home Company JE:
        CR Salaries Expense - <home>   (reduces home's expense)
        DR Due From Group Entities - <home>   (home now has receivable from covered)
        party_type='Employee' on Salaries row (DM-1)
        party_type='Customer' on Due From row (DM-1); party=internal Customer
            that represents `covered` (ERPNext intercompany pattern)

    Covered Company JE:
        DR Salaries Expense - <covered>   (increases covered's expense)
        CR Due To Group Entities - <covered>   (covered now has payable to home)
        party_type='Employee' on Salaries row
        party_type='Supplier' on Due To row; party=internal Supplier that
            represents `home`

Both JEs:
    voucher_type = 'Inter Company Journal Entry'
    inter_company_journal_entry_reference = <peer JE name>
    user_remark = 'S206 cost-sharing recharge: <employee> to <covered>, ...'
    reference_type = 'Salary Slip', reference_name = slip.name
    cost_center = Company default

Why Customer/Supplier and not party_type='Company':
    ERPNext v15 `journal_entry.validate_party()` throws on Receivable/Payable
    rows unless party_type is a registered Party Type whose account_type
    matches. Standard install fixtures seed only Customer, Supplier, Employee,
    Shareholder. 'Company' is not registered — so the canonical intercompany
    pattern uses an internal Customer/Supplier with `represents_company=<peer>`
    (see hrms/on_demand/s206_seed_intercompany_accounts).

Cost-sharing arrangement per BIR RR 2-2013 Section 4(B) — zero-margin recharge,
NOT a service. No VAT, no EWT. See `docs/compliance/s206-transfer-pricing-policy.md`.
"""

from __future__ import annotations

from datetime import date

import frappe

from hrms.utils.non_store_billing import is_non_store_billing_doc
from hrms.utils.punch_allocation import compute_shift_share


def posting_date_for_slip(slip_end_date: date) -> date:
	"""CFO PNL-001: payroll hits the P&L of its payout month, not the work month.

	- Slip ending on/before 15th → payout on the 25th of the same month
	- Slip ending on 16th–last-day → payout on the 10th of the next month

	Used by :func:`_build_paired_jes` (S207 Phase 3) so every paired JE posts on
	the Bimonthly payout date rather than the slip's own end date. Cross-month
	example: a March 16-31 half-period slip pays April 10 → JE posting_date =
	2026-04-10 → expense hits April P&L.
	"""
	d = slip_end_date
	if d.day <= 15:
		return date(d.year, d.month, 25)
	if d.month == 12:
		return date(d.year + 1, 1, 10)
	return date(d.year, d.month + 1, 10)

# Skip reason constants
SKIP_NON_STORE_BILLING = "non_store_billing"
SKIP_COMMISSARY_PRODUCER = "commissary_producer"
SKIP_NO_PUNCHES = "no_punches"
SKIP_ALL_HOME = "all_home"
SKIP_ZERO_GROSS = "zero_gross"
SKIP_ALREADY_ALLOCATED = "already_allocated"

# Account naming conventions (S175 template + S206 Phase 4 seeder)
DUE_FROM_ACCOUNT_PREFIX = "1104200 - DUE FROM GROUP ENTITIES"
DUE_TO_ACCOUNT_PREFIX = "2104200 - DUE TO GROUP ENTITIES"

# Intercompany JE constant (Frappe built-in voucher type)
INTER_COMPANY_VOUCHER_TYPE = "Inter Company Journal Entry"


def allocate_slip(slip_name: str, dry_run: bool = True) -> dict:
	"""Compute and optionally post paired-JE allocation for one Salary Slip.

	Args:
	    slip_name: Frappe Salary Slip docname.
	    dry_run: If True (default), return planned JE pairs without DB writes.
	             If False, insert + submit paired JEs.

	Returns:
	    dict with keys:
	        slip: slip name
	        employee: employee docname
	        home_company: legal employer (slip.company)
	        status: 'planned' (dry_run) | 'applied' | 'skipped'
	        reason: skip reason if skipped, else None
	        pairs: list of paired-JE dicts (home_je, covered_je, covered_company, amount, share)
	               JE dicts contain either full doc dicts (dry_run) or names (applied)
	"""
	slip = frappe.get_doc("Salary Slip", slip_name)

	# Skip check
	reason = _skip_reason(slip)
	if reason:
		return {
			"slip": slip.name,
			"employee": slip.employee,
			"home_company": slip.company,
			"status": "skipped",
			"reason": reason,
			"pairs": [],
		}

	# Compute shift shares
	shares = compute_shift_share(
		slip.employee,
		slip.start_date,
		slip.end_date,
		department=slip.department,
	)
	if not shares:
		return {
			"slip": slip.name,
			"employee": slip.employee,
			"home_company": slip.company,
			"status": "skipped",
			"reason": SKIP_NO_PUNCHES,
			"pairs": [],
		}

	# All-home shortcut: no JE needed
	home = slip.company
	if shares.get(home, 0) >= 0.999 and len(shares) == 1:
		return {
			"slip": slip.name,
			"employee": slip.employee,
			"home_company": home,
			"status": "skipped",
			"reason": SKIP_ALL_HOME,
			"pairs": [],
		}

	# Build paired JEs per non-home covered Company
	pairs: list[dict] = []
	for covered, share in shares.items():
		if covered == home:
			continue  # home portion stays on home books implicitly
		if share <= 0:
			continue
		amount = round(float(slip.gross_pay or 0) * share, 2)
		if amount <= 0:
			continue
		home_je_dict, covered_je_dict = _build_paired_jes(
			slip=slip,
			share=share,
			home=home,
			covered=covered,
			amount=amount,
		)
		if not dry_run:
			home_name, covered_name = _insert_and_link(home_je_dict, covered_je_dict)
			pairs.append(
				{
					"home_je": home_name,
					"covered_je": covered_name,
					"covered_company": covered,
					"amount": amount,
					"share": round(share, 6),
				}
			)
		else:
			pairs.append(
				{
					"home_je": home_je_dict,
					"covered_je": covered_je_dict,
					"covered_company": covered,
					"amount": amount,
					"share": round(share, 6),
				}
			)

	if not pairs:
		return {
			"slip": slip.name,
			"employee": slip.employee,
			"home_company": home,
			"status": "skipped",
			"reason": SKIP_ZERO_GROSS if float(slip.gross_pay or 0) <= 0 else SKIP_ALL_HOME,
			"pairs": [],
		}

	return {
		"slip": slip.name,
		"employee": slip.employee,
		"home_company": home,
		"status": "planned" if dry_run else "applied",
		"reason": None,
		"pairs": pairs,
	}


def _skip_reason(slip) -> str | None:
	"""Return skip reason string or None if slip should be allocated.

	Order:
	  1. zero_gross — nothing to allocate
	  2. non_store_billing — roving/AS/HO/IT/Marketing/etc.
	  3. commissary_producer — SHAW COMMISSARY - PRODUCTION + Commissary dept (stays on BKI)
	"""
	if float(getattr(slip, "gross_pay", 0) or 0) <= 0:
		return SKIP_ZERO_GROSS

	try:
		emp = frappe.get_doc("Employee", slip.employee)
	except frappe.DoesNotExistError:
		return "employee_missing"

	if is_non_store_billing_doc(emp):
		return SKIP_NON_STORE_BILLING

	dept = (emp.department or "").strip().upper()
	branch = (emp.branch or "").strip().upper()
	if dept == "COMMISSARY" and "PRODUCTION" in branch:
		return SKIP_COMMISSARY_PRODUCER

	return None


def _build_paired_jes(*, slip, share: float, home: str, covered: str, amount: float) -> tuple[dict, dict]:
	"""Construct the two Journal Entry dicts for one home<->covered pair.

	Does NOT insert. Returns (home_je_dict, covered_je_dict).
	"""
	remark = (
		f"S206 cost-sharing recharge: {slip.employee} from {home} to {covered}, "
		f"period {slip.start_date}..{slip.end_date}, share={share:.2%}, "
		f"slip={slip.name}"
	)

	home_accounts = _resolve_company_accounts(home)
	covered_accounts = _resolve_company_accounts(covered)
	home_parties = _resolve_company_parties(home)
	covered_parties = _resolve_company_parties(covered)

	# Home JE
	home_je = {
		"doctype": "Journal Entry",
		"voucher_type": INTER_COMPANY_VOUCHER_TYPE,
		"company": home,
		"posting_date": slip.end_date,
		"user_remark": remark,
		"accounts": [
			{
				"account": home_accounts["salaries_expense"],
				"credit_in_account_currency": amount,
				"party_type": "Employee",
				"party": slip.employee,
				"cost_center": home_accounts["cost_center"],
				"reference_type": "Salary Slip",
				"reference_name": slip.name,
			},
			{
				"account": home_accounts["due_from"],
				"debit_in_account_currency": amount,
				"party_type": "Customer",
				"party": covered_parties["internal_customer"],
				"cost_center": home_accounts["cost_center"],
				"reference_type": "Salary Slip",
				"reference_name": slip.name,
			},
		],
	}

	# Covered JE (mirror)
	covered_je = {
		"doctype": "Journal Entry",
		"voucher_type": INTER_COMPANY_VOUCHER_TYPE,
		"company": covered,
		"posting_date": slip.end_date,
		"user_remark": remark,
		"accounts": [
			{
				"account": covered_accounts["salaries_expense"],
				"debit_in_account_currency": amount,
				"party_type": "Employee",
				"party": slip.employee,
				"cost_center": covered_accounts["cost_center"],
				"reference_type": "Salary Slip",
				"reference_name": slip.name,
			},
			{
				"account": covered_accounts["due_to"],
				"credit_in_account_currency": amount,
				"party_type": "Supplier",
				"party": home_parties["internal_supplier"],
				"cost_center": covered_accounts["cost_center"],
				"reference_type": "Salary Slip",
				"reference_name": slip.name,
			},
		],
	}

	return home_je, covered_je


def _resolve_company_parties(company: str) -> dict:
	"""Resolve the internal Customer + Supplier records that represent `company`.

	Used by other Companies when posting intercompany JEs:
	  - Home's DR Due From row references covered's internal Customer
	  - Covered's CR Due To row references home's internal Supplier

	Both records are seeded by `hrms.on_demand.s206_seed_intercompany_accounts`.
	Fails loud with an actionable error if either is missing.
	"""
	customer = frappe.db.get_value(
		"Customer",
		{"represents_company": company, "is_internal_customer": 1, "disabled": 0},
		"name",
	)
	supplier = frappe.db.get_value(
		"Supplier",
		{"represents_company": company, "is_internal_supplier": 1, "disabled": 0},
		"name",
	)
	if not customer or not supplier:
		frappe.throw(
			f"S206 allocate: Company {company!r} missing internal Customer/Supplier "
			f"(customer={customer!r}, supplier={supplier!r}). "
			f"Run `bench execute hrms.on_demand.s206_seed_intercompany_accounts.execute` first."
		)
	return {"internal_customer": customer, "internal_supplier": supplier}


def _insert_and_link(home_dict: dict, covered_dict: dict) -> tuple[str, str]:
	"""Insert both JE docs as drafts, cross-link via inter_company_journal_entry_reference, submit both.

	Wrapped in savepoint by caller (API). Raises on any failure.
	Returns (home_name, covered_name).
	"""
	home_doc = frappe.get_doc(home_dict)
	home_doc.insert(ignore_permissions=True)

	covered_doc = frappe.get_doc(covered_dict)
	covered_doc.insert(ignore_permissions=True)

	# Cross-link
	home_doc.db_set("inter_company_journal_entry_reference", covered_doc.name, update_modified=False)
	covered_doc.db_set("inter_company_journal_entry_reference", home_doc.name, update_modified=False)

	# Submit both
	home_doc.submit()
	covered_doc.submit()

	return home_doc.name, covered_doc.name


def _resolve_company_accounts(company: str) -> dict:
	"""Look up Salaries Expense, Due From, Due To accounts + default cost center for a Company.

	Returns dict with keys: salaries_expense, due_from, due_to, cost_center.
	Raises `frappe.ValidationError` if any required account is missing.
	"""
	# Salaries Expense — account naming varies wildly across BEI Companies:
	#   - Canonical BEI template: "Salaries and Wages - <abbr>"
	#   - BKI pattern:            "CREW/STAFF SALARIES-BASIC PAY - BKI" etc.
	#   - Minimal COA:            "Salary - <abbr>"
	#   - Legacy upper:           "SALARIES AND WAGES - <abbr>"
	# Match anything with "salar" or "wage" (case-insensitive), prefer canonical
	# names, exclude payable accounts (we want expense, not liability).
	salaries = frappe.db.sql(
		"""
        SELECT name FROM tabAccount
        WHERE company = %(company)s
          AND is_group = 0
          AND (LOWER(name) LIKE '%%salar%%' OR LOWER(name) LIKE '%%wage%%')
          AND LOWER(name) NOT LIKE '%%payable%%'
        ORDER BY
          CASE
            WHEN name LIKE '%%Salaries and Wages%%' THEN 1
            WHEN name LIKE '%%SALARIES AND WAGES%%' THEN 2
            WHEN name LIKE '%%Salaries Expense%%' THEN 3
            WHEN LOWER(name) LIKE '%%basic pay%%' THEN 4
            WHEN name LIKE 'Salary - %%' THEN 5
            ELSE 9 END,
          name
        LIMIT 1
        """,
		{"company": company},
		as_dict=True,
	)
	if not salaries:
		frappe.throw(
			f"S206 allocate: Company {company!r} has no Salaries Expense account. "
			f"Run hrms.on_demand.s206_seed_intercompany_accounts first, or check COA."
		)
	salaries_account = salaries[0]["name"]

	# Due From / Due To (seeded by Phase 4 on_demand script)
	due_from = frappe.db.get_value(
		"Account",
		{"company": company, "name": ["like", f"{DUE_FROM_ACCOUNT_PREFIX}%"], "is_group": 0},
		"name",
	)
	due_to = frappe.db.get_value(
		"Account",
		{"company": company, "name": ["like", f"{DUE_TO_ACCOUNT_PREFIX}%"], "is_group": 0},
		"name",
	)
	if not due_from or not due_to:
		frappe.throw(
			f"S206 allocate: Company {company!r} missing Due From/To intercompany accounts. "
			f"Run `bench execute hrms.on_demand.s206_seed_intercompany_accounts.execute` first."
		)

	# Cost center
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	if not cost_center:
		# Fallback to Main - <abbr>
		abbr = frappe.db.get_value("Company", company, "abbr")
		cost_center = frappe.db.get_value(
			"Cost Center",
			{"company": company, "cost_center_name": "Main"},
			"name",
		)
		if not cost_center:
			frappe.throw(f"S206 allocate: Company {company!r} has no default cost center (abbr={abbr!r}).")

	return {
		"salaries_expense": salaries_account,
		"due_from": due_from,
		"due_to": due_to,
		"cost_center": cost_center,
	}

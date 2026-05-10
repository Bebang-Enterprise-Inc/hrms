"""S238 — Generate store-side Draft Purchase Invoice when a BKI Sales Invoice submits.

Implements ICT-003: each BKI->store SI must have a paired PI on the receiving
store's books for BIR per-entity bookkeeping. NOT an atomic auto-mirror — the
PI is a SEPARATE document on a SEPARATE Company, awaiting Denise's team review.

v2: audit fixes B1 (savepoint API), B2 (set_warehouse), B3 (on_cancel),
B4 (account_number resolution), B7 (naming series guard), B8 (posting_time/lock),
B9 (tax mirror), B10 (cost_center mirror), B11 (no auto_submit), W (IC ref
dual-set, has_field guard, S192/S203 fields).

v2.1: CRIT-1 (bei_legal_entity = buyer_company, NOT seller's),
CRIT-2 (per-store cost_center via Warehouse.custom_cost_center, NOT mirror SI's),
W2 (try/except on cascade), W3 (Sentry breadcrumb on silent skip),
W7 (has_field guards on S192/S203 fields), W9 (drift-detection entry point).
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from hrms.utils.sentry import set_backend_observability_context

try:
	import sentry_sdk
except Exception:  # pragma: no cover
	sentry_sdk = None

BKI_COMPANY = "BEBANG KITCHEN INC."
BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"

# Account number prefixes seeded by scripts/s238/seed_pi_generator_accounts.py.
# v2-B4: exact match by account_number, not LIKE %name%.
ACCT_INVENTORY_FROM_COMMISSARY = "1104210"   # Asset, leaf under Stock Assets - <ABBR>
ACCT_INPUT_VAT_BKI_INTERCO = "1106210"       # Asset (Tax)
ACCT_AP_TRADE_BKI = "2103210"                # Liability (Payable)


def maybe_generate_store_pi(doc, method=None):
	"""S238: Sales Invoice on_submit hook — generates store-side PI."""
	set_backend_observability_context(
		module="billing",
		action="maybe_generate_store_pi",
		mutation_type="create",
		extras={"si_name": doc.name, "company": doc.company, "customer": doc.customer},
	)

	# Filter 1: only BKI -> store SIs trigger the generator
	if doc.company != BKI_COMPANY:
		return

	# Filter 2 (v2-W has_field guard): skip if Custom Field not installed yet
	if not frappe.get_meta("Purchase Invoice").has_field("bki_si_reference"):
		frappe.log_error(
			"S238: bki_si_reference Custom Field not installed; skipping PI generation",
			"S238 Custom Field Missing",
		)
		return

	settings = frappe.get_single("BEI Settings")
	if not getattr(settings, "enable_bki_store_pi_generator", 1):
		return

	# Filter 3 (v2-B7): only fire when SI used BIR-authorized series
	bir_series = (getattr(settings, "bki_sales_naming_series", "") or "").strip()
	if (
		bir_series
		and doc.naming_series
		and not doc.naming_series.startswith(bir_series.split(".")[0])
	):
		return

	# Identify buyer Company (per canonical: Customer.name == per-store Company.name)
	buyer_company = doc.customer if frappe.db.exists("Company", doc.customer) else None
	if not buyer_company:
		# v2.1-W3: Sentry breadcrumb so non-matching customers are visible
		# (251/839 historical SIs hit this path; helps diagnose walk-in / holdco).
		if sentry_sdk is not None:
			try:
				sentry_sdk.add_breadcrumb(
					category="s238.pi_generator",
					message=f"Skipped SI {doc.name}: customer '{doc.customer}' is not a per-store Company",
					level="info",
				)
			except Exception:
				pass
		return

	# Idempotency: skip if a PI already exists referencing this SI
	if frappe.db.exists("Purchase Invoice", {"bki_si_reference": doc.name}):
		return

	sp_name = "s238_pi_gen"
	try:
		frappe.db.savepoint(sp_name)
		pi = build_store_pi(doc, buyer_company)
		pi.insert(ignore_permissions=True)
		# v2-B11: auto_submit_store_pi REMOVED. Always Draft.
		# Audit comment on the SI so Finance can trace
		si_comment = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Sales Invoice",
			"reference_name": doc.name,
			"content": (
				f"S238: Store-side PI auto-generated -> {pi.name} (Draft). "
				f"Awaiting review by Finance team."
			),
		})
		si_comment.insert(ignore_permissions=True)
	except Exception:
		# v2-B1: raw SQL ROLLBACK TO SAVEPOINT (rollback_to_savepoint API doesn't exist)
		try:
			frappe.db.sql(f"ROLLBACK TO SAVEPOINT {sp_name}")
		except Exception:
			pass
		frappe.log_error(
			f"S238: PI generation failed for SI {doc.name}: {frappe.get_traceback()}",
			"S238 Store PI Generator Error",
		)
		# Do NOT block the SI submit — log and surface via Sentry only.


def build_store_pi(si, buyer_company):
	"""Construct the Draft PI mirroring the SI's items + taxes."""
	# v2-B4: exact-match by account_number (deterministic)
	inv_account = resolve_account_by_number(buyer_company, ACCT_INVENTORY_FROM_COMMISSARY)
	vat_account = resolve_account_by_number(buyer_company, ACCT_INPUT_VAT_BKI_INTERCO)
	ap_account = resolve_account_by_number(buyer_company, ACCT_AP_TRADE_BKI)

	# v2-B2: per-store warehouse — canonical: Warehouse.docname == Company.name
	buyer_warehouse = buyer_company

	# v2.1-CRIT-2: resolve per-store cost_center BEFORE building items.
	buyer_cost_center = _resolve_per_store_cost_center(buyer_company, buyer_warehouse)

	# v2.2-currency-hotfix (2026-05-10): explicitly resolve currency from buyer Company.
	# `frappe.new_doc("Purchase Invoice")` initializes currency to the system default
	# (INR for fresh ERPNext) regardless of Supplier.default_currency. Without this
	# line, ERPNext's `validate_party_account_currency` throws:
	#   "Party Account ... currency (PHP) and document currency (INR) should be same"
	# because the AP-Trade-BKI account is PHP but the doc currency is still INR.
	# Discovered during PR #740 post-deploy smoke test (2026-05-10).
	buyer_currency = (
		frappe.db.get_value("Company", buyer_company, "default_currency") or "PHP"
	)

	pi = frappe.new_doc("Purchase Invoice")
	pi.company = buyer_company
	pi.supplier = BKI_TRADE_SUPPLIER
	pi.currency = buyer_currency                          # v2.2-currency-hotfix
	pi.conversion_rate = 1.0                              # PHP-to-PHP, no conversion
	pi.price_list_currency = buyer_currency               # v2.2-currency-hotfix
	pi.plc_conversion_rate = 1.0                          # PHP-to-PHP
	pi.posting_date = si.posting_date
	# v2-B8: mirror posting_time so SLE lands at SI's exact timestamp
	pi.set_posting_time = 1
	pi.posting_time = si.posting_time
	pi.bill_no = si.name
	pi.bill_date = si.posting_date
	pi.bki_si_reference = si.name
	# v2.2-icref-hotfix (2026-05-10): the original v2-W intent was to set the
	# standard ERPNext `inter_company_invoice_reference` field for G-046
	# dashboard support. But ERPNext's `validate_inter_company_party` in
	# sales_invoice.py:2095 throws "Invalid Supplier for Inter Company
	# Transaction" when this field is set AND `pi.supplier.is_internal_supplier=0`.
	# Per ICT-001..006 (CFO Butch's separate-legal-entity stance), the BKI Trade
	# Supplier MUST be `is_internal_supplier=0` — which is incompatible with
	# `inter_company_invoice_reference`. The two are mutually exclusive in
	# ERPNext's model. We use the new `bki_si_reference` Custom Field (set above)
	# as the authoritative cross-doc link instead. G-046 dashboard updates to
	# query `bki_si_reference` instead of `inter_company_invoice_reference` are
	# a separate follow-up sprint candidate.
	pi.update_stock = 1
	pi.set_warehouse = buyer_warehouse                    # v2-B2
	pi.credit_to = ap_account

	# v2.1-CRIT-1: bei_legal_entity is the BUYER's, NOT the seller's.
	# v2.1-W7: has_field guards prevent crashes if S192/S203 fields not installed.
	pi_meta = frappe.get_meta("Purchase Invoice")
	if pi_meta.has_field("bei_legal_entity"):
		pi.bei_legal_entity = buyer_company   # NOT si.bei_legal_entity (was bug in v2)
	if pi_meta.has_field("bei_store_label") and getattr(si, "bei_store_label", None):
		pi.bei_store_label = si.bei_store_label

	# v2-B9: explicit item + tax mirroring
	_mirror_items(pi, si, inv_account, buyer_warehouse, buyer_cost_center)
	_mirror_taxes(pi, si, vat_account, buyer_cost_center)
	return pi


def _resolve_per_store_cost_center(buyer_company, buyer_warehouse):
	"""v2.1-CRIT-2: resolve a Cost Center belonging to the per-store Company.

	SI's cost_center belongs to BKI; mirroring it onto a per-store PI fails
	Frappe's `Cost Center.company == doc.company` validation, and the
	savepoint try/except would silently swallow the error -> 0 PIs created.

	v2.2-hotfix (2026-05-10): the `Warehouse.custom_cost_center` Custom Field
	cited in the plan (pattern from store.py:5278) does NOT exist on production.
	The existing call site `store.py:_get_store_cost_center` is dead code (would
	throw 'Unknown column' if exercised). Guard the lookup with
	`frappe.get_meta().has_field()` so this function falls back to
	`Company.cost_center` cleanly when the field is absent.

	Resolution order:
	  1. `Warehouse.custom_cost_center` IF the Custom Field exists
	  2. `Company.cost_center` default (always works — set on every Company)
	  3. Throw if neither set — fail loud, not silent.
	"""
	cc = None
	# v2.2-hotfix: only query if the Custom Field actually exists on Warehouse
	if frappe.get_meta("Warehouse").has_field("custom_cost_center"):
		cc = frappe.db.get_value("Warehouse", buyer_warehouse, "custom_cost_center")
	if not cc:
		cc = frappe.db.get_value("Company", buyer_company, "cost_center")
	if not cc:
		frappe.throw(_(
			f"S238: per-store Cost Center not found for {buyer_company}. "
			f"Set Company({buyer_company}).cost_center "
			f"(or install Warehouse.custom_cost_center Custom Field if per-warehouse "
			f"granularity is needed)."
		))
	return cc


def _mirror_items(pi, si, inv_account, warehouse, cost_center):
	"""v2-B9 + B10 + v2.1-CRIT-2: mirror SI line items with per-store inventory + per-store CC."""
	for si_item in si.items:
		pi.append("items", {
			"item_code":   si_item.item_code,
			"item_name":   si_item.item_name,
			"description": si_item.description,
			"qty":         flt(si_item.qty),
			"uom":         si_item.uom,
			"rate":        flt(si_item.rate),
			"amount":      flt(si_item.amount),
			"warehouse":   warehouse,                      # v2-B2
			"expense_account": inv_account,
			"cost_center": cost_center,                    # v2.1-CRIT-2 (NOT si_item.cost_center)
		})


def _mirror_taxes(pi, si, vat_account, cost_center):
	"""v2-B9 + v2.1-CRIT-2: mirror only Output VAT rows from SI; skip EWT-deduct rows."""
	for si_tax in si.taxes:
		ah = (si_tax.account_head or "").lower()
		# Only mirror VAT rows
		if "vat" not in ah:
			continue
		# Defensive filter for EWT-deduct (per ICT-004 BKI has no EWT-deduct rows;
		# `add_deduct_tax` field doesn't exist on Sales Taxes side per audit, so
		# this getattr is fail-safe).
		if getattr(si_tax, "add_deduct_tax", "") and si_tax.add_deduct_tax.lower() == "deduct":
			continue
		pi.append("taxes", {
			"charge_type":    "Actual",
			"account_head":   vat_account,
			"description":    f"Input VAT - BKI Inter-Co (mirrors SI {si.name})",
			"tax_amount":     flt(si_tax.tax_amount),
			"category":       "Total",
			"add_deduct_tax": "Add",
			"cost_center":    cost_center,    # v2.1-CRIT-2 (NOT si_tax.cost_center)
		})


def resolve_account_by_number(company, account_number):
	"""v2-B4: exact match by account_number (deterministic).

	Replaces v1's LIKE %name% lookup which silently picked random matches on dupes.
	"""
	rows = frappe.db.sql(
		"SELECT name FROM `tabAccount` "
		"WHERE company=%s AND account_number=%s AND disabled=0 LIMIT 1",
		(company, account_number),
		as_dict=True,
	)
	if not rows:
		frappe.throw(_(
			f"S238: account number '{account_number}' not found on {company}. "
			f"Run scripts/s238/seed_pi_generator_accounts.py --apply first."
		))
	return rows[0]["name"]


def cascade_cancel_store_pi(doc, method=None):
	"""v2-B3: Sales Invoice on_cancel — cascade to paired store-side PI.

	- Draft PI: delete (no GL impact).
	- Submitted PI: file Comment, do NOT auto-cancel (Finance review required).

	v2.1-W2: try/except wrap so PI cleanup failure does NOT block SI cancel.
	Pattern matches commissary.py:1317-1353 (S168 fail-soft).
	"""
	set_backend_observability_context(
		module="billing",
		action="cascade_cancel_store_pi",
		mutation_type="delete",
		extras={"si_name": doc.name},
	)
	if doc.company != BKI_COMPANY:
		return
	if not frappe.get_meta("Purchase Invoice").has_field("bki_si_reference"):
		return

	try:
		pi_name = frappe.db.get_value(
			"Purchase Invoice", {"bki_si_reference": doc.name}, "name"
		)
		if not pi_name:
			return
		pi_status = frappe.db.get_value("Purchase Invoice", pi_name, "docstatus")
		if pi_status == 0:
			# Draft — safe to delete (no GL impact)
			frappe.delete_doc(
				"Purchase Invoice", pi_name, ignore_permissions=True, force=True
			)
			si_comment = frappe.get_doc({
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Sales Invoice",
				"reference_name": doc.name,
				"content": f"S238: Paired Draft PI {pi_name} deleted (SI cancelled).",
			})
			si_comment.insert(ignore_permissions=True)
		elif pi_status == 1:
			# Submitted — flag for manual review; DO NOT auto-cancel
			pi_comment = frappe.get_doc({
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Purchase Invoice",
				"reference_name": pi_name,
				"content": (
					f"S238: Paired BKI SI {doc.name} was CANCELLED. This PI was "
					f"already submitted; Finance review required to decide whether "
					f"to cancel this PI (will reverse inventory + Input VAT)."
				),
			})
			pi_comment.insert(ignore_permissions=True)
			frappe.log_error(
				f"S238: BKI SI {doc.name} cancelled but paired PI {pi_name} is submitted — manual review required",
				"S238 PI Cascade Manual Review",
			)
	except Exception:
		# Fail-soft: don't block SI cancel just because PI cleanup raised.
		frappe.log_error(
			f"S238: cascade_cancel_store_pi failed for SI {doc.name}: {frappe.get_traceback()}",
			"S238 PI Cascade Error",
		)


def lock_posting_date_on_bki_paired_pi(doc, method=None):
	"""v2-B8: prevent editing posting_date on auto-generated PIs.

	The posting_date must equal the SI's posting_date (per ICT-007 + PFRS 15
	period match). Only Administrator may override.
	"""
	if not doc.get("bki_si_reference"):
		return
	if doc.is_new():
		return  # initial insert by hook is fine
	if frappe.session.user == "Administrator":
		return
	db_pd = frappe.db.get_value("Purchase Invoice", doc.name, "posting_date")
	if db_pd and str(doc.posting_date) != str(db_pd):
		frappe.throw(_(
			"S238: posting_date is locked on BKI-paired PIs (must match the "
			"BKI SI's posting_date per ICT-007). Contact Administrator to override."
		))


# v2.1-W9: drift-detection scheduler entry point
def run_si_pi_pairing_check():
	"""Weekly scheduler job — flag BKI SIs without paired PIs (or vice versa).

	Logs to Sentry via frappe.log_error if drift detected. Read-only;
	does not auto-fix.
	"""
	set_backend_observability_context(
		module="billing",
		action="run_si_pi_pairing_check",
		mutation_type="read",
	)
	# SIs submitted in last 7 days without paired PI
	rows = frappe.db.sql(
		"""
		SELECT si.name, si.customer, si.grand_total, si.posting_date
		FROM `tabSales Invoice` si
		LEFT JOIN `tabPurchase Invoice` pi ON pi.bki_si_reference = si.name
		WHERE si.company = %s
		  AND si.docstatus = 1
		  AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
		  AND pi.name IS NULL
		  AND EXISTS (SELECT 1 FROM `tabCompany` c WHERE c.name = si.customer)
		""",
		BKI_COMPANY,
		as_dict=True,
	)
	if rows:
		frappe.log_error(
			f"S238 drift: {len(rows)} BKI SIs without paired PI in last 7d. Sample: {rows[:3]}",
			"S238 SI/PI Pairing Drift",
		)
	return {"unpaired_si_count": len(rows), "samples": rows[:3]}

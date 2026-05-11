"""S247 — Generate store-side Draft Stock Entry (Material Receipt) on BKI SI submit.

Paired with billing-only PI generator (`bki_store_pi_generator.py`). Together they
implement Option 3-corrected for the BKI->Store inter-company flow per the CEO
decision 2026-05-11 (output/l3/s246/DECISION.md).

# GL chain per BKI->Store shipment (Option 3-corrected):
#   SE (this generator, Material Receipt, update_stock=1):
#     Dr  1104210 Inventory-from-Commissary  (via Warehouse.account)
#     Cr  SRBNB                                (via SE item.expense_account)
#   PI (paired bki_store_pi_generator.py, update_stock=0):
#     Dr  SRBNB                                (CLEARS this SE's Cr)
#     Dr  1106210 Input VAT BKI Inter-Co
#     Cr  2103210 AP-Trade-BKI
#   Net per shipment:
#     Dr  1104210 Inventory + Dr 1106210 Input VAT
#     Cr  2103210 AP-Trade-BKI
#     SRBNB clearing nets to zero.

Atomicity (per S247 Decision 3): independent savepoint isolation. If SE generation
fails, PI generation still runs (and vice versa). SI submit never blocked. Daily
reconciliation cron (S248 follow-up) sweeps half-paired SIs.

Cancel cascade order: SE first, then PI (reverse-creation pattern). Registered in
hooks.py so SE handler comes before PI handler in the on_cancel list.
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


def maybe_generate_store_stock_entry(doc, method=None):
	"""S247: Sales Invoice on_submit hook — generates store-side Stock Entry.

	Mirrors `maybe_generate_store_pi` filter logic so both fire on the same SI set.
	"""
	set_backend_observability_context(
		module="warehouse",
		action="maybe_generate_store_stock_entry",
		mutation_type="create",
		extras={"si_name": doc.name, "company": doc.company, "customer": doc.customer},
	)

	# Filter 1: only BKI -> store SIs trigger the generator
	if doc.company != BKI_COMPANY:
		return

	# Filter 2: skip if SE Custom Field not installed yet (Phase 3C.4)
	if not frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
		frappe.log_error(
			"S247: bki_si_reference Custom Field not installed on Stock Entry; "
			"skipping SE generation",
			"S247 SE Custom Field Missing",
		)
		return

	# Filter 3: kill switch via BEI Settings
	settings = frappe.get_single("BEI Settings")
	if not getattr(settings, "enable_bki_store_stock_entry_generator", 1):
		return

	# Filter 4 (BIR-authorized series): only fire when SI used the canonical naming series
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
		if sentry_sdk is not None:
			try:
				sentry_sdk.add_breadcrumb(
					category="s247.se_generator",
					message=f"Skipped SI {doc.name}: customer '{doc.customer}' is not a per-store Company",
					level="info",
				)
			except Exception:
				pass
		return

	# Filter 5 (defense-in-depth Internal Customer guard, audit Blocker 7):
	# The canonical filter (line above — `frappe.db.exists("Company", doc.customer)`) already
	# excludes Internal Customers by naming convention (`SM TANZA (Internal)` doesn't match
	# Company `SM TANZA - BEBANG MEGA INC.`). Add explicit `is_internal_customer` guard so
	# future naming-convention changes can't accidentally trigger generators on S206 labor JEs.
	if frappe.db.get_value("Customer", doc.customer, "is_internal_customer"):
		return

	# Idempotency: skip if an SE already exists referencing this SI
	if frappe.db.exists("Stock Entry", {"bki_si_reference": doc.name}):
		return

	sp_name = "s247_se_gen"
	try:
		frappe.db.savepoint(sp_name)
		se = build_store_stock_entry(doc, buyer_company)
		se.insert(ignore_permissions=True)
		# Audit comment on the SI so Finance can trace
		si_comment = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Sales Invoice",
			"reference_name": doc.name,
			"content": (
				f"S247: Store-side Stock Entry auto-generated -> {se.name} (Draft). "
				f"Awaiting Finance team review."
			),
		})
		si_comment.insert(ignore_permissions=True)
	except Exception:
		# raw SQL ROLLBACK TO SAVEPOINT (Frappe rollback_to_savepoint API doesn't exist)
		try:
			frappe.db.sql(f"ROLLBACK TO SAVEPOINT {sp_name}")
		except Exception:
			pass
		frappe.log_error(
			f"S247: SE generation failed for SI {doc.name}: {frappe.get_traceback()}",
			"S247 Store SE Generator Error",
		)
		# Do NOT block the SI submit — log and surface via Sentry only.


def build_store_stock_entry(si, buyer_company):
	"""Construct the Draft Stock Entry (Material Receipt) on the buyer store's books.

	Posts inventory only — no billing side. The paired PI handles billing.
	"""
	# Resolve the SRBNB clearing account on the buyer Company (S247 Phase 4b sets this).
	# SE Cr posts to SRBNB; paired PI Dr clears it.
	srbnb_account = _resolve_srbnb_account(buyer_company)

	# Canonical: Warehouse name == Company name (per docs/STORE_COMPANY_CANONICAL.md).
	buyer_warehouse = buyer_company

	# Per-store cost center (S247 Phase 4a fixes the 4 missing ones).
	buyer_cost_center = _resolve_per_store_cost_center(buyer_company)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.company = buyer_company
	se.posting_date = si.posting_date
	se.set_posting_time = 1
	se.posting_time = si.posting_time
	se.bki_si_reference = si.name

	# Mirror SI line items as SE rows. Each line:
	#   - t_warehouse = buyer store's warehouse (canonical: == Company.name)
	#   - basic_rate = SI item rate (so SLE valuation matches the bill amount)
	#   - expense_account = SRBNB (GR/IR clearing — paired PI clears it)
	#   - cost_center = per-store CC
	for si_item in si.items:
		se.append("items", {
			"item_code": si_item.item_code,
			"qty": flt(si_item.qty),
			"uom": si_item.uom,
			"basic_rate": flt(si_item.rate),
			"t_warehouse": buyer_warehouse,
			"expense_account": srbnb_account,    # Cr side of SE JE
			"cost_center": buyer_cost_center,
		})
	return se


def cascade_cancel_store_stock_entry(doc, method=None):
	"""S247: Sales Invoice on_cancel hook — cascade to paired store-side SE.

	Cancel order (per Phase 3B Blocker 10): SE FIRST, then PI. This handler runs first
	by virtue of being listed first in hooks.py `Sales Invoice.on_cancel`.

	- Draft SE -> delete (no GL impact).
	- Submitted SE -> cancel (reverses SLE + JE).
	"""
	set_backend_observability_context(
		module="warehouse",
		action="cascade_cancel_store_stock_entry",
		mutation_type="delete",
		extras={"si_name": doc.name},
	)

	# Backwards-compat (audit WARNING F-04): historical SIs created before S247 deploy
	# have no paired SE — gracefully skip when none found.
	if not frappe.get_meta("Stock Entry").has_field("bki_si_reference"):
		return
	se_name = frappe.db.get_value("Stock Entry", {"bki_si_reference": doc.name}, "name")
	if not se_name:
		return

	try:
		se = frappe.get_doc("Stock Entry", se_name)
		if se.docstatus == 1:
			se.cancel()
		elif se.docstatus == 0:
			frappe.delete_doc("Stock Entry", se_name, force=True, ignore_permissions=True)
	except Exception:
		frappe.log_error(
			f"S247: SE cascade-cancel failed for SI {doc.name} -> SE {se_name}: "
			f"{frappe.get_traceback()}",
			"S247 SE Cancel Cascade Error",
		)


def lock_posting_date_on_bki_paired_se(doc, method=None):
	"""S247: Stock Entry validate hook — prevent edits to posting_date once SE is paired to a SI.

	Mirrors `bki_store_pi_generator.lock_posting_date_on_bki_paired_pi`. Prevents PFRS
	matching violations where finance shifts SE posting_date away from the paired PI's date.
	"""
	# Skip if no SI reference (not a paired SE)
	if not getattr(doc, "bki_si_reference", None):
		return
	if doc.is_new():
		return
	# Compare against db value
	db_date = frappe.db.get_value("Stock Entry", doc.name, "posting_date")
	if db_date and str(doc.posting_date) != str(db_date):
		si_date = frappe.db.get_value("Sales Invoice", doc.bki_si_reference, "posting_date")
		frappe.throw(_(
			f"S247: posting_date is locked on Stock Entries paired to a BKI Sales Invoice "
			f"(PFRS matching). The paired SI {doc.bki_si_reference} has posting_date={si_date}; "
			f"SE must match. Use a Stock Reconciliation or back-dated correction instead."
		))


# --- helpers ---


def _resolve_srbnb_account(buyer_company):
	"""Resolve the buyer Company's Stock Received But Not Billed account (GR/IR clearing).

	Resolution order:
	  1. Company.stock_received_but_not_billed (canonical, set by S247 Phase 4b)
	  2. Account on this Company with account_type='Stock Received But Not Billed' (fallback)
	  3. Throw — fail loud, captured by savepoint rollback.
	"""
	srbnb = frappe.db.get_value("Company", buyer_company, "stock_received_but_not_billed")
	if srbnb:
		return srbnb
	srbnb = frappe.db.get_value(
		"Account",
		{
			"company": buyer_company,
			"account_type": "Stock Received But Not Billed",
			"is_group": 0,
			"disabled": 0,
		},
		"name",
	)
	if srbnb:
		return srbnb
	frappe.throw(_(
		f"S247: SRBNB account not found for {buyer_company}. Set "
		f"Company({buyer_company}).stock_received_but_not_billed via /frappe-bulk-edits "
		f"(S247 Phase 4b)."
	))


def _resolve_per_store_cost_center(buyer_company):
	"""Resolve the per-store Cost Center.

	Mirrors the PI generator's resolver. Uses Company.cost_center directly. If NULL,
	throw — fail loud (DEFECT A surfaced this).
	"""
	cc = frappe.db.get_value("Company", buyer_company, "cost_center")
	if not cc:
		frappe.throw(_(
			f"S247: per-store Cost Center not found for {buyer_company}. "
			f"Set Company({buyer_company}).cost_center (S247 Phase 4a)."
		))
	return cc

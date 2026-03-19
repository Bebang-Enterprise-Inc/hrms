"""
Expense Review APIs - Accounting Dashboard Endpoints
Handles expense review, approval, and batch processing for accounting team.

Author: Claude Code
Date: 2026-02-02
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

# ============================================================
# ROLE VALIDATION
# ============================================================


def _check_accounting_role():
	"""Verify user has accounting role. Throw if not authorized."""
	roles = frappe.get_roles()
	allowed_roles = ["Accounts User", "Accounts Manager", "System Manager"]
	if not any(r in roles for r in allowed_roles):
		frappe.throw(_("Only accounting team can access this function"))


# ============================================================
# DASHBOARD ENDPOINTS
# ============================================================


@frappe.whitelist()
def get_review_dashboard():
	"""
	Get dashboard statistics for accounting review.
	Returns counts by category and recent activity.
	"""
	_check_accounting_role()

	# Count by review status
	pending_review = frappe.db.count(
		"BEI Expense Request", filters={"internal_review_status": "pending_review"}
	)

	mismatch_review = frappe.db.count(
		"BEI Expense Request", filters={"internal_review_status": "mismatch_review"}
	)

	needs_classification = frappe.db.count(
		"BEI Expense Request", filters={"internal_review_status": "needs_classification"}
	)

	ocr_failed = frappe.db.count("BEI Expense Request", filters={"internal_review_status": "ocr_failed"})

	auto_approved = frappe.db.count(
		"BEI Expense Request", filters={"internal_review_status": "auto_approved", "status": "Submitted"}
	)

	# This week's stats
	from frappe.utils import add_days

	week_start = add_days(today(), -7)

	approved_this_week = frappe.db.count(
		"BEI Expense Request", filters={"status": "Approved", "internal_review_date": [">=", week_start]}
	)

	total_amount_this_week = (
		frappe.db.sql(
			"""
        SELECT COALESCE(SUM(internal_approved_amount), 0)
        FROM `tabBEI Expense Request`
        WHERE status = 'Approved'
        AND internal_review_date >= %s
    """,
			week_start,
		)[0][0]
		or 0
	)

	return {
		"success": True,
		"data": {
			"pending_review": pending_review + needs_classification,
			"mismatch_review": mismatch_review,
			"ocr_failed": ocr_failed,
			"auto_approved_pending": auto_approved,
			"approved_this_week": approved_this_week,
			"total_amount_this_week": total_amount_this_week,
		},
	}


@frappe.whitelist()
def get_pending_review(
	review_type: str = "all",
	store: str | None = None,
	limit: int = 50,
	offset: int = 0,
):
	"""
	Get expenses pending review.

	Args:
	    review_type: all | mismatch | ocr_failed | needs_classification | auto_approved
	    store: Filter by store (optional)
	    limit: Page size
	    offset: Page offset
	"""
	_check_accounting_role()

	filters = {"status": "Submitted"}

	if review_type == "mismatch":
		filters["internal_review_status"] = "mismatch_review"
	elif review_type == "ocr_failed":
		filters["internal_review_status"] = "ocr_failed"
	elif review_type == "needs_classification":
		filters["internal_review_status"] = "needs_classification"
	elif review_type == "auto_approved":
		filters["internal_review_status"] = "auto_approved"
	else:
		filters["internal_review_status"] = [
			"in",
			["pending_review", "mismatch_review", "needs_classification", "ocr_failed"],
		]

	if store:
		filters["store"] = store

	expenses = frappe.get_all(
		"BEI Expense Request",
		filters=filters,
		fields=[
			"name",
			"employee",
			"store",
			"request_date",
			"manual_vendor",
			"manual_description",
			"manual_amount",
			"manual_date",
			"internal_ocr_vendor",
			"internal_ocr_amount",
			"internal_ocr_date",
			"internal_match_score",
			"internal_match_status",
			"internal_amount_diff",
			"internal_suggested_coa",
			"internal_coa_confidence",
			"internal_review_status",
			"creation",
		],
		order_by="creation asc",
		limit_page_length=limit,
		start=offset,
	)

	# Enrich with employee names
	for exp in expenses:
		emp = frappe.db.get_value("Employee", exp["employee"], "employee_name")
		exp["employee_name"] = emp or exp["employee"]

		# Parse match details
		exp["match_status_display"] = get_match_status_display(exp)

	return {"success": True, "data": expenses}


def get_match_status_display(expense):
	"""Get human-readable match status."""
	status = expense.get("internal_review_status")

	if status == "ocr_failed":
		return {"type": "error", "label": "Receipt Unclear", "icon": "🔴"}
	elif status == "mismatch_review":
		diff = expense.get("internal_amount_diff", 0)
		if diff > 0:
			return {"type": "warning", "label": f"Amount +PHP {abs(diff):.2f}", "icon": "⚠️"}
		elif diff < 0:
			return {"type": "warning", "label": f"Amount -PHP {abs(diff):.2f}", "icon": "⚠️"}
		return {"type": "warning", "label": "Mismatch", "icon": "⚠️"}
	elif status == "needs_classification":
		return {"type": "info", "label": "Needs COA", "icon": "🤔"}
	elif status == "auto_approved":
		return {"type": "success", "label": "Auto-Matched", "icon": "✅"}

	return {"type": "default", "label": "Pending", "icon": "⏳"}


@frappe.whitelist()
def get_expense_detail(expense_name: str):
	"""
	Get full expense detail with OCR comparison.
	For accounting review - shows all internal fields.
	"""
	_check_accounting_role()

	expense = frappe.get_doc("BEI Expense Request", expense_name)

	# Get employee details
	emp = frappe.db.get_value("Employee", expense.employee, ["employee_name", "branch"], as_dict=True)

	# Parse JSON fields
	ocr_line_items = []
	if expense.internal_ocr_line_items:
		try:
			ocr_line_items = json.loads(expense.internal_ocr_line_items)
		except (TypeError, ValueError):
			pass

	match_details = {}
	if expense.internal_match_details:
		try:
			match_details = json.loads(expense.internal_match_details)
		except (TypeError, ValueError):
			pass

	coa_alternatives = []
	if expense.internal_coa_alternatives:
		try:
			coa_alternatives = json.loads(expense.internal_coa_alternatives)
		except (TypeError, ValueError):
			pass

	# Build comparison view
	comparison = {
		"vendor": {
			"manual": expense.manual_vendor,
			"ocr": expense.internal_ocr_vendor,
			"match": match_details.get("vendor", 0) >= 80,
		},
		"amount": {
			"manual": expense.manual_amount,
			"ocr": expense.internal_ocr_amount,
			"diff": expense.internal_amount_diff,
			"match": match_details.get("amount", 0) >= 90,
		},
		"date": {
			"manual": expense.manual_date,
			"ocr": expense.internal_ocr_date,
			"match": match_details.get("date", 0) >= 90,
		},
	}

	return {
		"success": True,
		"data": {
			"name": expense.name,
			"employee": expense.employee,
			"employee_name": emp.employee_name if emp else None,
			"store": expense.store,
			"request_date": expense.request_date,
			# Manual input
			"manual_vendor": expense.manual_vendor,
			"manual_description": expense.manual_description,
			"manual_amount": expense.manual_amount,
			"manual_date": expense.manual_date,
			"receipt_photo": expense.receipt_photo,
			# OCR results
			"ocr_vendor": expense.internal_ocr_vendor,
			"ocr_amount": expense.internal_ocr_amount,
			"ocr_date": expense.internal_ocr_date,
			"ocr_line_items": ocr_line_items,
			"ocr_raw_text": expense.internal_ocr_raw_text,
			"ocr_confidence": expense.internal_ocr_confidence,
			"ocr_status": expense.internal_ocr_status,
			# Matching
			"match_score": expense.internal_match_score,
			"match_status": expense.internal_match_status,
			"match_details": match_details,
			"amount_diff": expense.internal_amount_diff,
			"comparison": comparison,
			# Classification
			"suggested_coa": expense.internal_suggested_coa,
			"coa_confidence": expense.internal_coa_confidence,
			"coa_alternatives": coa_alternatives,
			"classification_method": expense.internal_classification_method,
			# Review status
			"review_status": expense.internal_review_status,
			"status": expense.status,
		},
	}


# ============================================================
# APPROVAL ENDPOINTS
# ============================================================


@frappe.whitelist()
def approve_expense(
	expense_name: str,
	final_coa: str,
	approved_amount: float | None = None,
	approval_source: str = "manual",
	notes: str | None = None,
):
	"""
	Approve a single expense.

	Args:
	    expense_name: Expense request ID
	    final_coa: Selected Chart of Account
	    approved_amount: Amount to approve (defaults to manual_amount)
	    approval_source: manual | ocr | edited
	    notes: Optional review notes
	"""
	_check_accounting_role()

	expense = frappe.get_doc("BEI Expense Request", expense_name)

	if expense.status == "Approved":
		frappe.throw(_("Expense already approved"))

	expense.internal_final_coa = final_coa
	expense.internal_approved_amount = flt(approved_amount or expense.manual_amount)
	expense.internal_approval_source = approval_source
	expense.internal_reviewed_by = frappe.session.user
	expense.internal_review_date = now_datetime()
	expense.internal_review_notes = notes
	expense.status = "Approved"

	expense.save(ignore_permissions=True)

	# Wire record_correction (Task 19A)
	try:
		from hrms.api.expense_classifier import record_correction

		if expense.internal_suggested_coa and final_coa != expense.internal_suggested_coa:
			record_correction(expense.name, expense.internal_suggested_coa, final_coa)
	except ImportError:
		pass

	# Auto-generate PCF JV (Task F03A)
	_create_pcf_jv(expense)

	# Notify employee
	_notify_employee(expense, "approved")

	return {
		"success": True,
		"data": {
			"name": expense.name,
			"status": "Approved",
			"final_coa": final_coa,
			"approved_amount": expense.internal_approved_amount,
		},
		"message": _("Expense approved"),
	}


def _create_pcf_jv(expense):
	"""
	Best-effort PCF JV hook.

	Keeps approval flow stable even when PCF-to-JV mapping is unavailable.
	"""
	batch_name = getattr(expense, "pcf_batch", None)
	if not batch_name:
		return {"created": False, "journal_entry": None, "reason": "missing_pcf_batch"}

	final_coa = getattr(expense, "internal_final_coa", None)
	if not final_coa:
		return {"created": False, "journal_entry": None, "reason": "missing_final_coa"}

	amount = flt(getattr(expense, "internal_approved_amount", None) or getattr(expense, "manual_amount", 0))
	if amount <= 0:
		return {"created": False, "journal_entry": None, "reason": "invalid_amount"}

	# Explicit no-op until a dedicated expense-level JV policy is finalized.
	return {"created": False, "journal_entry": None, "reason": "pcf_jv_policy_pending"}


def _notify_employee(expense, action: str):
	"""Notify employee of expense status change."""
	try:
		from hrms.api.google_chat import send_notification_to_user

		user = frappe.db.get_value("Employee", expense.employee, "user_id")
		if not user:
			return

		if action == "approved":
			message = f"""*Expense Approved*

Your expense request {expense.name} has been approved.
*Amount:* PHP {expense.internal_approved_amount:,.2f}
*COA:* {expense.internal_final_coa}"""
		else:
			message = f"""*Expense Rejected*

Your expense request {expense.name} was rejected.
Please resubmit with a clearer receipt photo."""

		send_notification_to_user(user, message)

	except Exception as e:
		frappe.log_error(f"Employee notification failed: {e}")


@frappe.whitelist()
def batch_approve(expense_names: str):
	"""
	Batch approve multiple auto-matched expenses.
	Uses AI-suggested COA and manual amount.

	Args:
	    expense_names: JSON array of expense names
	"""
	_check_accounting_role()

	if isinstance(expense_names, str):
		expense_names = json.loads(expense_names)

	if not expense_names:
		frappe.throw(_("No expenses selected"))

	approved = []
	failed = []

	for name in expense_names:
		try:
			expense = frappe.get_doc("BEI Expense Request", name)

			if expense.status == "Approved":
				failed.append({"name": name, "error": "Already approved"})
				continue

			if not expense.internal_suggested_coa:
				failed.append({"name": name, "error": "No COA suggestion"})
				continue

			expense.internal_final_coa = expense.internal_suggested_coa
			expense.internal_approved_amount = expense.manual_amount
			expense.internal_approval_source = "auto"
			expense.internal_reviewed_by = frappe.session.user
			expense.internal_review_date = now_datetime()
			expense.status = "Approved"
			expense.save(ignore_permissions=True)

			approved.append(name)

		except Exception as e:
			failed.append({"name": name, "error": str(e)})

	frappe.db.commit()

	return {
		"success": True,
		"data": {
			"approved_count": len(approved),
			"failed_count": len(failed),
			"approved": approved,
			"failed": failed,
		},
		"message": _("{0} expenses approved").format(len(approved)),
	}


@frappe.whitelist()
def reject_expense(expense_name: str, reason: str | None = None):
	"""
	Reject an expense.
	Store staff will see generic rejection message.

	Args:
	    expense_name: Expense request ID
	    reason: Internal reason (not shown to store staff)
	"""
	_check_accounting_role()

	expense = frappe.get_doc("BEI Expense Request", expense_name)

	if expense.status in ["Approved", "Rejected"]:
		frappe.throw(_("Expense already processed"))

	expense.status = "Rejected"
	expense.internal_reviewed_by = frappe.session.user
	expense.internal_review_date = now_datetime()
	expense.internal_review_notes = reason  # Internal only

	expense.save(ignore_permissions=True)

	# Notify employee
	_notify_employee(expense, "rejected")

	return {
		"success": True,
		"data": {"name": expense.name, "status": "Rejected"},
		"message": _("Expense rejected"),
	}


# ============================================================
# AUTO-APPROVED BATCH ENDPOINTS
# ============================================================


@frappe.whitelist()
def get_auto_approved_batch(store: str | None = None, limit: int = 100):
	"""
	Get auto-matched expenses ready for batch approval.
	These have match score ≥90% and COA confidence ≥90%.
	"""
	_check_accounting_role()

	filters = {"status": "Submitted", "internal_review_status": "auto_approved"}

	if store:
		filters["store"] = store

	expenses = frappe.get_all(
		"BEI Expense Request",
		filters=filters,
		fields=[
			"name",
			"employee",
			"store",
			"request_date",
			"manual_vendor",
			"manual_description",
			"manual_amount",
			"internal_suggested_coa",
			"internal_coa_confidence",
			"internal_match_score",
		],
		order_by="creation asc",
		limit_page_length=limit,
	)

	# Enrich with employee names and COA labels
	for exp in expenses:
		emp = frappe.db.get_value("Employee", exp["employee"], "employee_name")
		exp["employee_name"] = emp or exp["employee"]

		if exp["internal_suggested_coa"]:
			coa = frappe.db.get_value("Account", exp["internal_suggested_coa"], "account_name")
			exp["coa_name"] = coa or exp["internal_suggested_coa"]

	# Calculate total
	total_amount = sum(exp["manual_amount"] or 0 for exp in expenses)

	return {
		"success": True,
		"data": {"expenses": expenses, "count": len(expenses), "total_amount": total_amount},
	}


# ============================================================
# STATISTICS & REPORTING
# ============================================================


@frappe.whitelist()
def get_classification_stats(days: int = 30):
	"""
	Get AI classification performance statistics.
	"""
	_check_accounting_role()

	from frappe.utils import add_days

	start_date = add_days(today(), -days)

	# Total processed
	total = frappe.db.count(
		"BEI Expense Request", filters={"status": "Approved", "internal_review_date": [">=", start_date]}
	)

	# Auto-approved (high confidence)
	auto_approved = frappe.db.count(
		"BEI Expense Request",
		filters={
			"status": "Approved",
			"internal_review_date": [">=", start_date],
			"internal_approval_source": "auto",
		},
	)

	# Manual corrections
	manual_corrections = (
		frappe.db.sql(
			"""
        SELECT COUNT(*)
        FROM `tabBEI Expense Request`
        WHERE status = 'Approved'
        AND internal_review_date >= %s
        AND internal_final_coa != internal_suggested_coa
    """,
			start_date,
		)[0][0]
		or 0
	)

	# By COA category
	by_coa = frappe.db.sql(
		"""
        SELECT internal_final_coa, COUNT(*) as count, SUM(internal_approved_amount) as amount
        FROM `tabBEI Expense Request`
        WHERE status = 'Approved'
        AND internal_review_date >= %s
        GROUP BY internal_final_coa
        ORDER BY count DESC
    """,
		start_date,
		as_dict=True,
	)

	# By store
	by_store = frappe.db.sql(
		"""
        SELECT store, COUNT(*) as count, SUM(internal_approved_amount) as amount
        FROM `tabBEI Expense Request`
        WHERE status = 'Approved'
        AND internal_review_date >= %s
        GROUP BY store
        ORDER BY count DESC
    """,
		start_date,
		as_dict=True,
	)

	return {
		"success": True,
		"data": {
			"total_processed": total,
			"auto_approved": auto_approved,
			"auto_approval_rate": (auto_approved / total * 100) if total > 0 else 0,
			"manual_corrections": manual_corrections,
			"correction_rate": (manual_corrections / total * 100) if total > 0 else 0,
			"by_coa": by_coa,
			"by_store": by_store,
		},
	}

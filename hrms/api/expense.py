"""
Expense Request APIs - Store Staff Endpoints
Handles expense submission for all employees.

Author: Claude Code
Date: 2026-02-02
"""
import frappe
from frappe import _
import json
from frappe.utils import today, now_datetime, flt, get_url
# Lazy imports - only when OCR/classification is needed
# This prevents module load failures if dependencies are missing
def _get_classifier():
    from hrms.api.expense_classifier import classify_expense
    return classify_expense

def _get_ocr():
    from hrms.api.expense_ocr import extract_receipt_data
    return extract_receipt_data


# ============================================================
# STORE STAFF ENDPOINTS
# ============================================================

@frappe.whitelist()
def submit_expense(
    manual_vendor: str,
    manual_description: str,
    manual_amount: float,
    manual_date: str,
    receipt_photo: str
):
    """
    Submit a new expense request.
    Store staff provides 5 fields only - no category selection.

    Args:
        manual_vendor: Where they bought it
        manual_description: What they bought (free text)
        manual_amount: How much they paid
        manual_date: When they paid
        receipt_photo: Attached receipt image

    Returns:
        Success response with expense ID
    """
    if not manual_vendor or not manual_description or not manual_amount:
        frappe.throw(_("Vendor, description, and amount are required"))

    if not receipt_photo:
        frappe.throw(_("Receipt photo is required"))

    # Get employee from current user
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        ["name", "employee_name", "branch"],
        as_dict=True
    )

    if not employee:
        frappe.throw(_("Employee record not found for current user"))

    # Create expense request
    expense = frappe.new_doc("BEI Expense Request")
    expense.employee = employee.name
    expense.store = employee.branch
    expense.request_date = today()

    # Manual input from store staff
    expense.manual_vendor = manual_vendor
    expense.manual_description = manual_description
    expense.manual_amount = flt(manual_amount)
    expense.manual_date = manual_date
    expense.receipt_photo = receipt_photo

    expense.status = "Submitted"

    expense.insert()

    # Trigger background processing (OCR, matching, classification)
    frappe.enqueue(
        "hrms.api.expense.process_expense_background",
        expense_name=expense.name,
        queue="default",
        timeout=120
    )

    return {
        "success": True,
        "data": {
            "name": expense.name,
            "status": "Submitted"
        },
        "message": _("Expense submitted successfully")
    }


def process_expense_background(expense_name: str):
    """
    Background job to process expense:
    1. OCR the receipt
    2. Match manual vs OCR
    3. Classify with AI
    4. Route for approval or review
    """
    expense = frappe.get_doc("BEI Expense Request", expense_name)

    # Step 1: OCR Receipt
    try:
        extract_receipt_data = _get_ocr()
        ocr_result = extract_receipt_data(expense.receipt_photo)
        expense.internal_ocr_vendor = ocr_result.get("vendor")
        expense.internal_ocr_amount = flt(ocr_result.get("amount"))
        expense.internal_ocr_date = ocr_result.get("date")
        expense.internal_ocr_line_items = json.dumps(ocr_result.get("line_items", []))
        expense.internal_ocr_raw_text = ocr_result.get("raw_text", "")
        expense.internal_ocr_confidence = flt(ocr_result.get("confidence", 0))
        expense.internal_ocr_status = ocr_result.get("status", "failed")
    except Exception as e:
        expense.internal_ocr_status = "failed"
        expense.internal_ocr_raw_text = str(e)
        frappe.log_error(f"OCR failed for {expense_name}: {e}")

    # Step 2: Match manual vs OCR
    match_result = calculate_match_score(expense)
    expense.internal_match_score = flt(match_result["score"])
    expense.internal_match_details = json.dumps(match_result["details"])
    expense.internal_match_status = match_result["status"]
    expense.internal_amount_diff = flt(match_result.get("amount_diff", 0))

    # Step 3: AI Classification
    try:
        classify_expense = _get_classifier()
        classification = classify_expense(
            description=expense.manual_description,
            vendor=expense.manual_vendor,
            amount=expense.manual_amount
        )
        expense.internal_suggested_coa = classification.get("coa")
        expense.internal_coa_confidence = flt(classification.get("confidence", 0))
        expense.internal_coa_alternatives = json.dumps(classification.get("alternatives", []))
        expense.internal_classification_method = classification.get("method", "rule")
    except Exception as e:
        frappe.log_error(f"Classification failed for {expense_name}: {e}")

    # Step 4: Route based on match score and COA confidence
    expense.internal_review_status = determine_review_status(expense)

    expense.save(ignore_permissions=True)
    frappe.db.commit()

    # Send notification if needs review
    _notify_if_needs_review(expense)


def _notify_if_needs_review(expense):
    """Send Google Chat notification for items needing review."""
    try:
        from hrms.api.google_chat import send_message_to_space

        status = expense.internal_review_status

        if status in ["mismatch_review", "ocr_failed", "needs_classification"]:
            status_labels = {
                "mismatch_review": "Amount Mismatch",
                "ocr_failed": "Receipt Unclear",
                "needs_classification": "Needs COA Selection"
            }

            emp_name = frappe.db.get_value("Employee", expense.employee, "employee_name")

            message = f"""*Expense Needs Review*

*Status:* {status_labels.get(status, status)}
*Employee:* {emp_name}
*Store:* {expense.store}
*Amount:* PHP {expense.manual_amount:,.2f}
*Description:* {expense.manual_description[:100]}

<https://my.bebang.ph/dashboard/accounting/expenses/{expense.name}|Review in Dashboard>"""

            # Send to ERP Automation Committee
            send_message_to_space("spaces/AAQA3NVVR6c", message)

    except Exception as e:
        # Don't fail the main process if notification fails
        frappe.log_error(f"Expense notification failed: {e}")


def calculate_match_score(expense):
    """
    Compare manual input vs OCR extraction.
    Returns score 0-100 and field-by-field breakdown.
    """
    if expense.internal_ocr_status == "failed":
        return {
            "score": 0,
            "status": "ocr_failed",
            "details": {"error": "Could not extract data from receipt"},
            "amount_diff": 0
        }

    scores = {}

    # Amount match (50% weight) - most important
    if expense.internal_ocr_amount:
        manual = flt(expense.manual_amount)
        ocr = flt(expense.internal_ocr_amount)
        if manual > 0:
            diff_pct = abs(manual - ocr) / manual
            if diff_pct == 0:
                scores["amount"] = 100
            elif diff_pct <= 0.02:  # 2% tolerance
                scores["amount"] = 95
            elif diff_pct <= 0.05:  # 5% tolerance
                scores["amount"] = 80
            else:
                scores["amount"] = max(0, 100 - (diff_pct * 200))
        else:
            scores["amount"] = 0
    else:
        scores["amount"] = 50  # OCR couldn't read amount

    # Vendor match (30% weight)
    if expense.internal_ocr_vendor and expense.manual_vendor:
        scores["vendor"] = fuzzy_match(
            expense.manual_vendor.upper(),
            expense.internal_ocr_vendor.upper()
        )
    else:
        scores["vendor"] = 50

    # Date match (20% weight)
    if expense.internal_ocr_date and expense.manual_date:
        try:
            from datetime import datetime
            manual_dt = datetime.strptime(str(expense.manual_date), "%Y-%m-%d")
            ocr_dt = datetime.strptime(str(expense.internal_ocr_date), "%Y-%m-%d")
            days_diff = abs((manual_dt - ocr_dt).days)
            scores["date"] = 100 if days_diff == 0 else (90 if days_diff <= 1 else 50)
        except:
            scores["date"] = 50
    else:
        scores["date"] = 50

    # Weighted total
    total = (
        scores.get("amount", 50) * 0.50 +
        scores.get("vendor", 50) * 0.30 +
        scores.get("date", 50) * 0.20
    )

    return {
        "score": round(total, 1),
        "status": "match" if total >= 90 else "mismatch",
        "details": scores,
        "amount_diff": flt(expense.manual_amount) - flt(expense.internal_ocr_amount or 0)
    }


def fuzzy_match(str1: str, str2: str) -> float:
    """
    Simple fuzzy matching for vendor names.
    Returns similarity score 0-100.
    """
    if not str1 or not str2:
        return 50

    str1 = str1.strip().upper()
    str2 = str2.strip().upper()

    # Exact match
    if str1 == str2:
        return 100

    # One contains the other
    if str1 in str2 or str2 in str1:
        return 90

    # Word overlap
    words1 = set(str1.split())
    words2 = set(str2.split())
    if words1 & words2:  # Any common words
        overlap = len(words1 & words2) / max(len(words1), len(words2))
        return 70 + (overlap * 25)

    return 30


def determine_review_status(expense):
    """
    Determine routing based on match score and COA confidence.
    """
    match_score = flt(expense.internal_match_score)
    coa_confidence = flt(expense.internal_coa_confidence)

    if expense.internal_ocr_status == "failed":
        return "ocr_failed"

    if match_score >= 90 and coa_confidence >= 90:
        return "auto_approved"

    if match_score >= 90 and coa_confidence < 90:
        return "needs_classification"

    if match_score < 90:
        return "mismatch_review"

    return "pending_review"


@frappe.whitelist()
def get_my_expenses(limit: int = 50, offset: int = 0):
    """
    Get current user's expense requests.
    Returns simplified view (no internal fields).
    """
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        "name"
    )

    if not employee:
        return {"success": True, "data": []}

    expenses = frappe.get_all(
        "BEI Expense Request",
        filters={"employee": employee},
        fields=[
            "name", "request_date", "manual_vendor", "manual_description",
            "manual_amount", "manual_date", "status", "creation"
        ],
        order_by="creation desc",
        limit_page_length=limit,
        start=offset
    )

    # Map internal status to simplified status for store staff
    status_map = {
        "Draft": "Draft",
        "Submitted": "Processing",
        "Pending Review": "Processing",
        "Mismatch Review": "Processing",
        "OCR Failed": "Processing",
        "Approved": "Approved",
        "Rejected": "Rejected"
    }

    for exp in expenses:
        exp["display_status"] = status_map.get(exp["status"], "Processing")

    return {"success": True, "data": expenses}


@frappe.whitelist()
def get_expense_status(expense_name: str):
    """
    Get simplified status for a specific expense.
    Store staff sees only basic status, not internal details.
    """
    expense = frappe.get_doc("BEI Expense Request", expense_name)

    # Verify ownership
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        "name"
    )

    if expense.employee != employee:
        frappe.throw(_("Access denied"))

    status_map = {
        "Draft": "Draft",
        "Submitted": "Processing",
        "Pending Review": "Processing",
        "Mismatch Review": "Processing",
        "OCR Failed": "Processing",
        "Approved": "Approved",
        "Rejected": "Rejected - Please resubmit with clearer receipt"
    }

    return {
        "success": True,
        "data": {
            "name": expense.name,
            "status": status_map.get(expense.status, "Processing"),
            "manual_vendor": expense.manual_vendor,
            "manual_description": expense.manual_description,
            "manual_amount": expense.manual_amount,
            "request_date": expense.request_date
        }
    }

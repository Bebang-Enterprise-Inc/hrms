# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Tax API — BIR Form 2307 (Certificate of Creditable Tax Withheld At Source)

Endpoints:
  get_form_2307_list       — list with filters
  get_form_2307_detail     — single doc full detail
  generate_form_2307       — create one Form 2307
  batch_generate_form_2307 — idempotent batch generation from PI EWT lines
  approve_form_2307        — For Review → Approved (Accounts Manager only)
  download_form_2307_pdf   — generate and stream BIR 2307 PDF via reportlab
"""

import os
import tempfile

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, get_first_day, get_last_day, nowdate


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# BIR ATC code → EWT rate (DM-3: never deviate from schedule)
ATC_EWT_RATES = {
	"WC010": 5.0,
	"WC020": 10.0,
	"WC100": 5.0,
	"WC120": 2.0,
	"WC140": 1.0,
	"WC158": 1.0,
	"WC160": 10.0,
	"WI010": 20.0,
}

# Full select-option label for each ATC code (matches DocType JSON options)
ATC_LABELS = {
	"WC010": "WC010 - EWT on professionals (individuals) 5%",
	"WC020": "WC020 - EWT on professionals (corporations) 10%",
	"WC100": "WC100 - EWT on rentals (real property) 5%",
	"WC120": "WC120 - EWT on services (contractors) 2%",
	"WC140": "WC140 - EWT on goods 1%",
	"WC158": "WC158 - EWT on purchase of goods 1%",
	"WC160": "WC160 - EWT on commissions 10%",
	"WI010": "WI010 - EWT on interest (savings) 20%",
}

_PAGE_SIZE_MAX = 100


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_accounts_manager():
	"""Raise PermissionError unless caller has Accounts Manager or System Manager role."""
	allowed = {"Accounts Manager", "System Manager"}
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & allowed):
		frappe.throw(_("Only Accounts Manager can perform this action"), frappe.PermissionError)


def _parse_atc_code(atc_code_value):
	"""Extract short code from full select label, e.g. 'WC010 - EWT...' → 'WC010'."""
	if not atc_code_value:
		return None
	return atc_code_value.split(" ")[0].strip()


def _resolve_atc_label(atc_code):
	"""Given a short code like 'WC010', return the full select-option label."""
	return ATC_LABELS.get(atc_code, atc_code)


def _ewt_rate_for_atc(atc_code):
	"""Return the BIR-mandated EWT rate for a short ATC code."""
	return ATC_EWT_RATES.get(atc_code)


# ---------------------------------------------------------------------------
# 1. List
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_form_2307_list(status=None, supplier=None, period_from=None, period_to=None,
                       page=1, page_size=20):
	"""
	List BEI Form 2307 documents with optional filters.

	Returns: {total, page, page_size, data: [...]}
	"""
	if not frappe.has_permission("BEI Form 2307", "read"):
		frappe.throw(_("No permission to read Form 2307"), frappe.PermissionError)

	page = max(1, cint(page))
	page_size = min(max(1, cint(page_size)), _PAGE_SIZE_MAX)

	filters = {}
	if status:
		filters["status"] = status
	if supplier:
		filters["supplier"] = supplier
	if period_from:
		filters["tax_period_from"] = [">=", getdate(period_from)]
	if period_to:
		filters["tax_period_to"] = ["<=", getdate(period_to)]

	total = frappe.db.count("BEI Form 2307", filters=filters)

	docs = frappe.get_list(
		"BEI Form 2307",
		filters=filters,
		fields=["name", "supplier", "supplier_name", "supplier_tin", "status",
		        "tax_period_from", "tax_period_to", "atc_code",
		        "gross_amount", "ewt_rate", "ewt_amount", "creation"],
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
		order_by="creation desc",
	)

	return {"total": total, "page": page, "page_size": page_size, "data": docs}


# ---------------------------------------------------------------------------
# 2. Detail
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_form_2307_detail(name):
	"""
	Return full BEI Form 2307 document as dict.
	"""
	if not frappe.has_permission("BEI Form 2307", "read", doc=name):
		frappe.throw(_("No permission to read {0}").format(name), frappe.PermissionError)

	doc = frappe.get_doc("BEI Form 2307", name)
	return doc.as_dict()


# ---------------------------------------------------------------------------
# 3. Generate (single)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def generate_form_2307(supplier, period_from, period_to, atc_code,
                       gross_amount, ewt_rate=None):
	"""
	Create a new BEI Form 2307 document.

	- ewt_rate defaults to BIR schedule for atc_code if not supplied.
	- ewt_amount = gross_amount * ewt_rate / 100 (auto-calculated in controller).
	"""
	if not frappe.has_permission("BEI Form 2307", "create"):
		frappe.throw(_("No permission to create Form 2307"), frappe.PermissionError)

	short_atc = _parse_atc_code(atc_code) or atc_code
	expected_rate = _ewt_rate_for_atc(short_atc)
	if expected_rate is None:
		frappe.throw(_("Unknown ATC code: {0}").format(short_atc))

	resolved_rate = flt(ewt_rate) if ewt_rate else expected_rate

	doc = frappe.get_doc({
		"doctype": "BEI Form 2307",
		"supplier": supplier,
		"status": "Draft",
		"tax_period_from": getdate(period_from),
		"tax_period_to": getdate(period_to),
		"atc_code": _resolve_atc_label(short_atc),
		"gross_amount": flt(gross_amount),
		"ewt_rate": resolved_rate,
	})
	doc.insert(ignore_permissions=True)

	return {"name": doc.name, "status": doc.status, "ewt_amount": doc.ewt_amount}


# ---------------------------------------------------------------------------
# 4. Batch generate
# ---------------------------------------------------------------------------

@frappe.whitelist()
def batch_generate_form_2307(month, year):
	"""
	Idempotently generate Form 2307 from Purchase Invoice EWT line items
	for the given month/year period.

	Skips suppliers for whom a Form 2307 already exists for this period.

	Returns: {created: int, skipped: int, errors: [...]}
	"""
	_require_accounts_manager()

	month = cint(month)
	year = cint(year)
	if not (1 <= month <= 12) or year < 2020:
		frappe.throw(_("Invalid month ({0}) or year ({1})").format(month, year))

	import datetime
	period_from = datetime.date(year, month, 1)
	# Last day of month
	if month == 12:
		period_to = datetime.date(year, 12, 31)
	else:
		period_to = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

	period_from_str = period_from.strftime("%Y-%m-%d")
	period_to_str = period_to.strftime("%Y-%m-%d")

	# Fetch EWT lines from submitted Purchase Invoices for this period
	ewt_lines = frappe.db.sql("""
		SELECT
			pi.supplier,
			pi.supplier_name,
			ptd.account_head,
			ptd.tax_amount,
			ptd.description
		FROM `tabPurchase Invoice` pi
		JOIN `tabPurchase Taxes and Charges` ptd ON ptd.parent = pi.name
		WHERE pi.docstatus = 1
		  AND pi.posting_date BETWEEN %(from)s AND %(to)s
		  AND ptd.tax_amount < 0
		ORDER BY pi.supplier
	""", {"from": period_from_str, "to": period_to_str}, as_dict=True)

	if not ewt_lines:
		return {"created": 0, "skipped": 0, "errors": [],
		        "message": "No EWT lines found for this period"}

	# Aggregate by supplier
	from collections import defaultdict
	supplier_totals = defaultdict(lambda: {"gross_amount": 0.0, "ewt_amount": 0.0})

	for line in ewt_lines:
		supplier_totals[line.supplier]["ewt_amount"] += abs(flt(line.tax_amount))

	# Derive gross amounts from PI totals for the period
	pi_totals = frappe.db.sql("""
		SELECT supplier, SUM(net_total) AS net_total
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1
		  AND posting_date BETWEEN %(from)s AND %(to)s
		GROUP BY supplier
	""", {"from": period_from_str, "to": period_to_str}, as_dict=True)

	for row in pi_totals:
		supplier_totals[row.supplier]["gross_amount"] = flt(row.net_total)

	created = 0
	skipped = 0
	errors = []

	for supplier, totals in supplier_totals.items():
		# Idempotency: skip if Form 2307 already exists for this supplier+period
		existing = frappe.db.exists("BEI Form 2307", {
			"supplier": supplier,
			"tax_period_from": period_from_str,
			"tax_period_to": period_to_str,
		})
		if existing:
			skipped += 1
			continue

		gross = totals["gross_amount"]
		ewt = totals["ewt_amount"]

		# Derive approximate rate — default WC120 (services 2%) if ambiguous
		if gross and ewt:
			approx_rate = round((ewt / gross) * 100, 0)
			# Match to nearest BIR rate
			best_atc = "WC120"
			min_diff = float("inf")
			for code, rate in ATC_EWT_RATES.items():
				if abs(rate - approx_rate) < min_diff:
					min_diff = abs(rate - approx_rate)
					best_atc = code
		else:
			best_atc = "WC120"

		expected_rate = ATC_EWT_RATES[best_atc]

		try:
			doc = frappe.get_doc({
				"doctype": "BEI Form 2307",
				"supplier": supplier,
				"status": "Draft",
				"tax_period_from": period_from_str,
				"tax_period_to": period_to_str,
				"atc_code": _resolve_atc_label(best_atc),
				"gross_amount": gross,
				"ewt_rate": expected_rate,
			})
			doc.insert(ignore_permissions=True)
			created += 1
		except Exception as e:
			errors.append({"supplier": supplier, "error": str(e)})

	return {"created": created, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# 5. Approve
# ---------------------------------------------------------------------------

@frappe.whitelist()
def approve_form_2307(name):
	"""
	Transition BEI Form 2307 from 'For Review' to 'Approved'.
	Requires Accounts Manager role.
	"""
	_require_accounts_manager()

	doc = frappe.get_doc("BEI Form 2307", name)
	if doc.status != "For Review":
		frappe.throw(
			_("Cannot approve Form 2307 '{0}' — current status is '{1}', expected 'For Review'").format(
				name, doc.status
			)
		)

	# status has allow_on_submit=1, so direct db update is fine post-submission
	frappe.db.set_value("BEI Form 2307", name, "status", "Approved")
	frappe.db.commit()

	return {"name": name, "status": "Approved"}


# ---------------------------------------------------------------------------
# 6. Download PDF
# ---------------------------------------------------------------------------

@frappe.whitelist()
def download_form_2307_pdf(name):
	"""
	Generate a BIR Form 2307 approximation PDF using reportlab and stream it
	to the caller as a file download.
	"""
	if not frappe.has_permission("BEI Form 2307", "read", doc=name):
		frappe.throw(_("No permission to read {0}").format(name), frappe.PermissionError)

	doc = frappe.get_doc("BEI Form 2307", name)

	try:
		from reportlab.lib.pagesizes import A4
		from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
		from reportlab.lib.units import cm
		from reportlab.lib import colors
		from reportlab.platypus import (
			SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
		)
	except ImportError:
		frappe.throw(_("reportlab is not installed. Please run: pip install reportlab"))

	# Build PDF in a temp file
	tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=frappe.get_site_path("private", "files"))
	os.close(tmp_fd)

	try:
		_build_2307_pdf(doc, tmp_path)
		with open(tmp_path, "rb") as f:
			pdf_bytes = f.read()
	finally:
		try:
			os.unlink(tmp_path)
		except OSError:
			pass

	filename = "BIR_2307_{0}.pdf".format(name.replace("/", "-"))

	frappe.local.response.filename = filename
	frappe.local.response.filecontent = pdf_bytes
	frappe.local.response.type = "download"


def _build_2307_pdf(doc, output_path):
	"""
	Render BIR Form 2307 layout into output_path using reportlab.
	Approximates the official BIR certificate layout.
	"""
	from reportlab.lib.pagesizes import A4
	from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
	from reportlab.lib.units import cm
	from reportlab.lib import colors
	from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

	styles = getSampleStyleSheet()
	title_style = ParagraphStyle(
		"Title2307",
		parent=styles["Title"],
		fontSize=13,
		spaceAfter=4,
	)
	header_style = ParagraphStyle(
		"Header2307",
		parent=styles["Normal"],
		fontSize=9,
		spaceAfter=2,
	)
	label_style = ParagraphStyle(
		"Label",
		parent=styles["Normal"],
		fontSize=8,
		textColor=colors.grey,
	)
	value_style = ParagraphStyle(
		"Value",
		parent=styles["Normal"],
		fontSize=10,
		fontName="Helvetica-Bold",
	)

	story = []

	# --- Header ---
	story.append(Paragraph("Republic of the Philippines", header_style))
	story.append(Paragraph("Department of Finance — Bureau of Internal Revenue", header_style))
	story.append(Spacer(1, 0.3 * cm))
	story.append(Paragraph("BIR FORM No. 2307", title_style))
	story.append(Paragraph(
		"Certificate of Creditable Tax Withheld At Source",
		ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11, spaceAfter=6)
	))
	story.append(Spacer(1, 0.5 * cm))

	# --- Supplier Info Table ---
	atc_short = _parse_atc_code(doc.atc_code) or (doc.atc_code or "")
	period_from_str = str(doc.tax_period_from) if doc.tax_period_from else "—"
	period_to_str = str(doc.tax_period_to) if doc.tax_period_to else "—"
	gross_str = "PHP {:,.2f}".format(flt(doc.gross_amount))
	rate_str = "{:.2f}%".format(flt(doc.ewt_rate))
	ewt_str = "PHP {:,.2f}".format(flt(doc.ewt_amount))

	info_data = [
		["Document No.", doc.name, "Status", doc.status or "Draft"],
		["Supplier TIN", doc.supplier_tin or "—", "ATC Code", atc_short],
		["Supplier Name", doc.supplier_name or doc.supplier, "", ""],
		["Tax Period From", period_from_str, "Tax Period To", period_to_str],
		["Gross Amount", gross_str, "EWT Rate", rate_str],
		["EWT Amount Withheld", ewt_str, "", ""],
	]

	info_table = Table(info_data, colWidths=[4 * cm, 7 * cm, 4 * cm, 5 * cm])
	info_table.setStyle(TableStyle([
		("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
		("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0f0f0")),
		("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
		("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
		("FONTSIZE", (0, 0), (-1, -1), 9),
		("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
		("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
		("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
		("TOPPADDING", (0, 0), (-1, -1), 5),
		("BOTTOMPADDING", (0, 0), (-1, -1), 5),
	]))

	story.append(info_table)
	story.append(Spacer(1, 1 * cm))

	# --- Certification text ---
	cert_text = (
		"This is to certify that the taxes shown above were withheld and remitted in accordance with "
		"the provisions of the National Internal Revenue Code, as amended, and its implementing rules "
		"and regulations."
	)
	story.append(Paragraph(cert_text, styles["Normal"]))
	story.append(Spacer(1, 1.5 * cm))

	# --- Signature block ---
	sig_data = [
		["Authorized Signature", "", "Date"],
		["", "", ""],
		["Name and Designation of Signatory", "", ""],
	]
	sig_table = Table(sig_data, colWidths=[10 * cm, 2 * cm, 8 * cm])
	sig_table.setStyle(TableStyle([
		("LINEABOVE", (0, 1), (0, 1), 1, colors.black),
		("LINEABOVE", (2, 1), (2, 1), 1, colors.black),
		("FONTSIZE", (0, 0), (-1, -1), 8),
		("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
	]))
	story.append(sig_table)

	pdf = SimpleDocTemplate(
		output_path,
		pagesize=A4,
		topMargin=1.5 * cm,
		bottomMargin=1.5 * cm,
		leftMargin=2 * cm,
		rightMargin=2 * cm,
	)
	pdf.build(story)

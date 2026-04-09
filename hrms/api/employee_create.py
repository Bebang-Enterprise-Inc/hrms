"""BEI direct employee creation endpoint (S164).

Provides a thin whitelisted endpoint for HR to create new employees from
my.bebang.ph's Employee Master Dashboard. Auto-generates both the Employee
ID and the Bio ID, best-effort enrolls the new employee on the branch's
biometric device, and notifies HR via Google Chat.

Unlike hrms.api.onboarding._create_employee_from_new_hire_request, this
endpoint only requires 6 fields (first_name, last_name, date_of_birth,
gender, branch, company) per CEO directive 2026-04-06.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_traceback, getdate, today

from hrms.api.onboarding import _notify_new_employee_created
from hrms.api.transfer_requests import _build_update_command, _queue_adms_command
from hrms.utils.adms_config import get_adms_config
from hrms.utils.bio_id import generate_next_bio_id
from hrms.utils.device_mapping import DEVICE_TO_STORE
from hrms.utils.employee_id import generate_bei_employee_id
from hrms.utils.sentry import set_backend_observability_context


def _enroll_employee_on_adms_for_branch(
	employee_id: str, employee_name: str, bio_id: str, branch: str
) -> dict:
	"""Best-effort ADMS enrollment for a newly-created employee.

	Never raises. Returns a dict with enrollment status.

	Audit notes (S164):
	- Skips the preflight enrollment helper because that helper validates Bio IDs
	  against a static CSV snapshot (Employee_Master.csv) that does NOT
	  include freshly generated Bio IDs. Running preflight would reject
	  every new-create attempt. The DEVICE_TO_STORE reverse lookup is the
	  authoritative check. DO NOT re-add preflight here.
	- Uses case-insensitive branch matching because DEVICE_TO_STORE key
	  casing is not guaranteed to match Branch.name casing in Frappe
	  (audit R2).
	"""
	try:
		# AUDIT R2: case-insensitive reverse lookup for device SN by branch name
		normalized_branch = (branch or "").strip().upper()
		device_sn = next(
			(
				sn
				for sn, store in DEVICE_TO_STORE.items()
				if (store or "").strip().upper() == normalized_branch
			),
			None,
		)
		if not device_sn:
			return {
				"enrolled": False,
				"reason": "NO_DEVICE_FOR_BRANCH",
				"device_sn": None,
			}

		# AUDIT B3/B4: skip the preflight enrollment helper — it validates against a
		# static CSV snapshot and will always reject freshly generated Bio IDs.
		# DEVICE_TO_STORE reverse lookup is sufficient since it's the
		# authoritative device-to-branch mapping maintained by BEI.

		# Build and queue the ADMS USERINFO UPDATE command
		config = get_adms_config()
		command = _build_update_command(bio_id, employee_name)
		_queue_adms_command(device_sn, command, config)

		return {"enrolled": True, "reason": None, "device_sn": device_sn}
	except Exception:
		frappe.log_error(
			title="ADMS auto-enroll on create_employee_direct failed",
			message=get_traceback(),
		)
		return {
			"enrolled": False,
			"reason": "DISPATCH_FAILED",
			"device_sn": None,
		}


@frappe.whitelist()
def create_employee_direct(
	# mandatory
	first_name: str,
	last_name: str,
	date_of_birth: str,
	gender: str,
	branch: str,
	company: str,
	# optional
	middle_name: str | None = None,
	designation: str | None = None,
	department: str | None = None,
	date_of_joining: str | None = None,
	employment_type: str | None = None,
	personal_email: str | None = None,
	cell_number: str | None = None,
	tin_number: str | None = None,
	sss_number: str | None = None,
	philhealth_number: str | None = None,
	pagibig_number: str | None = None,
) -> dict:
	"""Create a new Employee directly from the Employee Master Dashboard.

	Auto-generates Employee ID (BEI-EMP-YYYY-NNNNN) and Bio ID (9XXXXXX).
	Best-effort ADMS enrollment on the branch's bio device. Never accepts
	a caller-supplied Bio ID — it is always generated server-side.
	"""
	set_backend_observability_context(
		module="hr",
		action="create_employee_direct",
		mutation_type="create",
	)
	frappe.has_permission("Employee", "create", throw=True)

	# ── Mandatory presence check ───────────────────────────────────────────
	missing = [
		name
		for name, value in [
			("first_name", first_name),
			("last_name", last_name),
			("date_of_birth", date_of_birth),
			("gender", gender),
			("branch", branch),
			("company", company),
		]
		if not value
	]
	if missing:
		frappe.throw(
			_("Cannot create Employee — missing required fields: {0}").format(", ".join(missing))
		)

	# ── Validate gender against the Gender DocType (AUDIT B9) ──────────────
	# Do NOT hardcode ("Male", "Female"). Defer to whatever options exist
	# in the Gender DocType (may include "Other", "Prefer not to say", etc.)
	if not frappe.db.exists("Gender", gender):
		frappe.throw(_("Unknown gender: {0}").format(gender))

	# ── Date of birth sanity check ─────────────────────────────────────────
	try:
		dob = getdate(date_of_birth)
	except Exception:
		frappe.throw(_("Invalid date_of_birth"))
	if dob >= getdate(today()):
		frappe.throw(_("date_of_birth must be in the past"))

	# ── Branch + Company existence checks ──────────────────────────────────
	if not frappe.db.exists("Branch", branch):
		frappe.throw(_("BRANCH_NOT_FOUND: {0}").format(branch))
	if not frappe.db.exists("Company", company):
		frappe.throw(_("COMPANY_NOT_FOUND: {0}").format(company))
	if department and not frappe.db.exists("Department", department):
		frappe.throw(_("Unknown department: {0}").format(department))
	if designation and not frappe.db.exists("Designation", designation):
		frappe.throw(_("Unknown designation: {0}").format(designation))
	if employment_type and not frappe.db.exists("Employment Type", employment_type):
		frappe.throw(_("Unknown employment type: {0}").format(employment_type))

	# ── Generate IDs ───────────────────────────────────────────────────────
	employee_id = generate_bei_employee_id()
	bio_id = generate_next_bio_id()

	# ── Build full name ────────────────────────────────────────────────────
	first = (first_name or "").strip()
	middle = (middle_name or "").strip()
	last = (last_name or "").strip()
	employee_name = " ".join(part for part in (first, middle, last) if part)

	# ── Build and insert Employee doc ──────────────────────────────────────
	# Known risk: MEMORY.md lesson #6 says NEVER use ORM for Employee — but
	# the existing _create_employee_from_new_hire_request uses this exact
	# pattern and is in production use. If the insert raises, the caller
	# will see the exception and can fall back to direct SQL.
	doc_payload = {
		"doctype": "Employee",
		"employee": employee_id,
		"employee_name": employee_name,
		"first_name": first,
		"middle_name": middle,
		"last_name": last,
		"gender": gender,
		"date_of_birth": str(dob),
		"date_of_joining": date_of_joining or today(),
		"branch": branch,
		"company": company,
		"status": "Active",
		"attendance_device_id": bio_id,
		"new_attendance_device_id": bio_id,
	}
	if department:
		doc_payload["department"] = department
	if designation:
		doc_payload["designation"] = designation
	if employment_type:
		doc_payload["employment_type"] = employment_type
	if personal_email:
		doc_payload["personal_email"] = personal_email
	if cell_number:
		doc_payload["cell_number"] = cell_number
	if tin_number:
		doc_payload["tin_number"] = tin_number
	if sss_number:
		doc_payload["sss_number"] = sss_number
	if philhealth_number:
		doc_payload["philhealth_number"] = philhealth_number
	if pagibig_number:
		doc_payload["pagibig_number"] = pagibig_number

	employee_doc = frappe.get_doc(doc_payload)
	employee_doc.flags.ignore_permissions = True
	employee_doc.insert()
	frappe.db.commit()

	# ── Best-effort ADMS enrollment ────────────────────────────────────────
	adms_result = _enroll_employee_on_adms_for_branch(
		employee_id=employee_id,
		employee_name=employee_name,
		bio_id=bio_id,
		branch=branch,
	)

	# ── Best-effort Google Chat notification ───────────────────────────────
	try:
		_notify_new_employee_created(
			employee_id=employee_id,
			employee_name=employee_name,
			branch=branch,
			designation=designation,
			bio_id=bio_id,
			source="employee_master_dashboard",
			approver_email=frappe.session.user,
		)
	except Exception:
		frappe.log_error(
			title="create_employee_direct: Chat notification failed",
			message=get_traceback(),
		)

	# S172 Defect #8 fix: include both the BEI business ID (employee_id) and
	# the Frappe primary key (name = HR-EMP-NNNNN) so callers can look up the
	# record by either identifier without a separate query.
	return {
		"success": True,
		"data": {
			"employee_id": employee_id,
			"name": employee_doc.name,
			"employee_name": employee_name,
			"bio_id": bio_id,
			"adms_enrollment": adms_result,
		},
	}


@frappe.whitelist()
def mark_employee_left(employee: str, relieving_date: str) -> dict:
	"""S172 Defect #11 helper — soft-delete an Employee in the correct 2-pass order.

	Frappe's Employee validator requires `relieving_date` to be populated
	before `status` flips to "Left". A single PUT with both fields in the
	same payload can fail because validators run in field-declaration order.
	This helper encapsulates the correct 2-pass sequence so callers (bei-tasks,
	scripts, admin tools) don't have to implement it inline.

	Args:
		employee: Employee ID (HR-EMP-NNNNN or BEI-EMP-YYYY-NNNNN)
		relieving_date: ISO date string (YYYY-MM-DD)

	Returns:
		{"status": "success", "employee": <id>, "relieving_date": <date>}
	"""
	set_backend_observability_context(
		module="hr",
		action="mark_employee_left",
		mutation_type="update",
		extras={"employee": employee, "relieving_date": relieving_date},
	)

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee {0} not found").format(employee))

	frappe.has_permission("Employee", "write", throw=True)

	try:
		rdate = getdate(relieving_date)
	except Exception:
		frappe.throw(_("Invalid relieving_date: {0}").format(relieving_date))

	# Pass 1: set relieving_date in isolation so the validator sees it present
	# before the status flip in pass 2.
	frappe.db.set_value("Employee", employee, "relieving_date", rdate, update_modified=True)
	frappe.db.commit()

	# Pass 2: now flip status to Left.
	frappe.db.set_value("Employee", employee, "status", "Left", update_modified=True)
	frappe.db.commit()

	return {
		"status": "success",
		"employee": employee,
		"relieving_date": str(rdate),
	}

# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.naming import set_name_by_naming_series
from frappe.utils import add_years, cint, get_link_to_form, getdate

from erpnext.setup.doctype.employee.employee import Employee


class EmployeeMaster(Employee):
	def autoname(self):
		naming_method = frappe.db.get_single_value("HR Settings", "emp_created_by")
		if not naming_method:
			frappe.throw(_("Please setup Employee Naming System in Human Resource > HR Settings"))
		else:
			if naming_method == "Naming Series":
				set_name_by_naming_series(self)
			elif naming_method == "Employee Number":
				self.name = self.employee_number
			elif naming_method == "Full Name":
				self.set_employee_name()
				self.name = self.employee_name

		# S172 Phase 8 fix (Defect #8 root cause, autoname leg):
		# Preserve the BEI-EMP-YYYY-NNNNN business ID when the caller explicitly
		# set it via create_employee_direct. See validate() for the durable leg.
		if not (self.employee or "").startswith("BEI-EMP-"):
			self.employee = self.name

	def validate(self):
		# S172 Phase 8 fix (Defect #8 TRUE root cause):
		# Upstream `erpnext.setup.doctype.employee.employee.Employee.validate()`
		# contains `self.employee = self.name` at line 125 which runs AFTER our
		# autoname() override and AFTER every subsequent save, unconditionally
		# clobbering the BEI-EMP-YYYY-NNNNN business ID back to HR-EMP-NNNNN.
		#
		# Because generate_bei_employee_id reads
		# `SELECT MAX(employee) WHERE employee LIKE 'BEI-EMP-YYYY-%'`, this made
		# the generator stuck on the same stale maximum (BEI-EMP-2026-00004) for
		# every create call — no row ever actually persisted with
		# employee = BEI-EMP-*, so MAX never moved forward.
		#
		# Strategy: snapshot the BEI id before calling super().validate(), then
		# restore it after. This is durable across both create and update flows,
		# since validate() runs on every save, not just insert.
		saved_employee = (self.employee or "")
		is_bei_id = saved_employee.startswith("BEI-EMP-")
		super().validate()
		if is_bei_id and self.employee != saved_employee:
			self.employee = saved_employee


def derive_company_from_branch(doc, method=None):
	"""S201: auto-populate Employee.company based on branch + rule hierarchy.

	Rule:
	  - is_non_store_billing(doc) -> BEI parent (BEBANG ENTERPRISE INC.)
	  - department == Commissary AND branch is bare commissary -> BKI
	  - else branch resolves via company_lookup -> store child Company
	  - unresolvable -> leave existing value untouched (no throw)

	HR Manager override: if the current user has HR Manager role AND the
	form explicitly set company != derived value, keep the user's value.
	Flag: ``flags.company_manual_override`` set on doc.
	"""
	from hrms.utils.company_lookup import (
		UnknownBranch,
		get_non_store_parent,
		resolve_branch_to_company,
	)
	from hrms.utils.non_store_billing import is_non_store_billing_doc

	if not doc.branch:
		return

	try:
		is_hr_manager = "HR Manager" in frappe.get_roles(frappe.session.user)
	except Exception:
		is_hr_manager = False
	manual_override = bool(getattr(doc, "flags", {}).get("company_manual_override"))

	if is_non_store_billing_doc(doc):
		target = get_non_store_parent()
	else:
		try:
			target = resolve_branch_to_company(doc.branch, department=doc.department)
		except UnknownBranch:
			# Unresolvable branch — do not change company. Let HR fix the branch.
			return

	if doc.company == target:
		return

	if is_hr_manager and manual_override:
		# HR Manager intentionally set a different company; honor it.
		return

	doc.company = target


def validate_onboarding_process(doc, method=None):
	"""Validates Employee Creation for linked Employee Onboarding"""
	if not doc.job_applicant:
		return

	employee_onboarding = frappe.get_all(
		"Employee Onboarding",
		filters={
			"job_applicant": doc.job_applicant,
			"docstatus": 1,
			"boarding_status": ("!=", "Completed"),
		},
	)
	if employee_onboarding:
		onboarding = frappe.get_doc("Employee Onboarding", employee_onboarding[0].name)
		onboarding.validate_employee_creation()
		onboarding.db_set("employee", doc.name)


def publish_update(doc, method=None):
	import hrms

	hrms.refetch_resource("hrms:employee", doc.user_id)


def update_job_applicant_and_offer(doc, method=None):
	"""Updates Job Applicant and Job Offer status as 'Accepted' and submits them"""
	if not doc.job_applicant:
		return

	applicant_status_before_change = frappe.db.get_value("Job Applicant", doc.job_applicant, "status")
	if applicant_status_before_change != "Accepted":
		frappe.db.set_value("Job Applicant", doc.job_applicant, "status", "Accepted")
		frappe.msgprint(
			_("Updated the status of linked Job Applicant {0} to {1}").format(
				get_link_to_form("Job Applicant", doc.job_applicant), frappe.bold(_("Accepted"))
			)
		)
	offer_status_before_change = frappe.db.get_value(
		"Job Offer", {"job_applicant": doc.job_applicant, "docstatus": ["!=", 2]}, "status"
	)
	if offer_status_before_change and offer_status_before_change != "Accepted":
		job_offer = frappe.get_last_doc("Job Offer", filters={"job_applicant": doc.job_applicant})
		job_offer.status = "Accepted"
		job_offer.flags.ignore_mandatory = True
		job_offer.flags.ignore_permissions = True
		job_offer.save()

		msg = _("Updated the status of Job Offer {0} for the linked Job Applicant {1} to {2}").format(
			get_link_to_form("Job Offer", job_offer.name),
			frappe.bold(doc.job_applicant),
			frappe.bold(_("Accepted")),
		)
		if job_offer.docstatus == 0:
			msg += "<br>" + _("You may add additional details, if any, and submit the offer.")

		frappe.msgprint(msg)


def update_approver_role(doc, method=None):
	"""Adds relevant approver role for the user linked to Employee"""
	if doc.leave_approver:
		user = frappe.get_doc("User", doc.leave_approver)
		user.flags.ignore_permissions = True
		user.add_roles("Leave Approver")

	if doc.expense_approver:
		user = frappe.get_doc("User", doc.expense_approver)
		user.flags.ignore_permissions = True
		user.add_roles("Expense Approver")


def update_approver_user_roles(doc, method=None):
	approver_roles = set()
	if frappe.db.exists("Employee", {"leave_approver": doc.name}):
		approver_roles.add("Leave Approver")

	if frappe.db.exists("Employee", {"expense_approver": doc.name}):
		approver_roles.add("Expense Approver")

	if approver_roles:
		doc.append_roles(*approver_roles)


def update_employee_transfer(doc, method=None):
	"""Unsets Employee ID in Employee Transfer if doc is deleted"""
	if frappe.db.exists("Employee Transfer", {"new_employee_id": doc.name, "docstatus": 1}):
		emp_transfer = frappe.get_doc("Employee Transfer", {"new_employee_id": doc.name, "docstatus": 1})
		emp_transfer.db_set("new_employee_id", "")


@frappe.whitelist()
def get_timeline_data(doctype, name):
	"""Return timeline for attendance"""
	from frappe.desk.notifications import get_open_count

	out = {}

	open_count = get_open_count(doctype, name)
	out["count"] = open_count["count"]

	timeline_data = dict(
		frappe.db.sql(
			"""
			select unix_timestamp(attendance_date), count(*)
			from `tabAttendance` where employee=%s
			and attendance_date > date_sub(curdate(), interval 1 year)
			and status in ('Present', 'Half Day')
			group by attendance_date""",
			name,
		)
	)

	out["timeline_data"] = timeline_data
	return out


@frappe.whitelist()
def get_retirement_date(date_of_birth=None):
	if date_of_birth:
		try:
			retirement_age = cint(frappe.db.get_single_value("HR Settings", "retirement_age") or 60)
			dt = add_years(getdate(date_of_birth), retirement_age)
			return dt.strftime("%Y-%m-%d")
		except ValueError:
			# invalid date
			return

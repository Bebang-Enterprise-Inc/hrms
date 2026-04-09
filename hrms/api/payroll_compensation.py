"""Payroll Compensation & Sensitive Data Controls API (S114).

Owns two domains:
1. Compensation management — salary/allowance/bonus/earnings/deductions grid,
   bulk changes, effective dating, approval chain (HR Manager → Accounts Manager).
2. Sensitive-data dual-control — bank account, TIN, SSS, PhilHealth, Pag-IBIG
   changes require HR + Finance joint approval before activation.

This file is S114's exclusive property.  Do NOT add payroll query/reporting
logic here (that lives in payroll.py).  Do NOT duplicate enrichment approval
logic (enrichment.py routes sensitive fields into this module's queue).
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime, today, getdate, add_months, flt

from hrms.utils.sentry import set_backend_observability_context


# ============================================================================
# 2025 Philippine Statutory Computation Helpers
# Sources: SSS Circular 2024-005, PhilHealth Circular 2024-0009, HDMF Circular 417
# TRAIN Law: R.A. 10963 (permanent rates effective 2023+)
# ============================================================================


def compute_sss_employee(base):
	"""SSS employee share: map base to MSC bracket (₱500 intervals), then MSC × 4.5%.

	HARD BLOCKER: This MUST be a table lookup, NOT base * 0.045.
	MSC range: ₱5,000 to ₱35,000 (2025 ceiling per SSS Circular 2024-005).
	"""
	if not base or base <= 0:
		return 0
	# Map to nearest MSC bracket at ₱500 intervals, floor ₱5,000, cap ₱35,000
	msc = min(max(round(base / 500) * 500, 5000), 35000)
	return round(msc * 0.045, 2)


def compute_sss_employer(base):
	"""SSS employer share: MSC × 9.5%."""
	if not base or base <= 0:
		return 0
	msc = min(max(round(base / 500) * 500, 5000), 35000)
	return round(msc * 0.095, 2)


def compute_philhealth_employee(base):
	"""PhilHealth employee: 2.5% of base, floor ₱250/mo, cap ₱2,500/mo.

	Per PhilHealth Circular 2024-0009: 5% total (2.5% each side).
	Floor: ₱10,000 MBS → min ₱250 employee share.
	Cap: ₱100,000 MBS → max ₱2,500 employee share.
	"""
	if not base or base <= 0:
		return 0
	return round(max(min(base * 0.025, 2500), 250), 2)


def compute_philhealth_employer(base):
	"""PhilHealth employer: same as employee share."""
	return compute_philhealth_employee(base)


def compute_pagibig_employee(base):
	"""Pag-IBIG employee: 1% if base ≤ ₱1,500; 2% if > ₱1,500; cap ₱100/mo.

	Per HDMF Circular 417: two-tier rate structure.
	"""
	if not base or base <= 0:
		return 0
	if base <= 1500:
		return round(base * 0.01, 2)
	return round(min(base * 0.02, 100), 2)


def compute_pagibig_employer(base):
	"""Pag-IBIG employer: always 2%, cap ₱100/mo."""
	if not base or base <= 0:
		return 0
	return round(min(base * 0.02, 100), 2)


def compute_monthly_tax(base):
	"""TRAIN Law 2025 monthly income tax estimate.

	Annualize base × 12, apply brackets, divide by 12.
	Per BIR RR 11-2018 (TRAIN Law, R.A. 10963). Permanent rates from 2023+.
	"""
	if not base or base <= 0:
		return 0
	annual = base * 12
	if annual <= 250000:
		tax = 0
	elif annual <= 400000:
		tax = (annual - 250000) * 0.15
	elif annual <= 800000:
		tax = 22500 + (annual - 400000) * 0.20
	elif annual <= 2000000:
		tax = 102500 + (annual - 800000) * 0.25
	elif annual <= 8000000:
		tax = 402500 + (annual - 2000000) * 0.30
	else:
		tax = 2202500 + (annual - 8000000) * 0.35
	return round(tax / 12, 2)


# ============================================================================
# Constants
# ============================================================================

# Fields that go through the sensitive-change dual-control queue
SENSITIVE_FIELDS = frozenset({
	"bank_name",
	"bank_ac_no",
	"bank_account_name",
	"tin_number",
	"sss_number",
	"philhealth_number",
	"pagibig_number",
})

SENSITIVE_FIELD_LABELS = {
	"bank_name": "Bank Name",
	"bank_ac_no": "Bank Account Number",
	"bank_account_name": "Bank Account Name",
	"tin_number": "TIN",
	"sss_number": "SSS Number",
	"philhealth_number": "PhilHealth Number",
	"pagibig_number": "Pag-IBIG Number",
}


# ============================================================================
# Compensation Grid Endpoints (Phase 1)
# ============================================================================


@frappe.whitelist()
def get_compensation_grid(filters=None):
	"""Return employees with current salary structure, base salary, and components.

	Args:
		filters: JSON string or dict with optional keys:
			department, branch, employment_status, search (name/ID)
	"""
	set_backend_observability_context(
		module="payroll",
		action="get_compensation_grid",
		mutation_type="read",
	)

	if isinstance(filters, str):
		filters = json.loads(filters) if filters else {}
	filters = filters or {}

	conditions = ["e.status = 'Active'"]
	values = {}

	if filters.get("department"):
		conditions.append("e.department = %(department)s")
		values["department"] = filters["department"]

	if filters.get("branch"):
		conditions.append("e.branch = %(branch)s")
		values["branch"] = filters["branch"]

	if filters.get("employment_status"):
		conditions.append("e.employment_type = %(employment_status)s")
		values["employment_status"] = filters["employment_status"]

	if filters.get("search"):
		conditions.append(
			"(e.employee_name LIKE %(search)s OR e.name LIKE %(search)s)"
		)
		values["search"] = f"%{filters['search']}%"

	page = int(filters.get("page", 1))
	page_size = int(filters.get("page_size", 50))
	offset = (page - 1) * page_size

	where = " AND ".join(conditions)

	# Get total count
	count_sql = f"SELECT COUNT(*) FROM `tabEmployee` e WHERE {where}"
	total = frappe.db.sql(count_sql, values)[0][0]

	# Check if allowance custom fields exist in DB (safe for deploy-before-SSM)
	_allowance_fields = [
		"bei_comm_allow_monthly", "bei_deminimis_monthly", "bei_honorarium_monthly",
		"bei_meal_allow_monthly", "bei_gasoline_allow_monthly", "bei_other_fixed_monthly",
	]
	_existing_cols = {
		r[0] for r in frappe.db.sql("SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'")
	}
	_has_allowance_cols = all(f in _existing_cols for f in _allowance_fields)

	allowance_sql = ""
	if _has_allowance_cols:
		allowance_sql = """,
			COALESCE(e.bei_comm_allow_monthly, 0) AS bei_comm_allow_monthly,
			COALESCE(e.bei_deminimis_monthly, 0) AS bei_deminimis_monthly,
			COALESCE(e.bei_honorarium_monthly, 0) AS bei_honorarium_monthly,
			COALESCE(e.bei_meal_allow_monthly, 0) AS bei_meal_allow_monthly,
			COALESCE(e.bei_gasoline_allow_monthly, 0) AS bei_gasoline_allow_monthly,
			COALESCE(e.bei_other_fixed_monthly, 0) AS bei_other_fixed_monthly"""

	# Get employees with salary structure assignment + gov IDs + bank + allowances
	sql = f"""
		SELECT
			e.name AS employee,
			e.employee_name,
			e.department,
			e.branch,
			e.designation,
			e.employment_type,
			e.date_of_joining,
			ssa.salary_structure,
			ssa.base AS base_salary,
			ssa.income_tax_slab AS tax_slab,
			ssa.from_date AS ssa_from_date,
			ssa.payroll_payable_account,
			e.salary_mode,
			e.bank_name,
			e.bank_ac_no{allowance_sql}
		FROM `tabEmployee` e
		LEFT JOIN `tabSalary Structure Assignment` ssa
			ON ssa.employee = e.name
			AND ssa.docstatus = 1
			AND ssa.name = (
				SELECT ssa2.name
				FROM `tabSalary Structure Assignment` ssa2
				WHERE ssa2.employee = e.name
					AND ssa2.docstatus = 1
				ORDER BY ssa2.from_date DESC
				LIMIT 1
			)
		WHERE {where}
		ORDER BY e.employee_name ASC
		LIMIT %(limit)s OFFSET %(offset)s
	"""
	values["limit"] = page_size
	values["offset"] = offset

	employees = frappe.db.sql(sql, values, as_dict=True)

	if employees:
		emp_names = [e["employee"] for e in employees]

		# Compute daily rate (base / 26 working days)
		# and projected compensation from statutory rates
		for emp in employees:
			base = emp.get("base_salary") or 0
			emp["daily_rate"] = round(base / 26, 2) if base else None

			# Total allowances from payroll data (bei_* custom fields)
			allowances = (
				(emp.get("bei_comm_allow_monthly") or 0)
				+ (emp.get("bei_deminimis_monthly") or 0)
				+ (emp.get("bei_honorarium_monthly") or 0)
				+ (emp.get("bei_meal_allow_monthly") or 0)
				+ (emp.get("bei_gasoline_allow_monthly") or 0)
				+ (emp.get("bei_other_fixed_monthly") or 0)
			)
			emp["total_allowances"] = round(allowances, 2)

			# Projected gross = base + allowances
			emp["projected_gross"] = round(base + allowances, 2)
			emp["projected_sss"] = compute_sss_employee(base)
			emp["projected_philhealth"] = compute_philhealth_employee(base)
			emp["projected_pagibig"] = compute_pagibig_employee(base)
			emp["projected_tax"] = compute_monthly_tax(base)
			emp["projected_total_deductions"] = (
				emp["projected_sss"]
				+ emp["projected_philhealth"]
				+ emp["projected_pagibig"]
				+ emp["projected_tax"]
			)
			emp["projected_net"] = round(emp["projected_gross"] - emp["projected_total_deductions"], 2)
			emp["projected_company_cost"] = round(
				emp["projected_gross"]
				+ compute_sss_employer(base)
				+ compute_philhealth_employer(base)
				+ compute_pagibig_employer(base),
				2,
			)

		# Get pending compensation changes count per employee
		pending = frappe.db.sql(
			"""
			SELECT employee, COUNT(*) AS pending_count
			FROM `tabBEI Compensation Change`
			WHERE employee IN %(employees)s
				AND status IN ('Pending HR Manager', 'Pending Accounts Manager')
			GROUP BY employee
			""",
			{"employees": emp_names},
			as_dict=True,
		)
		pending_map = {p["employee"]: p["pending_count"] for p in pending}

		for emp in employees:
			emp["pending_changes"] = pending_map.get(emp["employee"], 0)

	return {
		"data": employees,
		"total": total,
		"page": page,
		"page_size": page_size,
		"total_pages": max(1, -(-total // page_size)),
	}


@frappe.whitelist()
def get_employee_compensation_detail(employee):
	"""Return full compensation detail for a single employee.

	Includes identity, salary structure, allowances, projected deductions,
	bank info, pending changes count, and last 10 compensation changes.
	"""
	set_backend_observability_context(
		module="payroll",
		action="get_employee_compensation_detail",
		mutation_type="read",
	)

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee {0} not found").format(employee), frappe.DoesNotExistError)

	# Employee identity + allowances
	emp_fields = [
		"name", "employee_name", "department", "branch", "designation",
		"employment_type", "date_of_joining", "salary_mode", "bank_name", "bank_ac_no", "bank_account_name",
	]

	# Check for bei_* custom fields
	_allowance_fields = [
		"bei_comm_allow_monthly", "bei_deminimis_monthly", "bei_honorarium_monthly",
		"bei_meal_allow_monthly", "bei_gasoline_allow_monthly", "bei_other_fixed_monthly",
	]
	_existing_cols = {
		r[0] for r in frappe.db.sql("SHOW COLUMNS FROM tabEmployee LIKE 'bei_%'")
	}
	_has_allowance_cols = all(f in _existing_cols for f in _allowance_fields)
	if _has_allowance_cols:
		emp_fields.extend(_allowance_fields)

	emp = frappe.db.get_value("Employee", employee, emp_fields, as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found").format(employee), frappe.DoesNotExistError)

	result = {
		"employee": emp.name,
		"employee_name": emp.employee_name,
		"department": emp.department,
		"branch": emp.branch,
		"designation": emp.designation,
		"employment_type": emp.employment_type,
		"date_of_joining": str(emp.date_of_joining) if emp.date_of_joining else None,
		"salary_mode": emp.salary_mode,
		"bank_name": emp.bank_name,
		"bank_ac_no": emp.bank_ac_no,
		"bank_account_name": emp.get("bank_account_name") or None,
	}

	# Mask bank account number
	if result.get("bank_ac_no") and len(result["bank_ac_no"]) > 4:
		result["bank_ac_no"] = "****" + result["bank_ac_no"][-4:]

	# Allowances
	for f in _allowance_fields:
		result[f] = float(emp.get(f) or 0) if _has_allowance_cols else 0

	# Latest SSA
	ssa = frappe.db.sql(
		"""
		SELECT base, salary_structure, income_tax_slab, from_date
		FROM `tabSalary Structure Assignment`
		WHERE employee = %s AND docstatus = 1
		ORDER BY from_date DESC LIMIT 1
		""",
		employee,
		as_dict=True,
	)
	if ssa:
		result["has_ssa"] = True
		result["base_salary"] = float(ssa[0].base or 0)
		result["salary_structure"] = ssa[0].salary_structure
		result["tax_slab"] = ssa[0].income_tax_slab
		result["ssa_from_date"] = str(ssa[0].from_date) if ssa[0].from_date else None
	else:
		# S172 Defect #21 fix: return stub so frontend Edit button can enable
		# and HR can set up the first salary for employees without SSA.
		result["has_ssa"] = False
		result["base_salary"] = 0
		result["salary_structure"] = None
		result["tax_slab"] = None
		result["ssa_from_date"] = None

	# Projected deductions
	base = result["base_salary"]
	result["projected_sss"] = compute_sss_employee(base)
	result["projected_philhealth"] = compute_philhealth_employee(base)
	result["projected_pagibig"] = compute_pagibig_employee(base)
	result["projected_tax"] = compute_monthly_tax(base)

	# Pending changes count
	pending_count = frappe.db.count(
		"BEI Compensation Change",
		filters={
			"employee": employee,
			"status": ("in", ["Pending HR Manager", "Pending Accounts Manager"]),
		},
	)
	result["pending_changes_count"] = pending_count

	# Last 10 compensation changes inline
	changes = frappe.get_all(
		"BEI Compensation Change",
		filters={"employee": employee},
		fields=[
			"name", "change_type", "salary_component", "employee_field_name",
			"old_value", "new_value", "effective_date", "reason",
			"status", "requested_by", "hr_reviewer", "final_approver",
			"approval_date", "rejection_reason", "submission_date",
		],
		order_by="creation DESC",
		limit_page_length=10,
	)
	result["changes"] = changes

	return result


@frappe.whitelist()
def get_compensation_history(employee):
	"""Return full change history for an employee's compensation.

	Args:
		employee: Employee ID
	"""
	set_backend_observability_context(
		module="payroll",
		action="get_compensation_history",
		mutation_type="read",
	)

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee {0} not found").format(employee))

	changes = frappe.get_all(
		"BEI Compensation Change",
		filters={"employee": employee},
		fields=[
			"name",
			"change_type",
			"salary_component",
			"old_value",
			"new_value",
			"effective_date",
			"reason",
			"status",
			"requested_by",
			"hr_reviewer",
			"final_approver",
			"approval_date",
			"rejection_reason",
			"submission_date",
		],
		order_by="creation DESC",
		limit_page_length=100,
	)

	return {"data": changes, "employee": employee}


@frappe.whitelist()
def update_compensation(
	employee,
	change_type,
	new_value,
	reason,
	effective_date,
	salary_component=None,
	bulk_employees=None,
):
	"""Create compensation change request(s) with history entry.

	Args:
		employee: Single employee ID (ignored if bulk_employees provided)
		change_type: Salary | Allowance | Bonus | Recurring Earning | Recurring Deduction
		new_value: New monetary value
		reason: Justification text
		effective_date: When the change takes effect
		salary_component: Required for non-Salary change types
		bulk_employees: JSON array of employee IDs for bulk operations
	"""
	set_backend_observability_context(
		module="payroll",
		action="update_compensation",
		mutation_type="create",
		extras={"change_type": change_type, "effective_date": effective_date},
	)

	# Validate change_type
	valid_types = ["Salary", "Allowance", "Bonus", "Recurring Earning", "Recurring Deduction"]
	if change_type not in valid_types:
		frappe.throw(_("Invalid change type: {0}").format(change_type))

	# Salary component required for non-Salary types
	if change_type != "Salary" and not salary_component:
		frappe.throw(_("Salary Component is required for {0} changes").format(change_type))

	new_value = float(new_value)
	if new_value < 0:
		frappe.throw(_("New value cannot be negative"))

	# Parse bulk employees
	if isinstance(bulk_employees, str):
		bulk_employees = json.loads(bulk_employees) if bulk_employees else None

	employee_list = bulk_employees or [employee]

	# S172 Phase 8 fix (Defect #16 unblock): when the originator is already an
	# HR Manager, the dual-control flow should skip the HR Manager stage and
	# send the request directly to Accounts Manager for final approval. An HR
	# Manager approving their own submission would defeat dual control; the
	# real second set of eyes in this case is the Accounts Manager. Without
	# this auto-advance, HR-originated comp changes got stranded at
	# "Pending HR Manager" because Finance's queue filters on
	# "Pending Accounts Manager" and never saw them — which is the exact failure
	# mode RT-S172-02 reproduced (the SSA-creation savepoint fix in
	# approve_compensation_change was never reached).
	submitter_roles = frappe.get_roles(frappe.session.user)
	initial_status = (
		"Pending Accounts Manager"
		if ("HR Manager" in submitter_roles or "System Manager" in submitter_roles)
		else "Pending HR Manager"
	)

	created = []
	for emp_id in employee_list:
		if not frappe.db.exists("Employee", emp_id):
			frappe.throw(_("Employee {0} not found").format(emp_id))

		# Get current value
		old_value = 0
		employee_field_name = None

		if change_type == "Salary":
			ssa = frappe.db.sql(
				"""
				SELECT base FROM `tabSalary Structure Assignment`
				WHERE employee = %s AND docstatus = 1
				ORDER BY from_date DESC LIMIT 1
				""",
				emp_id,
			)
			old_value = float(ssa[0][0]) if ssa else 0
		elif salary_component and salary_component.startswith("bei_"):
			# Direct Employee field allowances — read from Employee record
			old_value = float(frappe.db.get_value("Employee", emp_id, salary_component) or 0)
			employee_field_name = salary_component
		elif salary_component:
			# Look up current component amount from salary structure
			sd = frappe.db.sql(
				"""
				SELECT sd.amount
				FROM `tabSalary Detail` sd
				JOIN `tabSalary Structure` ss ON sd.parent = ss.name
				JOIN `tabSalary Structure Assignment` ssa ON ssa.salary_structure = ss.name
				WHERE ssa.employee = %s AND ssa.docstatus = 1
					AND sd.salary_component = %s
				ORDER BY ssa.from_date DESC
				LIMIT 1
				""",
				(emp_id, salary_component),
			)
			old_value = float(sd[0][0]) if sd else 0

		doc = frappe.get_doc(
			{
				"doctype": "BEI Compensation Change",
				"employee": emp_id,
				"change_type": change_type,
				"salary_component": None if employee_field_name else salary_component,
				"employee_field_name": employee_field_name,
				"old_value": old_value,
				"new_value": new_value,
				"effective_date": effective_date,
				"reason": reason,
				"status": initial_status,
				"requested_by": frappe.session.user,
				# When an HR Manager originates, their submission IS the HR-stage
				# sign-off — record it so the audit trail is complete.
				"hr_reviewer": (
					frappe.session.user
					if initial_status == "Pending Accounts Manager"
					else None
				),
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	return {
		"status": "success",
		"message": _("{0} compensation change request(s) created").format(len(created)),
		"change_ids": created,
	}


@frappe.whitelist()
def approve_compensation_change(change_id, approver_action, remarks=None):
	"""HR Manager or Accounts Manager approves/rejects a compensation change.

	Approval chain: Pending HR Manager → Pending Accounts Manager → Approved
	"""
	set_backend_observability_context(
		module="payroll",
		action="approve_compensation_change",
		mutation_type="update",
		extras={"change_id": change_id, "action": approver_action},
	)

	if approver_action not in ("approve", "reject"):
		frappe.throw(_("Action must be 'approve' or 'reject'"))

	doc = frappe.get_doc("BEI Compensation Change", change_id)
	roles = frappe.get_roles(frappe.session.user)

	if approver_action == "reject":
		if not remarks:
			frappe.throw(_("Rejection reason is required"))
		doc.status = "Rejected"
		doc.rejection_reason = remarks
		doc.save(ignore_permissions=True)
		return {"status": "success", "message": _("Compensation change rejected")}

	# Approve flow
	if doc.status == "Pending HR Manager":
		if "HR Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only HR Manager can approve at this stage"))
		doc.status = "Pending Accounts Manager"
		doc.hr_reviewer = frappe.session.user
		doc.save(ignore_permissions=True)
		return {"status": "success", "message": _("Approved by HR Manager. Pending Accounts Manager.")}

	elif doc.status == "Pending Accounts Manager":
		if "Accounts Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only Accounts Manager can approve at this stage"))

		# S172 Defect #16 fix: wrap status-change + activation in ONE savepoint so
		# that activation failure reverts the Approved status instead of silently
		# stranding the BCC with status=Approved but no SSA created.
		try:
			frappe.db.savepoint("compensation_activation")
			doc.status = "Approved"
			doc.final_approver = frappe.session.user
			doc.approval_date = now_datetime()
			doc.save(ignore_permissions=True)
			_activate_compensation_change(doc)
			frappe.db.release_savepoint("compensation_activation")
		except Exception as e:
			frappe.db.rollback_to_savepoint("compensation_activation")
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"S172: Compensation activation failed for {doc.name}",
			)
			# Propagate the real error to the caller so the frontend can show it
			# and HR knows to fix the underlying issue (e.g., missing salary structure).
			frappe.throw(
				_("Compensation activation failed: {0}. Change not applied.").format(str(e)),
				title=_("Activation Failed"),
			)

		return {"status": "success", "message": _("Compensation change approved")}

	else:
		frappe.throw(_("This change request is not in an approvable state (current: {0})").format(doc.status))


@frappe.whitelist()
def get_salary_structure_options():
	"""Return all active salary structures for dropdown selectors."""
	set_backend_observability_context(
		module="payroll",
		action="get_salary_structure_options",
		mutation_type="read",
	)

	structures = frappe.get_all(
		"Salary Structure",
		filters={"docstatus": 1, "is_active": "Yes"},
		fields=["name", "name as value", "name as label"],
		order_by="name ASC",
	)
	return structures


@frappe.whitelist()
def get_salary_component_options(component_type=None):
	"""Return salary components for dropdown selectors.

	Args:
		component_type: 'earning' or 'deduction' to filter
	"""
	set_backend_observability_context(
		module="payroll",
		action="get_salary_component_options",
		mutation_type="read",
	)

	filters = {}
	if component_type:
		filters["type"] = "Earning" if component_type == "earning" else "Deduction"

	components = frappe.get_all(
		"Salary Component",
		filters=filters,
		fields=["name", "name as value", "name as label", "type"],
		order_by="name ASC",
	)
	return components


# ============================================================================
# Sensitive-Change Endpoints (Phase 2)
# ============================================================================


@frappe.whitelist()
def get_sensitive_change_queue(status_filter=None, initiated_by_me=False):
	"""Return pending sensitive change requests.

	Args:
		status_filter: Optional status to filter by
		initiated_by_me: If truthy, filter to current user's requests
	"""
	set_backend_observability_context(
		module="payroll",
		action="get_sensitive_change_queue",
		mutation_type="read",
		extras={"status_filter": status_filter},
	)

	filters = {}
	if status_filter:
		filters["status"] = status_filter

	if initiated_by_me and str(initiated_by_me).lower() not in ("0", "false"):
		filters["initiated_by"] = frappe.session.user

	requests = frappe.get_all(
		"BEI Sensitive Change Request",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"branch",
			"field_name",
			"old_value",
			"new_value",
			"effective_date",
			"reason",
			"status",
			"initiated_by",
			"initiator_role",
			"hr_verifier",
			"finance_approver",
			"hr_activator",
			"activated_date",
			"submission_date",
			"proof_attachment",
		],
		order_by="creation DESC",
		limit_page_length=200,
	)

	# Mask bank account numbers — show only last 4 digits
	for req in requests:
		if req.get("field_name") == "bank_ac_no":
			for key in ("old_value", "new_value"):
				val = req.get(key) or ""
				if len(val) > 4:
					req[key] = "****" + val[-4:]

	# Determine pending approver for each request based on status + roles
	roles = frappe.get_roles(frappe.session.user)
	for req in requests:
		req["can_approve"] = False
		req["can_activate"] = False

		if req["status"] == "Pending HR Verification":
			if "HR Manager" in roles or "System Manager" in roles:
				req["can_approve"] = True
		elif req["status"] == "Pending Finance Approval":
			if "Accounts Manager" in roles or "System Manager" in roles:
				req["can_approve"] = True
		elif req["status"] == "Finance Approved":
			# Needs HR activation
			if "HR Manager" in roles or "System Manager" in roles:
				req["can_approve"] = True
		elif req["status"] == "Pending HR Activation":
			if "HR Manager" in roles or "System Manager" in roles:
				req["can_activate"] = True

	return {"data": requests}


@frappe.whitelist()
def submit_sensitive_change_request(
	employee,
	field_name,
	new_value,
	reason,
	effective_date,
	proof_attachment=None,
	exception_justification=None,
):
	"""Create a sensitive change request with dual-control routing.

	Args:
		employee: Employee ID
		field_name: One of SENSITIVE_FIELDS
		new_value: Requested new value
		reason: Justification text
		effective_date: When the change should take effect
		proof_attachment: Optional file path for proof
		exception_justification: Required if effective_date ≤ current cutoff start
	"""
	set_backend_observability_context(
		module="payroll",
		action="submit_sensitive_change_request",
		mutation_type="create",
		extras={"field_name": field_name, "effective_date": effective_date},
	)

	if field_name not in SENSITIVE_FIELDS:
		frappe.throw(_("Field '{0}' is not a sensitive payroll field").format(field_name))

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee {0} not found").format(employee))

	# D32: Effective date validation — default is future/next cutoff
	# Same-cutoff or retroactive requires exception justification
	eff_date = getdate(effective_date)
	current_cutoff_start = _get_current_cutoff_start()
	if current_cutoff_start and eff_date <= current_cutoff_start:
		if not exception_justification:
			frappe.throw(
				_(
					"Effective date is within or before the current payroll cutoff. "
					"Exception justification is required."
				)
			)

	# Check for duplicate
	open_statuses = [
		"Draft", "Pending HR Verification", "Pending Finance Approval",
		"Finance Approved", "Pending HR Activation",
	]
	existing = frappe.db.exists(
		"BEI Sensitive Change Request",
		{"employee": employee, "field_name": field_name, "status": ("in", open_statuses)},
	)
	if existing:
		frappe.throw(
			_("A sensitive change request for this field is already pending.")
		)

	# Get current value
	current_value = frappe.db.get_value("Employee", employee, field_name) or ""

	# D9/D10: Determine initiator role for routing
	roles = frappe.get_roles(frappe.session.user)
	if "HR Manager" in roles or "HR User" in roles:
		initiator_role = "HR"
		initial_status = "Pending Finance Approval"
	elif "Accounts Manager" in roles:
		initiator_role = "Finance"
		initial_status = "Pending HR Verification"
	else:
		# Employee self-service
		initiator_role = "Employee"
		initial_status = "Pending HR Verification"

	doc = frappe.get_doc(
		{
			"doctype": "BEI Sensitive Change Request",
			"employee": employee,
			"field_name": field_name,
			"old_value": str(current_value),
			"new_value": new_value,
			"effective_date": effective_date,
			"reason": reason,
			"proof_attachment": proof_attachment,
			"exception_justification": exception_justification,
			"initiated_by": frappe.session.user,
			"initiator_role": initiator_role,
			"status": initial_status,
			"audit_log": [
				{
					"actor": frappe.session.user,
					"action": "Submitted",
					"note": (
						f"Sensitive change request created by {initiator_role}. "
						f"Field: {SENSITIVE_FIELD_LABELS.get(field_name, field_name)}. "
						f"Routed to {initial_status}."
					),
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	# S172 Defect #15 fix: explicit commit prevents the first-of-session
	# silent rollback pattern — some downstream code later in the request
	# cycle was rolling the transaction back, leaving the BSCR invisible
	# despite the endpoint returning success. Committing here ensures the
	# insert is durable regardless of what else happens in the request.
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Sensitive change request created ({0})").format(doc.name),
		"request_id": doc.name,
	}


@frappe.whitelist()
def approve_sensitive_change(request_id, remarks=None):
	"""Approve a sensitive change request through the dual-control chain.

	D9 Guard: Approver role must differ from initiator role.
	Status transitions:
		Pending HR Verification + HR → Pending Finance Approval
		Pending Finance Approval + Finance → Pending HR Activation
		Finance Approved + HR → Pending HR Activation  (alternative path)
	"""
	set_backend_observability_context(
		module="payroll",
		action="approve_sensitive_change",
		mutation_type="update",
		extras={"request_id": request_id},
	)

	doc = frappe.get_doc("BEI Sensitive Change Request", request_id)
	roles = frappe.get_roles(frappe.session.user)

	if doc.status == "Pending HR Verification":
		if "HR Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only HR Manager can verify at this stage"))
		doc.status = "Pending Finance Approval"
		doc.hr_verifier = frappe.session.user

	elif doc.status == "Pending Finance Approval":
		if "Accounts Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only Accounts Manager can approve at this stage"))
		# D9: Ensure approver is different from initiator if both are in same-role scenario
		if doc.initiated_by == frappe.session.user:
			frappe.throw(
				_("The person who initiated a sensitive change cannot also approve it (dual-control).")
			)
		doc.status = "Pending HR Activation"
		doc.finance_approver = frappe.session.user

	elif doc.status == "Finance Approved":
		if "HR Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only HR Manager can proceed at this stage"))
		doc.status = "Pending HR Activation"

	else:
		frappe.throw(
			_("Request is not in an approvable state (current: {0})").format(doc.status)
		)

	doc.append("audit_log", {
		"actor": frappe.session.user,
		"action": f"Approved ({doc.status})",
		"note": remarks or f"Approved by {frappe.session.user}. Status: {doc.status}",
	})
	doc.save(ignore_permissions=True)

	return {"status": "success", "message": _("Request approved. Status: {0}").format(doc.status)}


@frappe.whitelist()
def reject_sensitive_change(request_id, reason):
	"""Reject a sensitive change request with mandatory reason."""
	set_backend_observability_context(
		module="payroll",
		action="reject_sensitive_change",
		mutation_type="update",
		extras={"request_id": request_id},
	)

	if not reason:
		frappe.throw(_("Rejection reason is required"))

	doc = frappe.get_doc("BEI Sensitive Change Request", request_id)
	doc.status = "Rejected"
	doc.rejection_reason = reason
	doc.append("audit_log", {
		"actor": frappe.session.user,
		"action": "Rejected",
		"note": f"Rejected by {frappe.session.user}. Reason: {reason}",
	})
	doc.save(ignore_permissions=True)

	return {"status": "success", "message": _("Sensitive change request rejected")}


@frappe.whitelist()
def activate_sensitive_change(request_id):
	"""Final activation: writes the field value to the employee record.

	Only callable when status = 'Pending HR Activation'.
	Only callable by HR Manager role.
	Creates immutable history entry with full audit trail.
	"""
	set_backend_observability_context(
		module="payroll",
		action="activate_sensitive_change",
		mutation_type="update",
		extras={"request_id": request_id},
	)

	doc = frappe.get_doc("BEI Sensitive Change Request", request_id)

	if doc.status != "Pending HR Activation":
		frappe.throw(
			_("Cannot activate: status is '{0}', expected 'Pending HR Activation'").format(doc.status)
		)

	roles = frappe.get_roles(frappe.session.user)
	if "HR Manager" not in roles and "System Manager" not in roles:
		frappe.throw(_("Only HR Manager can activate sensitive changes"))

	# Write the value to the employee record
	frappe.db.set_value(
		"Employee",
		doc.employee,
		doc.field_name,
		doc.new_value,
		update_modified=True,
	)

	doc.status = "Active"
	doc.hr_activator = frappe.session.user
	doc.activated_date = now_datetime()
	doc.append("audit_log", {
		"actor": frappe.session.user,
		"action": "Activated",
		"note": (
			f"Value written to Employee record by {frappe.session.user}. "
			f"Field: {doc.field_name}, New Value: {doc.new_value}, "
			f"Effective: {doc.effective_date}."
		),
	})
	doc.save(ignore_permissions=True)

	return {
		"status": "success",
		"message": _("Sensitive change activated. Employee record updated."),
	}


@frappe.whitelist()
def get_sensitive_change_detail(request_id):
	"""Return full detail of a sensitive change request including audit trail."""
	set_backend_observability_context(
		module="payroll",
		action="get_sensitive_change_detail",
		mutation_type="read",
	)

	doc = frappe.get_doc("BEI Sensitive Change Request", request_id)
	data = doc.as_dict()

	# Mask bank account in detail view too
	if data.get("field_name") == "bank_ac_no":
		for key in ("old_value", "new_value"):
			val = data.get(key) or ""
			if len(val) > 4:
				data[key] = "****" + val[-4:]

	return {"data": data}


# ============================================================================
# Helpers
# ============================================================================


def _activate_compensation_change(doc):
	"""Write approved change to Employee record or SSA.

	Called at final approval (Approved status). Handles:
	- bei_* fields: direct Employee field update
	- Salary changes: create new SSA (with fallback to default structure for new hires)
	- Other Salary Detail components: extend when needed

	S172 Defect #16 fix: when the employee has no prior SSA (new hire), fall back
	to the first active salary structure instead of silently skipping. If no
	active salary structure exists at all, raise a clear error so the caller
	can surface it (previously: silent corrupt-success).
	"""
	if doc.employee_field_name and doc.employee_field_name.startswith("bei_"):
		# Direct Employee field (bei_* allowances)
		frappe.db.set_value("Employee", doc.employee, doc.employee_field_name, flt(doc.new_value))
		return

	if doc.change_type == "Salary":
		# New SSA required — NOT set_value on Employee
		latest_ssa = frappe.db.get_value(
			"Salary Structure Assignment",
			{"employee": doc.employee, "docstatus": 1},
			["salary_structure", "income_tax_slab"],
			order_by="from_date DESC",
			as_dict=True,
		)

		if latest_ssa:
			salary_structure = latest_ssa.salary_structure
			income_tax_slab = latest_ssa.income_tax_slab
		else:
			# S172 Defect #16: no prior SSA — fall back to first active structure.
			fallback = frappe.db.get_value(
				"Salary Structure",
				{"docstatus": 1, "is_active": "Yes"},
				["name"],
				order_by="creation ASC",
			)
			if not fallback:
				frappe.throw(
					_(
						"Cannot activate salary change for {0}: no existing Salary "
						"Structure Assignment and no active Salary Structure available "
						"as a template. Please create an active Salary Structure first."
					).format(doc.employee)
				)
			salary_structure = fallback
			# Look up any active tax slab for the company.
			income_tax_slab = frappe.db.get_value(
				"Income Tax Slab",
				{"disabled": 0},
				"name",
				order_by="effective_from DESC",
			)

		new_ssa = frappe.get_doc({
			"doctype": "Salary Structure Assignment",
			"employee": doc.employee,
			"salary_structure": salary_structure,
			"income_tax_slab": income_tax_slab,
			"base": flt(doc.new_value),
			"from_date": doc.effective_date,
			"company": frappe.db.get_value("Employee", doc.employee, "company"),
		})
		new_ssa.insert(ignore_permissions=True)
		new_ssa.submit()


def _get_current_cutoff_start():
	"""Return the start date of the current payroll cutoff period.

	BEI uses bimonthly cutoffs: 1st-15th and 16th-end of month.
	"""
	today_date = getdate(today())
	if today_date.day <= 15:
		return today_date.replace(day=1)
	else:
		return today_date.replace(day=16)


def _get_next_cutoff_start():
	"""Return the start date of the next payroll cutoff period."""
	today_date = getdate(today())
	if today_date.day <= 15:
		return today_date.replace(day=16)
	else:
		# Next month 1st
		next_month = add_months(today_date, 1)
		return getdate(next_month).replace(day=1)

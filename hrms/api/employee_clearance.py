# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Employee Clearance API for my.bebang.ph

Provides endpoints for:
- Exit interview questionnaire
- Separation workflow management
- DOLE compliance tracking
- COE generation
"""

import frappe
from frappe import _

# ============================================================================
# EXIT INTERVIEW QUESTIONS
# ============================================================================


@frappe.whitelist(allow_guest=False)
def get_exit_interview_questions():
	"""
	Get all active exit interview questions for the questionnaire form.

	Returns:
		list: Questions grouped by category with response type info
	"""
	questions = frappe.get_all(
		"BEI Exit Interview Question",
		filters={"active": 1},
		fields=["name", "category", "question_text", "response_type", "display_order"],
		order_by="display_order asc",
	)

	# Group by category
	grouped = {}
	for q in questions:
		category = q.get("category")
		if category not in grouped:
			grouped[category] = []
		grouped[category].append(q)

	return {
		"questions": questions,
		"grouped": grouped,
		"total": len(questions),
	}


@frappe.whitelist(allow_guest=False)
def submit_exit_interview_responses(exit_interview: str, responses: list):
	"""
	Submit questionnaire responses for an exit interview.

	Args:
		exit_interview: Exit Interview document name
		responses: List of {question: str, response_scale: int, response_yesno: bool, response_text: str}

	Returns:
		dict: Success status and updated document
	"""
	if isinstance(responses, str):
		import json

		responses = json.loads(responses)

	doc = frappe.get_doc("Exit Interview", exit_interview)

	# Clear existing responses
	doc.custom_questionnaire_responses = []

	# Add new responses
	for resp in responses:
		doc.append(
			"custom_questionnaire_responses",
			{
				"question": resp.get("question"),
				"response_scale": resp.get("response_scale"),
				"response_yesno": resp.get("response_yesno"),
				"response_text": resp.get("response_text"),
			},
		)

	doc.save()

	return {
		"success": True,
		"message": _("Responses submitted successfully"),
		"exit_interview": doc.name,
	}


@frappe.whitelist(allow_guest=False)
def get_exit_interview_responses(exit_interview: str):
	"""
	Get submitted responses for an exit interview.

	Args:
		exit_interview: Exit Interview document name

	Returns:
		dict: Interview details with responses
	"""
	doc = frappe.get_doc("Exit Interview", exit_interview)

	responses = []
	for resp in doc.custom_questionnaire_responses:
		question_doc = frappe.get_doc("BEI Exit Interview Question", resp.question)
		responses.append(
			{
				"question": resp.question,
				"question_text": question_doc.question_text,
				"category": question_doc.category,
				"response_type": question_doc.response_type,
				"response_scale": resp.response_scale,
				"response_yesno": resp.response_yesno,
				"response_text": resp.response_text,
			}
		)

	return {
		"exit_interview": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"status": doc.status,
		"primary_reason": doc.custom_primary_reason,
		"rehire_recommendation": doc.custom_rehire_recommendation,
		"responses": responses,
	}


# ============================================================================
# EMPLOYEE SEPARATION
# ============================================================================


@frappe.whitelist(allow_guest=False)
def get_separation_types():
	"""
	Get available separation types for dropdown.

	Returns:
		list: Separation type options
	"""
	return [
		{"value": "Resignation", "label": "Resignation"},
		{"value": "Termination - Just Cause", "label": "Termination - Just Cause"},
		{"value": "Termination - Authorized Cause", "label": "Termination - Authorized Cause"},
		{"value": "AWOL", "label": "AWOL (Absence Without Leave)"},
		{"value": "Probation Failure", "label": "Probation Failure"},
		{"value": "End of Contract", "label": "End of Contract"},
		{"value": "Retirement", "label": "Retirement"},
	]


@frappe.whitelist(allow_guest=False)
def create_employee_separation(
	employee: str,
	separation_type: str,
	separation_reason: str | None = None,
	boarding_begins_on: str | None = None,
):
	"""
	Create a new Employee Separation document.

	Args:
		employee: Employee ID
		separation_type: Type of separation
		separation_reason: Optional reason text
		boarding_begins_on: Date separation begins

	Returns:
		dict: Created separation document details
	"""
	emp_doc = frappe.get_doc("Employee", employee)

	doc = frappe.new_doc("Employee Separation")
	doc.employee = employee
	doc.company = emp_doc.company
	doc.custom_separation_type = separation_type
	doc.custom_separation_reason = separation_reason

	if boarding_begins_on:
		doc.boarding_begins_on = boarding_begins_on
	else:
		doc.boarding_begins_on = frappe.utils.today()

	doc.insert()

	# Auto-populate DOLE compliance items
	populate_dole_compliance(doc.name, separation_type)

	return {
		"success": True,
		"message": _("Employee Separation created"),
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"separation_type": doc.custom_separation_type,
	}


@frappe.whitelist(allow_guest=False)
def get_employee_separation(name: str):
	"""
	Get Employee Separation details including DOLE compliance status.

	Args:
		name: Employee Separation document name

	Returns:
		dict: Full separation details
	"""
	doc = frappe.get_doc("Employee Separation", name)

	compliance_items = []
	for item in doc.custom_dole_compliance:
		compliance_doc = frappe.get_doc("BEI DOLE Compliance Item", item.compliance_item)
		compliance_items.append(
			{
				"name": item.name,
				"compliance_item": item.compliance_item,
				"item_code": compliance_doc.item_code,
				"description": compliance_doc.description,
				"sla_days": compliance_doc.sla_days,
				"dole_reference": compliance_doc.dole_reference,
				"status": item.status,
				"completed_date": item.completed_date,
				"completed_by": item.completed_by,
				"document": item.document,
				"notes": item.notes,
			}
		)

	return {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"department": doc.department,
		"designation": doc.designation,
		"company": doc.company,
		"separation_type": doc.custom_separation_type,
		"separation_reason": doc.custom_separation_reason,
		"boarding_status": doc.boarding_status,
		"boarding_begins_on": doc.boarding_begins_on,
		"rehire_eligible": doc.custom_rehire_eligible,
		"exit_interview_completed": doc.custom_exit_interview_completed,
		"final_pay_approved": doc.custom_final_pay_approved,
		"coe_generated": doc.custom_coe_generated,
		"compliance_items": compliance_items,
	}


@frappe.whitelist(allow_guest=False)
def get_employee_separations(employee: str | None = None, status: str | None = None):
	"""
	List employee separations with optional filters.

	Args:
		employee: Filter by employee ID
		status: Filter by boarding_status (Pending, In Process, Completed)

	Returns:
		list: Separation documents
	"""
	filters = {}
	if employee:
		filters["employee"] = employee
	if status:
		filters["boarding_status"] = status

	separations = frappe.get_all(
		"Employee Separation",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"designation",
			"custom_separation_type",
			"boarding_status",
			"boarding_begins_on",
			"custom_exit_interview_completed",
			"custom_final_pay_approved",
			"custom_coe_generated",
		],
		order_by="creation desc",
	)

	return separations


@frappe.whitelist(allow_guest=False)
def create_exit_interview(
	employee: str,
	separation_date: str | None = None,
	resignation_letter: str | None = None,
):
	"""Create (or reuse) exit interview for an employee."""
	existing = frappe.get_all(
		"Exit Interview",
		filters={"employee": employee, "docstatus": ["<", 2]},
		fields=["name", "status"],
		order_by="creation desc",
		limit=1,
	)
	if existing:
		return {
			"name": existing[0].name,
			"employee": employee,
			"status": existing[0].status,
			"reused": True,
		}

	employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
	interview = frappe.get_doc(
		{
			"doctype": "Exit Interview",
			"employee": employee,
			"employee_name": employee_name,
			"interview_date": separation_date or frappe.utils.today(),
			"status": "Draft",
		}
	)
	interview.insert(ignore_permissions=True)

	if resignation_letter:
		try:
			interview.add_comment("Comment", text=f"Resignation letter note: {resignation_letter}")
		except Exception:
			pass

	return {
		"name": interview.name,
		"employee": employee,
		"status": interview.status,
		"reused": False,
	}


@frappe.whitelist(allow_guest=False)
def get_team_separations():
	"""Return separation rows formatted for portal team separations grid."""
	separations = frappe.get_all(
		"Employee Separation",
		fields=[
			"name",
			"employee",
			"employee_name",
			"boarding_begins_on",
			"boarding_status",
			"custom_exit_interview_completed",
		],
		order_by="creation desc",
		limit=200,
	)

	rows = []
	for sep in separations:
		interview = frappe.get_all(
			"Exit Interview",
			filters={"employee": sep.employee, "docstatus": ["<", 2]},
			fields=["name", "status"],
			order_by="creation desc",
			limit=1,
		)
		interview_name = interview[0].name if interview else None
		interview_status = interview[0].status if interview else ""

		boarding_status = (sep.boarding_status or "Pending").strip()
		normalized_status = (
			"In Progress" if boarding_status in ("In Process", "In Progress") else boarding_status
		)

		if not interview_name:
			exit_status = "Not Started"
		elif interview_status in ("Submitted", "Completed"):
			exit_status = "Submitted"
		else:
			exit_status = "In Progress"

		compliance_items = frappe.get_all(
			"BEI DOLE Compliance Checklist",
			filters={"parent": sep.name, "parenttype": "Employee Separation"},
			fields=["status"],
		)
		total_items = len(compliance_items)
		completed_items = sum(1 for item in compliance_items if item.status == "Completed")
		clearance_progress = round((completed_items / total_items) * 100, 1) if total_items > 0 else 0

		store = frappe.db.get_value("Employee", sep.employee, "branch") or ""

		rows.append(
			{
				"employee": sep.employee,
				"employee_name": sep.employee_name,
				"separation_date": sep.boarding_begins_on,
				"status": normalized_status or "Pending",
				"exit_interview_status": exit_status,
				"exit_interview_name": interview_name,
				"clearance_progress": clearance_progress,
				"store": store,
				"store_name": store,
			}
		)

	return rows


@frappe.whitelist(allow_guest=False)
def get_exit_interview_analytics(date_from: str | None = None, date_to: str | None = None):
	"""Return analytics payload for exit interview dashboard."""
	date_to = date_to or frappe.utils.today()
	date_from = date_from or frappe.utils.add_days(date_to, -90)

	separations = frappe.get_all(
		"Employee Separation",
		filters={"boarding_begins_on": ["between", [date_from, date_to]]},
		fields=["name", "department", "custom_separation_type", "boarding_begins_on"],
	)
	interviews = frappe.get_all(
		"Exit Interview",
		filters={"creation": ["between", [date_from, date_to]], "docstatus": ["<", 2]},
		fields=["name"],
	)

	total_separations = len(separations)
	total_interviews = len(interviews)
	response_rate = round((total_interviews / total_separations) * 100, 2) if total_separations > 0 else 0

	reason_counts = {}
	for sep in separations:
		reason = sep.get("custom_separation_type") or "Unspecified"
		reason_counts[reason] = reason_counts.get(reason, 0) + 1

	reasons_for_leaving = []
	for reason, count in reason_counts.items():
		reasons_for_leaving.append(
			{
				"reason": reason,
				"count": count,
				"percentage": round((count / total_separations) * 100, 2) if total_separations > 0 else 0,
			}
		)

	dept_counts = {}
	for sep in separations:
		dept = sep.get("department") or "Unassigned"
		dept_counts[dept] = dept_counts.get(dept, 0) + 1

	department_breakdown = []
	for department, count in dept_counts.items():
		department_breakdown.append(
			{
				"department": department,
				"count": count,
				"percentage": round((count / total_separations) * 100, 2) if total_separations > 0 else 0,
			}
		)

	attrition_trend = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(boarding_begins_on, '%%Y-%%m') AS month, COUNT(*) AS count
		FROM `tabEmployee Separation`
		WHERE boarding_begins_on BETWEEN %(date_from)s AND %(date_to)s
		GROUP BY DATE_FORMAT(boarding_begins_on, '%%Y-%%m')
		ORDER BY month
		""",
		{"date_from": date_from, "date_to": date_to},
		as_dict=True,
	)

	return {
		"date_from": date_from,
		"date_to": date_to,
		"total_separations": total_separations,
		"total_interviews": total_interviews,
		"response_rate": response_rate,
		"reasons_for_leaving": reasons_for_leaving,
		"attrition_trend": attrition_trend,
		"department_breakdown": department_breakdown,
		"avg_tenure_months": 0,
	}


# ============================================================================
# DOLE COMPLIANCE
# ============================================================================


@frappe.whitelist(allow_guest=False)
def populate_dole_compliance(separation_name: str, separation_type: str):
	"""
	Auto-populate DOLE compliance checklist based on separation type.

	Args:
		separation_name: Employee Separation document name
		separation_type: Type of separation

	Returns:
		dict: Updated compliance items
	"""
	doc = frappe.get_doc("Employee Separation", separation_name)

	# Get applicable compliance items for this separation type
	compliance_items = frappe.db.sql(
		"""
		SELECT DISTINCT dci.name, dci.item_code, dci.description, dci.sla_days, dci.dole_reference
		FROM `tabBEI DOLE Compliance Item` dci
		JOIN `tabBEI Separation Type Item` sti ON sti.parent = dci.name
		WHERE sti.separation_type = %s
		ORDER BY dci.item_code
		""",
		(separation_type,),
		as_dict=True,
	)

	# Clear existing and add applicable items
	doc.custom_dole_compliance = []
	for item in compliance_items:
		doc.append(
			"custom_dole_compliance",
			{
				"compliance_item": item.name,
				"status": "Pending",
			},
		)

	doc.save()

	return {
		"success": True,
		"message": _("{0} compliance items added").format(len(compliance_items)),
		"items": compliance_items,
	}


@frappe.whitelist(allow_guest=False)
def update_compliance_status(
	separation_name: str,
	compliance_row_name: str,
	status: str,
	notes: str | None = None,
	document: str | None = None,
):
	"""
	Update status of a DOLE compliance item.

	Args:
		separation_name: Employee Separation document name
		compliance_row_name: Child table row name
		status: New status (Pending, Completed, Not Applicable)
		notes: Optional notes
		document: Optional attachment

	Returns:
		dict: Updated item
	"""
	doc = frappe.get_doc("Employee Separation", separation_name)

	for item in doc.custom_dole_compliance:
		if item.name == compliance_row_name:
			item.status = status
			if status == "Completed":
				item.completed_date = frappe.utils.today()
				item.completed_by = frappe.session.user
			if notes:
				item.notes = notes
			if document:
				item.document = document
			break

	doc.save()

	return {
		"success": True,
		"message": _("Compliance status updated"),
	}


@frappe.whitelist(allow_guest=False)
def get_dole_compliance_items():
	"""
	Get all DOLE compliance items master data.

	Returns:
		list: All compliance items with applicable separation types
	"""
	items = frappe.get_all(
		"BEI DOLE Compliance Item",
		fields=["name", "item_code", "description", "sla_days", "dole_reference"],
		order_by="item_code",
	)

	for item in items:
		# Get applicable separation types
		types = frappe.get_all(
			"BEI Separation Type Item",
			filters={"parent": item.name},
			fields=["separation_type"],
		)
		item["applicable_types"] = [t.separation_type for t in types]

	return items


# ============================================================================
# CLEARANCE STATUS
# ============================================================================


@frappe.whitelist(allow_guest=False)
def get_clearance_status(employee: str):
	"""
	Get clearance progress for an employee.

	Args:
		employee: Employee ID

	Returns:
		dict: Clearance status summary
	"""
	# Find active separation
	separation = frappe.get_all(
		"Employee Separation",
		filters={"employee": employee, "boarding_status": ["!=", "Completed"]},
		fields=["name"],
		limit=1,
	)

	if not separation:
		return {
			"has_active_separation": False,
			"message": _("No active separation found"),
		}

	sep_doc = frappe.get_doc("Employee Separation", separation[0].name)

	# Calculate compliance progress
	total_items = len(sep_doc.custom_dole_compliance)
	completed_items = sum(1 for i in sep_doc.custom_dole_compliance if i.status == "Completed")

	# Calculate activity progress
	total_activities = len(sep_doc.activities)
	completed_activities = sum(1 for a in sep_doc.activities if a.activity_status == "Completed")

	return {
		"has_active_separation": True,
		"separation_name": sep_doc.name,
		"separation_type": sep_doc.custom_separation_type,
		"boarding_status": sep_doc.boarding_status,
		"boarding_begins_on": sep_doc.boarding_begins_on,
		"compliance_progress": {
			"total": total_items,
			"completed": completed_items,
			"percentage": round((completed_items / total_items * 100) if total_items > 0 else 0, 1),
		},
		"activity_progress": {
			"total": total_activities,
			"completed": completed_activities,
			"percentage": round(
				(completed_activities / total_activities * 100) if total_activities > 0 else 0, 1
			),
		},
		"milestones": {
			"exit_interview_completed": sep_doc.custom_exit_interview_completed,
			"final_pay_approved": sep_doc.custom_final_pay_approved,
			"coe_generated": sep_doc.custom_coe_generated,
		},
	}


# ============================================================================
# BIO ID MANAGEMENT (ADMS Integration)
# ============================================================================


ADMS_BASE_URL = "http://localhost:8080"  # ADMS receiver on same EC2 instance


@frappe.whitelist(allow_guest=False)
def disable_bio_id(employee: str, removal_reason: str | None = None):
	"""
	Disable employee's Bio ID on all enrolled biometric devices.
	Called when IT Clearance activity is completed during separation.

	This integrates with the ADMS receiver to queue DELETE commands
	for all devices where the employee is enrolled.

	Args:
		employee: Employee ID
		removal_reason: Optional reason for removal (e.g., "Employee Separation")

	Returns:
		dict: Success status with details of devices queued for deletion
	"""
	import requests

	# Get employee's Bio ID (attendance_device_id)
	bio_id = frappe.db.get_value("Employee", employee, "attendance_device_id")

	if not bio_id:
		return {
			"success": False,
			"message": _("Employee has no Bio ID assigned"),
			"employee": employee,
		}

	try:
		response = requests.post(
			f"{ADMS_BASE_URL}/admin/user/{bio_id}/disable",
			json={
				"removal_reason": removal_reason or "Employee Separation",
				"removed_by": frappe.session.user,
			},
			timeout=10,
		)
		response.raise_for_status()
		result = response.json()

		# Log the action as a comment on the Employee record
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Employee",
				"reference_name": employee,
				"content": _("Bio ID {0} disabled: {1} devices queued for deletion").format(
					bio_id, result.get("devices_queued", 0)
				),
			}
		).insert(ignore_permissions=True)

		return {
			"success": True,
			"employee": employee,
			"bio_id": bio_id,
			"devices_queued": result.get("devices_queued", 0),
			"message": result.get("message", "Bio ID disabled successfully"),
		}

	except requests.exceptions.ConnectionError:
		frappe.log_error(
			f"ADMS disable failed for {bio_id}: Connection refused - ADMS receiver not running",
			"ADMS Integration",
		)
		return {
			"success": False,
			"message": _("ADMS receiver not available - Bio ID disable queued for retry"),
			"bio_id": bio_id,
		}

	except requests.exceptions.RequestException as e:
		frappe.log_error(f"ADMS disable failed for {bio_id}: {e}", "ADMS Integration")
		return {
			"success": False,
			"message": str(e),
			"bio_id": bio_id,
		}


@frappe.whitelist(allow_guest=False)
def get_bio_id_status(employee: str):
	"""
	Check Bio ID enrollment status for an employee.

	Args:
		employee: Employee ID

	Returns:
		dict: Bio ID status and enrollment details
	"""
	import requests

	bio_id = frappe.db.get_value("Employee", employee, "attendance_device_id")

	if not bio_id:
		return {
			"has_bio_id": False,
			"message": _("Employee has no Bio ID assigned"),
		}

	try:
		response = requests.get(
			f"{ADMS_BASE_URL}/admin/enrollment/{bio_id}",
			timeout=10,
		)

		if response.status_code == 200:
			enrollment_data = response.json()
			return {
				"has_bio_id": True,
				"bio_id": bio_id,
				"enrollment_status": enrollment_data.get("status"),
				"devices_enrolled": enrollment_data.get("devices_enrolled", []),
				"last_seen": enrollment_data.get("last_seen"),
			}
		elif response.status_code == 404:
			return {
				"has_bio_id": True,
				"bio_id": bio_id,
				"enrollment_status": "not_enrolled",
				"message": _("Bio ID assigned but not enrolled on any devices"),
			}
		else:
			return {
				"has_bio_id": True,
				"bio_id": bio_id,
				"error": f"ADMS returned status {response.status_code}",
			}

	except requests.exceptions.RequestException as e:
		return {
			"has_bio_id": True,
			"bio_id": bio_id,
			"error": _("Could not reach ADMS receiver: {0}").format(str(e)),
		}


# ============================================================================
# MY SEPARATION (Current User)
# ============================================================================


@frappe.whitelist(allow_guest=False)
def get_my_separation():
	"""
	Get the current user's active or most recent employee separation.
	Used by my.bebang.ph clearance page to show the logged-in user's clearance status.

	Returns:
		dict: Separation details or null if no separation found
	"""
	# Get the employee ID linked to the current user
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user, "status": ["in", ["Active", "Left"]]},
		"name",
	)

	if not employee:
		return {
			"has_separation": False,
			"message": _("No employee record found for current user"),
		}

	# Find active separation first, then most recent
	separation = frappe.get_all(
		"Employee Separation",
		filters={"employee": employee},
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"designation",
			"custom_separation_type",
			"custom_separation_reason",
			"boarding_status",
			"boarding_begins_on",
			"custom_exit_interview_completed",
			"custom_final_pay_approved",
			"custom_coe_generated",
			"custom_rehire_eligible",
		],
		order_by="creation desc",
		limit=1,
	)

	if not separation:
		return {
			"has_separation": False,
			"employee": employee,
			"message": _("No separation record found"),
		}

	sep = separation[0]

	# Get DOLE compliance items
	compliance_items = frappe.get_all(
		"BEI DOLE Compliance Checklist",
		filters={"parent": sep.name, "parenttype": "Employee Separation"},
		fields=["name", "compliance_item", "status", "completed_date", "completed_by", "notes"],
	)

	# Calculate progress
	total_items = len(compliance_items)
	completed_items = sum(1 for i in compliance_items if i.status == "Completed")

	return {
		"has_separation": True,
		"separation": sep,
		"compliance_items": compliance_items,
		"compliance_progress": {
			"total": total_items,
			"completed": completed_items,
			"percentage": round((completed_items / total_items * 100) if total_items > 0 else 0, 1),
		},
	}


# ============================================================================
# COE GENERATION
# ============================================================================


# ============================================================================
# SEPARATION NOTIFICATION HOOKS (called from hooks.py doc_events)
# ============================================================================


def on_separation_created(doc, method=None):
	"""After Employee Separation is created: notify department heads about clearance items.

	Sends Google Chat notification (via shared send_message_to_space).
	Falls back silently if Chat not configured.

	Called by hooks.py: Employee Separation → after_insert
	"""
	try:
		from hrms.api.google_chat import send_message_to_space

		employee_name = doc.employee_name or doc.employee
		dept = getattr(doc, "department", "") or ""
		sep_type = getattr(doc, "custom_separation_type", "") or "Separation"
		begins_on = str(getattr(doc, "boarding_begins_on", "") or frappe.utils.today())

		message = (
			f"*Employee Separation Created*\n"
			f"*Employee:* {employee_name}\n"
			f"*Department:* {dept}\n"
			f"*Type:* {sep_type}\n"
			f"*Clearance begins:* {begins_on}\n"
			f"*Action required:* Complete your department's clearance items for this employee.\n"
			f"View in ERP: {frappe.utils.get_url()}/app/employee-separation/{doc.name}"
		)

		# Get notification space from BEI Settings (HR notification channel)
		try:
			space = frappe.db.get_single_value("BEI Settings", "gchat_notification_space")
		except Exception:
			space = None

		if space:
			send_message_to_space(space, message)
		else:
			frappe.log_error(
				f"Separation created for {employee_name} but gchat_notification_space not configured",
				"Separation Notification",
			)

	except Exception:
		# Notifications must never crash the main flow
		frappe.log_error(frappe.get_traceback(), "Separation Created Notification Failed")


def on_separation_updated(doc, method=None):
	"""On Employee Separation update: check if all clearance items are completed.

	If complete → notify Finance to proceed with final pay.

	Called by hooks.py: Employee Separation → on_update
	"""
	try:
		# Check if all DOLE compliance items are Completed or Not Applicable
		compliance_items = getattr(doc, "custom_dole_compliance", []) or []

		if not compliance_items:
			return

		all_done = all(item.status in ("Completed", "Not Applicable") for item in compliance_items)

		if not all_done:
			return

		# Only notify once (check boarding_status hasn't already been set to Completed)
		if getattr(doc, "boarding_status", "") == "Completed":
			return

		from hrms.api.google_chat import send_message_to_space

		employee_name = doc.employee_name or doc.employee

		message = (
			f"*Clearance Complete — Final Pay Pending*\n"
			f"*Employee:* {employee_name}\n"
			f"*Separation:* {doc.name}\n"
			f"All clearance items have been completed.\n"
			f"*Finance:* Please proceed with final pay computation.\n"
			f"*HR:* Please update employee status to 'Left'.\n"
			f"View: {frappe.utils.get_url()}/app/employee-separation/{doc.name}"
		)

		try:
			space = frappe.db.get_single_value("BEI Settings", "gchat_notification_space")
		except Exception:
			space = None

		if space:
			send_message_to_space(space, message)
			frappe.db.set_value("Employee Separation", doc.name, "boarding_status", "Completed")

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Separation Updated Notification Failed")


@frappe.whitelist(allow_guest=False)
def generate_coe(employee: str):
	"""
	Generate Certificate of Employment for an employee.

	Args:
		employee: Employee ID

	Returns:
		dict: COE details or PDF URL
	"""
	emp_doc = frappe.get_doc("Employee", employee)

	# Check if separation exists and clearance is complete
	separation = frappe.get_all(
		"Employee Separation",
		filters={"employee": employee},
		fields=["name", "boarding_status", "custom_coe_generated"],
		order_by="creation desc",
		limit=1,
	)

	coe_data = {
		"employee_name": emp_doc.employee_name,
		"employee_id": emp_doc.name,
		"company": emp_doc.company,
		"designation": emp_doc.designation,
		"department": emp_doc.department,
		"date_of_joining": emp_doc.date_of_joining,
		"relieving_date": emp_doc.relieving_date,
		"issue_date": frappe.utils.today(),
	}

	# Mark COE as generated if separation exists
	pdf_url = ""
	if separation:
		sep_doc = frappe.get_doc("Employee Separation", separation[0].name)
		sep_doc.custom_coe_generated = 1
		sep_doc.save()
		pdf_url = f"/api/method/frappe.utils.print_format.download_pdf?doctype=Employee+Separation&name={separation[0].name}&format=Standard&no_letterhead=0"
	else:
		pdf_url = f"/api/method/frappe.utils.print_format.download_pdf?doctype=Employee&name={employee}&format=Standard&no_letterhead=0"

	return {
		"success": True,
		"message": _("COE generated successfully"),
		"coe_data": coe_data,
		"pdf_url": pdf_url,
	}

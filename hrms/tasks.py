import frappe
from frappe.utils import add_days, now_datetime, get_datetime


def auto_punch_out_stale_shifts():
	"""
	Scheduled task: Auto punch-out shifts in progress for >24 hours.
	Runs: Every hour via scheduler_events["hourly"]

	Logic:
	1. Find shifts punched in >24 hours ago with no punch_out
	2. Auto punch-out at 24-hour mark from punch_in
	3. Set auto_punched_out = 1, verification_status = "Flagged"
	4. Add note for manager review
	5. Send email to employee + supervisor
	6. Commit changes
	"""
	# Guard against concurrent runs
	lock_key = "auto_punch_out_running"
	if frappe.cache.get(lock_key):
		frappe.log_error(
			title="Auto Punch-Out Skipped",
			message="Auto punch-out already running, skipping this cycle",
		)
		return

	frappe.cache.set(lock_key, True, expires_in_sec=3600)

	try:
		# Find shifts punched in >24 hours ago, still in progress
		cutoff = add_days(now_datetime(), -1)

		stale_shifts = frappe.get_all(
			"BEI Shift Record",
			filters={
				"status": "In Progress",
				"punch_in_time": ["<", cutoff],
				"punch_out_time": ["is", "not set"],
			},
			fields=["name", "employee", "employee_name", "punch_in_time"],
		)

		if not stale_shifts:
			return

		for shift_data in stale_shifts:
			try:
				shift = frappe.get_doc("BEI Shift Record", shift_data.name)

				# Auto punch-out at 24-hour mark from punch_in
				auto_punch_time = add_days(get_datetime(shift.punch_in_time), 1)

				shift.punch_out_time = auto_punch_time
				shift.auto_punched_out = 1
				shift.status = "Completed"
				shift.verification_status = "Flagged"
				shift.notes = (
					"AUTO: Punched out after 24 hours. "
					"Manager please verify actual shift end."
				)

				# Calculate total (will be 24 hours)
				shift.total_hours = 24.0
				shift.overtime_flag = 1

				shift.save(ignore_permissions=True)

				# Notify employee + supervisor
				_notify_auto_punch_out(shift, shift_data)

			except Exception:
				frappe.log_error(
					title=f"Auto Punch-Out Error: {shift_data.name}",
					message=frappe.get_traceback(),
				)

		frappe.db.commit()

		frappe.log_error(
			title="Auto Punch-Out Summary",
			message=f"Auto punched-out {len(stale_shifts)} stale shifts",
		)

	finally:
		frappe.cache.delete(lock_key)


def _notify_auto_punch_out(shift, shift_data):
	"""Send notification emails to employee and supervisor about auto punch-out."""
	# Notify employee
	employee_email = frappe.get_value("Employee", shift.employee, "user_id")
	if employee_email:
		frappe.sendmail(
			recipients=[employee_email],
			subject=f"Auto Punch-Out: {shift_data.employee_name}",
			message=f"""
			<p>You were automatically punched out after 24 hours.</p>
			<p><strong>Punch-in:</strong> {shift.punch_in_time}</p>
			<p><strong>Auto punch-out:</strong> {shift.punch_out_time}</p>
			<p>Please confirm your actual shift end time with your supervisor.</p>
			""",
		)

	# Notify supervisor
	supervisor = frappe.get_value("Employee", shift.employee, "reports_to")
	if supervisor:
		supervisor_email = frappe.get_value("Employee", supervisor, "user_id")
		if supervisor_email:
			frappe.sendmail(
				recipients=[supervisor_email],
				subject=f"Review Required: {shift_data.employee_name} auto punched-out",
				message=f"""
				<p>{shift_data.employee_name} was automatically punched out after 24 hours.</p>
				<p>Please verify actual shift end time and adjust if needed.</p>
				<p><a href="/app/bei-shift-record/{shift.name}">Review Shift Record</a></p>
				""",
			)

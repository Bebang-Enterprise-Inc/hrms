from __future__ import annotations

import frappe


_TASK_NOTIFICATION_NAMES = [
	"New Task Created",
	"Task Due Tomorrow",
	"Task Overdue",
	"Task Status Changed",
	"Task Assigned",  # may be disabled; still useful to preview formatting
]


def _pick_task(task_name: str | None) -> frappe.model.document.Document:
	if task_name:
		return frappe.get_doc("Task", task_name)

	# Prefer a task with subject+project+due date if possible.
	rows = frappe.get_all(
		"Task",
		fields=["name"],
		filters=[["status", "!=", "Cancelled"]],
		order_by="modified desc",
		limit_page_length=1,
	)
	if not rows:
		frappe.throw("No Task records found to render test emails.")
	return frappe.get_doc("Task", rows[0]["name"])


def _render(value: str, doc: frappe.model.document.Document) -> str:
	# `frappe.render_template` safely renders Jinja with access to frappe helpers.
	return frappe.render_template(value or "", {"doc": doc, "frappe": frappe})


@frappe.whitelist()
def send_task_notification_tests(
	email: str = "sam@bebang.ph",
	task_name: str | None = None,
	include_disabled: int | str = 1,
):
	"""
	Send one test email for each Task Notification template to `email`.

	Uses real Notification `subject` + `message` fields and renders them with a real Task doc.
	"""
	# Basic access control: only logged-in users with permission to read Task + Notification
	if frappe.session.user == "Guest":
		frappe.throw("Not authenticated.")

	task_doc = _pick_task(task_name)

	include_disabled = int(include_disabled) if isinstance(include_disabled, (int, str)) else 1
	results: list[dict] = []

	for notif_name in _TASK_NOTIFICATION_NAMES:
		if not frappe.db.exists("Notification", notif_name):
			results.append({"name": notif_name, "sent": False, "reason": "missing_notification"})
			continue

		notification = frappe.get_doc("Notification", notif_name)
		if not include_disabled and not int(getattr(notification, "enabled", 0) or 0):
			results.append({"name": notif_name, "sent": False, "reason": "disabled"})
			continue

		try:
			subject = _render(notification.subject or notif_name, task_doc)
			message = _render(notification.message or "", task_doc)
			# Force HTML
			frappe.sendmail(
				recipients=[email],
				subject=subject,
				message=message,
				delayed=False,
			)
			results.append({"name": notif_name, "sent": True})
		except Exception as e:
			# Keep server-side evidence without leaking content
			frappe.log_error(
				title="Task Notification Test Email Failed",
				message=f"Notification={notif_name}, Task={task_doc.name}, Err={str(e)[:200]}",
			)
			results.append({"name": notif_name, "sent": False, "reason": "error"})

	return {
		"success": True,
		"task": task_doc.name,
		"email": email,
		"results": results,
	}



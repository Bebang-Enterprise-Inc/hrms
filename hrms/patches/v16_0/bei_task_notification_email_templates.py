from __future__ import annotations

import frappe


def _base_email_shell(*, title: str, subtitle: str, body_html: str, cta_url: str, cta_label: str) -> str:
	"""
	Returns a Gmail-safe-ish HTML email layout (inline styles, table-based).
	NOTE: `title/subtitle/body_html/cta_*` may include Jinja placeholders.
	"""
	# Keep CSS inline for client compatibility. Avoid external fonts.
	return f"""
<div style="background:#f5f7fb;margin:0;padding:24px 0">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse">
    <tr>
      <td align="center" style="padding:0 12px">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="border-collapse:collapse;max-width:600px;width:100%">
          <tr>
            <td style="padding:0 0 12px 0">
              <div style="font-family:Arial,Helvetica,sans-serif;color:#111827;font-size:14px;opacity:.9">
                <strong>Bebang Tasks</strong>
              </div>
            </td>
          </tr>

          <tr>
            <td style="background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:18px 20px">
              <div style="font-family:Arial,Helvetica,sans-serif;color:#111827">
                <div style="font-size:18px;font-weight:700;line-height:1.35;margin:0 0 6px 0">{title}</div>
                <div style="font-size:13px;line-height:1.45;color:#374151;margin:0 0 14px 0">{subtitle}</div>
                {body_html}
                <div style="margin:18px 0 0 0">
                  <a href="{cta_url}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;
                            padding:10px 14px;border-radius:10px">
                    {cta_label}
                  </a>
                </div>
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:12px 0 0 0">
              <div style="font-family:Arial,Helvetica,sans-serif;color:#6b7280;font-size:12px;line-height:1.45">
                This is an automated notification from <strong>tasks.bebang.ph</strong>.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
""".strip()


def _task_details_block() -> str:
	# Use a simple key/value table for consistent alignment across clients.
	return """
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;margin:12px 0 0 0">
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Task</strong>: {{ doc.subject or doc.name }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Task ID</strong>: {{ doc.name }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Project</strong>: {{ doc.project or "-" }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Status</strong>: {{ doc.status or "-" }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Priority</strong>: {{ doc.priority or "-" }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Due Date</strong>: {{ doc.exp_end_date or "-" }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Assigned to</strong>: {{ doc._assign or "-" }}
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Assigned/Updated by</strong>:
      {{ frappe.utils.get_fullname(doc.modified_by) if doc.modified_by else "-" }}
      ({{ doc.modified_by or "-" }})
    </td>
  </tr>
  <tr>
    <td style="padding:8px 0;border-top:1px solid #eef2f7;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827">
      <strong>Created by</strong>:
      {{ frappe.utils.get_fullname(doc.owner) if doc.owner else "-" }}
      ({{ doc.owner or "-" }})
    </td>
  </tr>
</table>
""".strip()


def _update_notification(name: str, *, subject: str, message_html: str) -> bool:
	"""Returns True if updated/created, False if notification not found."""
	if not frappe.db.exists("Notification", name):
		return False

	doc = frappe.get_doc("Notification", name)
	changed = False

	# Clean subject formatting (remove leading '? ' accidents).
	if getattr(doc, "subject", None) != subject:
		doc.subject = subject
		changed = True

	# Ensure email body is HTML and modern.
	if getattr(doc, "message", None) != message_html:
		doc.message = message_html
		changed = True

	# Make sure email is enabled if this notification exists.
	# (Don't force-enable disabled notifications like "Task Assigned".)
	if name != "Task Assigned":
		if getattr(doc, "enabled", 1) != 1:
			doc.enabled = 1
			changed = True

	if changed:
		doc.save(ignore_permissions=True)

	return True


def execute():
	"""
	Upgrade Task-related Notification emails for tasks.bebang.ph:
	- Remove stray '? ' from subjects
	- Replace bland/plain email bodies with branded HTML templates
	"""
	frappe.db.commit()  # keep patch behavior consistent if run in long migrate chains

	task_url = '{{ frappe.utils.get_url_to_form("Task", doc.name) }}'
	details = _task_details_block()

	notifications = {
		"New Task Created": {
			"subject": "New Task: {{ doc.subject or doc.name }}",
			"title": "New task created",
			"subtitle": "A new task was created and may need your attention.",
		},
		"Task Due Tomorrow": {
			"subject": "Task due tomorrow: {{ doc.subject or doc.name }}",
			"title": "Task due tomorrow",
			"subtitle": "Reminder: this task is due tomorrow.",
		},
		"Task Overdue": {
			"subject": "Task overdue: {{ doc.subject or doc.name }}",
			"title": "Task overdue",
			"subtitle": "This task is now overdue. Please review and update status if needed.",
		},
		"Task Status Changed": {
			"subject": "Task status updated: {{ doc.subject or doc.name }}",
			"title": "Task status updated",
			"subtitle": "The task status has changed. Here are the latest details.",
		},
		# Keep "Task Assigned" out of auto-enable, but still upgrade email formatting if present.
		"Task Assigned": {
			"subject": "Task assigned: {{ doc.subject or doc.name }}",
			"title": "Task assigned",
			"subtitle": "You were assigned to a task.",
		},
	}

	updated_any = False
	for notif_name, cfg in notifications.items():
		body = (
			'<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.55;color:#111827">'
			+ details
			+ "</div>"
		)
		html = _base_email_shell(
			title=cfg["title"],
			subtitle=cfg["subtitle"],
			body_html=body,
			cta_url=task_url,
			cta_label="View task",
		)
		ok = _update_notification(notif_name, subject=cfg["subject"], message_html=html)
		updated_any = updated_any or ok

	if updated_any:
		frappe.db.commit()



app_name = "hrms"
app_title = "Frappe HR"
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "Modern HR and Payroll Software"
app_email = "contact@frappe.io"
app_license = "GNU General Public License (v3)"
required_apps = ["frappe/erpnext"]
source_link = "http://github.com/frappe/hrms"
app_logo_url = "/assets/hrms/images/frappe-hr-logo.svg"
app_home = "/app/overview"

add_to_apps_screen = [
	{
		"name": "hrms",
		"logo": "/assets/hrms/images/frappe-hr-logo.svg",
		"title": "Frappe HR",
		"route": "/app/overview",
		"has_permission": "hrms.hr.utils.check_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hrms/css/hrms.css"
app_include_js = [
	"hrms.bundle.js",
]
app_include_css = "hrms.bundle.css"

# website

# include js, css files in header of web template
# Note: hrms.bundle.css contains login.scss styles for the login page
web_include_css = "hrms.bundle.css"
# web_include_js = "/assets/hrms/js/hrms.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hrms/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Employee": "public/js/erpnext/employee.js",
	"Company": "public/js/erpnext/company.js",
	"Department": "public/js/erpnext/department.js",
	"Timesheet": "public/js/erpnext/timesheet.js",
	"Payment Entry": "public/js/erpnext/payment_entry.js",
	"Journal Entry": "public/js/erpnext/journal_entry.js",
	"Delivery Trip": "public/js/erpnext/delivery_trip.js",
	"Bank Transaction": "public/js/erpnext/bank_transaction.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

calendars = ["Leave Application"]

# Generators
# ----------

# automatically create page for each record of this doctype
website_generators = ["Job Opening"]

website_route_rules = [
	{"from_route": "/hrms/<path:app_path>", "to_route": "hrms"},
	{"from_route": "/hr/<path:app_path>", "to_route": "roster"},
]

# Website redirects - redirect /login to custom BEI HQ login page
website_redirects = [
	{"source": "/login", "target": "/bei-login", "redirect_http_status": 302},
]
# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"hrms.utils.get_country",
	],
}

# Installation
# ------------

# before_install = "hrms.install.before_install"
after_install = "hrms.install.after_install"
after_migrate = "hrms.setup.update_select_perm_after_install"

setup_wizard_complete = "hrms.subscription_utils.update_erpnext_access"

# Uninstallation
# ------------

before_uninstall = "hrms.uninstall.before_uninstall"
# after_uninstall = "hrms.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hrms.utils.before_app_install"
after_app_install = "hrms.setup.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

before_app_uninstall = "hrms.setup.before_app_uninstall"
# after_app_uninstall = "hrms.utils.after_app_uninstall"

# Sentry Observability
# --------------------
# NOTE: after_exception is NOT a valid Frappe hook. Exception capture is done
# by monkey-patching frappe.app.handle_exception in sentry.py init.
before_request = "hrms.utils.sentry.add_request_breadcrumb"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hrms.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Employee": "hrms.api.hr_reports.get_employee_permission_query_conditions",
}

# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

has_upload_permission = {"Employee": "erpnext.setup.doctype.employee.employee.has_upload_permission"}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Employee": "hrms.overrides.employee_master.EmployeeMaster",
	"Timesheet": "hrms.overrides.employee_timesheet.EmployeeTimesheet",
	"Payment Entry": "hrms.overrides.employee_payment_entry.EmployeePaymentEntry",
	"Project": "hrms.overrides.employee_project.EmployeeProject",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"User": {
		"validate": [
			"erpnext.setup.doctype.employee.employee.validate_employee_role",
			"hrms.overrides.employee_master.update_approver_user_roles",
		],
	},
	"Company": {
		"validate": "hrms.overrides.company.validate_default_accounts",
		"on_update": [
			"hrms.overrides.company.make_company_fixtures",
			"hrms.overrides.company.set_default_hr_accounts",
		],
		"on_trash": "hrms.overrides.company.handle_linked_docs",
	},
	"Holiday List": {
		"on_update": "hrms.utils.holiday_list.invalidate_cache",
		"on_trash": "hrms.utils.holiday_list.invalidate_cache",
	},
	"Timesheet": {"validate": "hrms.hr.utils.validate_active_employee"},
	"Payment Entry": {
		"on_submit": "hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
		"on_cancel": "hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
		"on_update_after_submit": "hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
	},
	"Unreconcile Payment": {
		"on_submit": "hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
	},
	"Journal Entry": {
		"validate": "hrms.hr.doctype.expense_claim.expense_claim.validate_expense_claim_in_jv",
		"on_submit": [
			"hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
			"hrms.hr.doctype.full_and_final_statement.full_and_final_statement.update_full_and_final_statement_status",
			"hrms.payroll.doctype.salary_withholding.salary_withholding.update_salary_withholding_payment_status",
		],
		"on_update_after_submit": "hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
		"on_cancel": [
			"hrms.hr.doctype.expense_claim.expense_claim.update_payment_for_expense_claim",
			"hrms.payroll.doctype.salary_slip.salary_slip.unlink_ref_doc_from_salary_slip",
			"hrms.hr.doctype.full_and_final_statement.full_and_final_statement.update_full_and_final_statement_status",
			"hrms.payroll.doctype.salary_withholding.salary_withholding.update_salary_withholding_payment_status",
		],
	},
	"Loan": {"validate": "hrms.hr.utils.validate_loan_repay_from_salary"},
	"Employee": {
		"validate": [
			"hrms.overrides.employee_master.validate_onboarding_process",
			"hrms.utils.bio_id_validation.validate_employee_bio_id",
		],
		"on_update": [
			"hrms.overrides.employee_master.update_approver_role",
			"hrms.overrides.employee_master.publish_update",
		],
		"after_insert": "hrms.overrides.employee_master.update_job_applicant_and_offer",
		"on_trash": "hrms.overrides.employee_master.update_employee_transfer",
		"after_delete": "hrms.overrides.employee_master.publish_update",
	},
	"Project": {"validate": "hrms.controllers.employee_boarding_controller.update_employee_boarding_status"},
	"Task": {"on_update": "hrms.controllers.employee_boarding_controller.update_task"},
	"BEI Expense Request": {
		"on_update": "hrms.api.pcf.on_expense_update",
		"on_trash": "hrms.api.pcf.on_expense_delete",
	},
	"BEI PCF Batch": {
		"validate": "hrms.api.pcf.validate_pcf_batch",
		"on_update": "hrms.api.pcf.on_batch_update",
	},
	"BEI Billing Schedule": {
		"validate": "hrms.api.billing.on_billing_schedule_validate",
		"on_update": "hrms.api.billing.on_billing_schedule_update",
	},
	"BEI Approval Queue": {
		"after_insert": "hrms.api.google_chat.on_approval_queue_insert",
	},
	"BEI Store Order": {
		"on_update": "hrms.api.google_chat.on_store_order_update",
	},
	"Employee Separation": {
		# Notify dept heads when clearance items assigned (SEP-01)
		"after_insert": "hrms.api.employee_clearance.on_separation_created",
		# Notify Finance when all clearance items completed (SEP-02)
		"on_update": "hrms.api.employee_clearance.on_separation_updated",
	},
}

# ============================================================
# BEI Brain S023B: Register brain_sync hook for all configured DocTypes
# This adds on_event handler to doc_events for each DocType in
# hrms.utils.brain_sync.DOCTYPE_MAP without overwriting existing hooks.
# ============================================================
_BRAIN_SYNC_HANDLER = "hrms.utils.brain_sync.on_event"
_BRAIN_SYNC_EVENTS = [
	"on_submit",
	"on_update_after_submit",
	"on_cancel",
	"after_insert",
]
_BRAIN_SYNC_DOCTYPES = [
	# D01 - Procurement & Billing
	"BEI Purchase Order",
	"BEI Purchase Requisition",
	"BEI Goods Receipt",
	"BEI Invoice",
	"BEI Payment Request",
	"BEI Statement of Account",
	"Expense Claim",
	"Employee Advance",
	# D02 - Inventory & Warehouse
	"BEI Cycle Count",
	"BEI Store Order",
	"BEI Store Receiving",
	"BEI FQI Report",
	"BEI Pick List",
	# D03 - Commissary & Production
	"BEI Production",
	"BEI QC Form",
	"BEI Distribution Trip",
	# D04 - HR Core & Workforce
	"Attendance",
	"Attendance Request",
	"Leave Application",
	"Leave Allocation",
	"BEI Overtime Request",
	"Shift Assignment",
	"Shift Request",
	"Overtime Slip",
	"BEI Official Business",
	"Salary Slip",
	"Payroll Entry",
	"Employee Separation",
	"Employee Transfer",
	"Employee Promotion",
	"BEI Transfer Request",
	"BEI HR Personnel Action",
	"BEI Incident Report",
	"BEI Notice to Explain",
	"BEI Notice of Decision",
	"Job Applicant",
	"Job Offer",
	"Employee Onboarding",
	"Appraisal",
	"BEI Expense Request",
	"BEI Petty Cash Fund",
	# D05 - Projects & Maintenance
	"BEI Maintenance Request",
	"BEI Maintenance Completion",
	"BEI Project",
	"BEI Site Inspection",
	# D06 - Integrations & Platform
	"BEI Announcement",
	"BEI POS Upload",
	# D07 - Finance & Analytics
	"BEI Store Opening Report",
	"BEI Store Closing Report",
	"BEI Bank Deposit",
	"BEI Store Visit Report",
	"BEI Mid-Shift Handover",
]

for _dt in _BRAIN_SYNC_DOCTYPES:
	if _dt not in doc_events:
		doc_events[_dt] = {}
	for _evt in _BRAIN_SYNC_EVENTS:
		existing = doc_events[_dt].get(_evt)
		if existing is None:
			doc_events[_dt][_evt] = _BRAIN_SYNC_HANDLER
		elif isinstance(existing, str):
			if existing != _BRAIN_SYNC_HANDLER:
				doc_events[_dt][_evt] = [existing, _BRAIN_SYNC_HANDLER]
		elif isinstance(existing, list):
			if _BRAIN_SYNC_HANDLER not in existing:
				existing.append(_BRAIN_SYNC_HANDLER)

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"hrms.hr.doctype.interview.interview.send_interview_reminder",
	],
	"hourly": [
		"hrms.hr.doctype.daily_work_summary_group.daily_work_summary_group.trigger_emails",
		"hrms.api.pcf.check_threshold_and_auto_submit",
		"hrms.tasks.auto_punch_out_stale_shifts",
		"hrms.api.projects.check_sla_violations",
		"hrms.api.transfer_requests.run_due_transfer_submissions",
		"hrms.api.transfer_requests.run_ready_transfer_sync",
		"hrms.api.transfer_requests.reconcile_transfer_sync_status",
		"hrms.tasks.run_transfer_reliever_cleanup",
	],
	"cron": {
		# Weather collection 5x daily: 6AM, 10AM, 2PM, 6PM, 10PM
		"0 6,10,14,18,22 * * *": [
			"hrms.utils.weather_service.collect_all_weather",
		],
		# Biometric monitoring: refresh cache every 6 hours (midnight, 6AM, noon, 6PM UTC)
		"0 0,6,12,18 * * *": [
			"hrms.utils.adms_monitor.refresh_biometric_status",
		],
		# Biometric daily digest: 7 AM PHT = 23:00 UTC (previous day)
		"0 23 * * *": [
			"hrms.utils.biometric_alerts.send_daily_digest",
		],
		# Monthly billing generation: 6 AM on 1st of each month
		"0 6 1 * *": ["hrms.api.billing.scheduled_monthly_billing"],
		# Discount audit workbook: 12:50 AM PHT after Supabase alert refresh at 12:35 AM PHT
		"50 16 * * *": ["hrms.api.discount_abuse.scheduled_generate_daily_discount_audit_report"],
		# Discount alert notifications: 1:05 AM PHT after workbook generation
		"5 17 * * *": ["hrms.api.discount_abuse.scheduled_send_critical_discount_alert_notifications"],
	},
	"hourly_long": [
		"hrms.hr.doctype.shift_type.shift_type.update_last_sync_of_checkin",
		"hrms.hr.doctype.shift_type.shift_type.process_auto_attendance_for_all_shifts",
		"hrms.hr.doctype.shift_schedule_assignment.shift_schedule_assignment.process_auto_shift_creation",
	],
	"daily": [
		"hrms.controllers.employee_reminders.send_birthday_reminders",
		"hrms.controllers.employee_reminders.send_work_anniversary_reminders",
		"hrms.hr.doctype.daily_work_summary_group.daily_work_summary_group.send_summary",
		"hrms.hr.doctype.interview.interview.send_daily_feedback_reminder",
		"hrms.hr.doctype.job_opening.job_opening.close_expired_job_openings",
		"hrms.api.pcf.check_month_end_auto_submit",
		"hrms.api.procurement.check_overdue_or",
		"hrms.api.procurement.check_overdue_invoices",
		"hrms.api.inventory.send_low_stock_daily_alert",
		"hrms.api.inventory_risk.recompute_risk_snapshots",
		"hrms.api.permits.check_permit_expiry",
		"hrms.tasks.send_overdue_action_plan_reminders",
		"hrms.api.overtime.scheduled_overtime_detection",
	],
	"daily_long": [
		"hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry.process_expired_allocation",
		"hrms.hr.utils.generate_leave_encashment",
		"hrms.hr.utils.allocate_earned_leaves",
	],
	"weekly": ["hrms.controllers.employee_reminders.send_reminders_in_advance_weekly"],
	"monthly": ["hrms.controllers.employee_reminders.send_reminders_in_advance_monthly"],
}

advance_payment_payable_doctypes = ["Leave Encashment", "Gratuity", "Employee Advance"]

invoice_doctypes = ["Expense Claim"]

period_closing_doctypes = ["Payroll Entry"]

accounting_dimension_doctypes = [
	"Expense Claim",
	"Expense Claim Detail",
	"Expense Taxes and Charges",
	"Payroll Entry",
	"Leave Encashment",
]

bank_reconciliation_doctypes = ["Expense Claim"]

# Testing
# -------

before_tests = "hrms.tests.test_utils.before_tests"

# Overriding Methods
# -----------------------------

# get matching queries for Bank Reconciliation
get_matching_queries = "hrms.hr.utils.get_matching_queries"

regional_overrides = {
	"India": {
		"hrms.hr.utils.calculate_annual_eligible_hra_exemption": "hrms.regional.india.utils.calculate_annual_eligible_hra_exemption",
		"hrms.hr.utils.calculate_hra_exemption_for_period": "hrms.regional.india.utils.calculate_hra_exemption_for_period",
		"hrms.hr.utils.calculate_tax_with_marginal_relief": "hrms.regional.india.utils.calculate_tax_with_marginal_relief",
	},
}

# ERPNext doctypes for Global Search
global_search_doctypes = {
	"Default": [
		{"doctype": "Salary Slip", "index": 19},
		{"doctype": "Leave Application", "index": 20},
		{"doctype": "Expense Claim", "index": 21},
		{"doctype": "Employee Grade", "index": 37},
		{"doctype": "Job Opening", "index": 39},
		{"doctype": "Job Applicant", "index": 40},
		{"doctype": "Job Offer", "index": 41},
		{"doctype": "Salary Structure Assignment", "index": 42},
		{"doctype": "Appraisal", "index": 43},
	],
}

# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hrms.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Employee": "hrms.overrides.dashboard_overrides.get_dashboard_for_employee",
	"Holiday List": "hrms.overrides.dashboard_overrides.get_dashboard_for_holiday_list",
	"Task": "hrms.overrides.dashboard_overrides.get_dashboard_for_project",
	"Project": "hrms.overrides.dashboard_overrides.get_dashboard_for_project",
	"Timesheet": "hrms.overrides.dashboard_overrides.get_dashboard_for_timesheet",
	"Bank Account": "hrms.overrides.dashboard_overrides.get_dashboard_for_bank_account",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

ignore_links_on_delete = ["PWA Notification"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hrms.auth.validate"
# ]

# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []

company_data_to_be_ignored = [
	"Salary Component Account",
	"Salary Structure",
	"Salary Structure Assignment",
	"Payroll Period",
	"Income Tax Slab",
	"Leave Period",
	"Leave Policy Assignment",
	"Employee Onboarding Template",
	"Employee Separation Template",
]

# List of apps whose translatable strings should be excluded from this app's translations.
ignore_translatable_strings_from = ["frappe", "erpnext"]

# Fixtures
# --------
fixtures = ["Custom Field"]

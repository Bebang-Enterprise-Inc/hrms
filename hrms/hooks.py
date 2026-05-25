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
		"validate": [
			# S231-C2 — defense-in-depth: null any default_* / round_off_* /
			# depreciation_* / capital_* / asset_* / stock_* / expenses_*
			# field whose target Account / Cost Center no longer exists,
			# BEFORE validate_default_accounts runs. Guarded by
			# `first_provision_done == 1` so it never clobbers a fresh
			# Company mid-provisioning.
			"hrms.overrides.company.null_out_dead_default_refs",
			# S231 D-2 (N-8 fix) — reject empty store_ownership_type on
			# entity_category=Store Companies; forces explicit
			# classification so blank-default fallback in
			# sales_location_mapping.py never has to fire in production.
			"hrms.overrides.company.validate_store_ownership_type",
			"hrms.overrides.company.validate_default_accounts",
		],
		"on_update": [
			"hrms.overrides.company.make_company_fixtures",
			"hrms.overrides.company.set_default_hr_accounts",
			# S181 — sentinel-gated auto-provision (runs once per Company)
			"hrms.overrides.company.auto_provision_company",
			# S181 — ADMS enqueue worker (idempotent, non-blocking)
			"hrms.overrides.company.auto_enroll_adms_devices",
			# S200 — clear Analytics store mapping cache so new Companies
			# appear in the Store Leaderboard within 30 seconds
			"hrms.utils.sales_location_mapping.clear_cache",
			# S201 audit fix — invalidate branch->Company resolver cache when
			# Company docs change (rename, entity_category flip). Branch hook
			# was wired originally but not Company; a Company rename could leave
			# the resolver returning the old full name for up to 60s.
			"hrms.utils.company_lookup.clear_cache",
		],
		"on_trash": "hrms.overrides.company.handle_linked_docs",
	},
	"Warehouse": {
		# S200 — clear Analytics store mapping cache on warehouse changes
		"on_update": "hrms.utils.sales_location_mapping.clear_cache",
		"on_trash": "hrms.utils.sales_location_mapping.clear_cache",
	},
	"Sales Invoice": {
		# S238 v2.2 — autoname BKI SIs as BKI-SI-{YYYY}-{order-tail}-{n}
		# embedding the originating BEI Store Order # for traceability.
		# No-op for non-BKI SIs (Frappe falls back to naming_series).
		"autoname": "hrms.api.bki_si_naming.set_bki_si_name",
		# S238/S247 — paired-doc generators on SI submit. ORDER: PI first, SE second.
		# Each generator runs independently with its own savepoint isolation; one
		# failure doesn't block the other. Daily reconciliation cron (S248) sweeps
		# half-paired SIs. v3 (S247): converted from STRING to LIST per audit Blocker 1.
		"on_submit": [
			"hrms.api.bki_store_pi_generator.maybe_generate_store_pi",
			"hrms.api.bki_store_stock_entry_generator.maybe_generate_store_stock_entry",
		],
		# S253 fix — Frappe's cancel() calls check_if_doc_is_linked() BEFORE
		# on_cancel hooks fire. The bki_si_reference Link field on paired PI/SE
		# triggers LinkExistsError, preventing cancellation entirely. The
		# before_cancel hook sets ignore_links_for_doctype so the link check
		# passes, then on_cancel cascade handles the paired docs correctly.
		"before_cancel": "hrms.api.bki_store_pi_generator.allow_bki_si_cancel_with_paired_docs",
		# S238/S247 — cascade-cancel paired docs on SI cancel. ORDER: SE FIRST, PI SECOND
		# (reverse-creation, textbook cancellation pattern). Cancelling SE first keeps
		# SRBNB net at zero throughout the cancellation window. v3 (S247): converted
		# from STRING to LIST per audit Blocker 1 + cascade order per Blocker 10.
		"on_cancel": [
			"hrms.api.bki_store_stock_entry_generator.cascade_cancel_store_stock_entry",
			"hrms.api.bki_store_pi_generator.cascade_cancel_store_pi",
		],
	},
	"Purchase Invoice": {
		# S238 v2-B8 — lock posting_date on auto-generated paired PIs
		# (must match BKI SI's posting_date per ICT-007 + PFRS 15).
		"validate": "hrms.api.bki_store_pi_generator.lock_posting_date_on_bki_paired_pi",
	},
	"Branch": {
		# S201 — invalidate branch->Company resolver cache when Branch docs change
		"on_update": "hrms.utils.company_lookup.clear_cache",
		"on_trash": "hrms.utils.company_lookup.clear_cache",
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
			# S201 Option X (2026-04-17): derive_company_from_branch hook is
			# DISABLED. Employee.company stays on the legal employer and is
			# only changed manually by HR via the Frappe Desk Company dropdown.
			# Per-store internal billing is handled by S202 allocation JE engine
			# (punch-based), NOT by moving Employee.company. Keeping the
			# function in employee_master.py for reference / future use.
			# "hrms.overrides.employee_master.derive_company_from_branch",
		],
		"on_update": [
			"hrms.overrides.employee_master.update_approver_role",
			"hrms.overrides.employee_master.publish_update",
		],
		"after_insert": "hrms.overrides.employee_master.update_job_applicant_and_offer",
		"on_trash": "hrms.overrides.employee_master.update_employee_transfer",
		"after_delete": "hrms.overrides.employee_master.publish_update",
	},
	"Leave Application": {
		"validate": "hrms.overrides.leave_application_hooks.validate_no_overtime_conflict",
		"on_update": "hrms.overrides.leave_application_hooks.on_leave_status_change",
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
	"Stock Entry": {
		# S136: Update production target actuals when Manufacture SE is submitted/cancelled
		"on_submit": "hrms.api.commissary_planning.on_stock_entry_submit",
		# S168 Phase 3.1: chain orphan-draft-SI cleanup AFTER the S136 handler.
		# Frappe doc_events accept a list — handlers run in order.
		"on_cancel": [
			"hrms.api.commissary_planning.on_stock_entry_cancel",
			"hrms.api.commissary._delete_orphan_draft_si_on_se_cancel",
		],
		# S247 hotfix — lock posting_date on auto-generated paired SEs (BKI->Store flow).
		# v3 of S247 originally added a SECOND "Stock Entry": {} dict key after the
		# Purchase Invoice block; Python last-key-wins silently dropped this handler.
		# Merged into the existing Stock Entry block here. Must coexist with S136 on_submit.
		"validate": "hrms.api.bki_store_stock_entry_generator.lock_posting_date_on_bki_paired_se",
	},
	# S189: Auto-sync BOM recipe changes to Supabase product_bom table
	"BOM": {
		"on_update": "hrms.utils.bom_supabase_sync.sync_bom_to_supabase",
		"after_insert": "hrms.utils.bom_supabase_sync.sync_bom_to_supabase",
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
		"hrms.api.pcf.check_threshold_and_notify",
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
		# Biometric daily digest + store syncs: 7 AM PHT = 23:00 UTC (previous day)
		"0 23 * * *": [
			"hrms.utils.biometric_alerts.send_daily_digest",
			"hrms.api.erp_sync.enqueue_scheduled_store_inventory_shadow_sync",
			"hrms.api.erp_sync.enqueue_scheduled_store_demand_snapshot_sync",
		],
		# Monthly billing generation: 6 AM on 1st of each month
		"0 6 1 * *": ["hrms.api.billing.scheduled_monthly_billing"],
		# S207 reliever-labor cost-sharing preview (Bimonthly cadence).
		# Daily 22:00 UTC = 06:00 PHT. The function internally checks pht_date.day
		# and no-ops unless it's 1 or 16 — fires twice a month giving Finance
		# 9-10 days to validate before Bimonthly payroll runs (10th / 25th).
		# Daily firing with Python day-guard is robust across all month lengths
		# and DST. See LD-2 + LD-17 in the S207 plan.
		"0 22 * * *": [
			"hrms.api.labor_allocation.preview_scheduled",
		],
		# Morning sync health report: 8:15 AM PHT daily (00:15 UTC) after sync buffer
		"15 0 * * *": [
			"hrms.api.erp_sync.scheduled_generate_morning_sync_health_report",
		],
		# Store inventory shadow sync watchdog: resume stale in-progress runs after deploy interruptions
		"*/10 * * * *": [
			"hrms.api.erp_sync.watch_store_inventory_shadow_sync_health",
		],
		# Discount audit workbook: 12:50 AM PHT after Supabase alert refresh at 12:35 AM PHT
		"42 16 * * *": ["hrms.api.discount_abuse.scheduled_refresh_discount_benchmark_snapshots"],
		# Discount audit workbook: 12:50 AM PHT after benchmark refresh
		"50 16 * * *": ["hrms.api.discount_abuse.scheduled_generate_daily_discount_audit_report"],
		# Discount alert notifications: 1:05 AM PHT after workbook generation
		"5 17 * * *": ["hrms.api.discount_abuse.scheduled_send_critical_discount_alert_notifications"],
		# S043: Daily missing punch report at 00:00 PHT (16:00 UTC)
		# Runs after all retail shifts end (latest S-2P at 23:00 + 60 min checkout)
		# and after auto-attendance hourly job has processed
		"0 16 * * *": ["hrms.services.missing_punch_report.run_daily_missing_punch_report"],
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
		"hrms.api.procurement.escalate_pending_approvals",
		"hrms.api.inventory.send_low_stock_daily_alert",
		"hrms.api.inventory_risk.recompute_risk_snapshots",
		"hrms.api.procurement.check_supplier_document_expiry",
		"hrms.api.permits.check_permit_expiry",
		"hrms.tasks.send_overdue_action_plan_reminders",
		"hrms.api.overtime.scheduled_overtime_detection",
	],
	"daily_long": [
		"hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry.process_expired_allocation",
		"hrms.hr.utils.generate_leave_encashment",
		"hrms.hr.utils.allocate_earned_leaves",
	],
	"weekly": [
		"hrms.controllers.employee_reminders.send_reminders_in_advance_weekly",
		# S238 v2.1-W9 — drift detection: flag BKI SIs without paired PIs.
		# Read-only; logs to Sentry via frappe.log_error if drift found.
		"hrms.api.bki_store_pi_generator.run_si_pi_pairing_check",
	],
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
fixtures = ["Custom Field", "BEI Clearance Station"]

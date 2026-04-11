// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company", {
	refresh: function (frm) {
		frm.set_query("default_expense_claim_payable_account", function () {
			return {
				filters: {
					company: frm.doc.name,
					is_group: 0,
				},
			};
		});

		frm.set_query("default_employee_advance_account", function () {
			return {
				filters: {
					company: frm.doc.name,
					is_group: 0,
					root_type: "Asset",
					account_type: "Receivable",
				},
			};
		});

		frm.set_query("default_payroll_payable_account", function () {
			return {
				filters: {
					company: frm.doc.name,
					is_group: 0,
					root_type: "Liability",
				},
			};
		});

		frm.set_query("hra_component", function () {
			return {
				filters: { type: "Earning" },
			};
		});
	},
});

// S181: Retry Provisioning button (Blocker 14 fix).
//
// Shown only when `first_provision_done == 0` — i.e. a Company whose
// auto-provision hook either has not run yet or failed mid-way and rolled
// back its savepoint. Calls hrms.overrides.company.retry_provision_company
// which clears the sentinel and re-runs auto_provision_company idempotently.
//
// This is a SECOND frappe.ui.form.on("Company", ...) call so the ERPNext-
// origin refresh handler above is preserved unchanged. Frappe merges multiple
// registrations for the same DocType.
frappe.ui.form.on("Company", {
	refresh: function (frm) {
		if (frm.is_new()) return;
		// `first_provision_done` is a Custom Field added in S181 Phase 1 -
		// guard so this button is a no-op on environments where the fixture
		// has not been migrated yet.
		if (!("first_provision_done" in frm.doc)) return;
		if (frm.doc.first_provision_done == 1) return;

		frm.add_custom_button(
			__("Retry Provisioning (S181)"),
			function () {
				frappe.confirm(
					__(
						"Retry S181 provisioning? This will attempt to create the COA " +
							"(Sales + Balance Sheet templates), Warehouse, Cost Center, " +
							"default accounts and BKI Customer for {0}.",
						[frm.doc.name]
					),
					function () {
						frappe.call({
							method: "hrms.overrides.company.retry_provision_company",
							args: { company_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Retrying S181 provisioning..."),
							callback: function (r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("S181 provisioning retried successfully"),
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			},
			__("Actions")
		);
	},
});

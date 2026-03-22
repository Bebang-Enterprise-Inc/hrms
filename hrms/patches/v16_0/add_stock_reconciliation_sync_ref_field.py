from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	custom_fields = {
		"Stock Reconciliation": [
			{
				"fieldname": "custom_sync_ref",
				"fieldtype": "Data",
				"label": "Sync Reference",
				"insert_after": "expense_account",
				"hidden": 1,
				"read_only": 1,
				"no_copy": 1,
				"description": "Idempotency token for ERP sync retries and shadow sync recovery.",
			}
		]
	}

	create_custom_fields(custom_fields)

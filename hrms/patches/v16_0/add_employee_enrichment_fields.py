"""Add custom fields for Employee Data Enrichment Campaign.

These fields support the Store Supervisor data verification dashboard.
"""
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    custom_fields = {
        "Employee": [
            {
                "fieldname": "enrichment_section",
                "fieldtype": "Section Break",
                "label": "Data Enrichment",
                "insert_after": "company_email",
                "collapsible": 1,
            },
            {
                "fieldname": "custom_verification_status",
                "fieldtype": "Select",
                "label": "Verification Status",
                "options": "Pending\nVerified\nHas Issues",
                "default": "Pending",
                "insert_after": "enrichment_section",
            },
            {
                "fieldname": "custom_verified_by",
                "fieldtype": "Link",
                "label": "Verified By",
                "options": "User",
                "insert_after": "custom_verification_status",
                "read_only": 1,
            },
            {
                "fieldname": "custom_verified_date",
                "fieldtype": "Date",
                "label": "Verified Date",
                "insert_after": "custom_verified_by",
                "read_only": 1,
            },
            {
                "fieldname": "custom_verification_notes",
                "fieldtype": "Small Text",
                "label": "Verification Notes",
                "insert_after": "custom_verified_date",
            },
            {
                "fieldname": "enrichment_column_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_verification_notes",
            },
            {
                "fieldname": "custom_issue_type",
                "fieldtype": "Select",
                "label": "Issue Type",
                "options": "\nWrong Name\nWrong Store\nMissing Info\nDuplicate\nOther",
                "insert_after": "enrichment_column_break",
                "depends_on": 'eval:doc.custom_verification_status=="Has Issues"',
            },
            {
                "fieldname": "custom_issue_description",
                "fieldtype": "Small Text",
                "label": "Issue Description",
                "insert_after": "custom_issue_type",
                "depends_on": 'eval:doc.custom_verification_status=="Has Issues"',
            },
            {
                "fieldname": "custom_issue_reported_by",
                "fieldtype": "Link",
                "label": "Issue Reported By",
                "options": "User",
                "insert_after": "custom_issue_description",
                "read_only": 1,
                "depends_on": 'eval:doc.custom_verification_status=="Has Issues"',
            },
            {
                "fieldname": "custom_issue_reported_date",
                "fieldtype": "Date",
                "label": "Issue Reported Date",
                "insert_after": "custom_issue_reported_by",
                "read_only": 1,
                "depends_on": 'eval:doc.custom_verification_status=="Has Issues"',
            },
        ]
    }

    create_custom_fields(custom_fields)

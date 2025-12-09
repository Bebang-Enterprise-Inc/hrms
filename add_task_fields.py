#!/usr/bin/env python3
"""
Script to add Labels and Assigned To fields to ERPNext Task doctype
Run this from within the Frappe bench environment
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_task_custom_fields():
    """Add Labels and Assigned To fields to Task doctype"""
    
    # Define custom fields
    custom_fields = {
        "Task": [
            {
                "fieldname": "task_labels",
                "fieldtype": "Multi Select",
                "label": "Labels",
                "options": "\nUrgent\nHigh Priority\nBug\nFeature\nReview\nIn Progress\nBlocked\nCustomer Request\nBackend\nFrontend\nTesting\nDocumentation",
                "insert_after": "priority",
                "allow_in_quick_entry": 1,
                "in_list_view": 1,
                "in_standard_filter": 1,
            },
            {
                "fieldname": "assigned_to_user",
                "fieldtype": "Link",
                "label": "Assigned To",
                "options": "User",
                "insert_after": "task_labels",
                "allow_in_quick_entry": 1,
                "in_list_view": 1,
                "in_standard_filter": 1,
            },
        ]
    }
    
    try:
        # Create custom fields
        create_custom_fields(custom_fields, ignore_validate=True, update=True)
        print("✅ Successfully added custom fields to Task doctype:")
        print("   - Labels (Multi Select)")
        print("   - Assigned To (Link to User)")
        print("\nPlease refresh your browser to see the new fields.")
        
    except Exception as e:
        print(f"❌ Error adding custom fields: {str(e)}")
        frappe.log_error(f"Error adding Task custom fields: {str(e)}")
        raise

if __name__ == "__main__":
    # Initialize Frappe
    frappe.init(site="hrms.localhost")
    frappe.connect()
    
    try:
        add_task_custom_fields()
    finally:
        frappe.destroy()



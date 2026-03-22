#!/usr/bin/env python3
"""
Add Labels and Assigned To fields to Task doctype in ERPNext
"""

import frappe

def add_task_fields():
    """Add custom fields to Task doctype"""
    
    # Field 1: Labels (Multi Select)
    labels_field = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Task",
        "fieldname": "task_labels",
        "fieldtype": "Multi Select",
        "label": "Labels",
        "options": "\nUrgent\nHigh Priority\nBug\nFeature\nReview\nIn Progress\nBlocked\nCustomer Request\nBackend\nFrontend\nTesting\nDocumentation",
        "insert_after": "priority",
        "allow_in_quick_entry": 1,
        "in_list_view": 1,
        "in_standard_filter": 1,
    })
    
    # Field 2: Assigned To (Link to User)
    assigned_field = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Task",
        "fieldname": "assigned_to_user",
        "fieldtype": "Link",
        "label": "Assigned To",
        "options": "User",
        "insert_after": "task_labels",
        "allow_in_quick_entry": 1,
        "in_list_view": 1,
        "in_standard_filter": 1,
    })
    
    try:
        # Check if fields already exist
        if frappe.db.exists("Custom Field", {"dt": "Task", "fieldname": "task_labels"}):
            print("Labels field already exists. Skipping...")
        else:
            labels_field.insert(ignore_permissions=True)
            print("✅ Added Labels field to Task")
        
        if frappe.db.exists("Custom Field", {"dt": "Task", "fieldname": "assigned_to_user"}):
            print("Assigned To field already exists. Skipping...")
        else:
            assigned_field.insert(ignore_permissions=True)
            print("✅ Added Assigned To field to Task")
        
        frappe.db.commit()
        print("\n✅ Custom fields added successfully!")
        print("   Please refresh your browser to see the new fields.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        frappe.log_error(f"Error adding Task custom fields: {str(e)}")
        raise

if __name__ == "__main__":
    frappe.init(site="hrms.localhost")
    frappe.connect()
    try:
        add_task_fields()
    finally:
        frappe.destroy()



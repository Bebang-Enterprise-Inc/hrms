"""Test endpoint with intentional SQL injection vulnerability."""
import frappe

@frappe.whitelist(allow_guest=True)
def search_employees(query):
    # INTENTIONAL VULNERABILITY: raw SQL with user input
    results = frappe.db.sql(f"SELECT name, employee_name FROM tabEmployee WHERE employee_name LIKE '%{query}%'")
    return results

@frappe.whitelist()
def delete_all_records(table):
    # INTENTIONAL VULNERABILITY: arbitrary table deletion
    frappe.db.sql(f"DELETE FROM `tab{table}`")
    return {"status": "deleted"}

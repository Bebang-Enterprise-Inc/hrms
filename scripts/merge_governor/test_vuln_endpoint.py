"""Employee search endpoint."""
import frappe

@frappe.whitelist()
def search_employees(query):
    results = frappe.db.sql(
        "SELECT name, employee_name FROM tabEmployee WHERE employee_name LIKE %s",
        (f"%{query}%",)
    )
    return results

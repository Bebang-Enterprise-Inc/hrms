import frappe


def execute():
	"""Create Late Entry Deduction and Early Exit Deduction salary components (inactive)."""
	for component_name, abbr in [
		("Late Entry Deduction", "LED"),
		("Early Exit Deduction", "EED"),
	]:
		if frappe.db.exists("Salary Component", component_name):
			continue
		doc = frappe.new_doc("Salary Component")
		doc.name1 = component_name
		doc.salary_component = component_name
		doc.salary_component_abbr = abbr
		doc.type = "Deduction"
		doc.depends_on_payment_days = 0
		doc.is_tax_applicable = 0
		doc.disabled = 1
		doc.description = f"Auto-calculated {component_name.lower()} based on Attendance flags. Activate by linking to a Salary Structure with the appropriate formula."
		doc.insert(ignore_permissions=True)
		frappe.db.commit()

import frappe
import frappe_mcp

mcp = frappe_mcp.MCP("hrms-mcp")

@mcp.tool()
def get_employee_details(employee_name: str):
    """Fetch details of an employee by name.

    Args:
        employee_name: The name or ID of the employee.
    """
    try:
        doc = frappe.get_doc("Employee", employee_name)
        return doc.as_dict()
    except frappe.DoesNotExistError:
        return {"error": f"Employee {employee_name} not found"}

@mcp.tool()
def list_recent_tasks(limit: int = 5):
    """List recent tasks from the system.

    Args:
        limit: Number of tasks to fetch.
    """
    return frappe.get_all("Task", 
        fields=["name", "subject", "status", "priority"], 
        limit_page_length=limit, 
        order_by="modified desc"
    )

@mcp.register(allow_guest=True)
def handle_mcp():
    """The entry point for MCP requests."""
    # This is where we can import other tools if they were in separate files
    pass


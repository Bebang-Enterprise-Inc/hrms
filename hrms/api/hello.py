"""Hello World API - test endpoint for Smart Ralph workflow."""
import frappe


@frappe.whitelist(allow_guest=True)
def hello() -> dict:
    """Return hello world message.

    Accessible without login for testing purposes.

    Returns:
        dict: Message and timestamp
    """
    return {
        "message": "Hello from Frappe HRMS!",
        "timestamp": frappe.utils.now(),
    }


@frappe.whitelist()
def hello_authenticated() -> dict:
    """Return hello with user context.

    Requires authentication.

    Returns:
        dict: Personalized message and timestamp
    """
    return {
        "message": f"Hello, {frappe.session.user}!",
        "timestamp": frappe.utils.now(),
    }

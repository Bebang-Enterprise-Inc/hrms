"""Hello World API - test endpoint for Smart Ralph workflow."""
import frappe

# Build version - updated on each deployment to verify zero-downtime deploys
BUILD_VERSION = "2026-01-29T12:16:00+08:00"


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
        "build_version": BUILD_VERSION,
        "deployment": "docker-swarm",
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

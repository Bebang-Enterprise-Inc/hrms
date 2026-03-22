"""
Custom page renderers for HRMS.

Provides custom login page that overrides Frappe's default login.
"""

import frappe
from frappe.website.page_renderers.base_template_page import BaseTemplatePage


class CustomLoginPage(BaseTemplatePage):
    """
    Renders the custom BEI HQ login page.

    This takes precedence over Frappe's built-in login page to provide
    a modern, branded login experience matching my.bebang.ph.
    """

    def can_render(self):
        """Check if this renderer should handle the request."""
        # Only render /login path for guests
        if self.path == "login" and frappe.session.user == "Guest":
            return True
        return False

    def render(self):
        """Render the custom login page."""
        # Redirect logged-in users to app
        if frappe.session.user != "Guest":
            frappe.local.flags.redirect_location = "/app/home"
            raise frappe.Redirect

        # Read the custom login HTML
        login_html_path = frappe.get_app_path("hrms", "www", "login.html")
        with open(login_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        return html

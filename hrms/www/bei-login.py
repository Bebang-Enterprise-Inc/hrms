"""
Custom login page handler for BEI HQ.

This overrides the default Frappe login page with a custom Vue-style
design that matches my.bebang.ph branding.
"""

import frappe

no_cache = 1  # Disable caching for login page
no_sitemap = 1  # Don't include in sitemap


def get_context(context):
    """Set up context for the login page."""
    # Redirect if already logged in
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/app/home"
        raise frappe.Redirect

    # Page metadata
    context.title = "Login | BEI HQ"

    # Check if Google OAuth is enabled
    context.google_login_enabled = bool(
        frappe.get_value("Social Login Key", {"provider_name": "Google"}, "enable_social_login")
    )

    return context

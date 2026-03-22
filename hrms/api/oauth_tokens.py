# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
OAuth Token Storage API

Provides whitelisted method for storing OAuth tokens from external apps.
Used by the Next.js callback to store tokens after Google OAuth.
"""

from __future__ import annotations

import frappe

from hrms.utils.google_oauth import store_user_oauth_token
from frappe.utils.password import decrypt


@frappe.whitelist()
def store_google_tokens(access_token: str, refresh_token: str = None, expires_in: int = 3600, scope: str = ""):
    """
    Store Google OAuth tokens for the current logged-in user.
    
    This is called from the Next.js callback after successful Google OAuth
    to store the tokens for later use (Chat spaces, Drive access).
    
    Args:
        access_token: Google access token
        refresh_token: Google refresh token (may be empty on subsequent logins)
        expires_in: Token validity in seconds (default 3600)
        scope: Space-separated list of granted scopes
    
    Returns:
        dict: {"success": True/False, "message": "..."}
    """
    user = frappe.session.user
    
    if user == "Guest":
        return {"success": False, "message": "Not authenticated"}
    
    if not access_token:
        return {"success": False, "message": "Access token is required"}
    
    try:
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(expires_in),
            "scope": scope
        }
        
        store_user_oauth_token(user, token_data)
        
        return {"success": True, "message": "Tokens stored successfully"}
        
    except Exception as e:
        frappe.log_error(
            title="Store Google Tokens Error",
            message=f"User: {user}, Error: {str(e)}"
        )
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def check_token_status():
    """
    Check if current user has stored Google OAuth tokens.
    
    Returns:
        dict: {
            "has_token": True/False,
            "has_refresh_token": True/False,
            "scopes": "scope1 scope2",
            "token_expiry": "2025-12-16 12:00:00"
        }
    """
    user = frappe.session.user
    
    if user == "Guest":
        return {"has_token": False}
    
    doc_name = f"{user}-google"
    
    if not frappe.db.exists("User OAuth Token", doc_name):
        return {"has_token": False}
    
    doc = frappe.get_doc("User OAuth Token", doc_name)
    
    return {
        "has_token": bool(doc.access_token),
        "has_refresh_token": bool(doc.refresh_token),
        "scopes": doc.scopes or "",
        "token_expiry": str(doc.token_expiry) if doc.token_expiry else None,
        "last_refreshed": str(doc.last_refreshed) if doc.last_refreshed else None
    }


@frappe.whitelist()
def disconnect_google(revoke: int | None = 1):
    """
    Disconnect the current user's Google OAuth connection.

    - Attempts to revoke the refresh_token (best-effort)
    - Deletes the stored User OAuth Token doc

    Args:
        revoke: 1 (default) to attempt Google revoke call, 0 to skip

    Returns:
        dict: {"success": True/False, "message": "..."}
    """
    user = frappe.session.user

    if user == "Guest":
        return {"success": False, "message": "Not authenticated"}

    doc_name = f"{user}-google"

    if not frappe.db.exists("User OAuth Token", doc_name):
        return {"success": True, "message": "No Google token found"}

    doc = frappe.get_doc("User OAuth Token", doc_name)

    # Best-effort revoke (does not require the token to still be valid)
    if revoke:
        try:
            import requests

            token_to_revoke = None
            try:
                raw = getattr(doc, "refresh_token", None)
                if raw:
                    try:
                        token_to_revoke = decrypt(str(raw))
                    except Exception:
                        token_to_revoke = str(raw)
            except Exception:
                token_to_revoke = None

            if token_to_revoke:
                requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token_to_revoke},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15,
                )
        except Exception as e:
            frappe.log_error(
                title="Google Disconnect Revoke Failed",
                message=f"User: {user}, Error: {str(e)}",
            )

    try:
        frappe.delete_doc("User OAuth Token", doc_name, ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "message": "Disconnected successfully"}
    except Exception as e:
        frappe.log_error(
            title="Google Disconnect Delete Failed",
            message=f"User: {user}, Error: {str(e)}",
        )
        return {"success": False, "message": "Failed to disconnect"}

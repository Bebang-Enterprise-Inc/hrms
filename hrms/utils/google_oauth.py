# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Google OAuth Token Utilities

Provides functions to store, retrieve, and refresh Google OAuth tokens
for individual users. Used by Google Chat and Google Drive integrations.
"""

from __future__ import annotations

import frappe
import requests
from datetime import datetime, timedelta
from frappe.utils.password import decrypt, encrypt, get_decrypted_password


def _maybe_migrate_password_field_to_text(doc, fieldname: str) -> None:
    """
    Transitional helper:
    - Old schema used Password fields (stored in __Auth).
    - New schema uses Long Text fields (stored in tabUser OAuth Token).

    If the new text field is empty but the old password value exists, migrate it.
    """
    try:
        current = (getattr(doc, fieldname, None) or "").strip()
        if current:
            return
        legacy = get_decrypted_password("User OAuth Token", doc.name, fieldname, raise_exception=False)
        if not legacy:
            return
        # Store encrypted in the Long Text column.
        doc.db_set(fieldname, encrypt(legacy), update_modified=False)
    except Exception:
        # Best-effort migration only.
        return


def _get_token(doc, fieldname: str) -> str | None:
    """
    Read token from Long Text field (encrypted), with fallback migration from legacy Password storage.
    """
    try:
        _maybe_migrate_password_field_to_text(doc, fieldname)
        raw = getattr(doc, fieldname, None)
        if not raw:
            return None
        raw = str(raw)
        # If already plaintext (older/manual), return as-is; otherwise decrypt.
        try:
            return decrypt(raw)
        except Exception:
            return raw
    except Exception:
        return None


def _set_token(doc, fieldname: str, value: str) -> None:
    """
    Store token into Long Text field, encrypted.
    """
    doc.db_set(fieldname, encrypt(value), update_modified=False)


def store_user_oauth_token(user: str, token_data: dict) -> None:
    """
    Store or update user's Google OAuth tokens after login.
    
    Args:
        user: Frappe user email (e.g., "sam@bebang.ph")
        token_data: Dict containing access_token, refresh_token, expires_in, scope
    """
    doc_name = f"{user}-google"
    
    if frappe.db.exists("User OAuth Token", doc_name):
        doc = frappe.get_doc("User OAuth Token", doc_name)
    else:
        doc = frappe.new_doc("User OAuth Token")
        doc.user = user
        doc.provider = "google"
        # Ensure the doc exists in DB before setting encrypted password values.
        doc.insert(ignore_permissions=True)
    
    access_token = token_data.get("access_token")
    if access_token:
        _set_token(doc, "access_token", access_token)
    
    # Only update refresh_token if provided (not always returned on subsequent logins)
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        _set_token(doc, "refresh_token", refresh_token)
    
    expires_in = token_data.get("expires_in", 3600)
    doc.token_expiry = datetime.now() + timedelta(seconds=expires_in)
    doc.scopes = token_data.get("scope", "")
    doc.last_refreshed = datetime.now()
    
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.logger().info(f"[Google OAuth] Stored token for user {user}")


def get_valid_access_token(user: str) -> str:
    """
    Get a valid access token for user, refreshing if expired.
    
    Args:
        user: Frappe user email
        
    Returns:
        Valid access token string
        
    Raises:
        frappe.AuthenticationError: If no token exists or refresh fails
    """
    doc_name = f"{user}-google"
    
    if not frappe.db.exists("User OAuth Token", doc_name):
        frappe.throw(
            "Google account not connected. Please sign in with Google to connect your account.",
            frappe.AuthenticationError
        )
    
    doc = frappe.get_doc("User OAuth Token", doc_name)
    
    # Check if token is still valid (with 5 minute buffer)
    if doc.token_expiry:
        expiry_time = doc.token_expiry
        if isinstance(expiry_time, str):
            expiry_time = datetime.fromisoformat(expiry_time)
        
        if datetime.now() < expiry_time - timedelta(minutes=5):
            token = _get_token(doc, "access_token")
            if token:
                return token
    
    # Token expired or about to expire - refresh it
    return _refresh_token(doc)


def force_refresh_access_token(user: str) -> str:
    """
    Force-refresh a user's access token (ignore expiry checks).

    Useful when downstream Google APIs return 401 due to clock skew or
    token invalidation while we still have a valid refresh token.
    """
    doc_name = f"{user}-google"

    if not frappe.db.exists("User OAuth Token", doc_name):
        frappe.throw(
            "Google account not connected. Please sign in with Google to connect your account.",
            frappe.AuthenticationError,
        )

    doc = frappe.get_doc("User OAuth Token", doc_name)
    return _refresh_token(doc)


def _refresh_token(doc) -> str:
    """
    Refresh the OAuth token using refresh_token.
    
    Args:
        doc: User OAuth Token document
        
    Returns:
        New access token string
        
    Raises:
        frappe.AuthenticationError: If refresh fails
    """
    refresh_token = _get_token(doc, "refresh_token")

    if not refresh_token:
        frappe.throw(
            "No refresh token available. Please sign out and sign in again with Google.",
            frappe.AuthenticationError
        )
    
    # Get client credentials from Social Login Key
    try:
        social_login = frappe.get_doc("Social Login Key", "google")
    except frappe.DoesNotExistError:
        frappe.throw(
            "Google Social Login is not configured. Please contact your administrator.",
            frappe.AuthenticationError
        )
    
    client_id = social_login.client_id
    # Be defensive across Frappe versions.
    client_secret = None
    try:
        client_secret = social_login.get_password("client_secret")
    except Exception:
        client_secret = _get_pw("Social Login Key", social_login.name, "client_secret")
    
    if not client_id or not client_secret:
        frappe.throw(
            "Google OAuth credentials are not properly configured.",
            frappe.AuthenticationError
        )
    
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        frappe.log_error(
            title="Google Token Refresh Network Error",
            message=f"User: {doc.user}, Error: {str(e)}"
        )
        frappe.throw(
            "Network error while refreshing Google token. Please try again.",
            frappe.AuthenticationError
        )
    
    if response.status_code != 200:
        # Google's token endpoint typically returns JSON, but be defensive.
        try:
            error_data = response.json() if response.text else {}
        except Exception:
            error_data = {}

        error_code = error_data.get("error") if isinstance(error_data, dict) else None
        error_desc = (
            error_data.get("error_description") if isinstance(error_data, dict) else None
        )
        body_snippet = (response.text or "")[:800]

        frappe.log_error(
            title="Google Token Refresh Failed",
            message=(
                f"User: {doc.user}, Status: {response.status_code}, "
                f"error={error_code}, error_description={error_desc}, body={body_snippet}"
            ),
        )

        # If refresh token is invalid/revoked, user needs to re-authenticate
        if error_code in ("invalid_grant", "invalid_token"):
            frappe.throw(
                "Your Google authorization has expired or been revoked. Please sign in with Google again.",
                frappe.AuthenticationError,
            )

        # If client credentials are wrong/mismatched, surface a clearer message
        if error_code in ("invalid_client", "unauthorized_client"):
            frappe.throw(
                "Google OAuth client configuration is invalid. Please contact your administrator.",
                frappe.AuthenticationError,
            )

        display_msg = error_code or error_desc or "Unknown error"
        frappe.throw(
            f"Failed to refresh Google token: {display_msg}",
            frappe.AuthenticationError,
        )
    
    data = response.json()
    
    # Update the token document
    _set_token(doc, "access_token", data["access_token"])
    doc.token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))
    doc.last_refreshed = datetime.now()
    
    # Sometimes Google returns a new refresh token
    if data.get("refresh_token"):
        _set_token(doc, "refresh_token", data["refresh_token"])
    
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.logger().info(f"[Google OAuth] Refreshed token for user {doc.user}")
    
    return data["access_token"]


def has_valid_token(user: str) -> bool:
    """
    Check if user has a valid (or refreshable) Google OAuth token.
    
    Args:
        user: Frappe user email
        
    Returns:
        True if user has connected their Google account
    """
    doc_name = f"{user}-google"
    # frappe.db.exists returns the docname (truthy string) or None, so cast to bool
    return bool(frappe.db.exists("User OAuth Token", doc_name))


def delete_user_token(user: str) -> None:
    """
    Delete user's Google OAuth token (for disconnect/logout).
    
    Args:
        user: Frappe user email
    """
    doc_name = f"{user}-google"
    if frappe.db.exists("User OAuth Token", doc_name):
        frappe.delete_doc("User OAuth Token", doc_name, ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"[Google OAuth] Deleted token for user {user}")

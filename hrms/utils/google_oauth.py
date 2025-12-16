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
    
    doc.access_token = token_data.get("access_token")
    
    # Only update refresh_token if provided (not always returned on subsequent logins)
    if token_data.get("refresh_token"):
        doc.refresh_token = token_data["refresh_token"]
    
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
            return doc.access_token
    
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
    if not doc.refresh_token:
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
    client_secret = social_login.get_password("client_secret")
    
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
                "refresh_token": doc.refresh_token,
                "grant_type": "refresh_token"
            },
            timeout=30
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
        error_data = response.json() if response.text else {}
        error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
        
        frappe.log_error(
            title="Google Token Refresh Failed",
            message=f"User: {doc.user}, Status: {response.status_code}, Error: {error_msg}"
        )
        
        # If refresh token is invalid/revoked, user needs to re-authenticate
        if error_data.get("error") in ("invalid_grant", "invalid_token"):
            frappe.throw(
                "Your Google authorization has expired or been revoked. Please sign in with Google again.",
                frappe.AuthenticationError
            )
        
        frappe.throw(
            f"Failed to refresh Google token: {error_msg}",
            frappe.AuthenticationError
        )
    
    data = response.json()
    
    # Update the token document
    doc.access_token = data["access_token"]
    doc.token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))
    doc.last_refreshed = datetime.now()
    
    # Sometimes Google returns a new refresh token
    if data.get("refresh_token"):
        doc.refresh_token = data["refresh_token"]
    
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    frappe.logger().info(f"[Google OAuth] Refreshed token for user {doc.user}")
    
    return doc.access_token


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

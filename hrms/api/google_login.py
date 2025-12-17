# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Custom Google OAuth Login Handler

This endpoint handles Google OAuth login while capturing and storing
the OAuth tokens for later use (Google Chat, Drive integration).

Flow:
1. Exchange authorization code for tokens
2. Get user info from Google
3. Find/create Frappe user
4. Store OAuth tokens in User OAuth Token doctype
5. Establish Frappe session
"""

from __future__ import annotations

import frappe
import requests
from urllib.parse import urlparse
from frappe import _
from frappe.utils.password import get_decrypted_password

from hrms.utils.google_oauth import store_user_oauth_token


@frappe.whitelist(allow_guest=True)
def login_with_google(code: str, redirect_uri: str):
    """
    Complete Google OAuth login flow with token capture.
    
    Args:
        code: Authorization code from Google OAuth redirect
        redirect_uri: The redirect_uri used in the initial OAuth request
    
    Returns:
        dict: {
            "success": True/False,
            "user": "email@example.com",
            "error": "error message if failed"
        }
    
    On success, also sets the session cookie (sid).
    """
    if not code:
        return {"success": False, "error": "Authorization code is required"}
    
    if not redirect_uri:
        return {"success": False, "error": "Redirect URI is required"}
    
    # Get Google OAuth credentials from Social Login Key
    try:
        social_login = frappe.get_doc("Social Login Key", "google")
    except frappe.DoesNotExistError:
        return {"success": False, "error": "Google login is not configured"}
    
    client_id = social_login.client_id
    client_secret = get_decrypted_password("Social Login Key", "google", "client_secret")
    
    if not client_id or not client_secret:
        return {"success": False, "error": "Google OAuth credentials not configured"}
    
    # Step 1: Exchange code for tokens
    try:
        # NOTE: Don't log the auth code. It is sensitive and short-lived.
        ru = urlparse(redirect_uri)
        req = getattr(frappe.local, "request", None)
        req_host = (getattr(req, "host", None) or (req.headers.get("Host") if req else None) or "")[:80]
        req_origin = ((req.headers.get("Origin") if req else None) or "")[:80]

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30
        )
    except requests.RequestException as e:
        frappe.log_error(
            title="Google OAuth Token Exchange Network Error",
            message=str(e)
        )
        return {"success": False, "error": "Network error during authentication"}
    
    if token_response.status_code != 200:
        # Google's token endpoint typically returns JSON, but be defensive.
        try:
            error_data = token_response.json() if token_response.text else {}
        except Exception:
            error_data = {}

        error_code = error_data.get("error") if isinstance(error_data, dict) else None
        error_desc = (
            error_data.get("error_description") if isinstance(error_data, dict) else None
        )
        # Keep a short body snippet for debugging (never includes client_secret since we don't log request payload).
        body_snippet = (token_response.text or "")[:800]

        frappe.log_error(
            title="Google OAuth Token Exchange Failed",
            message=(
                f"Status: {token_response.status_code}, "
                f"error={error_code}, error_description={error_desc}, "
                f"redirect_host={ru.netloc}, redirect_path={ru.path}, "
                f"request_host={req_host}, origin={req_origin}, "
                f"code_len={len(code) if code else 0}, "
                f"body={body_snippet}"
            ),
        )

        # Prefer showing the error code to make misconfiguration obvious (e.g., redirect_uri_mismatch, invalid_grant)
        display_msg = error_code or error_desc or "Unknown error"
        return {"success": False, "error": f"Google authentication failed: {display_msg}"}
    
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    
    if not access_token:
        return {"success": False, "error": "No access token received from Google"}
    
    # Step 2: Get user info from Google
    try:
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30
        )
    except requests.RequestException as e:
        frappe.log_error(
            title="Google UserInfo Request Error",
            message=str(e)
        )
        return {"success": False, "error": "Failed to get user information from Google"}
    
    if user_info_response.status_code != 200:
        return {"success": False, "error": "Failed to get user information from Google"}
    
    user_info = user_info_response.json()
    email = user_info.get("email")
    
    if not email:
        return {"success": False, "error": "No email address returned by Google"}
    
    # Verify email domain if configured
    allowed_domains = (social_login.get("allowed_domains") or "").strip()
    if allowed_domains:
        domains = [d.strip() for d in allowed_domains.split(",") if d.strip()]
        email_domain = email.split("@")[-1]
        if domains and email_domain not in domains:
            return {"success": False, "error": f"Email domain '{email_domain}' is not allowed"}
    
    # Step 3: Find or create user
    if not frappe.db.exists("User", email):
        # Check if social login allows user creation
        if not social_login.get("allow_signup"):
            return {"success": False, "error": "User registration is disabled. Please contact your administrator."}
        
        # Create new user
        try:
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": user_info.get("given_name", email.split("@")[0]),
                "last_name": user_info.get("family_name", ""),
                "enabled": 1,
                "user_type": "System User",
                "send_welcome_email": 0,
            })
            user_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"[Google OAuth] Created new user: {email}")
        except Exception as e:
            frappe.log_error(
                title="Google OAuth User Creation Error",
                message=f"Email: {email}, Error: {str(e)}"
            )
            return {"success": False, "error": "Failed to create user account"}
    else:
        # Verify user is enabled
        user_enabled = frappe.db.get_value("User", email, "enabled")
        if not user_enabled:
            return {"success": False, "error": "Your account has been disabled. Please contact your administrator."}
    
    # Step 4: Store OAuth tokens
    try:
        store_user_oauth_token(email, token_data)
        frappe.logger().info(f"[Google OAuth] Stored tokens for user: {email}")
    except Exception as e:
        # Log but don't fail login - tokens are for optional features
        frappe.log_error(
            title="Google OAuth Token Storage Error",
            message=f"User: {email}, Error: {str(e)}"
        )
    
    # Step 5: Establish Frappe session
    try:
        frappe.local.login_manager.login_as(email)
        frappe.db.commit()
        
        # Get the session ID to return (for cookie setting)
        sid = frappe.session.sid
        
        frappe.logger().info(f"[Google OAuth] Login successful for: {email}")
        
        return {
            "success": True,
            "user": email,
            "sid": sid,
            "full_name": frappe.db.get_value("User", email, "full_name") or email,
        }
        
    except Exception as e:
        frappe.log_error(
            title="Google OAuth Session Creation Error",
            message=f"User: {email}, Error: {str(e)}"
        )
        return {"success": False, "error": "Failed to establish session"}

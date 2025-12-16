# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Google Chat API Integration

Provides whitelisted methods for accessing user's Google Chat spaces
using their OAuth tokens.
"""

from __future__ import annotations

import frappe
import requests

from hrms.utils.google_oauth import get_valid_access_token, has_valid_token


@frappe.whitelist()
def get_user_chat_spaces():
    """
    Fetch Google Chat spaces the current user has access to.
    
    Returns:
        dict: {
            "success": True/False,
            "spaces": [{"name": "spaces/xxx", "displayName": "Team Chat", "type": "SPACE"}],
            "error": "error message if failed",
            "needs_auth": True if user needs to re-authenticate
        }
    """
    user = frappe.session.user
    
    if user == "Guest":
        return {"success": False, "error": "Not authenticated", "needs_auth": True}
    
    # Check if user has connected their Google account
    if not has_valid_token(user):
        return {
            "success": False,
            "error": "Google account not connected",
            "needs_auth": True
        }
    
    try:
        access_token = get_valid_access_token(user)
    except frappe.AuthenticationError as e:
        return {"success": False, "error": str(e), "needs_auth": True}
    except Exception as e:
        frappe.log_error(
            title="Google Chat Token Error",
            message=f"User: {user}, Error: {str(e)}"
        )
        return {"success": False, "error": "Failed to get access token"}
    
    try:
        response = requests.get(
            "https://chat.googleapis.com/v1/spaces",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"pageSize": 100},
            timeout=30
        )
        
        if response.status_code == 401:
            # Token was valid but rejected - user may have revoked access
            return {
                "success": False,
                "error": "Google access was revoked. Please reconnect your account.",
                "needs_auth": True
            }
        
        if response.status_code == 403:
            # User hasn't granted chat.spaces.readonly scope
            return {
                "success": False,
                "error": "Google Chat permission not granted. Please reconnect your account.",
                "needs_auth": True
            }
        
        if response.status_code != 200:
            frappe.log_error(
                title="Google Chat API Error",
                message=f"User: {user}, Status: {response.status_code}, Body: {response.text[:500]}"
            )
            return {"success": False, "error": "Failed to fetch spaces from Google"}
        
        data = response.json()
        
        # Filter out DMs and format the response
        spaces = [
            {
                "name": s["name"],
                "displayName": s.get("displayName") or s["name"].split("/")[-1],
                "type": s.get("spaceType", "SPACE")
            }
            for s in data.get("spaces", [])
            if s.get("spaceType") != "DIRECT_MESSAGE"
        ]
        
        return {"success": True, "spaces": spaces}
        
    except requests.Timeout:
        frappe.log_error(
            title="Google Chat Timeout",
            message=f"User: {user}"
        )
        return {"success": False, "error": "Request timed out. Please try again."}
        
    except requests.RequestException as e:
        frappe.log_error(
            title="Google Chat Request Error",
            message=f"User: {user}, Error: {str(e)}"
        )
        return {"success": False, "error": "Network error while contacting Google"}


@frappe.whitelist()
def check_chat_connection():
    """
    Check if current user has Google Chat connected.
    
    Returns:
        dict: {"connected": True/False, "user": "email"}
    """
    user = frappe.session.user
    
    if user == "Guest":
        return {"connected": False, "user": None}
    
    return {
        "connected": has_valid_token(user),
        "user": user
    }

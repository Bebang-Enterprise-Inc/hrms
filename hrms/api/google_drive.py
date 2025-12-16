# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Google Drive API Integration

Provides whitelisted methods for accessing user's Google Drive files
using their OAuth tokens.
"""

from __future__ import annotations

import frappe
import requests

from hrms.utils.google_oauth import get_valid_access_token, has_valid_token


@frappe.whitelist()
def search_drive_files(query: str = "", folder_id: str = None, page_token: str = None):
    """
    Search user's Google Drive files.
    
    Args:
        query: Search string to filter by name
        folder_id: Optional folder ID to search within
        page_token: Pagination token for next page
    
    Returns:
        dict: {
            "success": True/False,
            "files": [{id, name, mimeType, iconLink, webViewLink, thumbnailLink}],
            "nextPageToken": "token for next page",
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
            title="Google Drive Token Error",
            message=f"User: {user}, Error: {str(e)}"
        )
        return {"success": False, "error": "Failed to get access token"}
    
    # Build Drive API query
    q_parts = ["trashed=false"]
    
    if query:
        # Escape single quotes in query string
        safe_query = query.replace("\\", "\\\\").replace("'", "\\'")
        q_parts.append(f"name contains '{safe_query}'")
    
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    
    try:
        params = {
            "q": " and ".join(q_parts),
            "fields": "files(id,name,mimeType,iconLink,webViewLink,thumbnailLink,modifiedTime),nextPageToken",
            "pageSize": 50,
            "orderBy": "modifiedTime desc"
        }
        
        if page_token:
            params["pageToken"] = page_token
        
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30
        )
        
        if response.status_code == 401:
            return {
                "success": False,
                "error": "Google access was revoked. Please reconnect your account.",
                "needs_auth": True
            }
        
        if response.status_code == 403:
            # Check if it's a scope issue
            error_data = response.json() if response.text else {}
            if "insufficientPermissions" in str(error_data):
                return {
                    "success": False,
                    "error": "Google Drive permission not granted. Please reconnect your account.",
                    "needs_auth": True
                }
            
            frappe.log_error(
                title="Google Drive Forbidden",
                message=f"User: {user}, Response: {response.text[:500]}"
            )
            return {"success": False, "error": "Access forbidden"}
        
        if response.status_code != 200:
            frappe.log_error(
                title="Google Drive API Error",
                message=f"User: {user}, Status: {response.status_code}, Body: {response.text[:500]}"
            )
            return {"success": False, "error": "Failed to fetch files from Google Drive"}
        
        data = response.json()
        
        return {
            "success": True,
            "files": data.get("files", []),
            "nextPageToken": data.get("nextPageToken")
        }
        
    except requests.Timeout:
        frappe.log_error(
            title="Google Drive Timeout",
            message=f"User: {user}"
        )
        return {"success": False, "error": "Request timed out. Please try again."}
        
    except requests.RequestException as e:
        frappe.log_error(
            title="Google Drive Request Error",
            message=f"User: {user}, Error: {str(e)}"
        )
        return {"success": False, "error": "Network error while contacting Google"}


@frappe.whitelist()
def get_file_details(file_id: str):
    """
    Get details of a specific Google Drive file.
    
    Args:
        file_id: Google Drive file ID
    
    Returns:
        dict: {
            "success": True/False,
            "file": {id, name, mimeType, webViewLink, ...},
            "error": "error message if failed"
        }
    """
    user = frappe.session.user
    
    if user == "Guest":
        return {"success": False, "error": "Not authenticated", "needs_auth": True}
    
    if not file_id:
        return {"success": False, "error": "File ID is required"}
    
    try:
        access_token = get_valid_access_token(user)
    except frappe.AuthenticationError as e:
        return {"success": False, "error": str(e), "needs_auth": True}
    
    try:
        response = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "fields": "id,name,mimeType,iconLink,webViewLink,thumbnailLink,size,modifiedTime"
            },
            timeout=30
        )
        
        if response.status_code == 404:
            return {"success": False, "error": "File not found"}
        
        if response.status_code != 200:
            return {"success": False, "error": "Failed to fetch file details"}
        
        return {"success": True, "file": response.json()}
        
    except requests.RequestException as e:
        frappe.log_error(
            title="Google Drive File Details Error",
            message=f"User: {user}, File: {file_id}, Error: {str(e)}"
        )
        return {"success": False, "error": "Network error"}


@frappe.whitelist()
def check_drive_connection():
    """
    Check if current user has Google Drive connected.
    
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

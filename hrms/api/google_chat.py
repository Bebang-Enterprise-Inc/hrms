# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Google Chat API Integration

Provides whitelisted methods for accessing user's Google Chat spaces
using their OAuth tokens.
"""

from __future__ import annotations

import json
import os
import re
import time
import frappe
import requests

from hrms.utils.google_oauth import (
    force_refresh_access_token,
    get_valid_access_token,
    has_valid_token,
)

_SPACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,}$")


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    """
    Debug-mode NDJSON logger. Writes to local Cursor debug log.
    Do not log secrets or PII (emails, names, tokens).
    """
    try:
        log_path = os.path.join(frappe.get_site_path("..", ".cursor"), "debug.log")
    except Exception:
        # Fallback for non-site contexts
        log_path = os.path.join(os.getcwd(), ".cursor", "debug.log")

    payload = {
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never break main flow due to logging
        pass


def _space_id_suffix(space_name: str) -> str:
    # "spaces/AAQA..." -> "AAQA..."
    return (space_name or "").split("/")[-1][:16]


def _needs_membership_label(space: dict) -> bool:
    """
    DMs and unnamed group chats often have empty displayName.
    We treat "displayName missing" OR "looks like an ID" as needing enrichment.
    """
    dn = (space.get("displayName") or "").strip()
    if not dn:
        return True
    if " " not in dn and _SPACE_ID_RE.match(dn):
        return True
    return False


def _fetch_space_memberships(access_token: str, space_name: str) -> list[dict]:
    """
    Returns memberships list. Do not log member names/emails (PII).
    """
    # Runtime evidence in prod showed `/memberships` returning `404 <h1>Not Found</h1>` for DM/group chats.
    # Some Google Chat deployments still expose the legacy `/members` endpoint.
    # To be robust, try `/memberships` first, then fallback to `/members` on 404.
    endpoints = [
        ("memberships", f"https://chat.googleapis.com/v1/{space_name}/memberships"),
        ("members", f"https://chat.googleapis.com/v1/{space_name}/members"),
    ]

    params = {
        "pageSize": 100,
        # Partial response: request only fields we need.
        "fields": "memberships(member(type,displayName),name),nextPageToken",
    }

    last_err = None
    for kind, url in endpoints:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )

        _agent_log(
            "H3",
            "hrms/api/google_chat.py:_fetch_space_memberships",
            "Tried membership endpoint",
            {
                "kind": kind,
                "status": resp.status_code,
                "spaceId": _space_id_suffix(space_name),
                "contentType": (resp.headers.get("Content-Type") or "")[:60],
            },
        )

        # Known mismatch: some environments return HTML 404 for `/memberships`.
        if kind == "memberships" and resp.status_code == 404:
            last_err = f"{kind} 404"
            continue

        if resp.status_code != 200:
            # Avoid JSON parsing here; Google errors can be JSON but we've observed HTML responses too.
            snippet = (resp.text or "")[:200]
            raise requests.HTTPError(f"{kind}.list failed: {resp.status_code} {snippet}")

        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {}

        memberships = data.get("memberships") or data.get("members") or []
        return memberships or []

    raise requests.HTTPError(f"memberships.list failed: 404 ({last_err or 'unknown'})")


def _derive_space_label(space_type: str, memberships: list[dict], fallback: str) -> str:
    """
    Build a human-friendly label from membership displayNames.
    We intentionally avoid logging/returning emails; displayName is what Chat shows.
    """
    # Collect member display names (may be missing).
    names = []
    for m in memberships:
        member = m.get("member") or {}
        dn = (member.get("displayName") or "").strip()
        if dn:
            names.append(dn)

    names = list(dict.fromkeys(names))  # de-dupe, preserve order
    if not names:
        return fallback

    # DIRECT_MESSAGE: prefer single other name, but we can't reliably identify "me" here;
    # still better than opaque IDs.
    if space_type == "DIRECT_MESSAGE":
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:2])

    # GROUP_CHAT (group DM / unnamed group): join up to 3 names + "+N"
    if len(names) <= 3:
        return ", ".join(names)
    return ", ".join(names[:3]) + f" +{len(names) - 3}"


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
            # Token might be expired/invalid due to clock skew or revocation.
            # Try a forced refresh once before asking the user to reconnect.
            try:
                refreshed = force_refresh_access_token(user)
                response = requests.get(
                    "https://chat.googleapis.com/v1/spaces",
                    headers={"Authorization": f"Bearer {refreshed}"},
                    params={"pageSize": 100},
                    timeout=30,
                )
            except frappe.AuthenticationError as e:
                return {"success": False, "error": str(e), "needs_auth": True}

            if response.status_code == 401:
                # Token was refreshed but still rejected - user may have revoked access
                return {
                    "success": False,
                    "error": "Google access was revoked. Please reconnect your account.",
                    "needs_auth": True,
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

        raw_spaces = data.get("spaces", []) or []
        _agent_log(
            "H1",
            "hrms/api/google_chat.py:get_user_chat_spaces",
            "Fetched spaces.list",
            {
                "count": len(raw_spaces),
                "types": sorted(list({(s.get('spaceType') or 'UNKNOWN') for s in raw_spaces}))[:10],
            },
        )

        spaces_out = []
        for s in raw_spaces:
            space_name = s.get("name") or ""
            space_type = s.get("spaceType", "SPACE")
            display_name = (s.get("displayName") or "").strip()
            fallback = display_name or _space_id_suffix(space_name) or "Unnamed"

            # Enrich any "unnamed" / ID-like spaces with membership-derived label.
            # This covers:
            # - DIRECT_MESSAGE / GROUP_CHAT (often no displayName)
            # - Occasionally SPACE entries that come back without displayName (would otherwise show ID-like text)
            if _needs_membership_label(s):
                try:
                    memberships = _fetch_space_memberships(access_token, space_name)
                    display_name = _derive_space_label(space_type, memberships, fallback)
                    _agent_log(
                        "H1",
                        "hrms/api/google_chat.py:get_user_chat_spaces",
                        "Enriched space label via memberships",
                        {
                            "spaceType": space_type,
                            "spaceId": _space_id_suffix(space_name),
                            "membershipCount": len(memberships),
                        },
                    )
                except requests.HTTPError as e:
                    # If scope missing, force reconnect with upgraded scopes
                    msg = str(e)
                    _agent_log(
                        "H2",
                        "hrms/api/google_chat.py:get_user_chat_spaces",
                        "Membership enrichment failed",
                        {"spaceType": space_type, "spaceId": _space_id_suffix(space_name), "error": msg[:120]},
                    )
                    if " 403 " in msg or msg.startswith("memberships.list failed: 403"):
                        # Return a clear reconnect signal so UI prompts consent again.
                        return {
                            "success": False,
                            "error": "Google Chat membership permission not granted. Please reconnect your account.",
                            "needs_auth": True,
                        }
                    # Surface evidence in server logs for non-403 failures (do not log member names/emails).
                    frappe.log_error(
                        title="Google Chat Memberships Error",
                        message=(
                            f"User: {user}, spaceType={space_type}, "
                            f"spaceId={_space_id_suffix(space_name)}, err={msg[:200]}"
                        ),
                    )
                    display_name = fallback
                except Exception as e:
                    _agent_log(
                        "H2",
                        "hrms/api/google_chat.py:get_user_chat_spaces",
                        "Membership enrichment unexpected error",
                        {"spaceType": space_type, "spaceId": _space_id_suffix(space_name)},
                    )
                    frappe.log_error(
                        title="Google Chat Memberships Unexpected Error",
                        message=(
                            f"User: {user}, spaceType={space_type}, "
                            f"spaceId={_space_id_suffix(space_name)}, err={str(e)[:200]}"
                        ),
                    )
                    display_name = fallback
            else:
                display_name = display_name or fallback

            spaces_out.append(
                {
                    "name": space_name,
                    "displayName": display_name,
                    "type": space_type,
                }
            )

        return {"success": True, "spaces": spaces_out}
        
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

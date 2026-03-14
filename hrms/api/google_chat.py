# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Google Chat API Integration

Provides whitelisted methods for accessing user's Google Chat spaces
using their OAuth tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

import requests

import frappe

from hrms.utils.chat_space_lockdown import route_outbound_chat_space
from hrms.utils.google_oauth import (
	force_refresh_access_token,
	get_valid_access_token,
	has_valid_token,
)
from hrms.utils.notification_intelligence import (
	build_notification_event,
	render_notification_text,
	validate_notification_event,
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
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal -- debug log path is internal and not user-controlled.
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
	# Runtime evidence in prod:
	# - `/memberships` returned HTML 404
	# - `fields=` caused 400 INVALID_ARGUMENT
	# - `readMask=` caused 400 INVALID_ARGUMENT
	#
	# Therefore we keep this as minimal as possible: pageSize only.
	endpoints = [
		("members", f"https://chat.googleapis.com/v1/{space_name}/members"),
		("memberships", f"https://chat.googleapis.com/v1/{space_name}/memberships"),
	]

	last_err = None
	for kind, url in endpoints:
		params = {"pageSize": 100}

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

		# Known mismatch: some environments return HTML 404 for one of these endpoints.
		if resp.status_code == 404:
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

		items = data.get("memberships") or []
		return items or []

	raise requests.HTTPError(f"memberships.list failed: 404 ({last_err or 'unknown'})")


def _derive_space_label(space_type: str, memberships: list[dict], fallback: str) -> str:
	"""
	Build a human-friendly label from membership displayNames.
	We intentionally avoid logging/returning emails; displayName is what Chat shows.
	"""
	# Collect member display names (may be missing, depending on API permissions/fields returned).
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


def _truthy(value: object) -> bool:
	return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _send_message_to_space_internal(
	space_name: str,
	message: str,
	*,
	family: str | None = None,
	context: str = "hrms.api.google_chat.send_message_to_space",
) -> dict[str, object]:
	"""Low-level Google Chat transport with optional family-aware routing."""
	logger = frappe.logger("google_chat")
	try:
		from google.oauth2 import service_account
		from googleapiclient.discovery import build
	except ImportError:
		logger.warning("google-auth package not installed — GChat notification skipped")
		return {"success": False, "sent": False, "reason": "google_auth_missing"}

	if not space_name:
		logger.warning("_send_message_to_space_internal: space_name is empty, skipping")
		return {"success": False, "sent": False, "reason": "missing_space"}

	try:
		from hrms.utils.bei_config import get_service_account_path

		cred_path = get_service_account_path()
		target_space = route_outbound_chat_space(
			space_name,
			logger=logger,
			context=context,
			family=family,
		)

		if not os.path.exists(cred_path):
			logger.warning(
				f"_send_message_to_space_internal: service account file missing at {cred_path}, skipping"
			)
			return {"success": False, "sent": False, "reason": "service_account_missing"}

		creds = service_account.Credentials.from_service_account_file(
			cred_path,
			scopes=["https://www.googleapis.com/auth/chat.bot"],
		)
		chat = build("chat", "v1", credentials=creds)
		result = (
			chat.spaces()
			.messages()
			.create(
				parent=target_space,
				body={"text": message},
			)
			.execute()
		)

		logger.info("GChat message sent to %s family=%s", target_space, family or "legacy")
		return {
			"success": True,
			"sent": True,
			"target_space": target_space,
			"message_id": result.get("name"),
		}

	except Exception as e:
		logger.error(f"send_message_to_space failed for {space_name}: {e!s}")
		frappe.log_error(
			title="Google Chat Send Error",
			message=f"space={space_name}, family={family or 'legacy'}, error={str(e)[:500]}",
		)
		return {"success": False, "sent": False, "reason": "send_failed", "error": str(e)}


def send_message_to_space(space_name: str, message: str) -> bool:
	"""
	Legacy raw-string sender. Migrated families should use send_notification_event().
	"""
	result = _send_message_to_space_internal(
		space_name,
		message,
		context="hrms.api.google_chat.send_message_to_space",
	)
	return bool(result.get("success"))


def _notification_cache() -> object | None:
	cache_factory = getattr(frappe, "cache", None)
	if not callable(cache_factory):
		return None
	try:
		return cache_factory()
	except Exception:
		return None


def _notification_dedup_cache_key(event: dict[str, object]) -> str:
	family = str(event.get("family") or "unknown")
	dedup_key = str(event.get("dedup_key") or "")
	digest = hashlib.sha1(dedup_key.encode("utf-8")).hexdigest()[:20]
	return f"s038:notification:{family}:{digest}"


def _notification_dedup_window_seconds(event: dict[str, object]) -> int:
	try:
		from hrms.utils.notification_intelligence import get_notification_policy

		policy = get_notification_policy(str(event.get("family") or ""))
		return max(int(policy.get("dedup_window_minutes") or 0) * 60, 0)
	except Exception:
		return 0


def _notification_dedup_hit(event: dict[str, object]) -> bool:
	cache = _notification_cache()
	ttl_seconds = _notification_dedup_window_seconds(event)
	if cache is None or ttl_seconds <= 0:
		return False
	try:
		return bool(cache.get_value(_notification_dedup_cache_key(event)))
	except Exception:
		return False


def _mark_notification_delivered(event: dict[str, object]) -> None:
	cache = _notification_cache()
	ttl_seconds = _notification_dedup_window_seconds(event)
	if cache is None or ttl_seconds <= 0:
		return
	try:
		cache.set_value(
			_notification_dedup_cache_key(event),
			{"sent_at": time.time(), "source_ref": event.get("source_ref")},
			expires_in_sec=ttl_seconds,
		)
		# Store snapshot for delta-aware rendering next time
		snapshot = event.get("_current_snapshot")
		if snapshot:
			family = str(event.get("family") or "unknown")
			cache.set_value(
				f"s038:snapshot:{family}",
				snapshot,
				expires_in_sec=86400,  # 24h — snapshots survive across dedup windows
			)
	except Exception:
		return


def _get_previous_snapshot(family: str) -> dict[str, object] | None:
	"""Retrieve the last-sent snapshot for delta-aware rendering."""
	cache = _notification_cache()
	if cache is None:
		return None
	try:
		return cache.get_value(f"s038:snapshot:{family}") or None
	except Exception:
		return None


def _notification_config_get(key: str, default: object | None = None) -> object | None:
	config = getattr(frappe, "conf", {})
	getter = getattr(config, "get", None)
	if callable(getter):
		return getter(key, default)
	return default


def _maybe_polish_notification_text(
	event: dict[str, object], deterministic_text: str
) -> tuple[str, dict[str, str]]:
	"""Optional OpenAI phrasing layer with deterministic fallback."""
	if not _truthy(_notification_config_get("notification_ai_polish_enabled", False)):
		return deterministic_text, {"mode": "deterministic", "reason": "disabled"}

	api_key = str(_notification_config_get("openai_api_key", "") or "").strip()
	if not api_key:
		return deterministic_text, {"mode": "deterministic", "reason": "missing_openai_key"}

	model = str(_notification_config_get("notification_ai_model", "gpt-4o-mini") or "gpt-4o-mini")
	prompt = (
		"Rewrite this operations notification to sound like a concise AI assistant brief. "
		"Preserve every fact, number, owner, action, evidence link, and section heading exactly. "
		"Do not invent causes, fix steps, or new facts.\n\n"
		f"{deterministic_text}"
	)

	try:
		response = requests.post(
			"https://api.openai.com/v1/chat/completions",
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			},
			json={
				"model": model,
				"temperature": 0.2,
				"messages": [
					{
						"role": "system",
						"content": "You rewrite operational alerts without changing facts or sections.",
					},
					{"role": "user", "content": prompt},
				],
			},
			timeout=12,
		)
		response.raise_for_status()
		data = response.json()
		content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
		text = str(content or "").strip()
		if not text:
			return deterministic_text, {"mode": "deterministic", "reason": "empty_ai_response"}
		return text, {"mode": "ai_polished", "model": model}
	except Exception as exc:
		return deterministic_text, {"mode": "deterministic", "reason": f"ai_error:{str(exc)[:80]}"}


def _coerce_notification_event_payload(
	event: dict[str, object] | str | None = None,
	**kwargs,
) -> dict[str, object]:
	if isinstance(event, dict):
		payload = dict(event)
	elif isinstance(event, str) and event.strip():
		payload = json.loads(event)
	else:
		payload = {}
	if kwargs:
		payload.update({key: value for key, value in kwargs.items() if key not in {"dry_run"}})
	facts = payload.get("facts")
	if isinstance(facts, str) and facts.strip():
		payload["facts"] = json.loads(facts)
	elif facts is None:
		payload["facts"] = {}
	return payload


def _deliver_notification_event(
	event: dict[str, object] | str | None = None,
	*,
	dry_run: bool = False,
	**kwargs,
) -> dict[str, object]:
	logger = frappe.logger("google_chat")
	try:
		payload = _coerce_notification_event_payload(event, **kwargs)
		family = str(payload.get("family") or "")
		previous_snapshot = _get_previous_snapshot(family) if family else None
		normalized = build_notification_event(payload, previous_snapshot=previous_snapshot)
		validation_errors = validate_notification_event(normalized)
		if validation_errors:
			raise ValueError("Missing notification fields: " + ", ".join(validation_errors))

		deterministic_text = render_notification_text(normalized)
		final_text, ai_meta = _maybe_polish_notification_text(normalized, deterministic_text)
		normalized["rendered_text"] = final_text
		effective_target_space = route_outbound_chat_space(
			str(normalized["requested_space"]),
			logger=logger,
			context="hrms.api.google_chat.send_notification_event",
			family=str(normalized["family"]),
		)

		if dry_run:
			return {
				"success": True,
				"sent": False,
				"skipped": False,
				"dry_run": True,
				"family": normalized["family"],
				"target_space": effective_target_space,
				"rendered_text": final_text,
				"ai_meta": ai_meta,
				"source_ref": normalized["source_ref"],
				"dedup_key": normalized["dedup_key"],
			}

		if _notification_dedup_hit(normalized):
			logger.info(
				"Notification dedup hit family=%s source_ref=%s",
				normalized["family"],
				normalized["source_ref"],
			)
			return {
				"success": True,
				"sent": False,
				"skipped": True,
				"reason": "dedup_window_active",
				"family": normalized["family"],
				"target_space": effective_target_space,
				"dedup_key": normalized["dedup_key"],
			}

		send_result = _send_message_to_space_internal(
			str(normalized["requested_space"]),
			final_text,
			family=str(normalized["family"]),
			context="hrms.api.google_chat.send_notification_event",
		)
		if send_result.get("success"):
			_mark_notification_delivered(normalized)
			return {
				"success": bool(send_result.get("success")),
				"sent": bool(send_result.get("sent")),
				"skipped": False,
				"family": normalized["family"],
				"target_space": send_result.get("target_space", effective_target_space),
				"message_id": send_result.get("message_id"),
				"rendered_text": final_text,
				"ai_meta": ai_meta,
			"source_ref": normalized["source_ref"],
			"dedup_key": normalized["dedup_key"],
		}
	except Exception as exc:
		logger.error("send_notification_event failed: %s", exc)
		frappe.log_error(
			title="Structured Notification Error",
			message=f"error={str(exc)[:500]} event={str(event)[:1000]}",
		)
		return {"success": False, "sent": False, "skipped": False, "error": str(exc)}


def send_notification_event(event: dict[str, object]) -> bool:
	"""Canonical structured sender for Sprint 38 migrated families."""
	result = _deliver_notification_event(event)
	return bool(result.get("success"))


@frappe.whitelist()
def ingest_notification_event(event: dict[str, object] | str | None = None, dry_run: bool = False, **kwargs):
	"""Whitelisted structured ingest endpoint for standalone services."""
	dry_run_flag = dry_run if isinstance(dry_run, bool) else _truthy(dry_run)
	return _deliver_notification_event(event, dry_run=dry_run_flag, **kwargs)


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
		return {"success": False, "error": "Google account not connected", "needs_auth": True}

	try:
		access_token = get_valid_access_token(user)
	except frappe.AuthenticationError as e:
		return {"success": False, "error": str(e), "needs_auth": True}
	except Exception as e:
		frappe.log_error(title="Google Chat Token Error", message=f"User: {user}, Error: {e!s}")
		return {"success": False, "error": "Failed to get access token"}

	try:
		response = requests.get(
			"https://chat.googleapis.com/v1/spaces",
			headers={"Authorization": f"Bearer {access_token}"},
			params={"pageSize": 100},
			timeout=30,
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
				"needs_auth": True,
			}

		if response.status_code != 200:
			frappe.log_error(
				title="Google Chat API Error",
				message=f"User: {user}, Status: {response.status_code}, Body: {response.text[:500]}",
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
				"types": sorted(list({(s.get("spaceType") or "UNKNOWN") for s in raw_spaces}))[:10],
			},
		)

		spaces_out = []
		for s in raw_spaces:
			space_name = s.get("name") or ""
			space_type = s.get("spaceType", "SPACE")
			display_name = (s.get("displayName") or "").strip()
			fallback = display_name or _space_id_suffix(space_name) or "Unnamed"

			# Pragmatic product decision (runtime evidence):
			# Listing membership for DMs / unnamed group chats is not reliable in this environment
			# (404/400 errors), and Google often does not provide enough data to derive a label.
			#
			# To avoid showing users opaque IDs like "AAQA...", we filter:
			# - ALL DIRECT_MESSAGE spaces
			# - GROUP_CHAT spaces whose displayName looks like an ID or is missing
			if space_type == "DIRECT_MESSAGE":
				continue
			if space_type == "GROUP_CHAT" and _needs_membership_label(s):
				continue

			# For regular SPACE entries (and named group chats), attempt enrichment only if needed.
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
						{
							"spaceType": space_type,
							"spaceId": _space_id_suffix(space_name),
							"error": msg[:120],
						},
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
		frappe.log_error(title="Google Chat Timeout", message=f"User: {user}")
		return {"success": False, "error": "Request timed out. Please try again."}

	except requests.RequestException as e:
		frappe.log_error(title="Google Chat Request Error", message=f"User: {user}, Error: {e!s}")
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

	return {"connected": has_valid_token(user), "user": user}


# ---------------------------------------------------------------------------
# Doc Event Handlers (wired via hooks.py doc_events)
# ---------------------------------------------------------------------------


def on_approval_queue_insert(doc, method=None):
	"""
	Notify relevant space when a new BEI Approval Queue item is created.
	Fires via doc_events: BEI Approval Queue → after_insert.
	"""
	try:
		reference_doctype = (
			getattr(doc, "reference_doctype", None) or getattr(doc, "approval_type", None) or "Approval"
		)
		reference_name = (
			getattr(doc, "reference_name", None)
			or getattr(doc, "subject", None)
			or getattr(doc, "name", "Unknown")
		)
		dashboard_url = (
			"https://my.bebang.ph/dashboard/store-ops/order-approvals"
			if reference_doctype == "BEI Store Order"
			else ""
		)
		send_notification_event(
			{
				"family": "approval_queue_new",
				"source_system": "frappe",
				"source_ref": getattr(doc, "name", None) or reference_name,
				"severity": "critical" if getattr(doc, "priority", None) == "Urgent" else "high",
				"owner": getattr(doc, "assigned_approver", None) or "Assigned Approver",
				"facts": {
					"queue_name": getattr(doc, "name", None),
					"reference_doctype": reference_doctype,
					"reference_name": reference_name,
					"store": getattr(doc, "store", None),
					"priority": getattr(doc, "priority", None),
					"assigned_approver": getattr(doc, "assigned_approver", None),
					"dashboard_url": dashboard_url,
				},
			}
		)
	except Exception as e:
		frappe.log_error(
			title="Approval Queue Notification Error",
			message=f"doc={doc.name}, error={str(e)[:300]}",
		)


def on_store_order_update(doc, method=None):
	"""
	Notify store's Google Chat space when a BEI Store Order status changes.
	Fires via doc_events: BEI Store Order → on_update.
	Notifies on: Approved, Cancelled.
	"""
	_NOTIFY_STATUSES = {"Cancelled"}
	status = getattr(doc, "status", None)
	if status not in _NOTIFY_STATUSES:
		return

	# Only notify on actual status transitions, not re-saves
	if not doc.is_new() and not doc.has_value_changed("status"):
		return

	try:
		# Prefer per-store space from linked Warehouse, fall back to global setting
		space = None
		store_warehouse = getattr(doc, "warehouse", None) or getattr(doc, "store_warehouse", None)
		if store_warehouse:
			space = frappe.db.get_value("Warehouse", store_warehouse, "custom_gchat_space")

		if not space:
			from hrms.utils.bei_config import SPACE_NOTIFICATIONS, get_chat_space

			space = get_chat_space(SPACE_NOTIFICATIONS)

		if status == "Approved":
			message = f"*Store Order Approved*\n\nOrder *{doc.name}* has been approved and is being prepared."
		else:
			reason = getattr(doc, "cancellation_reason", None) or ""
			reason_text = f"\nReason: {reason}" if reason else ""
			message = f"*Store Order Cancelled*\n\nOrder *{doc.name}* was cancelled.{reason_text}"

		send_message_to_space(space, message)
	except Exception as e:
		frappe.log_error(
			title="Store Order Notification Error",
			message=f"doc={doc.name}, status={status}, error={str(e)[:300]}",
		)

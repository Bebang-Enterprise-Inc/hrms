"""Sentry integration for Frappe HRMS.

All Sentry initialization happens here, triggered by Frappe hooks.
This ensures frappe.conf is available (not the case at module import time).
Thread-safe: uses locks to handle multiple gunicorn workers.

Hooks used (registered in hooks.py):
  - before_request: init + breadcrumbs
  - before_request_end: capture exceptions from Frappe's error handler
"""

import os
import sys
import threading
from typing import Any

import frappe

# Test accounts whose errors should NOT be sent to Sentry.
# These generate hundreds of expected validation errors during E2E testing.
_TEST_USERS = frozenset({
	"Administrator",
	"test.area@bebang.ph",
	"test.supervisor@bebang.ph",
	"test.staff@bebang.ph",
	"test.crew1@bebang.ph",
	"test.hr@bebang.ph",
	"test.projects@bebang.ph",
	"test.projects.staff@bebang.ph",
	"test.commissary@bebang.ph",
	"test.warehouse@bebang.ph",
})

_sentry_initialized = False
_log_error_patched = False
_handle_exception_patched = False


def _is_test_user():
	"""Return True if the current session user is a test/admin account."""
	try:
		user = getattr(frappe.session, "user", None) if hasattr(frappe, "session") and frappe.session else None
		return user in _TEST_USERS
	except Exception:
		return False


_init_lock = threading.Lock()
_patch_lock = threading.Lock()
_exc_patch_lock = threading.Lock()
_original_log_error = None
_original_handle_exception = None
_MAX_TAG_LENGTH = 200
_MAX_ARRAY_ITEMS = 10
_MAX_OBJECT_KEYS = 20
_MAX_DEPTH = 3


def _to_safe_tag_value(value: Any) -> str | None:
	"""Return a bounded Sentry tag value or None when empty."""
	if value is None:
		return None

	normalized = str(value).strip()
	if not normalized:
		return None

	return normalized[:_MAX_TAG_LENGTH]


def _sanitize_value(value: Any, depth: int = 0):
	"""Best-effort sanitizer for Sentry context payloads."""
	if value is None or isinstance(value, (str, int, float, bool)):
		return value

	if depth >= _MAX_DEPTH:
		return "[truncated]"

	if isinstance(value, (list, tuple, set)):
		return [_sanitize_value(item, depth + 1) for item in list(value)[:_MAX_ARRAY_ITEMS]]

	if isinstance(value, dict):
		items = list(value.items())[:_MAX_OBJECT_KEYS]
		return {str(key): _sanitize_value(entry, depth + 1) for key, entry in items}

	if isinstance(value, Exception):
		return {"type": type(value).__name__, "message": str(value)}

	return str(value)


def _sanitize_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
	"""Return a Sentry-safe dict or None when there is nothing to attach."""
	if not record:
		return None

	sanitized = _sanitize_value(record)
	return sanitized if isinstance(sanitized, dict) and sanitized else None


def _set_sentry_user():
	"""Attach the current Frappe user to the active Sentry scope."""
	try:
		import sentry_sdk

		if hasattr(frappe, "session") and frappe.session and frappe.session.user:
			sentry_sdk.set_user({"email": frappe.session.user, "id": frappe.session.user})
	except Exception:
		pass


def _get_request_metadata() -> dict[str, str]:
	"""Extract normalized request metadata from the current Frappe request."""
	path = ""
	method = ""
	if hasattr(frappe, "request") and frappe.request:
		path = frappe.request.path or ""
		method = frappe.request.method or ""

	cmd = ""
	if frappe.form_dict:
		cmd = frappe.form_dict.get("cmd", "") or ""

	endpoint_or_job = cmd or path or "unknown"
	route_action = cmd.rsplit(".", 1)[-1] if cmd else ""

	return {
		"route": path or "unknown",
		"http_method": method or "unknown",
		"frappe_cmd": cmd,
		"endpoint_or_job": endpoint_or_job,
		"route_action": route_action,
	}


def set_backend_observability_context(
	*,
	module: str | None = None,
	action: str | None = None,
	route: str | None = None,
	route_action: str | None = None,
	mutation_type: str | None = None,
	endpoint_or_job: str | None = None,
	phase: str | None = None,
	surface: str = "frappe_whitelist",
	extras: dict[str, Any] | None = None,
):
	"""Apply stable BEI tags/context to the current request scope."""
	init_sentry()

	if _is_test_user():
		return

	try:
		import sentry_sdk

		request_meta = _get_request_metadata()
		_set_sentry_user()

		tags = {
			"module": module,
			"route": route or request_meta["route"],
			"action": action,
			"route_action": route_action or request_meta["route_action"],
			"mutation_type": mutation_type,
			"endpoint_or_job": endpoint_or_job or request_meta["endpoint_or_job"],
			"surface": surface,
			"phase": phase,
			"http_method": request_meta["http_method"],
			"frappe_cmd": request_meta["frappe_cmd"],
		}

		for key, value in tags.items():
			safe_value = _to_safe_tag_value(value)
			if safe_value:
				sentry_sdk.set_tag(key, safe_value)

		context_payload = _sanitize_record(
			{
				"request_route": request_meta["route"],
				"http_method": request_meta["http_method"],
				"frappe_cmd": request_meta["frappe_cmd"],
				"extras": extras or {},
			}
		)
		if context_payload:
			sentry_sdk.set_context("bei_backend_observability", context_payload)

		sentry_sdk.add_breadcrumb(
			category="bei.backend",
			message=action or route_action or request_meta["route_action"] or "backend_event",
			level="info",
			data=_sanitize_record(
				{
					"module": module,
					"route": route or request_meta["route"],
					"endpoint_or_job": endpoint_or_job or request_meta["endpoint_or_job"],
					"mutation_type": mutation_type,
					"phase": phase,
				}
			),
		)
	except Exception:
		pass


def capture_backend_message(
	message: str,
	*,
	level: str = "error",
	module: str | None = None,
	action: str | None = None,
	route: str | None = None,
	route_action: str | None = None,
	mutation_type: str | None = None,
	endpoint_or_job: str | None = None,
	phase: str | None = None,
	surface: str = "frappe_whitelist",
	extras: dict[str, Any] | None = None,
):
	"""Capture handled backend failures without relying on an exception bubble."""
	set_backend_observability_context(
		module=module,
		action=action,
		route=route,
		route_action=route_action,
		mutation_type=mutation_type,
		endpoint_or_job=endpoint_or_job,
		phase=phase,
		surface=surface,
		extras=extras,
	)

	if _is_test_user():
		return

	try:
		import sentry_sdk

		sentry_sdk.capture_message(message, level=level)
	except Exception:
		pass


def init_sentry():
	"""Initialize Sentry SDK. Called by before_request hook.

	Thread-safe: uses lock + flag to ensure single initialization
	even with multiple gunicorn workers.

	CRITICAL: Flag is only set True AFTER successful init, so failures
	can be retried on the next request.
	"""
	global _sentry_initialized

	if _sentry_initialized:
		return

	with _init_lock:
		if _sentry_initialized:
			return

		try:
			import sentry_sdk

			dsn = os.environ.get("SENTRY_DSN") or frappe.conf.get("sentry_dsn")
			if not dsn:
				_sentry_initialized = True
				return

			from hrms import __version__

			sentry_sdk.init(
				dsn=dsn,
				environment=(
					"development"
					if getattr(frappe.conf, "developer_mode", 0)
					else "production"
				),
				release=f"bei-hrms@{__version__}",
				traces_sample_rate=0.1,
				profiles_sample_rate=0.1,
				enable_tracing=True,
			)

			_patch_log_error()
			_patch_handle_exception()
			_patch_frappe_set_scope_for_non_request_contexts()
			_sentry_initialized = True

		except Exception:
			pass


def _patch_frappe_set_scope_for_non_request_contexts():
	"""S225 follow-up — gracefully handle non-request contexts in frappe.utils.sentry.set_scope.

	Frappe's built-in set_scope accesses `frappe.request.path` directly, which raises
	`RuntimeError: object is not bound` when called from a worker thread or
	scheduled job. This causes spurious Sentry errors during non-request log_error
	calls (e.g., the S225 lock-wait telemetry from concurrent dispatches).

	Wrap it to skip silently when no request is bound. The error reporting still
	flows through Frappe's other paths.
	"""
	try:
		import frappe.utils.sentry as _frappe_sentry
		if getattr(_frappe_sentry, "_bei_set_scope_patched", False):
			return
		_orig_set_scope = _frappe_sentry.set_scope

		def _safe_set_scope(*args, **kwargs):
			try:
				return _orig_set_scope(*args, **kwargs)
			except RuntimeError:
				# "object is not bound" — no Werkzeug request context. Skip.
				return None

		_frappe_sentry.set_scope = _safe_set_scope
		_frappe_sentry._bei_set_scope_patched = True
	except Exception:
		pass


def _patch_log_error():
	"""Monkey-patch frappe.log_error to forward errors to Sentry.

	Thread-safe with double-checked locking.
	Covers all 446 existing frappe.log_error() calls with zero per-file changes.
	"""
	global _log_error_patched, _original_log_error

	if _log_error_patched:
		return

	with _patch_lock:
		if _log_error_patched:
			return
		if not hasattr(frappe, "log_error"):
			return

		_original_log_error = frappe.log_error

		def patched_log_error(*args, **kwargs):
			# S204: Error-handler self-harm guard — Frappe's Error Log.method
			# field is VARCHAR(140). frappe.log_error's own auto-swap only
			# fires when `"\n" in title`; single-line long strings (common
			# for `frappe.ValidationError("...allowlist...")`) stay as title
			# and trip the cap. This causes the insert to throw, which
			# propagates OUT of the caller's silent except block and masks
			# the real root cause. Clamp BOTH positional args + title kwarg
			# defensively, regardless of argument order / intent.
			new_args = list(args)
			for idx in (0, 1):
				if idx < len(new_args) and isinstance(new_args[idx], str) and len(new_args[idx]) > 135:
					new_args[idx] = new_args[idx][:132] + "..."
			args = tuple(new_args)
			for key in ("title", "message"):
				if key in kwargs and isinstance(kwargs[key], str) and len(kwargs[key]) > 135:
					# Only clamp title; leave message alone unless it's also overlong
					# enough to cause issues (Error Log.error is TEXT, no cap).
					if key == "title":
						kwargs[key] = kwargs[key][:132] + "..."
			result = _original_log_error(*args, **kwargs)

			try:
				if _is_test_user():
					return result

				import sentry_sdk

				title = kwargs.get("title", args[1] if len(args) > 1 else "Frappe Error")
				message = kwargs.get("message", args[0] if args else "")
				set_backend_observability_context(
					action="frappe_log_error",
					phase="log_error",
					surface="frappe_log_error",
					extras={"title": title, "message_preview": str(message)[:300]},
				)

				_set_sentry_user()

				exc_info = sys.exc_info()
				if exc_info[0] is not None:
					sentry_sdk.capture_exception(exc_info)
				else:
					# Include actual error content instead of generic "New Exception"
					msg_str = str(message)[:1000] if message else ""
					title_str = str(title) if title else "Frappe Error"
					sentry_sdk.capture_message(
						f"{title_str}\n{msg_str}" if msg_str else title_str,
						level="error",
					)
			except Exception:
				pass

			return result

		frappe.log_error = patched_log_error
		_log_error_patched = True


def _patch_handle_exception():
	"""Monkey-patch frappe.app.handle_exception to capture all web exceptions.

	Frappe does NOT have an after_exception hook. All web exceptions are
	caught by handle_exception() in frappe/app.py. This patch ensures
	every unhandled web error reaches Sentry.
	"""
	global _handle_exception_patched, _original_handle_exception

	if _handle_exception_patched:
		return

	with _exc_patch_lock:
		if _handle_exception_patched:
			return

		try:
			from frappe import app as frappe_app

			if not hasattr(frappe_app, "handle_exception"):
				return

			_original_handle_exception = frappe_app.handle_exception

			def patched_handle_exception(e):
				try:
					if _is_test_user():
						return _original_handle_exception(e)

					import sentry_sdk

					http_status = getattr(e, "http_status_code", 500)
					request_meta = _get_request_metadata()

					# Determine if this is a custom API endpoint (hrms.api.*)
					# vs a Desk form submission. Errors from our API endpoints
					# indicate real bugs (bad data, missing references, etc.)
					# even if they're 4xx. Desk form validation (4xx) is expected.
					endpoint = request_meta["route"]
					cmd = request_meta["frappe_cmd"]

					is_custom_api = cmd.startswith("hrms.api.") or "hrms.api." in endpoint

					if http_status < 500 and not is_custom_api:
						return _original_handle_exception(e)

					set_backend_observability_context(
						action="handle_exception",
						route=endpoint,
						route_action=request_meta["route_action"] or None,
						mutation_type="load" if request_meta["http_method"] == "GET" else "mutation",
						endpoint_or_job=request_meta["endpoint_or_job"],
						phase="backend_exception",
						surface="frappe_request",
						extras={
							"http_status": http_status,
							"exception_type": type(e).__name__,
						},
					)

					# Tag API validation errors distinctly so they can be filtered
					if is_custom_api and http_status < 500:
						sentry_sdk.set_tag("error_source", "api_validation")
						sentry_sdk.set_level("warning")
					else:
						sentry_sdk.set_tag("error_source", "server_error")

					sentry_sdk.capture_exception(e)
				except Exception:
					pass

				return _original_handle_exception(e)

			frappe_app.handle_exception = patched_handle_exception
			_handle_exception_patched = True

		except Exception:
			pass


def add_request_breadcrumb():
	"""Add Frappe request context as Sentry breadcrumb.

	Also triggers deferred Sentry init on first request.
	"""
	init_sentry()

	try:
		import sentry_sdk

		if hasattr(frappe, "request") and frappe.request:
			sentry_sdk.add_breadcrumb(
				category="frappe.request",
				message=f"Request to {frappe.request.path}",
				data={
					"doctype": frappe.form_dict.get("doctype", "") if frappe.form_dict else "",
					"method": frappe.form_dict.get("cmd", "") if frappe.form_dict else "",
				},
				level="info",
			)
	except Exception:
		pass

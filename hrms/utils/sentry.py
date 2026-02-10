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
			_sentry_initialized = True

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
			result = _original_log_error(*args, **kwargs)

			try:
				if _is_test_user():
					return result

				import sentry_sdk

				title = kwargs.get("title", args[1] if len(args) > 1 else "Frappe Error")
				message = kwargs.get("message", args[0] if args else "")

				if hasattr(frappe, "session") and frappe.session and frappe.session.user:
					sentry_sdk.set_user(
						{
							"email": frappe.session.user,
							"id": frappe.session.user,
						}
					)

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

					# Only capture server errors (5xx), not client validation (4xx).
					# 4xx errors (ValidationError, PermissionError, etc.) are expected
					# user-facing errors, not bugs.
					if http_status < 500:
						return _original_handle_exception(e)

					if hasattr(frappe, "session") and frappe.session and frappe.session.user:
						sentry_sdk.set_user(
							{
								"email": frappe.session.user,
								"id": frappe.session.user,
							}
						)

					if hasattr(frappe, "request") and frappe.request:
						sentry_sdk.set_tag("endpoint", frappe.request.path or "unknown")
						sentry_sdk.set_tag("method", frappe.request.method or "unknown")

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

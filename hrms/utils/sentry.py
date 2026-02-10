"""Sentry integration for Frappe HRMS.

All Sentry initialization happens here, triggered by Frappe hooks.
This ensures frappe.conf is available (not the case at module import time).
Thread-safe: uses locks to handle multiple gunicorn workers.
"""

import os
import sys
import threading

import frappe

_sentry_initialized = False
_log_error_patched = False
_init_lock = threading.Lock()
_patch_lock = threading.Lock()
_original_log_error = None


def init_sentry():
	"""Initialize Sentry SDK. Called by before_request hook.

	Thread-safe: uses lock + flag to ensure single initialization
	even with multiple gunicorn workers.
	"""
	global _sentry_initialized

	if _sentry_initialized:
		return

	with _init_lock:
		if _sentry_initialized:
			return
		_sentry_initialized = True

	try:
		import sentry_sdk

		dsn = os.environ.get("SENTRY_DSN") or frappe.conf.get("sentry_dsn")
		if not dsn:
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
			integrations=[],
		)

		_patch_log_error()

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
					sentry_sdk.capture_message(
						f"{title}: {str(message)[:500]}",
						level="error",
					)
			except Exception:
				pass

			return result

		frappe.log_error = patched_log_error
		_log_error_patched = True


def capture_exception():
	"""Hook called by Frappe after any unhandled exception."""
	try:
		import sentry_sdk

		exc_info = sys.exc_info()
		if exc_info[0] is None:
			return

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

		sentry_sdk.capture_exception(exc_info)
	except Exception:
		pass


def add_request_breadcrumb():
	"""Add Frappe request context as Sentry breadcrumb.

	Also triggers deferred Sentry init on first request.
	"""
	init_sentry()

	try:
		import sentry_sdk

		if frappe.form_dict:
			sentry_sdk.add_breadcrumb(
				category="frappe.request",
				message=f"Request to {frappe.request.path}",
				data={
					"doctype": frappe.form_dict.get("doctype", ""),
					"method": frappe.form_dict.get("cmd", ""),
				},
				level="info",
			)
	except Exception:
		pass

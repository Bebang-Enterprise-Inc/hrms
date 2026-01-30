import frappe

__version__ = "16.0.0-dev"

# Import API module to register whitelisted methods at startup
import hrms.api  # noqa: E402, F401


def refetch_resource(cache_key: str | list, user=None):
	frappe.publish_realtime(
		"hrms:refetch_resource",
		{"cache_key": cache_key},
		user=user or frappe.session.user,
		after_commit=True,
	)

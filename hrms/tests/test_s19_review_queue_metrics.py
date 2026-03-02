import importlib.util
import pathlib
import sys
import types


def _install_stubs(query_capture):
	frappe = types.ModuleType("frappe")
	frappe._ = lambda value: value
	frappe.whitelist = lambda fn=None, **kwargs: fn if fn else (lambda inner: inner)
	frappe.logger = lambda _name: types.SimpleNamespace(warning=lambda *args, **kwargs: None)
	frappe.parse_json = lambda payload: payload

	class _DB:
		@staticmethod
		def sql(query, params=None, as_dict=False):
			query_capture.append(str(query))
			return []

	frappe.local = types.SimpleNamespace(db=_DB())
	frappe.__dict__["db"] = frappe.local.db

	utils = types.ModuleType("frappe.utils")
	utils.today = lambda: "2026-03-02"
	utils.now = lambda: "2026-03-02 09:00:00"
	utils.getdate = lambda value=None: value or "2026-03-02"
	utils.get_time = lambda value=None: value or "09:00:00"
	utils.nowdate = lambda: "2026-03-02"
	utils.now_datetime = lambda: "2026-03-02 09:00:00"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils

	hrms_pkg = types.ModuleType("hrms")
	hrms_pkg.__path__ = []
	utils_pkg = types.ModuleType("hrms.utils")
	utils_pkg.__path__ = []
	scm_roles = types.ModuleType("hrms.utils.scm_roles")
	scm_roles.ORDERING_STORE_ROLES = []
	scm_roles.ORDERING_WAREHOUSE_ROLES = []
	scm_roles.ORDERING_APPROVAL_ROLES = []
	scm_roles.check_scm_permission = lambda *args, **kwargs: None

	sys.modules["hrms"] = hrms_pkg
	sys.modules["hrms.utils"] = utils_pkg
	sys.modules["hrms.utils.scm_roles"] = scm_roles


def _load_module(query_capture):
	_install_stubs(query_capture)
	file_path = pathlib.Path(__file__).resolve().parents[1] / "api" / "ordering.py"
	spec = importlib.util.spec_from_file_location("s19_ordering_under_test", file_path)
	module = importlib.util.module_from_spec(spec)
	assert spec and spec.loader
	spec.loader.exec_module(module)
	return module


def test_review_queue_counts_edited_lines_using_is_edited_flag():
	queries = []
	ordering = _load_module(queries)
	ordering.get_order_review_queue(date="2026-03-02", status="Pending Approval")

	assert queries, "Expected query execution in get_order_review_queue()"
	query_text = queries[-1]
	assert "soi.is_edited" in query_text
	assert "deviation_count" in query_text

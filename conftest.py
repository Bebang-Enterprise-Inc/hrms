import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def _install_frappe_stub() -> None:
    frappe = types.ModuleType("frappe")
    frappe.__path__ = []

    class ValidationError(Exception):
        pass

    class PermissionError(Exception):
        pass

    def _whitelist(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(function):
            return function

        return decorator

    def _throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    frappe._ = lambda value: value
    frappe.whitelist = _whitelist
    frappe.throw = _throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError
    frappe.log_error = lambda *args, **kwargs: None
    frappe.msgprint = lambda *args, **kwargs: None
    frappe.get_roles = lambda *args, **kwargs: []
    frappe.get_all = lambda *args, **kwargs: []
    frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace()
    frappe.new_doc = lambda *args, **kwargs: types.SimpleNamespace()
    frappe.publish_realtime = lambda *args, **kwargs: None
    frappe.defaults = types.SimpleNamespace(get_global_default=lambda *args, **kwargs: None)
    frappe.session = types.SimpleNamespace(user="pytest@example.com")
    frappe.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: None,
        exists=lambda *args, **kwargs: None,
        savepoint=lambda *args, **kwargs: None,
        rollback=lambda *args, **kwargs: None,
        release_savepoint=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        get_table_columns=lambda *args, **kwargs: [],
        table_exists=lambda *args, **kwargs: False,
        sql=lambda *args, **kwargs: [],
        commit=lambda *args, **kwargs: None,
    )

    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.flt = lambda value=0, precision=None: (
        round(float(value or 0), precision) if precision is not None else float(value or 0)
    )
    frappe_utils.nowdate = lambda: "2026-01-01"
    frappe_utils.now_datetime = lambda: "2026-01-01 00:00:00"
    frappe_utils.add_days = lambda value, days: value
    frappe_utils.cint = lambda value=0: int(float(value or 0))

    frappe_model = types.ModuleType("frappe.model")
    frappe_model.__path__ = []
    frappe_model_document = types.ModuleType("frappe.model.document")

    class Document:
        pass

    frappe_model_document.Document = Document
    frappe_model.document = frappe_model_document

    frappe.utils = frappe_utils
    frappe.model = frappe_model

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = frappe_utils
    sys.modules["frappe.model"] = frappe_model
    sys.modules["frappe.model.document"] = frappe_model_document


def _install_hrms_api_stub() -> None:
    if "hrms.api" in sys.modules:
        return

    # hrms/__init__.py imports hrms.api at package import time; keep this lightweight.
    # Set a real package path so submodule imports (e.g. hrms.api.billing) still work.
    hrms_api = types.ModuleType("hrms.api")
    hrms_api.__path__ = [str(REPO_ROOT / "hrms" / "api")]
    sys.modules["hrms.api"] = hrms_api


# Enable isolated unit tests in environments without a full Frappe install.
if importlib.util.find_spec("frappe") is None and "frappe" not in sys.modules:
    _install_frappe_stub()
    _install_hrms_api_stub()

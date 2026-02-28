import importlib.util
import sys
import types


# Enable isolated unit tests in environments without a full Frappe install.
if importlib.util.find_spec("frappe") is None and "frappe" not in sys.modules:
    frappe = types.ModuleType("frappe")
    frappe.publish_realtime = lambda *args, **kwargs: None
    frappe.session = types.SimpleNamespace(user="pytest@example.com")
    sys.modules["frappe"] = frappe

    # hrms/__init__.py imports hrms.api at package import time; provide a light stub.
    if "hrms.api" not in sys.modules:
        hrms_api = types.ModuleType("hrms.api")
        hrms_api.__path__ = []
        sys.modules["hrms.api"] = hrms_api

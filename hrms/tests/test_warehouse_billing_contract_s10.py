import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_modules():
	if "frappe" not in sys.modules:
		frappe = types.ModuleType("frappe")
		utils = types.ModuleType("frappe.utils")

		def whitelist(*args, **kwargs):
			def decorator(fn):
				return fn

			return decorator

		frappe.whitelist = whitelist
		frappe._ = lambda text: text
		frappe.throw = lambda message, *args, **kwargs: (_ for _ in ()).throw(Exception(message))
		frappe.log_error = lambda *args, **kwargs: None
		frappe.PermissionError = type("PermissionError", (Exception,), {})
		frappe.ValidationError = type("ValidationError", (Exception,), {})
		frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
		frappe.session = types.SimpleNamespace(user="finance@bebang.ph")
		frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [])

		utils.flt = lambda value, precision=None: float(value or 0)
		utils.now_datetime = lambda: "2026-02-28 10:00:00"
		utils.get_first_day = lambda value: value
		utils.get_last_day = lambda value: value
		utils.nowdate = lambda: "2026-02-28"
		def _getdate(value):
			if isinstance(value, (datetime.date, datetime.datetime)):
				return value
			return datetime.datetime.fromisoformat(str(value))

		utils.getdate = _getdate

		sys.modules["frappe"] = frappe
		sys.modules["frappe.utils"] = utils

	if "hrms" not in sys.modules:
		hrms_pkg = types.ModuleType("hrms")
		hrms_pkg.__path__ = []
		sys.modules["hrms"] = hrms_pkg

	if "hrms.utils" not in sys.modules:
		hrms_utils_pkg = types.ModuleType("hrms.utils")
		hrms_utils_pkg.__path__ = []
		sys.modules["hrms.utils"] = hrms_utils_pkg

	if "hrms.api" not in sys.modules:
		hrms_api_pkg = types.ModuleType("hrms.api")
		hrms_api_pkg.__path__ = []
		sys.modules["hrms.api"] = hrms_api_pkg

	if "hrms.utils.bei_config" not in sys.modules:
		bei_config_mod = types.ModuleType("hrms.utils.bei_config")
		bei_config_mod.get_company = lambda: "Bebang Enterprise Inc."
		sys.modules["hrms.utils.bei_config"] = bei_config_mod

	if "hrms.utils.scm_roles" not in sys.modules:
		scm_roles_mod = types.ModuleType("hrms.utils.scm_roles")
		scm_roles_mod.RATE_MANAGEMENT_ROLES = ["System Manager"]
		scm_roles_mod.SCM_BILLING_ROLES = ["System Manager"]
		scm_roles_mod.check_scm_permission = lambda roles, action: None
		sys.modules["hrms.utils.scm_roles"] = scm_roles_mod


_install_fake_modules()

billing_spec = importlib.util.spec_from_file_location(
	"billing_under_test",
	ROOT / "hrms" / "api" / "billing.py",
)
billing = importlib.util.module_from_spec(billing_spec)
billing_spec.loader.exec_module(billing)


class TestWarehouseBillingContractS10(unittest.TestCase):
	def test_get_3pl_rates_applies_ewt_defaults_when_missing(self):
		billing.frappe.db.sql = lambda *args, **kwargs: [
			{
				"name": "RATE-001",
				"rate_name": "3MD Frozen",
				"threepl_partner": "3MD",
				"cargo_type": "FC",
				"zone": "NORTH",
				"rate_per_trip": 1000,
				"overtime_rate": 100,
				"surcharge_rate": 50,
			}
		]

		result = billing.get_3pl_rates(partner="3MD")

		self.assertEqual(result["count"], 1)
		self.assertEqual(result["rates"][0]["ewt_atc"], "WC110")
		self.assertEqual(result["rates"][0]["ewt_rate"], 1.0)

	def test_get_3pl_rates_preserves_existing_ewt_fields(self):
		billing.frappe.db.sql = lambda *args, **kwargs: [
			{
				"name": "RATE-002",
				"rate_name": "RCS Mixed",
				"threepl_partner": "RCS",
				"cargo_type": "Mixed",
				"zone": "SOUTH",
				"rate_per_trip": 1200,
				"overtime_rate": 120,
				"surcharge_rate": 60,
				"ewt_atc": "WC158",
				"ewt_rate": 2.0,
			}
		]

		result = billing.get_3pl_rates(partner="RCS")

		self.assertEqual(result["count"], 1)
		self.assertEqual(result["rates"][0]["ewt_atc"], "WC158")
		self.assertEqual(result["rates"][0]["ewt_rate"], 2.0)


if __name__ == "__main__":
	unittest.main()

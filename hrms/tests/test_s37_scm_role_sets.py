import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	if "frappe" in sys.modules:
		return
	frappe = types.ModuleType("frappe")
	frappe._ = lambda text: text
	frappe.get_roles = lambda user=None: []
	sys.modules["frappe"] = frappe


_install_fake_frappe()

spec = importlib.util.spec_from_file_location(
	"scm_roles_under_test",
	ROOT / "hrms" / "utils" / "scm_roles.py",
)
scm_roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scm_roles)


class TestS37ScmRoleSets(unittest.TestCase):
	def test_warehouse_user_is_in_dispatch_approval_and_receiving_sets(self):
		self.assertIn("Warehouse User", scm_roles.SCM_DISPATCH_ROLES)
		self.assertIn("Warehouse User", scm_roles.SCM_APPROVAL_ROLES)
		self.assertIn("Warehouse User", scm_roles.SCM_RECEIVING_ROLES)


if __name__ == "__main__":
	unittest.main()

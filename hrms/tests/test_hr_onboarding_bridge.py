import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
	if "frappe" in sys.modules:
		return

	frappe = types.ModuleType("frappe")
	utils = types.ModuleType("frappe.utils")

	def whitelist(*_args, **_kwargs):
		def decorator(fn):
			return fn

		return decorator

	class PermissionError(Exception):
		pass

	def _throw(message, exc=None):
		if isinstance(exc, type) and issubclass(exc, Exception):
			raise exc(message)
		raise Exception(message)

	frappe.whitelist = whitelist
	frappe._ = lambda text: text
	frappe.throw = _throw
	frappe.PermissionError = PermissionError
	frappe.__dict__["session"] = types.SimpleNamespace(user="Administrator")
	frappe.get_roles = lambda user=None: ["System Manager"] if user and user != "Guest" else []
	local_db = types.SimpleNamespace(
		sql=lambda *args, **kwargs: [],
		exists=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		get_value=lambda *args, **kwargs: None,
	)
	frappe.local = types.SimpleNamespace(db=local_db)
	frappe.__dict__["db"] = frappe.local.db
	frappe.get_doc = lambda *args, **kwargs: types.SimpleNamespace()

	utils.cint = lambda value: int(float(value or 0))
	utils.nowdate = lambda: "2026-02-27"

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils


_install_fake_frappe()
spec = importlib.util.spec_from_file_location(
	"hr_onboarding_under_test",
	ROOT / "hrms" / "api" / "hr_onboarding.py",
)
hr_onboarding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hr_onboarding)


class _Offer:
	def __init__(self, status="Accepted", job_applicant="APP-001"):
		self.name = "OFF-0001"
		self.status = status
		self.job_applicant = job_applicant
		self.applicant_name = "Test Applicant"
		self.company = "BEI"
		self.designation = "Store OIC"
		self.saved = False
		self.comments = []

	def save(self, ignore_permissions=False):
		self.saved = bool(ignore_permissions)

	def add_comment(self, comment_type, comment):
		self.comments.append((comment_type, comment))


class _OnboardingDraft:
	def __init__(self):
		self.name = "ONB-0001"
		self.inserted = False

	def insert(self, ignore_permissions=False):
		self.inserted = bool(ignore_permissions)
		return self


class TestHrOnboardingBridge(unittest.TestCase):
	def setUp(self):
		hr_onboarding.frappe.session.user = "hr@bebang.ph"
		hr_onboarding.frappe.get_roles = MagicMock(return_value=["HR Manager"])
		hr_onboarding.frappe.db.sql = MagicMock()
		hr_onboarding.frappe.db.exists = MagicMock(return_value=None)
		hr_onboarding.frappe.db.set_value = MagicMock()
		hr_onboarding.frappe.db.get_value = MagicMock(return_value=None)

	def test_permission_block_for_non_hr_role(self):
		hr_onboarding.frappe.get_roles = MagicMock(return_value=["Employee"])
		with self.assertRaises(hr_onboarding.frappe.PermissionError):
			hr_onboarding.get_job_offers()

	def test_get_job_offers_returns_paginated_payload(self):
		hr_onboarding.frappe.db.sql.side_effect = [
			[(2,)],
			[
				{
					"name": "OFF-0001",
					"applicant_name": "Applicant One",
					"designation": "Crew",
					"company": "BEI",
					"offer_date": "2026-02-27",
					"status": "Accepted",
					"job_applicant": "APP-001",
					"department": "Operations",
				},
				{
					"name": "OFF-0002",
					"applicant_name": "Applicant Two",
					"designation": "Store OIC",
					"company": "BEI",
					"offer_date": "2026-02-26",
					"status": "Pending",
					"job_applicant": "APP-002",
					"department": "Operations",
				},
			],
		]

		result = hr_onboarding.get_job_offers(status="Accepted", page=1, page_size=20)

		self.assertEqual(result["total"], 2)
		self.assertEqual(result["page"], 1)
		self.assertEqual(result["page_size"], 20)
		self.assertEqual(len(result["data"]), 2)
		total_query = hr_onboarding.frappe.db.sql.call_args_list[0].args[0]
		rows_query = hr_onboarding.frappe.db.sql.call_args_list[1].args[0]
		self.assertIn("`tabJob Opening`", total_query)
		self.assertIn("jop.department", total_query)
		self.assertNotIn("ja.department", total_query)
		self.assertIn("`tabJob Opening`", rows_query)
		self.assertIn("COALESCE(jop.department, '') AS department", rows_query)
		self.assertNotIn("ja.department", rows_query)

	def test_update_job_offer_status_updates_offer_and_applicant(self):
		offer = _Offer(status="Pending")
		hr_onboarding.frappe.get_doc = MagicMock(return_value=offer)

		result = hr_onboarding.update_job_offer_status("OFF-0001", "Accepted", notes="signed")

		self.assertTrue(offer.saved)
		self.assertEqual(offer.status, "Accepted")
		hr_onboarding.frappe.db.set_value.assert_called_once_with(
			"Job Applicant", "APP-001", "status", "Accepted"
		)
		self.assertTrue(result["success"])

	def test_create_onboarding_from_offer_returns_existing(self):
		offer = _Offer(status="Accepted")
		hr_onboarding.frappe.get_doc = MagicMock(return_value=offer)
		hr_onboarding.frappe.db.exists = MagicMock(return_value="ONB-0099")

		result = hr_onboarding.create_onboarding_from_offer("OFF-0001")

		self.assertTrue(result["already_exists"])
		self.assertEqual(result["onboarding_name"], "ONB-0099")

	def test_create_onboarding_from_offer_creates_new_doc(self):
		offer = _Offer(status="Accepted")
		draft = _OnboardingDraft()

		def _get_doc(arg1, arg2=None):
			if arg1 == "Job Offer":
				return offer
			if isinstance(arg1, dict):
				return draft
			raise AssertionError("unexpected get_doc call")

		hr_onboarding.frappe.get_doc = MagicMock(side_effect=_get_doc)
		hr_onboarding.frappe.db.exists = MagicMock(return_value=None)

		result = hr_onboarding.create_onboarding_from_offer("OFF-0001")

		self.assertTrue(draft.inserted)
		self.assertFalse(result["already_exists"])
		self.assertEqual(result["onboarding_name"], "ONB-0001")

	def test_get_onboarding_checklist_computes_progress(self):
		onboarding = types.SimpleNamespace(
			name="ONB-0001",
			employee_name="Applicant One",
			designation="Crew",
			department="Operations",
			company="BEI",
			boarding_status="In Process",
			job_offer="OFF-0001",
			activities=[
				types.SimpleNamespace(
					activity_name="ID Creation",
					required_for_employee_creation=1,
					task="TASK-001",
					description="Create employee ID",
					user="hr@bebang.ph",
					role="",
				),
				types.SimpleNamespace(
					activity_name="Uniform Release",
					required_for_employee_creation=0,
					task="TASK-002",
					description="Release uniform",
					user="ops@bebang.ph",
					role="",
				),
			],
		)
		hr_onboarding.frappe.get_doc = MagicMock(return_value=onboarding)
		hr_onboarding.frappe.db.get_value = MagicMock(
			side_effect=lambda doctype, name, field: "Completed" if name == "TASK-001" else "Open"
		)

		result = hr_onboarding.get_onboarding_checklist("ONB-0001")

		self.assertEqual(result["boarding_status"], "In Progress")
		self.assertEqual(result["total_activities"], 2)
		self.assertEqual(result["completed_activities"], 1)
		self.assertEqual(result["progress"], 50.0)


if __name__ == "__main__":
	unittest.main()

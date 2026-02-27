import unittest
from unittest.mock import patch

import frappe

from hrms.api import supervisor


class TestSupervisorProjectsOpenFirstS06(unittest.TestCase):
	def test_unified_queue_includes_opening_and_closing_reports(self):
		def _mock_get_all(doctype, **kwargs):
			if doctype == "BEI Store Opening Report":
				return [
					frappe._dict(
						{
							"name": "OPEN-0001",
							"store": "AYALA EVO - BEI",
							"report_date": "2026-02-27",
							"report_time": "06:00:00",
							"submitted_by": "test.supervisor@bebang.ph",
							"creation": "2026-02-27 06:05:00",
						}
					)
				]
			if doctype == "BEI Store Closing Report":
				return [
					frappe._dict(
						{
							"name": "CLOSE-0001",
							"store": "AYALA EVO - BEI",
							"report_date": "2026-02-27",
							"report_time": "23:00:00",
							"submitted_by": "test.supervisor@bebang.ph",
							"creation": "2026-02-27 23:05:00",
							"cash_variance": 0,
						}
					)
				]
			return []

		with patch("frappe.get_all", side_effect=_mock_get_all), patch(
			"frappe.db.get_value", return_value="Test Supervisor"
		), patch("hrms.api.supervisor._get_area_supervisor_stores", return_value=[frappe._dict({"name": "AYALA EVO - BEI"})]):
			result = supervisor.get_unified_approval_queue(approver="test.area@bebang.ph")

		queue_types = {item["type"] for item in result.get("items", [])}
		self.assertIn("opening_report", queue_types)
		self.assertIn("closing_report", queue_types)

	def test_unified_queue_includes_onboarding_request_type(self):
		def _mock_get_all(doctype, **kwargs):
			if doctype == "BEI Onboarding Request":
				return [
					frappe._dict(
						{
							"name": "ONB-0001",
							"employee": "EMP-0001",
							"employee_name": "Test Crew",
							"store": "AYALA EVO - BEI",
							"creation": "2026-02-27 07:00:00",
						}
					)
				]
			return []

		with patch("frappe.get_all", side_effect=_mock_get_all), patch(
			"frappe.db.get_value", return_value=None
		), patch("hrms.api.supervisor._get_area_supervisor_stores", return_value=[]):
			result = supervisor.get_unified_approval_queue(approver="test.supervisor@bebang.ph")

		onboarding_items = [item for item in result.get("items", []) if item.get("type") == "onboarding_request"]
		self.assertEqual(len(onboarding_items), 1)
		self.assertEqual(onboarding_items[0]["name"], "ONB-0001")

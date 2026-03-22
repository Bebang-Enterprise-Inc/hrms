import unittest
from unittest.mock import patch

import frappe

from hrms.api import supervisor


class TestSupervisorCoveragePunchContractS06(unittest.TestCase):
	def test_unified_queue_includes_coverage_request_payload(self):
		def _mock_get_all(doctype, **kwargs):
			if doctype == "BEI Staff Coverage Request":
				return [
					frappe._dict(
						{
							"name": "COV-0001",
							"store": "AYALA EVO - BEI",
							"coverage_date": "2026-02-27",
							"shift": "Opening",
							"requested_by": "test.supervisor@bebang.ph",
							"creation": "2026-02-27 05:50:00",
							"absent_employee": "EMP-0001",
							"reason": "Sick leave",
						}
					)
				]
			return []

		with patch("frappe.get_all", side_effect=_mock_get_all), patch(
			"frappe.db.get_value", return_value=None
		), patch("hrms.api.supervisor._get_area_supervisor_stores", return_value=[]):
			result = supervisor.get_unified_approval_queue(approver="test.supervisor@bebang.ph")

		coverage_items = [item for item in result.get("items", []) if item.get("type") == "coverage_request"]
		self.assertEqual(len(coverage_items), 1)
		self.assertEqual(coverage_items[0]["name"], "COV-0001")
		self.assertEqual(coverage_items[0]["shift"], "Opening")

	def test_unified_queue_includes_labor_plan_payload(self):
		def _mock_get_all(doctype, **kwargs):
			if doctype == "BEI Weekly Labor Plan":
				return [
					frappe._dict(
						{
							"name": "LAB-0001",
							"store": "AYALA EVO - BEI",
							"week_start_date": "2026-02-23",
							"total_hours": 320,
							"creation": "2026-02-27 08:10:00",
							"planned_by": "test.supervisor@bebang.ph",
						}
					)
				]
			return []

		with patch("frappe.get_all", side_effect=_mock_get_all), patch(
			"frappe.db.get_value", return_value=None
		), patch("hrms.api.supervisor._get_area_supervisor_stores", return_value=[]):
			result = supervisor.get_unified_approval_queue(approver="test.supervisor@bebang.ph")

		labor_items = [item for item in result.get("items", []) if item.get("type") == "labor_plan"]
		self.assertEqual(len(labor_items), 1)
		self.assertEqual(labor_items[0]["name"], "LAB-0001")
		self.assertEqual(labor_items[0]["total_hours"], 320)

import types
import unittest
from unittest.mock import patch

from hrms.api import projects
from hrms.hr.doctype.bei_maintenance_request.bei_maintenance_request import (
	BEIMaintenanceRequest,
)


class _DummyMaintenanceDoc:
	def __init__(self):
		self.name = "MR-S06-0001"
		self.store = "AYALA EVO - BEI"
		self.priority = "High"
		self.issue_category = "Electrical"
		self.impact_on_operations = "Limited Operations"
		self.description = "Main outlet sparking near prep area"
		self.assigned_to = "projects.staff@bebang.ph"
		self.vendor = ""
		self.scheduled_date = "2026-02-27"
		self.status = "Assigned"


class _ChargeDoc:
	def __init__(self):
		self.name = "MR-S06-0002"
		self.store = "AYALA EVO - BEI"
		self.charge_amount = 0
		self.charging_reason = ""
		self.charge_to_store = 0
		self.status = "Open"
		self.flags = types.SimpleNamespace(ignore_permissions=False)
		self.saved = False

	def save(self):
		self.saved = True

	def as_dict(self):
		return {
			"name": self.name,
			"store": self.store,
			"charge_amount": self.charge_amount,
			"charging_reason": self.charging_reason,
			"status": self.status,
		}


class _AckDoc:
	def __init__(self):
		self.name = "MR-S06-ACK-0001"
		self.charge_to_store = 1
		self.store_acknowledged = 0
		self.acknowledged_by = None
		self.acknowledgement_date = None
		self.status = "Pending Acknowledgement"
		self.flags = types.SimpleNamespace(ignore_permissions=False)
		self.saved = False

	def save(self):
		self.saved = True


class TestProjectsNotificationsS06(unittest.TestCase):
	def test_new_request_notification_dispatches_event(self):
		doc = _DummyMaintenanceDoc()
		with patch(
			"hrms.hr.doctype.bei_maintenance_request.bei_maintenance_request._notify_maintenance_event"
		) as notify_mock:
			BEIMaintenanceRequest.send_notification(doc)

		notify_mock.assert_called_once()
		call_args = notify_mock.call_args.kwargs
		self.assertIn("New Maintenance Request", call_args["title"])
		self.assertEqual(call_args["store"], doc.store)

	def test_status_notification_dispatches_event(self):
		doc = _DummyMaintenanceDoc()
		with patch(
			"hrms.hr.doctype.bei_maintenance_request.bei_maintenance_request._notify_maintenance_event"
		) as notify_mock:
			BEIMaintenanceRequest.send_status_notification(doc)

		notify_mock.assert_called_once()
		call_args = notify_mock.call_args.kwargs
		self.assertIn("Maintenance Status Updated", call_args["title"])
		self.assertEqual(call_args["store"], doc.store)

	def test_set_maintenance_charge_triggers_pending_ack_notification(self):
		doc = _ChargeDoc()

		with patch("frappe.get_roles", return_value=["Projects Manager"]), patch(
			"frappe.db.exists", return_value=True
		), patch("frappe.get_doc", return_value=doc), patch(
			"hrms.api.projects._notify_maintenance_charge_pending_ack"
		) as notify_mock:
			result = projects.set_maintenance_charge(
				request_id=doc.name,
				charge_amount=1250,
				charging_reason="Parts replacement",
			)

		self.assertTrue(result["success"])
		self.assertTrue(doc.saved)
		self.assertEqual(doc.status, "Pending Acknowledgement")
		self.assertEqual(doc.charge_amount, 1250)
		notify_mock.assert_called_once_with(doc)

	def test_acknowledge_charge_allows_store_staff(self):
		doc = _AckDoc()

		def _db_get_value(doctype, filters_or_name=None, fieldname=None):
			if doctype == "Employee" and isinstance(filters_or_name, dict):
				return "HR-EMP-TEST-0001"
			if doctype == "Employee" and filters_or_name == "HR-EMP-TEST-0001" and fieldname == "branch":
				return "AYALA EVO - BEI"
			if doctype == "BEI Maintenance Request" and fieldname == "store":
				return "AYALA EVO - BEI"
			return None

		with patch("frappe.get_roles", return_value=["Store Staff"]), patch(
			"frappe.db.exists", return_value=True
		), patch("frappe.db.get_value", side_effect=_db_get_value), patch(
			"frappe.get_doc", return_value=doc
		):
			result = projects.acknowledge_maintenance_charge(request_id=doc.name)

		self.assertTrue(result["success"])
		self.assertTrue(doc.saved)
		self.assertEqual(doc.status, "Verified")
		self.assertEqual(doc.store_acknowledged, 1)

	def test_get_pending_charges_allows_store_staff(self):
		rows = [
			{
				"name": "MR-S06-ACK-0002",
				"store": "AYALA EVO - BEI",
				"store_code": "AYALA EVO",
				"request_date": "2026-02-27",
				"issue_category": "Electrical",
				"description": "Pending ack sample",
				"charge_amount": 750.0,
				"charging_reason": "Wire replacement",
				"concern_type": "Wear & Tear",
				"priority": "High",
				"status": "Pending Acknowledgement",
			}
		]

		with patch("frappe.get_roles", return_value=["Store Staff"]), patch(
			"frappe.db.count", return_value=1
		), patch("frappe.get_all", return_value=rows), patch(
			"frappe.db.get_value", return_value="Ayala Evo"
		):
			result = projects.get_pending_charges(page=1, page_size=20)

		self.assertEqual(result["total"], 1)
		self.assertEqual(len(result["requests"]), 1)
		self.assertEqual(result["requests"][0]["name"], "MR-S06-ACK-0002")

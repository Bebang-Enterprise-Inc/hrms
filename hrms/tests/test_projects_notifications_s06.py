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

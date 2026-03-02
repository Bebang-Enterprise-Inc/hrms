from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hrms.api import store


class _FakeOrder:
    def __init__(
        self,
        name="BEI-ORD-TEST-0001",
        status="Pending Approval",
        is_emergency=1,
        store_name="TEST-STORE - BEI",
        creation="2026-03-03 12:30:00",
    ):
        self.name = name
        self.status = status
        self.is_emergency = is_emergency
        self.store = store_name
        self.creation = creation
        self.approved_by = None
        self.approved_at = None
        self.items = [
            SimpleNamespace(item_code="ITEM-001", qty_requested=3, qty_approved=0),
            SimpleNamespace(item_code="ITEM-002", qty_requested=5, qty_approved=0),
        ]
        self._save_count = 0

    def save(self, ignore_permissions=True):
        self._save_count += 1


class _FakeQueueDoc:
    def __init__(self, name):
        self.name = name
        self.status = "Pending"
        self.approved_by = None
        self.approved_at = None
        self._save_count = 0

    def save(self, ignore_permissions=True):
        self._save_count += 1


class TestStoreOrderApprovalFlow(FrappeTestCase):
    def test_resolve_routing_requires_regional_after_area_when_emergency_after_cutoff(self):
        with patch("hrms.api.store._get_area_supervisor_for_store", return_value="test.area@bebang.ph"), patch(
            "hrms.api.store._get_regional_manager_for_store",
            return_value=("test.regional@bebang.ph", "unit-test"),
        ):
            routing = store._resolve_order_approval_routing(
                warehouse="TEST-STORE - BEI",
                is_emergency=1,
                submitted_after_cutoff=True,
            )

        self.assertEqual(routing["first_source"], "area_supervisor")
        self.assertEqual(routing["first_approver"], "test.area@bebang.ph")
        self.assertTrue(routing["requires_regional_after_area"])
        self.assertEqual(routing["regional_approver"], "test.regional@bebang.ph")

    def test_resolve_routing_falls_back_to_regional_when_area_unmapped(self):
        with patch("hrms.api.store._get_area_supervisor_for_store", return_value=None), patch(
            "hrms.api.store._get_regional_manager_for_store",
            return_value=("edlice@bebang.ph", "default_regional_manager"),
        ):
            routing = store._resolve_order_approval_routing(
                warehouse="TEST-STORE - BEI",
                is_emergency=1,
                submitted_after_cutoff=True,
            )

        self.assertEqual(routing["first_source"], "regional_manager_fallback")
        self.assertEqual(routing["first_approver"], "edlice@bebang.ph")
        self.assertFalse(routing["requires_regional_after_area"])

    def test_approve_order_area_stage_forwards_to_regional(self):
        fake_order = _FakeOrder()
        fake_queue_doc = _FakeQueueDoc("BEI-APQ-AREA-0001")
        frappe.session.user = "test.area@bebang.ph"

        def fake_get_doc(doctype, name):
            if doctype == "BEI Store Order":
                return fake_order
            if doctype == "BEI Approval Queue":
                return fake_queue_doc
            raise AssertionError(f"Unexpected get_doc call: {doctype} / {name}")

        with patch("frappe.get_doc", side_effect=fake_get_doc), patch(
            "hrms.api.store._get_pending_approval_entries",
            return_value=[
                {
                    "name": "BEI-APQ-AREA-0001",
                    "assigned_approver": "test.area@bebang.ph",
                }
            ],
        ), patch("hrms.api.store._is_system_approver", return_value=False), patch(
            "hrms.api.store._get_area_supervisor_for_store",
            return_value="test.area@bebang.ph",
        ), patch(
            "hrms.api.store._get_regional_manager_for_store",
            return_value=("test.hr@bebang.ph", "employee.reports_to"),
        ), patch(
            "hrms.api.store._create_approval_queue_entry",
            return_value=SimpleNamespace(name="BEI-APQ-REG-0001"),
        ) as create_queue, patch("hrms.api.store._assign_order_for_approval"), patch(
            "hrms.api.store._append_order_comment"
        ), patch(
            "hrms.api.store._notify_store_ops"
        ), patch(
            "hrms.api.store._close_order_assignments"
        ), patch(
            "hrms.api.store._create_mr_for_store_order"
        ) as create_mr:
            result = store.approve_order(
                order_name=fake_order.name,
                approved_quantities=[{"item_code": "ITEM-001", "qty_approved": 2}],
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["stage"], "area_supervisor")
        self.assertTrue(result["requires_regional_manager_review"])
        self.assertEqual(fake_order.status, "Pending Approval")
        self.assertEqual(fake_queue_doc.status, "Approved")
        self.assertEqual(fake_queue_doc.approved_by, "test.area@bebang.ph")
        self.assertEqual(create_queue.call_count, 1)
        self.assertFalse(create_mr.called)

    def test_approve_order_regional_stage_finalizes(self):
        fake_order = _FakeOrder()
        fake_queue_doc = _FakeQueueDoc("BEI-APQ-REG-0001")
        frappe.session.user = "test.hr@bebang.ph"

        def fake_get_doc(doctype, name):
            if doctype == "BEI Store Order":
                return fake_order
            if doctype == "BEI Approval Queue":
                return fake_queue_doc
            raise AssertionError(f"Unexpected get_doc call: {doctype} / {name}")

        with patch("frappe.get_doc", side_effect=fake_get_doc), patch(
            "hrms.api.store._get_pending_approval_entries",
            return_value=[
                {
                    "name": "BEI-APQ-REG-0001",
                    "assigned_approver": "test.hr@bebang.ph",
                }
            ],
        ), patch("hrms.api.store._is_system_approver", return_value=False), patch(
            "hrms.api.store._get_area_supervisor_for_store",
            return_value="test.area@bebang.ph",
        ), patch(
            "hrms.api.store._get_regional_manager_for_store",
            return_value=("test.hr@bebang.ph", "employee.reports_to"),
        ), patch(
            "hrms.api.store._notify_store_ops"
        ), patch(
            "hrms.api.store._close_order_assignments"
        ), patch(
            "hrms.api.store._create_mr_for_store_order",
            return_value="MAT-REQ-0001",
        ) as create_mr, patch(
            "hrms.api.store._create_approval_queue_entry"
        ) as create_queue:
            result = store.approve_order(
                order_name=fake_order.name,
                approved_quantities=[{"item_code": "ITEM-001", "qty_approved": 3}],
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["stage"], "regional_manager")
        self.assertEqual(result["status"], "Approved")
        self.assertEqual(result["material_request"], "MAT-REQ-0001")
        self.assertEqual(fake_order.status, "Approved")
        self.assertEqual(fake_order.approved_by, "test.hr@bebang.ph")
        self.assertEqual(fake_queue_doc.status, "Approved")
        self.assertEqual(create_mr.call_count, 1)
        self.assertFalse(create_queue.called)

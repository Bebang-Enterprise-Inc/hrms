import datetime
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_frappe():
    frappe = types.ModuleType("frappe")
    utils = types.ModuleType("frappe.utils")

    class ValidationError(Exception):
        pass

    class PermissionError(Exception):
        pass

    def whitelist(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    def throw(message, exc=None):
        if isinstance(exc, type) and issubclass(exc, Exception):
            raise exc(message)
        raise Exception(message)

    def _getdate(value=None):
        if isinstance(value, datetime.date):
            return value
        if not value:
            return datetime.date(2026, 3, 2)
        return datetime.date.fromisoformat(str(value))

    frappe.whitelist = whitelist
    frappe._ = lambda text: text
    frappe.throw = throw
    frappe.ValidationError = ValidationError
    frappe.PermissionError = PermissionError
    frappe.parse_json = lambda value: json.loads(value) if isinstance(value, str) else value
    frappe.has_permission = lambda *args, **kwargs: True
    frappe.get_roles = lambda user=None: ["System Manager"]
    frappe.log_error = lambda *args, **kwargs: None
    frappe.enqueue = lambda *args, **kwargs: None
    frappe.get_doc = lambda *args, **kwargs: None
    frappe.get_all = lambda *args, **kwargs: []
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.db = types.SimpleNamespace(
        exists=lambda *args, **kwargs: None,
        get_value=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        sql=lambda *args, **kwargs: [],
    )

    utils.flt = lambda value, precision=None: round(float(value or 0), int(precision)) if precision is not None else float(value or 0)
    utils.cint = lambda value: int(float(value or 0))
    utils.getdate = _getdate
    utils.nowdate = lambda: "2026-03-02"
    utils.add_days = lambda date_obj, days: _getdate(date_obj) + datetime.timedelta(days=int(days))
    utils.get_first_day = lambda date_obj: datetime.date(_getdate(date_obj).year, _getdate(date_obj).month, 1)
    utils.get_last_day = lambda date_obj: _getdate(date_obj)

    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = utils


def _install_stub_dependencies():
    bei_config = types.ModuleType("hrms.utils.bei_config")
    bei_config.get_company = lambda: "Bebang Enterprises Inc."

    delivery_policy = types.ModuleType("hrms.utils.delivery_billing_policy")
    delivery_policy.CPO_APPROVER_EMAIL = "mae@bebang.ph"
    delivery_policy.CFO_APPROVER_EMAIL = "butch@bebang.ph"
    delivery_policy.append_approval_audit_log = lambda *args, **kwargs: None

    scm_roles = types.ModuleType("hrms.utils.scm_roles")
    scm_roles.SCM_APPROVAL_ROLES = ["SCM Manager"]
    scm_roles.check_scm_permission = lambda *args, **kwargs: True

    sys.modules["hrms.utils.bei_config"] = bei_config
    sys.modules["hrms.utils.delivery_billing_policy"] = delivery_policy
    sys.modules["hrms.utils.scm_roles"] = scm_roles


_install_fake_frappe()
_install_stub_dependencies()

procurement_spec = importlib.util.spec_from_file_location(
    "procurement_under_test",
    ROOT / "hrms" / "api" / "procurement.py",
)
procurement = importlib.util.module_from_spec(procurement_spec)
assert procurement_spec and procurement_spec.loader
procurement_spec.loader.exec_module(procurement)

warehouse_spec = importlib.util.spec_from_file_location(
    "warehouse_under_test",
    ROOT / "hrms" / "api" / "warehouse.py",
)
warehouse = importlib.util.module_from_spec(warehouse_spec)
assert warehouse_spec and warehouse_spec.loader
warehouse_spec.loader.exec_module(warehouse)


class TestS22OperationalFiltersContract(unittest.TestCase):
    def test_purchase_order_filter_contract_clauses(self):
        clauses, values = procurement.build_purchase_order_operational_filters(
            {"item_code": "test-item-005", "warehouse": "test-warehouse-west"}
        )
        self.assertEqual(values["item_code"], "test-item-005")
        self.assertEqual(values["warehouse"], "test-warehouse-west")
        self.assertTrue(any("poi.item_code" in clause for clause in clauses))
        self.assertTrue(any("poi.warehouse" in clause for clause in clauses))

    def test_purchase_orders_mark_exact_operational_matches(self):
        procurement.frappe.db.sql = MagicMock(
            side_effect=[
                [(1,)],
                [
                    {
                        "name": "PO-TEST-001",
                        "po_no": "PO-TEST-001",
                        "po_date": "2026-03-02",
                        "status": "Pending",
                        "supplier": "SUP-001",
                        "supplier_name": "test-supplier-01",
                        "grand_total": 1500,
                        "requires_dual_approval": 0,
                        "mae_approval": None,
                        "butch_approval": None,
                        "delivery_date": "2026-03-08",
                    }
                ],
            ]
        )

        payload = procurement.get_purchase_orders(
            filters={"item_code": "test-item-005", "warehouse": "test-warehouse-west"},
            page=1,
            page_size=20,
        )

        self.assertEqual(len(payload["data"]), 1)
        self.assertTrue(payload["data"][0]["has_item_match"])
        self.assertTrue(payload["data"][0]["has_warehouse_match"])

    def test_warehouse_pending_pos_apply_exact_item_and_warehouse(self):
        def _get_all(doctype, filters=None, fields=None, order_by=None, limit=None):
            if doctype == "Purchase Order":
                return [
                    {
                        "name": "PO-TEST-001",
                        "supplier": "SUP-001",
                        "supplier_name": "test-supplier-01",
                        "transaction_date": "2026-03-02",
                        "grand_total": 1000,
                        "status": "To Receive",
                        "per_received": 0,
                    },
                    {
                        "name": "PO-TEST-002",
                        "supplier": "SUP-002",
                        "supplier_name": "test-supplier-02",
                        "transaction_date": "2026-03-02",
                        "grand_total": 2000,
                        "status": "To Receive",
                        "per_received": 0,
                    },
                ]
            if doctype == "Purchase Order Item":
                return [
                    {
                        "parent": "PO-TEST-001",
                        "item_code": "test-item-005",
                        "item_name": "test-item-005",
                        "qty": 10,
                        "received_qty": 0,
                        "uom": "Nos",
                        "warehouse": "test-warehouse-west",
                    },
                    {
                        "parent": "PO-TEST-002",
                        "item_code": "test-item-999",
                        "item_name": "test-item-999",
                        "qty": 5,
                        "received_qty": 0,
                        "uom": "Nos",
                        "warehouse": "test-warehouse-north",
                    },
                ]
            return []

        warehouse.frappe.get_all = MagicMock(side_effect=_get_all)

        payload = warehouse.get_pending_purchase_orders(
            item_code="test-item-005",
            warehouse="test-warehouse-west",
        )

        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["name"], "PO-TEST-001")
        self.assertTrue(payload["data"][0]["has_item_match"])
        self.assertTrue(payload["data"][0]["has_warehouse_match"])


if __name__ == "__main__":
    unittest.main()

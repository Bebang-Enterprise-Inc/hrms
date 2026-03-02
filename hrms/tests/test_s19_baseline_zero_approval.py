import importlib.util
import pathlib
import sys
import types


def _install_frappe_stubs():
    frappe = types.ModuleType("frappe")
    frappe.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(RuntimeError(msg))

    model_mod = types.ModuleType("frappe.model")
    document_mod = types.ModuleType("frappe.model.document")

    class Document:  # pragma: no cover - minimal stub for DocType import
        pass

    document_mod.Document = Document

    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-03-02"
    utils.add_days = lambda _d, _n: "2026-03-03"

    sys.modules["frappe"] = frappe
    sys.modules["frappe.model"] = model_mod
    sys.modules["frappe.model.document"] = document_mod
    sys.modules["frappe.utils"] = utils


def _load_doctype_module():
    _install_frappe_stubs()
    file_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "hr"
        / "doctype"
        / "bei_store_order"
        / "bei_store_order.py"
    )
    spec = importlib.util.spec_from_file_location("s19_store_order_doctype_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _line(qty_requested, recommended_qty=0, suggested_qty=0):
    return types.SimpleNamespace(
        item_code="ITEM-001",
        qty_requested=qty_requested,
        recommended_qty=recommended_qty,
        suggested_qty=suggested_qty,
        deviation_pct=0.0,
        is_edited=0,
    )


def test_baseline_zero_edit_forces_pending_approval():
    module = _load_doctype_module()
    doc = module.BEIStoreOrder()
    doc.status = "Draft"
    doc.is_bulk_order = 0
    doc.items = [_line(qty_requested=3, recommended_qty=0, suggested_qty=0)]

    doc.compute_deviations()
    doc.set_approval_status()

    assert doc.items[0].is_edited == 1
    assert doc.status == "Pending Approval"


def test_unedited_line_remains_auto_approved():
    module = _load_doctype_module()
    doc = module.BEIStoreOrder()
    doc.status = "Draft"
    doc.is_bulk_order = 0
    doc.items = [_line(qty_requested=2, recommended_qty=2, suggested_qty=2)]

    doc.compute_deviations()
    doc.set_approval_status()

    assert doc.items[0].is_edited == 0
    assert doc.status == "Approved"

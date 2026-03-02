from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _declared_functions(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    names: set[str] = set()
    for line in source.splitlines():
        line = line.strip()
        if line.startswith("def "):
            name = line.split("def ", 1)[1].split("(", 1)[0].strip()
            names.add(name)
    return names


def test_s18_commissary_modules_expose_contract_methods():
    dashboard_path = ROOT / "hrms" / "api" / "commissary_dashboard.py"
    requisition_path = ROOT / "hrms" / "api" / "commissary_requisition.py"
    quality_path = ROOT / "hrms" / "api" / "commissary_quality.py"

    dashboard_methods = _declared_functions(dashboard_path)
    requisition_methods = _declared_functions(requisition_path)
    quality_methods = _declared_functions(quality_path)

    assert {"get_commissary_dashboard", "get_production_items", "get_production_history", "submit_production_output"}.issubset(
        dashboard_methods
    )

    # Sprint 18 portal remap requires these methods to exist under commissary_requisition.
    assert {
        "get_rm_reorder_alerts",
        "get_rm_for_requisition",
        "get_my_requisitions",
        "create_rm_requisition",
        "approve_requisition",
        "create_work_order",
        "start_work_order",
        "complete_work_order",
        "get_production_suggestions",
        "submit_production_output",
        "create_dispatch_transfer",
        "create_hub_transfer",
        "fulfill_store_order",
        "update_hub_inventory",
        "check_production_feasibility",
    }.issubset(requisition_methods)

    assert {
        "get_pending_inspections",
        "get_inspection_history",
        "get_inspection_details",
        "get_wastage_history",
        "get_wastage_reasons",
        "get_wastage_trends",
        "get_fefo_picking_list",
        "get_expiring_batches",
        "create_quality_inspection",
        "log_wastage",
    }.issubset(quality_methods)

def test_s18_commissary_wrapper_targets_are_declared():
    requisition_source = (ROOT / "hrms" / "api" / "commissary_requisition.py").read_text(
        encoding="utf-8"
    )
    assert "from hrms.api.commissary_dashboard import submit_production_output" in requisition_source
    assert "from hrms.api.commissary import create_dispatch_transfer" in requisition_source
    assert "from hrms.api.commissary import create_hub_transfer" in requisition_source
    assert "from hrms.api.commissary import fulfill_store_order" in requisition_source
    assert "from hrms.api.commissary import update_hub_inventory" in requisition_source
    assert "from hrms.api.commissary_bom import check_production_feasibility" in requisition_source

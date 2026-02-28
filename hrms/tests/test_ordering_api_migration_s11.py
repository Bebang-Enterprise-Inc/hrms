from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_ordering_contract_symbols_exist() -> None:
    src = _read("hrms/api/ordering.py")
    assert "def get_orderable_items" in src
    assert "def submit_order" in src
    assert "def get_order_review_queue" in src


def test_warehouse_contract_symbols_exist() -> None:
    src = _read("hrms/api/warehouse.py")
    assert "def get_pending_material_requests" in src
    assert "def approve_material_request" in src
    assert "def create_stock_transfer" in src


def test_inventory_reconciliation_symbol_exists() -> None:
    src = _read("hrms/api/inventory.py")
    assert "def export_count_to_cos_recon" in src

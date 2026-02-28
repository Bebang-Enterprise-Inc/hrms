from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_dispatch_trip_contract_symbols_exist() -> None:
    src = _read("hrms/api/dispatch.py")
    assert "def get_trips" in src
    assert "def get_trip_detail" in src
    assert "def get_available_drivers" in src


def test_store_returns_and_fqi_symbols_exist() -> None:
    src = _read("hrms/api/store.py")
    assert "def create_store_return" in src
    assert "def get_returns_pending" in src
    assert "def create_fqi_report" in src


def test_inventory_return_contract_symbols_exist() -> None:
    src = _read("hrms/api/inventory.py")
    assert "def get_returnable_items" in src
    assert "def submit_return_request" in src

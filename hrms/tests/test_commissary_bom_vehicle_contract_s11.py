from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_commissary_bom_symbols_exist() -> None:
    src = _read("hrms/api/commissary_bom.py")
    assert "def create_bom" in src
    assert "def update_bom" in src
    assert "def check_production_feasibility" in src


def test_dispatch_vehicle_symbols_exist() -> None:
    src = _read("hrms/api/dispatch.py")
    assert "def get_vehicles" in src
    assert "def assign_driver" in src


def test_commissary_route_symbols_exist() -> None:
    src = _read("hrms/api/commissary.py")
    assert "def get_delivery_routes" in src
    assert "def get_distribution_hubs" in src
    assert "def create_hub_transfer" in src

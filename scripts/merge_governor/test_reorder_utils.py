"""Store reorder point utilities."""

def check_reorder_point(item_code: str, current_qty: float, reorder_level: float) -> bool:
    """Check if item is below reorder point."""
    return current_qty <= reorder_level

def create_restock_request(item_code: str, qty: float, warehouse: str) -> dict:
    """Create a material request for restocking."""
    return {
        "doctype": "Material Request",
        "material_request_type": "Purchase",
        "items": [{"item_code": item_code, "qty": qty, "warehouse": warehouse}],
    }

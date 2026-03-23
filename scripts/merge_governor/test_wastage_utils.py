"""Wastage tracking utilities."""

def log_wastage(item_code: str, qty: float, reason: str) -> dict:
    return {"status": "logged", "item": item_code, "qty": qty}

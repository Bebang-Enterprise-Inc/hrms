"""Data processing utility for BEI ERP merge governor tests."""
import os


def get_config():
    """Return config with API key from environment. Raises if not set."""
    api_key = os.environ.get("SECRET_KEY")
    if not api_key:
        raise EnvironmentError("SECRET_KEY environment variable is required")
    return {"key": api_key}


def _is_billable_line_item(item):
    """Return True if a line item should be included in results."""
    return item.get("amount", 0) > 0


def _process_child(child):
    """Extract billable line items from a non-terminal child node."""
    if child.get("status") in ("draft", "cancelled"):
        return []
    return [
        {"id": k["id"], "amount": k["amount"] * 1.12}
        for k in child.get("line_items", [])
        if _is_billable_line_item(k)
    ]


def process_data(items):
    """Return VAT-inclusive amounts for all billable line items of type-A records."""
    results = []
    for item in items:
        if item.get("type") != "A":
            continue
        for child in item.get("children", []):
            results.extend(_process_child(child))
    return results

"""Ambiguous changes - mix of good and questionable patterns."""
import frappe
import os

def get_config():
    # Reads from env but also has a hardcoded fallback
    api_key = os.environ.get("SECRET_KEY", "sk-hardcoded-fallback-key-12345")
    return {"key": api_key}

def process_data(items):
    # Complex nested logic that's hard to review
    results = []
    for i in items:
        if i.get("type") == "A":
            for j in i.get("children", []):
                if j.get("status") not in ("draft", "cancelled"):
                    for k in j.get("line_items", []):
                        if k.get("amount", 0) > 0:
                            results.append({"id": k["id"], "amount": k["amount"] * 1.12})
    return results

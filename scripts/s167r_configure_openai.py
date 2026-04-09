#!/usr/bin/env python3
"""Configure openai_api_key in site_config.json from environment (DEFECT-029 mitigation)."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

# Key is passed as sys.argv[1]
import sys
key = sys.argv[1].strip() if len(sys.argv) > 1 else os.environ.get("OPENAI_API_KEY", "").strip()
if not key:
    print("ERROR: OPENAI_API_KEY not provided")
    raise SystemExit(1)
masked = key[:10] + "***" + key[-4:]
print(f"Installing openai_api_key: {masked}")

config_path = "/home/frappe/frappe-bench/sites/hq.bebang.ph/site_config.json"
with open(config_path) as f:
    cfg = json.load(f)

before = cfg.get("openai_api_key", "<not set>")
cfg["openai_api_key"] = key
with open(config_path, "w") as f:
    json.dump(cfg, f, indent=1)
print(f"site_config.json updated (was {before[:10] if before != '<not set>' else before}***)")

# Verify classifier now sees it
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.expense_classifier import _get_runtime_health, classify_expense
h = _get_runtime_health()
print(f"\nClassifier health after config:")
for k, v in h.items(): print(f"  {k}: {v}")

print("\nTest classify with OpenAI path:")
for desc, vendor, amt in [
    ("Office printer paper", "National Book Store", 480),
    ("Snacks for team", "Jollibee", 350),
]:
    r = classify_expense(description=desc, vendor=vendor, amount=amt)
    print(f"  {vendor}: coa={r.get('coa')}, label={r.get('coa_label')}, method={r.get('method')}")

frappe.destroy()

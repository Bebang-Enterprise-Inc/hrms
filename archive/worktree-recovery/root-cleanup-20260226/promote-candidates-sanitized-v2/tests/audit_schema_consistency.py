import json
import os
import glob
import re

def load_doctype_fields(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return {f['fieldname'] for f in data.get('fields', [])}

def scan_frontend_usage(frontend_path, fields):
    usage_count = {field: 0 for field in fields}
    
    # We will just do a simple substring search for robustness in this quick audit.
    # Regex is better but error-prone in quick scripts without testing the regex itself.
    
    for root, _, files in os.walk(frontend_path):
        for file in files:
            if file.endswith('.vue') or file.endswith('.js'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for field in fields:
                        if field in content:
                            usage_count[field] += 1
                except Exception as e:
                    print(f"Skipping {path}: {e}")

    return usage_count

def audit_doctype(name, json_path, frontend_path):
    print(f"\n--- Auditing Schema: {name} ---")
    if not os.path.exists(json_path):
        print(f"Error: JSON not found at {json_path}")
        return

    fields = load_doctype_fields(json_path)
    print(f"Backend Fields ({len(fields)}) loaded.")
    
    usage = scan_frontend_usage(frontend_path, fields)
    
    unused = [f for f, count in usage.items() if count == 0]
    
    if unused:
        print(f"\n[WARNING] Potentially Unused Backend Fields (Orphaned?):")
        for f in sorted(unused):
            print(f"  - {f}")
    else:
        print("\n[OK] All backend fields appear to be referenced in Frontend.")

if __name__ == '__main__':
    frontend_dir = os.path.abspath("frontend/src")
    
    # 1. BEI Store Order
    audit_doctype(
        "BEI Store Order", 
        "hrms/hr/doctype/bei_store_order/bei_store_order.json",
        frontend_dir
    )
    
    # 2. BEI Store Closing Report
    audit_doctype(
        "BEI Store Closing Report", 
        "hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.json",
        frontend_dir
    )
    
    # 3. BEI Expense Request (PCF)
    audit_doctype(
        "BEI Expense Request", 
        "hrms/hr/doctype/bei_expense_request/bei_expense_request.json",
        frontend_dir
    )

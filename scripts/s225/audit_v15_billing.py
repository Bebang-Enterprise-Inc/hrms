"""Audit v15 49-store sweep billing chain.

For each of the 49 SIs in the sweep ledger, verify:
  1. SI.customer == fixture.customer (per-store Customer = canonical per-store name)
  2. SI.customer's tax_id == fixture.tin (matches BIR registration)
  3. SI.company == 'Bebang Kitchen Inc.' (BKI is the seller per ICT-005)
  4. GL Entry party = SI.customer (DM-1 — receivable booked against the buyer)
  5. Customer record exists and has a customer_name (entity legal name)
  6. tabCustomer.tax_id matches the fixture.tin
  7. fixture.parent_company maps to the actual registered BD entity

Output: JSON report. Any mismatches flagged in 'mismatches' array.
"""
import os, json, sys
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Fixture passed in via /tmp file (we'll write it from outside)
with open("/tmp/v15_fixture.json", "r") as f:
    fixture_list = json.load(f)
fixture_by_store = {e["store"]: e for e in fixture_list}

# SI list passed in via /tmp file
with open("/tmp/v15_sis.json", "r") as f:
    sis = json.load(f)

BKI_COMPANY = "Bebang Kitchen Inc."
def _norm(s): return (s or "").strip().upper()

result = {
    "audited_sis": 0,
    "passes": 0,
    "mismatches": [],
    "warnings": [],
    "store_results": {},
}

for si_name, store in sis:
    result["audited_sis"] += 1
    fixture = fixture_by_store.get(store)
    if not fixture:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "fixture_missing",
            "message": f"Store {store} not in fixture",
        })
        continue

    if not frappe.db.exists("Sales Invoice", si_name):
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "si_missing",
            "message": f"SI {si_name} not found in DB",
        })
        continue

    si = frappe.db.get_value("Sales Invoice", si_name,
        ["name", "customer", "customer_name", "company", "tax_id", "docstatus", "status",
         "grand_total", "net_total", "outstanding_amount"], as_dict=True)

    expected_customer = fixture["customer"]
    expected_tin = fixture["tin"]
    expected_parent = fixture.get("parent_company")
    allow_empty_tin = fixture.get("allowEmptyTin", False)

    store_audit = {
        "si": si_name,
        "fixture": {
            "expected_customer": expected_customer,
            "expected_tin": expected_tin,
            "expected_parent_corporation": expected_parent,
            "store_ownership_type": fixture.get("store_ownership_type"),
        },
        "actual": dict(si),
        "checks": {},
    }

    # 1. SI.customer matches fixture per-store Customer
    customer_ok = si.customer == expected_customer
    store_audit["checks"]["customer_matches_fixture"] = customer_ok
    if not customer_ok:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "wrong_customer",
            "expected": expected_customer, "actual": si.customer,
        })

    # 2. SI tax_id matches fixture TIN
    actual_tin = (si.tax_id or "").strip()
    if not actual_tin and allow_empty_tin:
        tin_ok = True
        tin_note = "allowEmptyTin=true (e.g., ORTIGAS GREENHILLS)"
    else:
        tin_ok = actual_tin == expected_tin
        tin_note = None
    store_audit["checks"]["tin_matches_fixture"] = tin_ok
    if tin_note: store_audit["checks"]["tin_note"] = tin_note
    if not tin_ok:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "wrong_tin",
            "expected": expected_tin, "actual": actual_tin,
        })

    # 3. SI.company is BKI (case-insensitive — Frappe stores as BEBANG KITCHEN INC.)
    company_is_bki = _norm(si.company) == _norm(BKI_COMPANY)
    store_audit["checks"]["company_is_bki"] = company_is_bki
    if not company_is_bki:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "wrong_seller_company",
            "expected": BKI_COMPANY, "actual": si.company,
        })

    # 4. GL Entry: party=Customer should be the per-store Customer
    gl_party_rows = frappe.db.sql("""
        SELECT party_type, party, debit, credit, account
        FROM `tabGL Entry`
        WHERE voucher_type = 'Sales Invoice'
          AND voucher_no = %(si)s
          AND party_type = 'Customer'
    """, {"si": si_name}, as_dict=True)
    gl_party_set = {r["party"] for r in gl_party_rows}
    party_ok = expected_customer in gl_party_set
    store_audit["checks"]["gl_party_matches_customer"] = party_ok
    store_audit["checks"]["gl_party_set"] = list(gl_party_set)
    if not party_ok:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "wrong_gl_party",
            "expected_in_set": expected_customer, "gl_party_set": list(gl_party_set),
        })

    # 5. Customer record exists + has customer_name
    cust_record = frappe.db.get_value("Customer", expected_customer,
        ["name", "customer_name", "tax_id", "customer_group", "represents_company", "disabled"],
        as_dict=True)
    if not cust_record:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "customer_record_missing",
            "expected": expected_customer,
        })
        store_audit["checks"]["customer_record_exists"] = False
        result["store_results"][store] = store_audit
        continue
    store_audit["checks"]["customer_record_exists"] = True
    store_audit["actual"]["customer_record"] = dict(cust_record)

    # 6. Customer record tax_id matches fixture TIN
    cust_tin = (cust_record.tax_id or "").strip()
    if not cust_tin and allow_empty_tin:
        cust_tin_ok = True
    else:
        cust_tin_ok = cust_tin == expected_tin
    store_audit["checks"]["customer_record_tax_id_matches"] = cust_tin_ok
    if not cust_tin_ok:
        result["mismatches"].append({
            "si": si_name, "store": store, "type": "customer_record_tin_mismatch",
            "expected": expected_tin, "actual_in_customer_record": cust_tin,
        })

    # 7. parent_company verification — does the per-store Customer's parent_company match fixture?
    # Per-store Company has parent_company field; verify alignment.
    actual_parent = frappe.db.get_value("Company", expected_customer, "parent_company")
    parent_ok = (actual_parent == expected_parent) if expected_parent else (actual_parent is None or actual_parent == "")
    store_audit["checks"]["company_parent_matches_fixture"] = parent_ok
    store_audit["actual"]["company_parent_company"] = actual_parent
    if not parent_ok and expected_parent:
        result["warnings"].append({
            "si": si_name, "store": store, "type": "parent_company_mismatch",
            "expected": expected_parent, "actual": actual_parent,
        })

    # All-pass for this store
    if (customer_ok and tin_ok and company_is_bki and party_ok
            and store_audit["checks"]["customer_record_exists"] and cust_tin_ok and parent_ok):
        result["passes"] += 1
        store_audit["verdict"] = "PASS"
    else:
        store_audit["verdict"] = "MISMATCH"

    result["store_results"][store] = store_audit

# Summary
result["pass_rate"] = f"{result['passes']}/{result['audited_sis']}"
result["mismatch_count"] = len(result["mismatches"])
result["warning_count"] = len(result["warnings"])

print(json.dumps(result, indent=2, default=str))

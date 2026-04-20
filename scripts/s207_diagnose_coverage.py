"""S207 diagnostic — check what S206 records actually exist per Company."""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json
# Sample a Company we expect to be complete
sample = "SM TANZA - BEBANG MEGA INC."
if not frappe.db.exists("Company", sample):
    # Fallback: any entity_category='Store' Company that's not BEBANG ENTERPRISE direct child
    sample = frappe.db.sql("SELECT name FROM `tabCompany` WHERE entity_category='Store' AND parent_company != 'BEBANG ENTERPRISE INC.' LIMIT 1")
    sample = sample[0][0] if sample else None

report = {"sampled_company": sample}
if sample:
    abbr = frappe.db.get_value("Company", sample, "abbr")
    report["abbr"] = abbr
    # Check for Due From / Due To accounts under several name/number conventions
    report["accounts_on_company"] = frappe.db.sql(
        "SELECT name, account_name, account_number, is_group, root_type FROM `tabAccount` "
        "WHERE company = %s AND (account_number IN ('1104200','2104200') OR account_name LIKE '%%DUE FROM%%' OR account_name LIKE '%%DUE TO%%') "
        "ORDER BY account_number, account_name",
        (sample,), as_dict=True,
    )
    report["internal_customers_represents_self"] = frappe.db.sql(
        "SELECT name, customer_name, is_internal_customer, represents_company FROM `tabCustomer` "
        "WHERE represents_company = %s",
        (sample,), as_dict=True,
    )
    report["internal_suppliers_represents_self"] = frappe.db.sql(
        "SELECT name, supplier_name, is_internal_supplier, represents_company FROM `tabSupplier` "
        "WHERE represents_company = %s",
        (sample,), as_dict=True,
    )

# Global S206 account counts (regardless of company)
report["global_due_from_count"] = int(frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE account_number='1104200' AND is_group=0")[0][0])
report["global_due_to_count"] = int(frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE account_number='2104200' AND is_group=0")[0][0])
report["global_internal_customer_count"] = int(frappe.db.sql("SELECT COUNT(*) FROM `tabCustomer` WHERE is_internal_customer=1")[0][0])
report["global_internal_supplier_count"] = int(frappe.db.sql("SELECT COUNT(*) FROM `tabSupplier` WHERE is_internal_supplier=1")[0][0])

# All companies with at least ONE S206 receivable — to understand coverage distribution
report["companies_with_any_due_from"] = [r[0] for r in frappe.db.sql(
    "SELECT DISTINCT company FROM `tabAccount` WHERE account_number='1104200' AND is_group=0 ORDER BY company"
)]

print("===RESULT_JSON_BEGIN===")
print(json.dumps(report, indent=2, default=str))
print("===RESULT_JSON_END===")
"""

if __name__ == "__main__":
    rc, out, err = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print("STDERR:", err[:1000])
        sys.exit(rc)
    result = extract_result_json(out)
    if result:
        import json
        print(json.dumps(result, indent=2))
    else:
        print(out[:3000])

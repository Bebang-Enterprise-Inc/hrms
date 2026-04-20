"""Check what went wrong with s207_labor_allocation_log_bimonthly patch."""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json

# 1. Is the patch marked as done in the Patch Log?
patch_rows = frappe.db.sql(
    "SELECT name, patch, creation FROM `tabPatch Log` WHERE patch LIKE '%%s207%%' ORDER BY creation DESC LIMIT 5",
    as_dict=True,
)

# 2. Error Log entries mentioning our patch or migration SQL
errs = frappe.db.sql(
    "SELECT name, creation, LEFT(error, 4000) AS error, method "
    "FROM `tabError Log` "
    "WHERE (method LIKE '%%S207%%' OR error LIKE '%%s207_labor_allocation_log_bimonthly%%' OR error LIKE '%%idx_slip_employee%%' OR error LIKE '%%DROP COLUMN%%year%%' OR error LIKE '%%DROP COLUMN%%month%%' OR method LIKE '%%labor_allocation_log%%') "
    "AND creation >= DATE_SUB(NOW(), INTERVAL 4 HOUR) "
    "ORDER BY creation DESC LIMIT 10",
    as_dict=True,
)

# 3. Current schema state
cols = [r[0] for r in frappe.db.sql(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'tabBEI Labor Allocation Log' "
    "ORDER BY ordinal_position"
)]
idx = frappe.db.sql("SHOW INDEX FROM `tabBEI Labor Allocation Log`", as_dict=True)

# 4. Row count — if any rows have NULL slip_name the unique index would fail? (MariaDB allows multi-NULL, but let's check)
null_slip = int(frappe.db.sql("SELECT COUNT(*) FROM `tabBEI Labor Allocation Log` WHERE slip_name IS NULL")[0][0])
total = int(frappe.db.sql("SELECT COUNT(*) FROM `tabBEI Labor Allocation Log`")[0][0])
null_year = int(frappe.db.sql("SELECT COUNT(*) FROM `tabBEI Labor Allocation Log` WHERE year IS NULL")[0][0]) if "year" in cols else None

# 5. Try manual DROP COLUMN + CREATE INDEX now to surface the actual error
repair_log = []
try:
    frappe.db.sql("ALTER TABLE `tabBEI Labor Allocation Log` DROP COLUMN `year`")
    repair_log.append("dropped year OK")
except Exception as e:
    repair_log.append(f"DROP COLUMN year failed: {e}")

try:
    frappe.db.sql("ALTER TABLE `tabBEI Labor Allocation Log` DROP COLUMN `month`")
    repair_log.append("dropped month OK")
except Exception as e:
    repair_log.append(f"DROP COLUMN month failed: {e}")

try:
    frappe.db.sql("CREATE UNIQUE INDEX `idx_slip_employee` ON `tabBEI Labor Allocation Log` (`slip_name`, `employee`)")
    repair_log.append("created idx_slip_employee OK")
except Exception as e:
    repair_log.append(f"CREATE INDEX failed: {e}")

frappe.db.commit()  # persist repair

# 6. Post-repair schema
cols_after = [r[0] for r in frappe.db.sql(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'tabBEI Labor Allocation Log' "
    "ORDER BY ordinal_position"
)]
idx_after_unique = sorted({r["Key_name"] for r in frappe.db.sql("SHOW INDEX FROM `tabBEI Labor Allocation Log` WHERE Non_unique = 0", as_dict=True)})

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "patch_log_rows": [{"name": r["name"], "patch": r["patch"], "creation": str(r["creation"])} for r in patch_rows],
    "recent_errors": [{"name": r["name"], "creation": str(r["creation"]), "method": r["method"], "error_head": (r["error"] or "")[:800]} for r in errs],
    "columns_before_repair": cols,
    "null_slip_rows": null_slip,
    "null_year_rows": null_year,
    "total_rows": total,
    "unique_indexes_before_repair": sorted({r["Key_name"] for r in idx if not r["Non_unique"]}),
    "repair_log": repair_log,
    "columns_after_repair": cols_after,
    "unique_indexes_after_repair": idx_after_unique,
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main():
    import json
    rc, out, err = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print(f"[ERR] SSM rc={rc}\n{err[:1500]}")
        return rc
    res = extract_result_json(out)
    if not res:
        print("Unparseable:\n", out[:2000])
        return 1
    outp = REPO / "output" / "l3" / "s207" / "migration_repair.json"
    outp.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())

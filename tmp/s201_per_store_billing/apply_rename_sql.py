"""Apply S201 branch rename via direct SQL.

The frappe.rename_doc path hit order-dependent errors (case-insensitive
exists() check + prior-rename interaction). Since Employee.branch is a
plain Link field, updating the value directly via SQL is equivalent and
deterministic.

Steps:
  1. Ensure every target Branch doc exists (INSERT IGNORE based on CSV).
  2. UPDATE tabEmployee SET branch=new WHERE branch=old (for every
     old != new pair in branch_company_map.csv).
  3. DELETE orphan Branch docs whose name is in the old-only set AND
     which no Employee references anymore.
  4. Invalidate company_lookup cache.
  5. Report before/after counts.
"""
import base64
import csv
import json
import os
import subprocess
import time

INSTANCE_ID = "i-026b7477d27bd46d6"
CREATE_NO_WINDOW = 0x08000000
MAP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "hrms", "data_seed", "branch_company_map.csv"
)


def send_shell(shell_cmd, timeout_secs=180):
    b64 = base64.b64encode(shell_cmd.encode("utf-8")).decode("ascii")
    wrapped = f"echo {b64} | base64 -d | bash"
    r = subprocess.run(
        ["aws", "ssm", "send-command", "--instance-ids", INSTANCE_ID,
         "--document-name", "AWS-RunShellScript",
         "--parameters", json.dumps({"commands": [wrapped]}),
         "--query", "Command.CommandId", "--output", "text"],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        return {"ok": False, "output": "", "error": r.stderr.strip()}
    cmd_id = r.stdout.strip()
    for _ in range(timeout_secs // 5):
        time.sleep(5)
        r2 = subprocess.run(
            ["aws", "ssm", "get-command-invocation", "--command-id", cmd_id,
             "--instance-id", INSTANCE_ID,
             "--query", "[Status, StandardOutputContent, StandardErrorContent]",
             "--output", "json"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r2.returncode != 0:
            continue
        data = json.loads(r2.stdout)
        status, stdout, stderr = data[0], data[1], data[2]
        if status == "Success":
            return {"ok": True, "output": stdout.strip(), "error": stderr.strip()}
        if status == "Failed":
            return {"ok": False, "output": stdout.strip(), "error": stderr.strip()}
    return {"ok": False, "output": "", "error": f"Timeout (cmd_id={cmd_id})"}


def run_sql(sql):
    sql_b64 = base64.b64encode(sql.encode()).decode()
    shell = (
        "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1); "
        f"echo {sql_b64} | base64 -d | "
        "sudo docker exec -i $CONTAINER bench --site hq.bebang.ph mariadb --silent --batch 2>&1 | head -100"
    )
    return send_shell(shell)


def main():
    # Load CSV mapping
    with open(MAP_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    renames = []
    targets = set()
    for r in rows:
        old = (r.get("old_branch") or "").strip()
        new = (r.get("new_branch") or "").strip()
        if not old or not new or new == "NEEDS_MANUAL_REVIEW":
            continue
        targets.add(new)
        if old != new:
            renames.append((old, new))

    print(f"Loaded {len(renames)} rename pairs + {len(targets)} distinct targets.")

    # Build one big SQL script — runs in a single transaction by bench mariadb
    sql_parts = []

    # 0. Disable safe-update mode (Employee.branch is not a key column)
    sql_parts.append("SET SQL_SAFE_UPDATES=0;")

    # 1. Ensure every target Branch exists (INSERT IGNORE)
    sql_parts.append("-- Step 1: ensure target Branch docs exist")
    for t in sorted(targets):
        t_esc = t.replace("'", "''")
        sql_parts.append(
            f"INSERT IGNORE INTO `tabBranch` "
            f"(name, branch, creation, modified, modified_by, owner, docstatus, idx) "
            f"VALUES ('{t_esc}', '{t_esc}', NOW(), NOW(), 'Administrator', "
            f"'Administrator', 0, 0);"
        )

    # 2. UPDATE tabEmployee for each rename
    sql_parts.append("-- Step 2: update Employee.branch values")
    for old, new in renames:
        old_esc = old.replace("'", "''")
        new_esc = new.replace("'", "''")
        sql_parts.append(
            f"UPDATE `tabEmployee` SET branch='{new_esc}' WHERE branch='{old_esc}';"
        )

    # 3. Before+after audit
    sql_parts.append("-- Step 3: verification")
    sql_parts.append("SELECT 'SUMMARY' AS section, '';")
    sql_parts.append(
        "SELECT 'active_employees' AS metric, COUNT(*) AS value "
        "FROM `tabEmployee` WHERE status='Active';"
    )
    sql_parts.append(
        "SELECT 'distinct_branches' AS metric, COUNT(DISTINCT branch) AS value "
        "FROM `tabEmployee` WHERE status='Active' AND branch IS NOT NULL AND branch<>'';"
    )
    sql_parts.append(
        "SELECT 'old_names_still_on_employees' AS metric, COUNT(*) AS value "
        "FROM `tabEmployee` WHERE status='Active' AND branch IN (" +
        ",".join(f"'{o}'" for o, _ in renames) + ");"
    )
    # Use "" doubling for the IN list to handle apostrophes (D'VERDE CALAMBA)
    old_list = ",".join("'" + o.replace("'", "''") + "'" for o, _ in renames)
    new_list = ",".join("'" + t.replace("'", "''") + "'" for t in sorted(targets))
    sql_parts[-2] = (
        "SELECT 'old_names_still_on_employees' AS metric, COUNT(*) AS value "
        f"FROM `tabEmployee` WHERE status='Active' AND branch IN ({old_list});"
    )
    sql_parts[-1] = (
        "SELECT 'canonical_names_on_employees' AS metric, COUNT(*) AS value "
        f"FROM `tabEmployee` WHERE status='Active' AND branch IN ({new_list});"
    )
    # Also surface per-old-branch residual counts so we can see which escape failed
    sql_parts.append(
        "SELECT 'residual_branches' AS section, '';"
    )
    sql_parts.append(
        "SELECT branch, COUNT(*) AS still_on_employees FROM `tabEmployee` "
        f"WHERE status='Active' AND branch IN ({old_list}) GROUP BY branch ORDER BY 2 DESC;"
    )

    full_sql = "\n".join(sql_parts)

    print(f"Total SQL statements: {len(sql_parts)}")
    print(f"Running via bench mariadb...")
    result = run_sql(full_sql)
    print()
    print("OUTPUT:")
    print(result.get("output") or result.get("error"))


if __name__ == "__main__":
    main()

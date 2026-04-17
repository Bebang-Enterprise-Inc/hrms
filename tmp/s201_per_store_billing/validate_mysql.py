"""Direct MariaDB queries against Frappe DB to validate Option X."""
import base64
import json
import subprocess
import time

INSTANCE_ID = "i-026b7477d27bd46d6"
CREATE_NO_WINDOW = 0x08000000


def send_shell(shell_cmd, timeout_secs=90):
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


def run_bench_sql(sql):
    """Run SQL via bench mariadb on hq.bebang.ph site (reads site_config for creds)."""
    sql_b64 = base64.b64encode(sql.encode()).decode()
    shell = (
        "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1); "
        f"echo {sql_b64} | base64 -d | "
        "sudo docker exec -i $CONTAINER bench --site hq.bebang.ph mariadb --silent --batch 2>&1 | head -60"
    )
    return send_shell(shell)


if __name__ == "__main__":
    queries = [
        ("Active employee count by company (top 20)",
         "SELECT company, COUNT(*) AS n FROM tabEmployee WHERE status='Active' GROUP BY company ORDER BY n DESC LIMIT 20;"),
        ("Distinct branch values (top 20)",
         "SELECT COALESCE(branch,''), COUNT(*) AS n FROM tabEmployee WHERE status='Active' GROUP BY branch ORDER BY n DESC LIMIT 20;"),
        ("Branch doctype rows vs Employee.branch cardinality",
         "SELECT (SELECT COUNT(*) FROM tabBranch) AS branch_docs, (SELECT COUNT(DISTINCT branch) FROM tabEmployee WHERE branch IS NOT NULL AND branch<>'') AS distinct_emp_branches;"),
        ("Sample branches — canonical names present?",
         "SELECT name FROM tabBranch WHERE name IN ('AYALA UP TOWN CENTER','XENTROMALL MONTALBAN','BRITTANY HOTEL','ORTIGAS ESTANCIA','BF HOMES PARANAQUE','NAIA T3','UPTOWN BGC') ORDER BY name;"),
        ("Sample branches — old names GONE?",
         "SELECT name FROM tabBranch WHERE name IN ('AYALA UPTC','XENTRO MONTALBAN','BGC','MARKET MARKET','ESTANCIA','GREENHILLS','MYTOWN','BRITTANY OFFICE','THE TERMINAL') ORDER BY name;"),
        ("Company count by entity_category",
         "SELECT entity_category, COUNT(*) AS n FROM tabCompany GROUP BY entity_category ORDER BY n DESC;"),
    ]

    for title, sql in queries:
        print("=" * 70)
        print(title)
        print("-" * 70)
        r = run_bench_sql(sql)
        if r["ok"]:
            print(r["output"] or "(no rows)")
        else:
            print(f"ERROR: {r['error'] or r['output']}")
        print()

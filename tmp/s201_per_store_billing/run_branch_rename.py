"""Execute the S201 branch rename patch on production via SSM.

Step 1: Dry-run (default) to show what would change.
Step 2: After reviewing the dry-run, apply with S201_APPLY=1.
Step 3: Post-apply validation.
"""
import base64
import json
import subprocess
import time
import sys

INSTANCE_ID = "i-026b7477d27bd46d6"
CREATE_NO_WINDOW = 0x08000000


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


def run_with_env(env_var_line, cmd):
    shell = (
        "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1); "
        "echo CONTAINER=$CONTAINER; "
        f"sudo docker exec {env_var_line} $CONTAINER {cmd} 2>&1 | tail -60"
    )
    return send_shell(shell)


def run_mysql(sql):
    sql_b64 = base64.b64encode(sql.encode()).decode()
    shell = (
        "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1); "
        f"echo {sql_b64} | base64 -d | "
        "sudo docker exec -i $CONTAINER bench --site hq.bebang.ph mariadb --silent --batch 2>&1 | head -80"
    )
    return send_shell(shell)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry-run"

    if mode == "dry-run":
        print("=" * 70)
        print("Step 1: DRY-RUN s201_rename_branches")
        print("=" * 70)
        r = run_with_env("", "bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute")
        print(r.get("output") or r.get("error"))

        print("\n" + "=" * 70)
        print("Latest dry-run report (private/files):")
        print("=" * 70)
        shell = (
            "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1); "
            "LATEST=$(sudo docker exec $CONTAINER ls -1t /home/frappe/frappe-bench/sites/hq.bebang.ph/private/files/branch_rename_report_*.json 2>/dev/null | head -1); "
            "echo 'LATEST:' $LATEST; "
            "sudo docker exec $CONTAINER cat $LATEST 2>&1 | python3 -c \"import json,sys; d=json.load(sys.stdin); print('dry_run:', d.get('dry_run')); print('counts:', d.get('counts')); print('planned (first 15):'); [print(' -', p['old'], '->', p['new'], f'(emp={p[\\\"employees_on_old\\\"]}, merge={p[\\\"will_merge\\\"]})')  for p in d.get('planned', [])[:15]]; print('total planned:', len(d.get('planned', [])))\""
        )
        rep = send_shell(shell)
        print(rep.get("output") or rep.get("error"))

    elif mode == "apply":
        print("=" * 70)
        print("Step 2: APPLY s201_rename_branches (S201_APPLY=1)")
        print("=" * 70)
        r = run_with_env("-e S201_APPLY=1",
                         "bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute")
        print(r.get("output") or r.get("error"))

    elif mode == "validate":
        print("=" * 70)
        print("Step 3: POST-APPLY VALIDATION")
        print("=" * 70)
        queries = [
            ("Branches that should be GONE (old names):",
             "SELECT name FROM tabBranch WHERE name IN ('AYALA UPTC','XENTRO MONTALBAN','BGC','MARKET MARKET','ESTANCIA','GREENHILLS','MYTOWN','BRITTANY OFFICE','THE TERMINAL','ROBINSON GENTRI','STA LUCIA GRAND MALL','BF HOMES','AYALA EVO','STA LUCIA EAST GRAND MALL','NAIA TERMINAL 3','D VERDE CALAMBA','FESTIVAL MALL','COMMISSARY SHAW','SM STA ROSA','SHAW COMMISSARY - Production','SHAW COMMISSARY - Logistics') ORDER BY name;"),
            ("Branches that should be PRESENT (canonical):",
             "SELECT name FROM tabBranch WHERE name IN ('AYALA UP TOWN CENTER','XENTROMALL MONTALBAN','BRITTANY HOTEL','AYALA MARKET MARKET','ORTIGAS ESTANCIA','ORTIGAS GREENHILLS','MY TOWN','NAIA T3','ROBINSONS GENERAL TRIAS','BF HOMES PARANAQUE','AYALA EVO CITY','FESTIVAL MALL ALABANG',\"D'VERDE CALAMBA\",'SHAW COMMISSARY','SHAW COMMISSARY - PRODUCTION','SHAW COMMISSARY - LOGISTICS','SM STA. ROSA') ORDER BY name;"),
            ("Distinct branches on active employees (top 20):",
             "SELECT branch, COUNT(*) AS n FROM tabEmployee WHERE status='Active' GROUP BY branch ORDER BY n DESC LIMIT 20;"),
            ("Total distinct branches used by active employees:",
             "SELECT COUNT(DISTINCT branch) AS n FROM tabEmployee WHERE status='Active' AND branch IS NOT NULL AND branch<>'';"),
            ("Branch docs vs employee branch cardinality:",
             "SELECT (SELECT COUNT(*) FROM tabBranch) AS branch_docs, (SELECT COUNT(DISTINCT branch) FROM tabEmployee WHERE status='Active' AND branch IS NOT NULL AND branch<>'') AS distinct_emp_branches;"),
        ]
        for title, sql in queries:
            print("-" * 70)
            print(title)
            r = run_mysql(sql)
            print(r.get("output") or r.get("error") or "(empty)")
            print()

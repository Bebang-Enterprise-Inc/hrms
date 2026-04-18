"""Validate Option X post-deploy: branch rename, Employee.company, cache hook."""
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


def run_frappe(python_code):
    """Execute a Python snippet inside the frappe-backend container via bench console."""
    shell = (
        "CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep -i frappe | grep -i backend | head -1); "
        "if [ -z \"$CONTAINER\" ]; then "
        "  CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep bench | head -1); "
        "fi; "
        "echo 'CONTAINER:' $CONTAINER; "
        f"echo '{base64.b64encode(python_code.encode()).decode()}' | base64 -d | "
        "sudo docker exec -i $CONTAINER bench --site hq.bebang.ph console"
    )
    return send_shell(shell)


if __name__ == "__main__":
    print("=" * 70)
    print("S201 Option X post-deploy validation")
    print("=" * 70)

    # Probe containers first
    print("\n--- ADMS DB container ---")
    r = send_shell("sudo docker ps --format '{{.Names}}' | head -20")
    print(r.get("output") or r.get("error"))

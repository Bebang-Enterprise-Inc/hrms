#!/usr/bin/env python3
"""S231 — shared SSM helper for production probes and mutations.

All S231 scripts that talk to production Frappe go through this helper
so the SSM contract (region, instance, container, base64 transport,
output marker pattern) lives in one place.

Pattern lifted from `scripts/s212_probe_frappe_errors.py` per plan
external-dependencies checklist line 911.
"""

from __future__ import annotations

import base64
import gzip
import json
import sys
import time
from typing import Any

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
BACKEND_CONTAINER_FILTER = "frappe_backend"
SITE = "hq.bebang.ph"
SITES_PATH = "/home/frappe/frappe-bench/sites"

OUT_MARKER_START = "__S231_OUT_B64_START__"
OUT_MARKER_END = "__S231_OUT_B64_END__"


def run_in_container(python_script: str, timeout: int = 180) -> str:
	"""Execute a Python payload inside the Frappe backend container via SSM.

	Returns raw stdout. Caller decodes the base64 / gzip payload between
	`OUT_MARKER_START` and `OUT_MARKER_END` markers.
	"""
	import boto3

	ssm = boto3.client("ssm", region_name=AWS_REGION)
	enc = base64.b64encode(python_script.encode()).decode()
	cmds = [
		f"BACKEND=$(docker ps --filter name={BACKEND_CONTAINER_FILTER} --format '{{{{.ID}}}}' | head -1)",
		f"echo '{enc}' | base64 -d > /tmp/s231_payload.py",
		"docker cp /tmp/s231_payload.py $BACKEND:/tmp/s231_payload.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s231_payload.py",
	]
	r = ssm.send_command(
		InstanceIds=[INSTANCE_ID],
		DocumentName="AWS-RunShellScript",
		Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
	)
	cid = r["Command"]["CommandId"]
	print(f"CommandId: {cid}", file=sys.stderr)
	deadline = time.time() + timeout + 30
	while time.time() < deadline:
		time.sleep(3)
		inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
		status = inv["Status"]
		if status in ("Success", "Failed", "TimedOut", "Cancelled"):
			out = inv.get("StandardOutputContent", "")
			err = inv.get("StandardErrorContent", "")
			if status != "Success":
				sys.stderr.write(err or "")
				raise RuntimeError(f"SSM failed ({status}): {err[:500]}")
			return out
	raise TimeoutError(f"SSM CommandId {cid} timed out after {timeout}s")


def decode_output(stdout: str) -> Any:
	"""Decode the base64-gzip payload between S231 markers."""
	s = stdout.find(OUT_MARKER_START)
	e = stdout.find(OUT_MARKER_END)
	if s < 0 or e < 0:
		raise ValueError(
			f"Missing S231 output markers in stdout. First 500 chars:\n{stdout[:500]}"
		)
	b64 = stdout[s + len(OUT_MARKER_START):e].strip()
	return json.loads(gzip.decompress(base64.b64decode(b64)).decode())


# Standard preamble injected at the top of every payload — initialises Frappe
# and sets the user. Caller appends the actual logic + an emit call.
PAYLOAD_PREAMBLE = f"""\
import json, base64, gzip
import frappe

frappe.init(site="{SITE}", sites_path="{SITES_PATH}")
frappe.connect()
frappe.set_user("Administrator")

def _s231_emit(payload):
    compressed = gzip.compress(json.dumps(payload, default=str).encode())
    print("{OUT_MARKER_START}")
    print(base64.b64encode(compressed).decode())
    print("{OUT_MARKER_END}")

"""

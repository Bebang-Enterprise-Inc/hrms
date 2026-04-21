"""S214 shared Meta API helpers.

Usage: from s214_meta_lib import get_token, meta_get, meta_post, meta_post_json
Windows-safe: uses creationflags=CREATE_NO_WINDOW for subprocess calls.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

CREATE_NO_WINDOW = 0x08000000
AD_ACCOUNT = "act_843498792928069"
PAGE_ID = "102628625216977"
API_VERSION = "v25.0"
BASE = f"https://graph.facebook.com/{API_VERSION}"

OUTPUT_DIR = Path(r"F:\Dropbox\Projects\BEI-ERP-s214-meta-ads-rules-fix-refresh-archive\output\s214")
TMP_DIR = Path(r"F:\Dropbox\Projects\BEI-ERP-s214-meta-ads-rules-fix-refresh-archive\tmp\s214")
REPO_ROOT = Path(r"F:\Dropbox\Projects\BEI-ERP-s214-meta-ads-rules-fix-refresh-archive")


def force_utf8():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")


def get_token(secret_name: str = "META_ACCESS_TOKEN") -> str:
    result = subprocess.run(
        ["doppler", "secrets", "get", secret_name, "--project", "bei-erp", "--config", "dev", "--plain"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        cwd=r"F:\Dropbox\Projects\BEI-ERP",
    )
    token = result.stdout.strip()
    if not token or len(token) < 100:
        raise RuntimeError(f"Doppler {secret_name} not retrievable (got {len(token)} chars)")
    return token


def meta_get(path: str, token: str, params: Optional[dict] = None) -> dict:
    p = dict(params or {})
    p["access_token"] = token
    url = f"{BASE}{path}?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    data = json.loads(body)
    return data


def meta_post(path: str, token: str, params: dict, log_as_mutation: bool = True) -> dict:
    """POST with application/x-www-form-urlencoded body (Meta default)."""
    url = f"{BASE}{path}"
    data = dict(params)
    data["access_token"] = token
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_body = resp.read()
    except urllib.error.HTTPError as e:
        resp_body = e.read()
    try:
        result = json.loads(resp_body)
    except json.JSONDecodeError:
        result = {"raw": resp_body.decode("utf-8", errors="replace")}

    if log_as_mutation:
        log_mutation({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "method": "POST",
            "path": path,
            "params_sent": {k: v for k, v in params.items() if k != "access_token"},
            "response": result,
        })
    return result


def log_mutation(entry: dict):
    """Append entry to output/s214/api_mutations.json (array)."""
    mut_file = OUTPUT_DIR / "api_mutations.json"
    mut_file.parent.mkdir(parents=True, exist_ok=True)
    if mut_file.exists():
        with open(mut_file, encoding="utf-8") as f:
            arr = json.load(f)
    else:
        arr = []
    arr.append(entry)
    with open(mut_file, "w", encoding="utf-8") as f:
        json.dump(arr, f, indent=2)


def log_form_submission(entry: dict):
    """Append entry to output/s214/form_submissions.json (array)."""
    f_file = OUTPUT_DIR / "form_submissions.json"
    f_file.parent.mkdir(parents=True, exist_ok=True)
    if f_file.exists():
        with open(f_file, encoding="utf-8") as f:
            arr = json.load(f)
    else:
        arr = []
    arr.append(entry)
    with open(f_file, "w", encoding="utf-8") as f:
        json.dump(arr, f, indent=2)


def save_pre_state(phase: str, data: Any):
    out = OUTPUT_DIR / "pre_state" / f"{phase}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return out


def save_post_state(phase: str, data: Any):
    out = OUTPUT_DIR / "post_state" / f"{phase}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return out

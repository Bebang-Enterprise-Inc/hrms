"""S258 shared library for scripts/coa_fix/*.py.

Provides:
- Doppler-driven Frappe API client (headers, get/post helpers)
- get_companies_by_status() — read output/s258/baseline_state.json
- frappe_create_account() — REST API POST wrapper with idempotency check
- frappe_set_company_field() — REST API PUT wrapper
- write_rollback_sql() — append to tmp/s258/rollback_phaseN.sql
- log_action() — append to tmp/s258/account_rename_log_phaseN.csv
"""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


def doppler(key: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
    ).strip()


BASE = "https://hq.bebang.ph"
API_KEY = doppler("FRAPPE_API_KEY")
API_SECRET = doppler("FRAPPE_API_SECRET")
HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Accept": "application/json",
    "X-Frappe-CSRF-Token": "token",
}


def api_get(path: str, params: dict | None = None) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params or {}, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def api_post(path: str, payload: dict) -> dict:
    for attempt in range(3):
        try:
            r = requests.post(f"{BASE}{path}", headers=HEADERS, json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def api_put(path: str, payload: dict) -> dict:
    for attempt in range(3):
        try:
            r = requests.put(f"{BASE}{path}", headers=HEADERS, json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def submit_doc(doctype: str, name: str) -> dict:
    """Submit a draft document via frappe.client.submit.

    Frappe expects the FULL doc dict (form-encoded), not just (doctype, name).
    We fetch first, then submit.
    """
    full = api_get(f"/api/resource/{doctype}/{name}")
    doc = full.get("data") or {}
    headers_no_json = {"Authorization": HEADERS["Authorization"], "Accept": "application/json"}
    r = requests.post(
        f"{BASE}/api/method/frappe.client.submit",
        headers=headers_no_json,
        data={"doc": json.dumps(doc)},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def get_companies_by_status(status: str) -> list[dict]:
    """Read baseline_state.json and return Companies matching status."""
    state = json.load(open("output/s258/baseline_state.json"))
    return [r for r in state["rows"] if r["status"] == status]


def get_company_by_name(name: str) -> dict:
    state = json.load(open("output/s258/baseline_state.json"))
    return next(r for r in state["rows"] if r["name"] == name)


def account_exists(account_name: str) -> bool:
    res = api_get(
        "/api/method/frappe.client.get_count",
        params={"doctype": "Account",
                "filters": json.dumps([["name", "=", account_name]])},
    )
    return (res.get("message") or 0) > 0


def create_account(name: str, account_name: str, parent_account: str,
                   company: str, is_group: int, account_type: str | None,
                   root_type: str, account_currency: str = "PHP",
                   account_number: str | None = None) -> dict:
    """Create a tabAccount row via Frappe REST API."""
    if account_exists(name):
        return {"already_exists": True, "name": name}
    payload = {
        "doctype": "Account",
        "account_name": account_name,
        "parent_account": parent_account,
        "company": company,
        "is_group": is_group,
        "account_type": account_type or "",
        "root_type": root_type,
        "account_currency": account_currency,
    }
    if account_number:
        payload["account_number"] = account_number
    res = api_post("/api/resource/Account", payload)
    return res.get("data") or res


def set_company_field(company: str, field: str, value: Any) -> dict:
    """PUT tabCompany.{field} = value."""
    res = api_put(f"/api/resource/Company/{company}",
                  {field: value})
    return res.get("data") or res


def write_rollback_sql(phase: int, sql_lines: list[str]):
    os.makedirs("tmp/s258", exist_ok=True)
    path = f"tmp/s258/rollback_phase{phase}.sql"
    mode = "a" if os.path.exists(path) else "w"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write(f"-- S258 Phase {phase} rollback SQL — generated " +
                    time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
            f.write("-- Apply only if Phase " + str(phase) + " fails mid-execution.\n\n")
        for line in sql_lines:
            f.write(line.rstrip() + "\n")


def log_action(phase: str, action: str, target: str, before: str, after: str,
               extras: dict | None = None):
    os.makedirs("tmp/s258", exist_ok=True)
    path = f"tmp/s258/account_rename_log_phase{phase}.csv"
    is_new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "action", "target",
                                          "before", "after", "extras"])
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "target": target,
            "before": before,
            "after": after,
            "extras": json.dumps(extras or {}),
        })


def sql_quote(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"

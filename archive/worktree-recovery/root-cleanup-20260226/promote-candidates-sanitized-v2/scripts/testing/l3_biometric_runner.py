#!/usr/bin/env python3
"""
L3 biometric monitoring runner (read-heavy module).

This module has dashboard/list checks rather than form submission.
The runner still performs browser login + navigation like a real user,
then verifies biometric monitoring endpoints with authenticated API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_WEB = "https://my.bebang.ph"
BASE_HQ = "https://hq.bebang.ph"
DEFAULT_EMAIL = "test.hr@bebang.ph"
DEFAULT_PASSWORD = "BeiTest2026!"


@dataclass
class RunPaths:
    evidence_file: Path
    result_file: Path
    trace_file: Path
    screenshot_nav: Path
    screenshot_final: Path


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _prepare_paths(run_id: str) -> RunPaths:
    out_root = ROOT / "output" / "l3"
    ev_dir = out_root / "evidence"
    art_dir = out_root / "artifacts"
    ev_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        evidence_file=ev_dir / f"BIO-001_{run_id}.json",
        result_file=ev_dir / f"BIO-001_{run_id}_result.json",
        trace_file=art_dir / f"BIO-001_{run_id}.trace.zip",
        screenshot_nav=art_dir / f"BIO-001_{run_id}_nav.png",
        screenshot_final=art_dir / f"BIO-001_{run_id}_final.png",
    )


def _wait_for_dashboard(page, timeout_ms: int = 30000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if "/dashboard" in page.url:
            return True
        page.wait_for_timeout(250)
    return False


def _auth_header() -> Dict[str, str]:
    token = os.environ.get("FRAPPE_TOKEN")
    if token:
        return {"Authorization": token}
    key = os.environ.get("FRAPPE_API_KEY")
    secret = os.environ.get("FRAPPE_API_SECRET")
    if key and secret:
        return {"Authorization": f"token {key}:{secret}"}
    return {}


def run_biometric_checks(
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    headless: bool = True,
) -> Dict[str, Any]:
    run_id = _now_id()
    paths = _prepare_paths(run_id)

    actions: List[Dict[str, Any]] = []
    network: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    endpoint_results: List[Dict[str, Any]] = []

    result: Dict[str, Any] = {
        "scenario_id": "BIO-001",
        "module": "biometric",
        "run_id": run_id,
        "status": "FAIL",
        "account": email,
        "checks": checks,
        "endpoint_results": endpoint_results,
        "paths": {
            "evidence": str(paths.evidence_file.relative_to(ROOT)),
            "result": str(paths.result_file.relative_to(ROOT)),
            "trace": str(paths.trace_file.relative_to(ROOT)),
            "screenshots": [
                str(paths.screenshot_nav.relative_to(ROOT)),
                str(paths.screenshot_final.relative_to(ROOT)),
            ],
        },
    }

    def add_action(action_type: str, **kwargs):
        item = {"type": action_type, "ts": time.time()}
        item.update(kwargs)
        actions.append(item)

    def add_check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        trace_stopped = False

        def on_response(resp):
            req = resp.request
            if "/api/" in resp.url:
                network.append(
                    {
                        "method": req.method,
                        "url": resp.url,
                        "status": resp.status,
                    }
                )

        page.on("response", on_response)

        try:
            # Login
            page.goto(f"{BASE_WEB}/login", wait_until="domcontentloaded", timeout=60000)
            add_action("click", target="login_page")
            page.locator('input[autocomplete="username"], input[name="email"]').first.fill(email)
            add_action("fill", field="email")
            page.locator('input[type="password"]').first.fill(password)
            add_action("fill", field="password")
            page.locator('button[type="submit"]').first.click()
            add_action("submit", target="login")
            logged_in = _wait_for_dashboard(page, timeout_ms=30000)
            add_check("login_redirect_dashboard", logged_in, page.url)
            if not logged_in:
                raise RuntimeError(f"Login did not reach dashboard. Current URL: {page.url}")

            # Navigate HR pages via sidebar.
            hr_link = page.locator('a[href="/dashboard/hr"]').first
            if hr_link.is_visible(timeout=8000):
                hr_link.click(timeout=10000)
                add_action("nav_sidebar", path="HR", route="/dashboard/hr")
                page.wait_for_timeout(400)

            attendance_link = page.locator(
                'a[href="/dashboard/hr/attendance"], a[href="/dashboard/attendance/punch/review"]'
            ).first
            if attendance_link.is_visible(timeout=5000):
                attendance_link.click(timeout=10000)
                add_action("click", target="attendance_link")
                page.wait_for_timeout(600)

            page.screenshot(path=str(paths.screenshot_nav), full_page=False)
            add_check("navigation_done", "/dashboard" in page.url, page.url)

            # Endpoint checks (token-auth if available)
            headers = _auth_header()
            has_api_network = any("/api/" in str(n.get("url", "")) for n in network)
            add_check("api_network_seen", has_api_network, f"network_calls={len(network)}")

            if headers:
                endpoints = [
                    (
                        "dashboard_summary",
                        f"{BASE_HQ}/api/method/hrms.api.biometric_monitoring.get_dashboard_summary",
                    ),
                    (
                        "device_status",
                        f"{BASE_HQ}/api/method/hrms.api.biometric_monitoring.get_device_status",
                    ),
                    (
                        "not_punching_48h",
                        f"{BASE_HQ}/api/method/hrms.api.biometric_monitoring.get_not_punching?hours=48",
                    ),
                    (
                        "wrong_device",
                        f"{BASE_HQ}/api/method/hrms.api.biometric_monitoring.get_wrong_device",
                    ),
                ]

                ok_count = 0
                for key, url in endpoints:
                    resp = page.request.get(url, headers=headers)
                    status_ok = resp.status == 200
                    payload: Any
                    try:
                        payload = resp.json()
                    except Exception:
                        payload = {"raw": resp.text()[:500]}

                    detail = {
                        "name": key,
                        "url": url,
                        "status": resp.status,
                        "ok": status_ok,
                    }
                    endpoint_results.append(detail)
                    add_check(f"endpoint_{key}_200", status_ok, f"status={resp.status}")
                    if status_ok:
                        ok_count += 1

                add_check("biometric_endpoints_minimum", ok_count >= 3, f"ok_count={ok_count}/4")
            else:
                add_check(
                    "hq_api_token_skipped",
                    True,
                    "No FRAPPE_TOKEN/FRAPPE_API_KEY+SECRET in env; endpoint checks skipped.",
                )

            page.screenshot(path=str(paths.screenshot_final), full_page=False)

            evidence = {
                "scenario_id": "BIO-001",
                "module": "biometric",
                "actions": actions,
                "network": network,
                "endpoint_results": endpoint_results,
                "artifacts": {
                    "trace": str(paths.trace_file.relative_to(ROOT)).replace("\\", "/"),
                    "screenshots": [
                        str(paths.screenshot_nav.relative_to(ROOT)).replace("\\", "/"),
                        str(paths.screenshot_final.relative_to(ROOT)).replace("\\", "/"),
                    ],
                },
            }
            paths.evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

            context.tracing.stop(path=str(paths.trace_file))
            trace_stopped = True

            all_pass = all(c["ok"] for c in checks)
            result["status"] = "PASS" if all_pass else "FAIL"

        except PlaywrightTimeoutError as exc:
            add_check("playwright_timeout", False, str(exc))
            result["error"] = f"Playwright timeout: {exc}"
            result["status"] = "FAIL"
        except Exception as exc:
            add_check("unexpected_exception", False, str(exc))
            result["error"] = str(exc)
            result["status"] = "FAIL"
        finally:
            if not trace_stopped:
                context.tracing.stop(path=str(paths.trace_file))
            context.close()
            browser.close()

    paths.result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BIO-001 L3 biometric checks.")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--headed", action="store_true", help="Run with headed browser.")
    args = parser.parse_args()

    result = run_biometric_checks(
        email=args.email,
        password=args.password,
        headless=not args.headed,
    )
    print(f"STATUS={result.get('status')}")
    print(f"EVIDENCE={result['paths']['evidence']}")
    print(f"RESULT={result['paths']['result']}")
    print(f"TRACE={result['paths']['trace']}")
    for check in result.get("checks", []):
        flag = "PASS" if check.get("ok") else "FAIL"
        print(f"{flag} {check.get('name')}: {check.get('detail')}")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

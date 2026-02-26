#!/usr/bin/env python3
"""
Browser-driven L3 runner for my.bebang.ph Communication Support flow (COMM-003).

Goal:
- Execute like a real user (click/type/select/submit in UI)
- Verify backend state changed
- Emit guard-compatible evidence JSON + trace + screenshots
- Run browser-realism validation using scripts/testing/l3_browser_guard.py logic
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_WEB = "https://my.bebang.ph"
DEFAULT_EMAIL = "test.crew1@bebang.ph"
DEFAULT_PASSWORD = "BeiTest2026!"


@dataclass
class RunPaths:
    evidence_file: Path
    result_file: Path
    trace_file: Path
    screenshot_before: Path
    screenshot_after: Path


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _prepare_paths(run_id: str) -> RunPaths:
    out_root = ROOT / "output" / "l3"
    ev_dir = out_root / "evidence"
    art_dir = out_root / "artifacts"
    ev_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        evidence_file=ev_dir / f"COMM-003_{run_id}.json",
        result_file=ev_dir / f"COMM-003_{run_id}_result.json",
        trace_file=art_dir / f"COMM-003_{run_id}.trace.zip",
        screenshot_before=art_dir / f"COMM-003_{run_id}_before_submit.png",
        screenshot_after=art_dir / f"COMM-003_{run_id}_after_submit.png",
    )


def _load_guard_validate_fn():
    guard_path = ROOT / "scripts" / "testing" / "l3_browser_guard.py"
    spec = importlib.util.spec_from_file_location("l3_browser_guard", guard_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load guard module: {guard_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module.validate_evidence


def _wait_for_dashboard(page, timeout_ms: int = 30000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if "/dashboard" in page.url:
            return True
        page.wait_for_timeout(250)
    return False


def run_comm_003(
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    headless: bool = True,
) -> Dict[str, Any]:
    run_id = _now_id()
    paths = _prepare_paths(run_id)

    actions: List[Dict[str, Any]] = []
    network: List[Dict[str, Any]] = []
    failed_network: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    subject = f"L3 COMM-003 {int(time.time())}"

    result: Dict[str, Any] = {
        "scenario_id": "COMM-003",
        "module": "communication",
        "run_id": run_id,
        "status": "FAIL",
        "account": email,
        "subject": subject,
        "checks": checks,
        "guard_validation": {"ok": False, "errors": []},
        "paths": {
            "evidence": str(paths.evidence_file.relative_to(ROOT)),
            "result": str(paths.result_file.relative_to(ROOT)),
            "trace": str(paths.trace_file.relative_to(ROOT)),
            "screenshots": [
                str(paths.screenshot_before.relative_to(ROOT)),
                str(paths.screenshot_after.relative_to(ROOT)),
            ],
        },
    }

    def add_action(action_type: str, **kwargs):
        item = {"type": action_type, "ts": time.time()}
        item.update(kwargs)
        actions.append(item)

    def add_check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})

    def request_failure_text(req: Any) -> str:
        try:
            failure = req.failure  # property on newer Playwright builds
            if callable(failure):
                failure = failure()
        except Exception:
            try:
                failure = req.failure()  # fallback for callable style
            except Exception:
                failure = None

        if isinstance(failure, dict):
            return str(failure.get("errorText") or failure)
        if failure is None:
            return "requestfailed (no error text)"
        return str(failure)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        trace_stopped = False

        def on_response(resp):
            req = resp.request
            if req.method in {"POST", "PUT", "PATCH", "DELETE"} and "/api/" in resp.url:
                network.append(
                    {
                        "ts": time.time(),
                        "method": req.method,
                        "url": resp.url,
                        "status": resp.status,
                    }
                )

        def on_request_failed(req):
            if req.method in {"POST", "PUT", "PATCH", "DELETE"} and "/api/" in req.url:
                row = {
                    "ts": time.time(),
                    "method": req.method,
                    "url": req.url,
                    "status": -1,
                    "failure": request_failure_text(req),
                }
                network.append(row)
                failed_network.append(row)

        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)

        try:
            # Step 1: UI login
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

            # Step 2: Sidebar navigation
            page.locator('a[href="/dashboard/communication"]').first.click(timeout=10000)
            page.wait_for_timeout(300)
            page.locator('a[href="/dashboard/communication/support"]').first.click(timeout=10000)
            page.wait_for_url("**/dashboard/communication/support**", timeout=30000)
            add_action(
                "nav_sidebar",
                path="Communication > Support",
                route="/dashboard/communication/support",
            )
            add_check("sidebar_navigation", True, page.url)

            # Step 3: Fill support form
            page.locator('button:has-text("New Ticket")').first.click(timeout=10000)
            add_action("click", target="New Ticket")

            dialog = page.locator('[role="dialog"]').first
            dialog.wait_for(timeout=10000)

            # Category
            dialog.locator('button[role="combobox"]').nth(0).click(timeout=10000)
            add_action("click", target="Category combobox")
            page.locator('[role="option"]:has-text("IT/Technical")').first.click(timeout=10000)
            add_action("click", target="Category option IT/Technical")

            # Subject
            dialog.locator("input#subject").fill(subject)
            add_action("fill", field="subject")

            # Priority
            dialog.locator('button[role="combobox"]').nth(1).click(timeout=10000)
            add_action("click", target="Priority combobox")
            page.locator('[role="option"]:has-text("Low")').first.click(timeout=10000)
            add_action("click", target="Priority option Low")

            # Description
            description = "Browser-driven L3 submit+verify for COMM-003 support ticket."
            dialog.locator("textarea#description").fill(description)
            add_action("fill", field="description")

            page.screenshot(path=str(paths.screenshot_before), full_page=False)

            # Step 4: Submit and verify response
            submit_resp = None
            submit_attempts = 0
            submit_transport_notes: List[str] = []
            for attempt in range(1, 3):
                submit_attempts = attempt
                submit_start = time.time()
                try:
                    with page.expect_response(
                        lambda r: r.request.method == "POST" and "/api/communication/support" in r.url,
                        timeout=15000,
                    ) as resp_info:
                        dialog.locator('button:has-text("Submit")').first.click(timeout=10000)
                        add_action("submit", target="Support Ticket Form", attempt=attempt)
                    submit_resp = resp_info.value
                    break
                except PlaywrightTimeoutError as exc:
                    failed_req = next(
                        (
                            row
                            for row in failed_network
                            if row["ts"] >= submit_start and "/api/communication/support" in str(row["url"])
                        ),
                        None,
                    )
                    if failed_req:
                        note = f"attempt={attempt} requestfailed: {failed_req.get('failure')}"
                    else:
                        note = f"attempt={attempt} timeout waiting for /api/communication/support response: {exc}"
                    submit_transport_notes.append(note)
                    if attempt < 2:
                        page.wait_for_timeout(1500)
                        continue
                    raise RuntimeError(note) from exc

            if submit_resp is None:
                raise RuntimeError("Support submit did not produce a response after retries.")

            add_check(
                "submit_transport_response_captured",
                True,
                f"attempts={submit_attempts}; retries={'; '.join(submit_transport_notes) if submit_transport_notes else 'none'}",
            )

            submit_ok = submit_resp.status == 200
            submit_json: Dict[str, Any]
            try:
                submit_json = submit_resp.json()
            except Exception:
                submit_json = {"raw": submit_resp.text()[:800]}

            api_success = bool(submit_json.get("success") is True)
            ticket_name = str(submit_json.get("name") or "")
            ticket_created = ticket_name.startswith("BEI-TKT-")

            add_check(
                "submit_response_status_200",
                submit_ok,
                f"status={submit_resp.status}",
            )
            add_check(
                "submit_response_success_true",
                api_success,
                f"json={json.dumps(submit_json)[:240]}",
            )
            add_check(
                "submit_response_ticket_name",
                ticket_created,
                f"name={ticket_name}",
            )

            page.wait_for_timeout(1200)
            page.screenshot(path=str(paths.screenshot_after), full_page=False)

            # Step 5: Post-submit backend verify via app read API
            list_resp = page.request.get(f"{BASE_WEB}/api/communication/support")
            list_ok = list_resp.status == 200
            try:
                list_json = list_resp.json()
            except Exception:
                list_json = {"raw": list_resp.text()[:800]}

            tickets = (
                list_json.get("data", {}).get("tickets", [])
                if isinstance(list_json, dict)
                else []
            )
            found_subject = any(
                isinstance(t, dict) and str(t.get("subject", "")) == subject for t in tickets
            )

            add_check("verify_list_status_200", list_ok, f"status={list_resp.status}")
            add_check("verify_subject_found_in_list", found_subject, f"subject={subject}")

            # Step 6: Emit evidence + run guard validation
            evidence = {
                "scenario_id": "COMM-003",
                "module": "communication",
                "actions": actions,
                "network": network,
                "artifacts": {
                    "trace": str(paths.trace_file.relative_to(ROOT)).replace("\\", "/"),
                    "screenshots": [
                        str(paths.screenshot_before.relative_to(ROOT)).replace("\\", "/"),
                        str(paths.screenshot_after.relative_to(ROOT)).replace("\\", "/"),
                    ],
                },
            }
            paths.evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

            # Ensure trace file exists before guard validation.
            context.tracing.stop(path=str(paths.trace_file))
            trace_stopped = True

            validate_evidence = _load_guard_validate_fn()
            guard_ok, guard_errors = validate_evidence(
                evidence_path=paths.evidence_file,
                expected_endpoint="/api/communication/support",
                requires_upload=False,
            )
            result["guard_validation"] = {"ok": guard_ok, "errors": guard_errors}
            add_check("guard_validate_evidence", guard_ok, "; ".join(guard_errors) or "ok")

            all_pass = all(c["ok"] for c in checks)
            result["status"] = "PASS" if all_pass else "FAIL"
            result["submit_response"] = submit_json
            result["verify_tickets_count"] = len(tickets) if isinstance(tickets, list) else 0

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
    parser = argparse.ArgumentParser(description="Run COMM-003 L3 browser test.")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--headed", action="store_true", help="Run with headed browser.")
    args = parser.parse_args()

    result = run_comm_003(
        email=args.email,
        password=args.password,
        headless=not args.headed,
    )

    print(f"STATUS={result['status']}")
    print(f"EVIDENCE={result['paths']['evidence']}")
    print(f"RESULT={result['paths']['result']}")
    print(f"TRACE={result['paths']['trace']}")
    print(f"GUARD_OK={result['guard_validation']['ok']}")
    for check in result["checks"]:
        print(
            f"{'PASS' if check['ok'] else 'FAIL'} {check['name']}: {check['detail']}"
        )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

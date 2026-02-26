#!/usr/bin/env python3
"""
L2 page render runner.

Reads docs/testing/ROUTE_REGISTRY.md and validates page accessibility/rendering
using browser login + navigation for each declared test role.
Writes standardized run artifact JSON under output/l2/runs/.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import ConsoleMessage
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ROUTE_REGISTRY = ROOT / "docs" / "testing" / "ROUTE_REGISTRY.md"
BASE_WEB = "https://my.bebang.ph"
DEFAULT_PASSWORD = "BeiTest2026!"


SECTION_TO_MODULE = {
    "Home & Profile": "home-profile",
    "Store Operations": "store-ops",
    "Inventory": "inventory",
    "Receiving": "receiving",
    "HR Self-Service": "hr",
    "Expenses": "expense",
    "Communication": "communication",
    "Supervisor Tools": "supervisor",
    "Maintenance & Projects": "maintenance",
    "Warehouse": "warehouse",
    "Commissary": "commissary",
    "Procurement (HQ User only)": "procurement",
    "Stock Counting (External Auditor, Store Staff, Warehouse)": "stock-counting",
    "Finance & Accounting (HQ User only)": "finance",
    "Tasks & Projects": "tasks-projects",
    "Analytics": "analytics",
    "Employee Clearance": "employee-clearance",
    "Recruitment": "recruitment",
    "Onboarding": "onboarding",
}

ROLE_TO_EMAIL = {
    "test.crew1": "test.crew1@bebang.ph",
    "test.staff": "test.staff@bebang.ph",
    "test.supervisor": "test.supervisor@bebang.ph",
    "test.area": "test.area@bebang.ph",
    "test.hr": "test.hr@bebang.ph",
    "test.projects": "test.projects@bebang.ph",
    "test.projects.staff": "test.projects.staff@bebang.ph",
    "test.warehouse": "test.warehouse@bebang.ph",
    "test.commissary": "test.commissary@bebang.ph",
    "hq_user_fallback": "test.hr@bebang.ph",
}


@dataclass
class RouteEntry:
    module: str
    section: str
    feature: str
    route: str
    test_role: str
    endpoint: str


def _norm_role(raw: str) -> str:
    role = raw.strip().strip("`").lower()
    role = role.replace(" ", "")
    role = role.replace("(", "").replace(")", "")
    if role in {"notestaccount", "no test account", ""}:
        return "hq_user_fallback"
    if role in {"notmapped", "unmapped", "-"}:
        return "unmapped_role"
    return role


def _parse_registry(path: Path) -> list[RouteEntry]:
    text = path.read_text(encoding="utf-8")
    section = ""
    entries: list[RouteEntry] = []
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            section = heading.group(1).strip()
            continue

        if not line.startswith("|"):
            continue
        if "---" in line or "Feature" in line:
            continue

        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 4:
            continue
        feature, route, test_role, endpoint = parts[:4]
        route = route.strip("`")
        endpoint = endpoint.strip("`")
        if route in {"-", ""}:
            continue
        module = SECTION_TO_MODULE.get(section)
        if not module:
            continue
        entries.append(
            RouteEntry(
                module=module,
                section=section,
                feature=feature,
                route=route,
                test_role=_norm_role(test_role),
                endpoint=endpoint,
            )
        )
    return entries


def _available_modules(entries: list[RouteEntry]) -> list[str]:
    return sorted({e.module for e in entries})


def _collect_targets(entries: list[RouteEntry], module: str) -> list[RouteEntry]:
    if module == "all":
        return entries
    return [e for e in entries if e.module == module]


def _wait_for_dashboard(page, timeout_ms: int = 30000) -> bool:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if "/dashboard" in page.url:
            return True
        page.wait_for_timeout(250)
    return False


def _login(page, email: str, password: str) -> tuple[bool, str]:
    try:
        page.goto(f"{BASE_WEB}/login", wait_until="domcontentloaded", timeout=60000)
        email_input = page.locator(
            'input[autocomplete="username"], input[name="email"], input[name="usr"], input[type="email"]'
        ).first
        pass_input = page.locator(
            'input[autocomplete="current-password"], input[name="password"], input[type="password"]'
        ).first
        submit = page.locator(
            'button[type="submit"]:has-text("Sign in"), button[type="submit"]:has-text("Login"), button[type="submit"]'
        ).first

        if email_input.is_visible(timeout=4000):
            email_input.fill(email)
            pass_input.fill(password)
            submit.click()
            page.wait_for_timeout(700)
        else:
            api_login = page.request.post(
                f"{BASE_WEB}/api/auth/login",
                data={"usr": email, "pwd": password},
                headers={"Content-Type": "application/json"},
                timeout=30000,
            )
            if api_login.status < 200 or api_login.status >= 300:
                return False, f"API login fallback failed: {api_login.status}"
            page.goto(f"{BASE_WEB}/dashboard", wait_until="domcontentloaded", timeout=60000)

        ok = _wait_for_dashboard(page, timeout_ms=30000)
        return ok, page.url
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _blocking_console_errors(errors: list[str]) -> list[str]:
    blocking: list[str] = []
    for msg in errors:
        low = msg.lower()
        # Ignore noisy static asset fetch misses.
        if "failed to load resource" in low and "404" in low:
            continue
        # Ignore expected non-fatal forbidden asset fetches.
        if "failed to load resource" in low and "403" in low:
            continue
        if any(x in low for x in ("typeerror", "referenceerror", "syntaxerror", "application error", "hydration failed")):
            blocking.append(msg)
            continue
        # Unknown console errors are still useful signal at L2.
        blocking.append(msg)
    return blocking


def _resolve_route_for_render_check(route: str) -> str:
    """
    Resolve route templates like /foo/[id] to a render-checkable path.
    L2 validates that the page shell/route is healthy; entity-specific detail
    routes are covered in L3 with real IDs.
    """
    if "[" not in route:
        return route
    resolved = re.sub(r"/\[[^/\]]+\]", "", route).strip()
    return resolved or "/"


def _check_page(page, row: RouteEntry, screenshot_file: Path, email: str, password: str) -> dict[str, Any]:
    console_errors: list[str] = []

    def _on_console(msg: ConsoleMessage):
        if msg.type == "error":
            text = msg.text or ""
            console_errors.append(text[:240])

    page.on("console", _on_console)
    started = time.time()
    target_url = f"{BASE_WEB}{row.route}"
    nav_error = ""
    http_status = 0
    redirected_to = ""
    screenshot_ok = False
    route_resolved = _resolve_route_for_render_check(row.route)

    try:
        target_url = f"{BASE_WEB}{route_resolved}"
        resp = page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        if resp:
            http_status = int(resp.status)
        page.wait_for_timeout(1200)

        # If shell spinner remains, allow a short settle window.
        spinner = page.locator("text=Loading dashboard...")
        if spinner.count() > 0 and spinner.first.is_visible(timeout=500):
            page.wait_for_timeout(6000)

        redirected_to = page.url
        if "/login" in redirected_to:
            relog_ok, _ = _login(page, email=email, password=password)
            if relog_ok:
                resp = page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                if resp:
                    http_status = int(resp.status)
                page.wait_for_timeout(900)
                redirected_to = page.url

        body_text = page.locator("body").inner_text(timeout=10000)
        low = body_text.lower()
        has_main = page.locator("main, [role='main'], [data-testid='main-content']").count() > 0
        body_len = len(body_text.strip())

        is_login_redirect = "/login" in redirected_to
        access_denied = any(
            x in low
            for x in ("access restricted", "permission denied", "not authorized", "unauthorized")
        )
        app_error_phrases = (
            "application error",
            "something went wrong",
            "internal server error",
            "page not found",
            "this page doesn't exist",
            "this page does not exist",
        )
        has_http_error_token = re.search(r"\b(?:404|500)\b(?:\s+error)?", low) is not None
        app_error = any(x in low for x in app_error_phrases) or (
            has_http_error_token and ("page" in low or "error" in low)
        )
        stuck_loading = "loading dashboard..." in low and body_len < 180
        blocking_console = _blocking_console_errors(console_errors)
        no_console_errors = len(blocking_console) == 0

        screenshot_file.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_file), full_page=False, timeout=10000)
        screenshot_ok = True

        checks = {
            "not_login_redirect": not is_login_redirect,
            "not_access_denied": not access_denied,
            "not_app_error": not app_error,
            "not_stuck_loading": not stuck_loading,
            "has_content": body_len > 80,
            "has_main_or_content": has_main or body_len > 200,
            "no_console_errors": no_console_errors,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        detail = []
        if status == "FAIL":
            detail.extend([k for k, v in checks.items() if not v])
            if blocking_console:
                detail.append(f"console_errors={len(blocking_console)}")

        return {
            "module": row.module,
            "section": row.section,
            "feature": row.feature,
            "route": row.route,
            "resolved_route": route_resolved,
            "url": target_url,
            "role": row.test_role,
            "status": status,
            "http_status": http_status,
            "redirected_to": redirected_to,
            "detail": ", ".join(detail) if detail else "ok",
            "console_errors": blocking_console,
            "screenshot": str(screenshot_file.relative_to(ROOT)).replace("\\", "/") if screenshot_ok else "",
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except PlaywrightTimeoutError as exc:
        nav_error = f"Timeout: {exc}"
    except Exception as exc:
        nav_error = f"{type(exc).__name__}: {exc}"
    finally:
        page.remove_listener("console", _on_console)

    return {
        "module": row.module,
        "section": row.section,
        "feature": row.feature,
        "route": row.route,
        "resolved_route": route_resolved,
        "url": target_url,
        "role": row.test_role,
        "status": "FAIL",
        "http_status": http_status,
        "redirected_to": redirected_to,
        "detail": nav_error,
        "console_errors": _blocking_console_errors(console_errors),
        "screenshot": str(screenshot_file.relative_to(ROOT)).replace("\\", "/") if screenshot_ok else "",
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run L2 page checks from ROUTE_REGISTRY.")
    parser.add_argument("--module", default="all", help="Module key from route registry or 'all'.")
    parser.add_argument("--list", action="store_true", help="List available modules and exit.")
    parser.add_argument("--headed", action="store_true", help="Run with headed browser.")
    args = parser.parse_args()

    if not ROUTE_REGISTRY.exists():
        print(f"Missing route registry: {ROUTE_REGISTRY}")
        return 2

    entries = _parse_registry(ROUTE_REGISTRY)
    modules = _available_modules(entries)

    if args.list:
        print("L2 modules:")
        for module in modules:
            count = len([e for e in entries if e.module == module])
            print(f"- {module:14} routes={count}")
        return 0

    if args.module != "all" and args.module not in modules:
        print(f"Unknown module: {args.module}")
        print(f"Available: {', '.join(modules)}")
        return 2

    targets = _collect_targets(entries, args.module)
    if not targets:
        print(f"No routes found for module={args.module}")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    screenshot_root = ROOT / "output" / "l2" / "artifacts" / stamp
    out_dir = ROOT / "output" / "l2" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"l2_run_{stamp}.json"

    results: list[dict[str, Any]] = []
    hard_fail = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        role_pages: dict[str, Any] = {}
        role_contexts: dict[str, Any] = {}

        try:
            for idx, row in enumerate(targets, start=1):
                role = row.test_role
                email = ROLE_TO_EMAIL.get(role)
                if not email:
                    results.append(
                        {
                            "module": row.module,
                            "section": row.section,
                            "feature": row.feature,
                            "route": row.route,
                            "url": f"{BASE_WEB}{row.route}",
                            "role": role,
                            "status": "WARN",
                            "http_status": 0,
                            "redirected_to": "",
                            "detail": f"No mapped account for role '{role}' (skipped).",
                            "console_errors": [],
                            "screenshot": "",
                            "elapsed_ms": 0,
                        }
                    )
                    print(f"WARN  [  0] {row.module:12} {row.route} role={row.test_role}")
                    continue

                if role not in role_pages:
                    context = browser.new_context(viewport={"width": 1366, "height": 900})
                    page = context.new_page()
                    ok, detail = _login(page, email=email, password=DEFAULT_PASSWORD)
                    if not ok:
                        hard_fail = True
                        results.append(
                            {
                                "module": row.module,
                                "section": row.section,
                                "feature": row.feature,
                                "route": row.route,
                                "url": f"{BASE_WEB}{row.route}",
                                "role": role,
                                "status": "FAIL",
                                "http_status": 0,
                                "redirected_to": "",
                                "detail": f"Login failed for {email}: {detail}",
                                "console_errors": [],
                                "screenshot": "",
                                "elapsed_ms": 0,
                            }
                        )
                        context.close()
                        continue

                    role_contexts[role] = context
                    role_pages[role] = page

                screenshot_file = (
                    screenshot_root
                    / row.module
                    / f"{idx:03d}_{re.sub(r'[^a-zA-Z0-9]+', '_', row.feature).strip('_').lower()}.png"
                )
                result = _check_page(
                    page=role_pages[role],
                    row=row,
                    screenshot_file=screenshot_file,
                    email=email,
                    password=DEFAULT_PASSWORD,
                )
                if result["status"] != "PASS":
                    hard_fail = True
                results.append(result)
                print(
                    f"{result['status']:5} [{result.get('http_status', 0):3}] "
                    f"{row.module:12} {row.route} role={row.test_role}"
                )
        finally:
            for ctx in role_contexts.values():
                try:
                    ctx.close()
                except Exception:
                    pass
            browser.close()

    module_summary: dict[str, dict[str, int]] = {}
    for module in _available_modules(targets):
        rows = [r for r in results if r["module"] == module]
        passed = len([r for r in rows if r["status"] == "PASS"])
        warned = len([r for r in rows if r["status"] == "WARN"])
        failed = len([r for r in rows if r["status"] == "FAIL"])
        module_summary[module] = {"total": len(rows), "passed": passed, "warned": warned, "failed": failed}

    payload = {
        "ran_at": datetime.now().isoformat(),
        "requested_module": args.module,
        "route_registry": str(ROUTE_REGISTRY.relative_to(ROOT)).replace("\\", "/"),
        "base_web": BASE_WEB,
        "summary": {
            "total": len(results),
            "passed": len([r for r in results if r["status"] == "PASS"]),
            "warned": len([r for r in results if r["status"] == "WARN"]),
            "failed": len([r for r in results if r["status"] == "FAIL"]),
            "by_module": module_summary,
        },
        "results": results,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"RESULT_FILE={out_file.relative_to(ROOT)}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Documentation Truth Protocol checker.

Fails CI when architecture docs drift from code/setup evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Iterable

import requests
import yaml


ROOT = Path(__file__).resolve().parents[2]
SAD = ROOT / "docs" / "architecture" / "SOLUTION_ARCHITECTURE_DOCUMENT.md"
ROUTE_MAP = ROOT / "docs" / "plans" / "system-flow-gaps-v3-full-route-map.md"
ROUTE_REGISTRY = ROOT / "docs" / "testing" / "ROUTE_REGISTRY.md"
SCENARIO_INDEX = ROOT / "docs" / "testing" / "scenarios" / "index.yaml"
START_HERE = ROOT / "docs" / "00_START_HERE.md"
ARCH_INDEX = ROOT / "docs" / "architecture" / "INDEX.md"
REPO_INV = ROOT / "docs" / "architecture" / "REPOSITORY_INVENTORY.md"
INFRA_INV = ROOT / "docs" / "architecture" / "INFRASTRUCTURE_INVENTORY.md"
NFR_SLO = ROOT / "docs" / "architecture" / "NFR_SLO_BASELINE.md"
SECURITY_ARCH = ROOT / "docs" / "architecture" / "SECURITY_ARCHITECTURE.md"
DEPLOYMENT_DR = ROOT / "docs" / "architecture" / "DEPLOYMENT_TOPOLOGY_AND_DR.md"
OWNERSHIP_MATRIX = ROOT / "docs" / "architecture" / "OWNERSHIP_MATRIX.md"
DOC_TRUTH_PROTOCOL = ROOT / "docs" / "architecture" / "DOCUMENTATION_TRUTH_PROTOCOL.md"
HOSTING_DOMAINS = ROOT / "docs" / "architecture" / "HOSTING_AND_DOMAINS.md"
FLOW_CATALOG = ROOT / "docs" / "architecture" / "FLOW_CATALOG.md"
SNAPSHOT_DIR = ROOT / "docs" / "architecture" / "snapshots"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _count_whitelist_markers(paths: Iterable[Path]) -> int:
    marker = re.compile(r"^\s*@frappe\.whitelist", re.M)
    total = 0
    for p in paths:
        total += len(marker.findall(_read(p)))
    return total


def _count_route_table_rows(text: str) -> int:
    return len(re.findall(r"^\|\s*\d+\s*\|", text, flags=re.M))


def _count_registry_rows(text: str) -> int:
    count = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if "Feature" in line or "---" in line:
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        route = parts[1].strip().strip("`")
        if len(parts) >= 4 and route.startswith("/"):
            count += 1
    return count


def _extract_int(pattern: str, text: str, label: str) -> int:
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"Could not parse {label}.")
    return int(m.group(1))


def _extract_triplet(pattern: str, text: str, label: str) -> tuple[int, int, int]:
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"Could not parse {label}.")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _parse_named_date(text: str, field_name: str) -> dt.date:
    pattern = rf"{re.escape(field_name)}[^\n]*?(\d{{4}}-\d{{2}}-\d{{2}})"
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"Could not parse date for '{field_name}'.")
    return dt.date.fromisoformat(m.group(1))


def _days_old(day: dt.date) -> int:
    return (dt.date.today() - day).days


def _parse_sad_metric_row(sad_text: str, metric_name: str) -> int:
    pattern = rf"\|\s*{re.escape(metric_name)}\s*\|\s*(\d+)"
    return _extract_int(pattern, sad_text, metric_name)


def _extract_markdown_field(text: str, field_name: str) -> str:
    patterns = [
        rf"(?mi)^\s*\*\*{re.escape(field_name)}:\*\*\s*(.+?)\s*$",
        rf"(?mi)^\s*{re.escape(field_name)}:\s*(.+?)\s*$",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    raise ValueError(f"Could not parse field '{field_name}'.")


def _parse_date_token(value: str, field_name: str) -> dt.date:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if not m:
        raise ValueError(f"Could not parse date token in field '{field_name}'.")
    return dt.date.fromisoformat(m.group(1))


def _lint_markdown_doc(path: Path) -> list[str]:
    issues: list[str] = []
    text = _read(path)
    lines = text.splitlines()
    first_nonempty = next((line for line in lines if line.strip()), "")
    if not first_nonempty:
        issues.append(f"Markdown lint: file is empty: {path.relative_to(ROOT)}")
    elif not (first_nonempty.startswith("#") or first_nonempty.startswith("---")):
        issues.append(
            f"Markdown lint: first non-empty line must be H1 or frontmatter: {path.relative_to(ROOT)}"
        )
    if not re.search(r"(?m)^#\s+", text):
        issues.append(f"Markdown lint: missing H1 heading: {path.relative_to(ROOT)}")
    if text and not text.endswith("\n"):
        issues.append(f"Markdown lint: file must end with newline: {path.relative_to(ROOT)}")
    return issues


def _iter_local_markdown_links(text: str) -> Iterable[str]:
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for raw in link_pattern.findall(text):
        target = raw.strip()
        if not target:
            continue
        # Strip optional title: (path "title")
        if " " in target and not target.startswith("<"):
            target = target.split(" ", 1)[0].strip()
        target = target.strip("<>").strip()
        yield target


def _check_local_links(path: Path) -> list[str]:
    issues: list[str] = []
    text = _read(path)
    for target in _iter_local_markdown_links(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean_target = target.split("#", 1)[0]
        if not clean_target:
            continue
        if re.match(r"^[A-Za-z]:[\\/]", clean_target):
            continue
        candidate = (ROOT / clean_target.lstrip("/")) if clean_target.startswith("/") else (path.parent / clean_target)
        if not candidate.exists():
            issues.append(
                f"Broken local markdown link in {path.relative_to(ROOT)} -> {target}"
            )
    return issues


def _check_network(strict: bool) -> list[str]:
    issues: list[str] = []
    targets = [
        "https://hq.bebang.ph/api/method/frappe.ping",
        "https://my.bebang.ph",
    ]
    for url in targets:
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code >= 500:
                msg = f"Network check failed ({resp.status_code}): {url}"
                issues.append(msg)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"Network check exception for {url}: {exc}")
    if not strict:
        return ["WARN: " + x for x in issues]
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Documentation Truth Protocol checks.")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="Maximum allowed staleness for baseline docs.",
    )
    parser.add_argument(
        "--frontend-path",
        default=str((ROOT.parent / "bei-tasks").resolve()),
        help="Path to BEI-Tasks repo checkout for frontend metrics.",
    )
    parser.add_argument(
        "--strict-network",
        action="store_true",
        help="Fail if public endpoint reachability checks fail.",
    )
    parser.add_argument(
        "--snapshot-month",
        default=dt.date.today().strftime("%Y-%m"),
        help="Required architecture snapshot month (YYYY-MM).",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    required_files = [
        SAD,
        ROUTE_MAP,
        ROUTE_REGISTRY,
        SCENARIO_INDEX,
        START_HERE,
        ARCH_INDEX,
        REPO_INV,
        INFRA_INV,
        NFR_SLO,
        SECURITY_ARCH,
        DEPLOYMENT_DR,
        OWNERSHIP_MATRIX,
        DOC_TRUTH_PROTOCOL,
        HOSTING_DOMAINS,
        FLOW_CATALOG,
    ]
    for path in required_files:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")

    snapshot_file = SNAPSHOT_DIR / f"{args.snapshot_month}.md"
    if not snapshot_file.exists():
        errors.append(
            f"Missing required monthly snapshot: {snapshot_file.relative_to(ROOT)}"
        )

    if errors:
        print("DOCUMENTATION TRUTH CHECK: FAIL")
        for msg in errors:
            print(f"[ERROR] {msg}")
        return 1

    sad_text = _read(SAD)
    route_map_text = _read(ROUTE_MAP)
    route_registry_text = _read(ROUTE_REGISTRY)
    scenario_index = yaml.safe_load(_read(SCENARIO_INDEX))

    # Live code footprint metrics.
    api_files = list((ROOT / "hrms" / "api").glob("*.py"))
    backend_api_count = len(api_files)
    whitelist_count = _count_whitelist_markers(api_files)
    bei_doctype_count = len(
        [
            p
            for p in (ROOT / "hrms" / "hr" / "doctype").iterdir()
            if p.is_dir() and p.name.startswith("bei_")
        ]
    )

    frontend_root = Path(args.frontend_path)
    if not frontend_root.exists():
        errors.append(f"Frontend path not found: {frontend_root}")
        frontend_api_routes = -1
        frontend_pages = -1
    else:
        frontend_api_routes = len(
            [
                p
                for p in (frontend_root / "app" / "api").rglob("*")
                if p.is_file() and re.match(r"^route\.(ts|tsx|js|jsx)$", p.name)
            ]
        )
        frontend_pages = len(
            [
                p
                for p in (frontend_root / "app").rglob("*")
                if p.is_file() and re.match(r"^page\.(ts|tsx|js|jsx)$", p.name)
            ]
        )

    # Route counts.
    route_map_rows = _count_route_table_rows(route_map_text)
    route_registry_rows = _count_registry_rows(route_registry_text)
    route_map_registry_yes = len(re.findall(r"\|\s*yes\s*\|", route_map_text))

    # Parse SAD claimed metrics.
    sad_backend_api = _parse_sad_metric_row(sad_text, "Backend API files")
    sad_whitelist = _parse_sad_metric_row(sad_text, "Whitelisted endpoints marker count")
    sad_bei_doctypes = _parse_sad_metric_row(sad_text, "BEI custom DocType count")
    sad_frontend_api = _parse_sad_metric_row(sad_text, "Frontend API route files")
    sad_frontend_pages = _parse_sad_metric_row(sad_text, "Frontend page files")
    sad_route_rows = _parse_sad_metric_row(sad_text, "Full route map rows")
    sad_route_bound = _parse_sad_metric_row(sad_text, "Registry-bound routes in full map")

    claimed_exec_triplet = _extract_triplet(
        r"Full route map:\s*(\d+) mapped rows,\s*(\d+) registry-bound,\s*(\d+) not yet bound",
        sad_text,
        "SAD executive route-map line",
    )

    # Parse route-map summary metrics.
    summary_rows = _extract_int(r"Total mapped rows:\s*\*\*(\d+)\*\*", route_map_text, "route map total rows")
    summary_bound = _extract_int(r"Registry-bound routes:\s*\*\*(\d+)\*\*", route_map_text, "route map bound")
    summary_missing = _extract_int(r"Missing from route registry:\s*\*\*(\d+)\*\*", route_map_text, "route map missing")

    # Metric comparisons.
    comparisons = [
        ("Backend API files", backend_api_count, sad_backend_api),
        ("Whitelisted endpoint markers", whitelist_count, sad_whitelist),
        ("BEI custom DocTypes", bei_doctype_count, sad_bei_doctypes),
        ("Frontend API route files", frontend_api_routes, sad_frontend_api),
        ("Frontend page files", frontend_pages, sad_frontend_pages),
        ("Full route map rows", route_map_rows, sad_route_rows),
        ("Registry-bound routes", route_map_registry_yes, sad_route_bound),
    ]
    for label, actual, claimed in comparisons:
        if actual != claimed:
            errors.append(f"Metric drift: {label} actual={actual} claimed={claimed}")

    if route_registry_rows != route_map_rows:
        errors.append(
            f"Route registry row count mismatch: registry={route_registry_rows}, full-map={route_map_rows}"
        )

    if summary_rows != route_map_rows:
        errors.append(f"Route-map summary mismatch: summary rows={summary_rows}, parsed rows={route_map_rows}")
    if summary_bound != route_map_registry_yes:
        errors.append(
            f"Route-map summary mismatch: summary bound={summary_bound}, parsed bound={route_map_registry_yes}"
        )
    if summary_missing != (route_map_rows - route_map_registry_yes):
        errors.append(
            "Route-map summary mismatch: missing count does not equal total-bound."
        )

    if claimed_exec_triplet != (route_map_rows, route_map_registry_yes, route_map_rows - route_map_registry_yes):
        errors.append(
            "SAD executive route-map line is out of sync with full route-map metrics."
        )

    # Flow readiness checks.
    flow_by_key = {row.get("key"): row for row in scenario_index.get("flows", [])}
    for key, prefix in (("dispatch-warehouse-commissary", "DWC"), ("hire-to-onboard", "HTO")):
        row = flow_by_key.get(key)
        if not row:
            errors.append(f"Missing flow in index.yaml: {key}")
            continue
        if row.get("status") != "ready":
            errors.append(f"Flow not ready in index.yaml: {key} status={row.get('status')}")
        prefixes = row.get("prefixes", [])
        if prefix not in prefixes:
            errors.append(f"Flow prefix missing in index.yaml: {key} requires {prefix}")

    # Freshness checks.
    try:
        route_registry_day = _parse_named_date(route_registry_text, "Last Updated")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
        route_registry_day = dt.date.today()

    try:
        scenario_day = dt.date.fromisoformat(str(scenario_index.get("last_updated")))
    except Exception:  # noqa: BLE001
        errors.append("Could not parse docs/testing/scenarios/index.yaml last_updated")
        scenario_day = dt.date.today()

    arch_index_text = _read(ARCH_INDEX)
    m_scan = re.search(r"\*\*Last Scanned:\*\*\s*(\d{4}-\d{2}-\d{2})", arch_index_text)
    if not m_scan:
        errors.append("Could not parse Last Scanned date in docs/architecture/INDEX.md")
        arch_scan_day = dt.date.today()
    else:
        arch_scan_day = dt.date.fromisoformat(m_scan.group(1))

    freshness_items = [
        ("docs/testing/ROUTE_REGISTRY.md", route_registry_day),
        ("docs/testing/scenarios/index.yaml", scenario_day),
        ("docs/architecture/INDEX.md (Last Scanned)", arch_scan_day),
    ]
    for label, day in freshness_items:
        age = _days_old(day)
        if age > args.max_age_days:
            errors.append(
                f"Stale baseline doc: {label} age={age} days (> {args.max_age_days})"
            )

    baseline_docs = [
        START_HERE,
        ARCH_INDEX,
        SAD,
        NFR_SLO,
        SECURITY_ARCH,
        DEPLOYMENT_DR,
        OWNERSHIP_MATRIX,
        REPO_INV,
        INFRA_INV,
        DOC_TRUTH_PROTOCOL,
        HOSTING_DOMAINS,
        FLOW_CATALOG,
        snapshot_file,
    ]
    for path in baseline_docs:
        rel = path.relative_to(ROOT)
        text = _read(path)
        try:
            last_updated_val = _extract_markdown_field(text, "Last Updated")
            last_updated_day = _parse_date_token(last_updated_val, "Last Updated")
            age = _days_old(last_updated_day)
            if age > args.max_age_days:
                errors.append(
                    f"Stale baseline doc: {rel} age={age} days (> {args.max_age_days})"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rel}: {exc}")
        for field in ("Owner", "Next Review"):
            try:
                _extract_markdown_field(text, field)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {exc}")
        try:
            next_review_day = _parse_date_token(
                _extract_markdown_field(text, "Next Review"), "Next Review"
            )
            if next_review_day < dt.date.today():
                errors.append(
                    f"Review overdue: {rel} next_review={next_review_day.isoformat()}"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{rel}: {exc}")

    for path in baseline_docs:
        errors.extend(_check_local_links(path))
        errors.extend(_lint_markdown_doc(path))

    for issue in _check_network(strict=args.strict_network):
        if issue.startswith("WARN:"):
            warnings.append(issue)
        else:
            errors.append(issue)

    if errors:
        print("DOCUMENTATION TRUTH CHECK: FAIL")
        for msg in errors:
            print(f"[ERROR] {msg}")
        for msg in warnings:
            print(f"[WARN]  {msg}")
        return 1

    print("DOCUMENTATION TRUTH CHECK: PASS")
    print(f"- backend_api_files={backend_api_count}")
    print(f"- whitelist_markers={whitelist_count}")
    print(f"- bei_doctypes={bei_doctype_count}")
    print(f"- frontend_api_routes={frontend_api_routes}")
    print(f"- frontend_pages={frontend_pages}")
    print(f"- route_map_rows={route_map_rows}")
    print(f"- route_registry_rows={route_registry_rows}")
    if warnings:
        for msg in warnings:
            print(f"[WARN]  {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

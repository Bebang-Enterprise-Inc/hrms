"""Seed intercompany Due From / Due To Group Entities accounts (S206 Phase 4).

Creates, on each in-scope Company, the two accounts S206 paired-JE allocation
depends on:

    1104200 - DUE FROM GROUP ENTITIES - <abbr>   (Receivable, Asset)
    2104200 - DUE TO GROUP ENTITIES - <abbr>     (Payable, Liability)

In-scope Companies:
    - every Company with entity_category='Store' (49)
    - BEBANG ENTERPRISE INC. (parent)
    - BEBANG KITCHEN INC. (commissary)

Total new accounts: 102 (51 × 2). Idempotent — INSERT IGNOREs by name if
already present.

Run on production via:

    docker exec $BACKEND bench --site hq.bebang.ph execute \
        hrms.on_demand.s206_seed_intercompany_accounts.execute

No dry-run switch needed — invoke only when you want to create the accounts.

Wrapped in `frappe.db.savepoint`; any row-level failure rolls back the full
batch and logs via `frappe.log_error` so Sentry captures it (DM-7).
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import frappe


SAVEPOINT_NAME = "s206_seed_intercompany_accounts"
SITE_REPORT_SUBPATH = ("private", "files")

DUE_FROM_ACCOUNT_NAME = "1104200 - DUE FROM GROUP ENTITIES - {abbr}"
DUE_TO_ACCOUNT_NAME = "2104200 - DUE TO GROUP ENTITIES - {abbr}"

# Parent account groups per Company's CoA. If the canonical parents differ by
# Company, we pick the group that matches by name pattern.
PARENT_RECEIVABLE_GROUP_PATTERNS = ["%Accounts Receivable%", "%Current Assets%"]
PARENT_PAYABLE_GROUP_PATTERNS = ["%Accounts Payable%", "%Current Liabilities%"]


def _in_scope_companies() -> list[dict]:
    rows = frappe.db.sql(
        """
        SELECT name, abbr, entity_category
        FROM tabCompany
        WHERE entity_category = 'Store'
           OR name IN ('BEBANG ENTERPRISE INC.', 'BEBANG KITCHEN INC.')
        ORDER BY entity_category, name
        """,
        as_dict=True,
    )
    return rows


def _find_parent_group(company: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        parent = frappe.db.sql(
            """
            SELECT name FROM tabAccount
            WHERE company = %(company)s
              AND is_group = 1
              AND name LIKE %(pat)s
            ORDER BY lft LIMIT 1
            """,
            {"company": company, "pat": pat},
            as_dict=True,
        )
        if parent:
            return parent[0]["name"]
    return None


def _ensure_account(
    *,
    company: str,
    abbr: str,
    account_name: str,
    account_type: str,
    root_type: str,
    parent_group: str,
) -> tuple[str, str]:
    """Ensure an Account with this name exists; return (name, 'created' | 'existed')."""
    existing = frappe.db.exists("Account", account_name)
    if existing:
        return (existing, "existed")

    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": account_name.rsplit(" - ", 1)[0],  # strip the abbr suffix Frappe auto-appends
        "parent_account": parent_group,
        "company": company,
        "is_group": 0,
        "account_type": account_type,
        "root_type": root_type,
        "account_currency": frappe.db.get_value("Company", company, "default_currency") or "PHP",
    })
    doc.insert(ignore_permissions=True)
    return (doc.name, "created")


def _write_report(payload: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"s206_intercompany_seed_report_{stamp}.json"
    try:
        site_path = frappe.get_site_path(*SITE_REPORT_SUBPATH)
        os.makedirs(site_path, exist_ok=True)
        out_path = os.path.join(site_path, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        return out_path
    except Exception as exc:
        frappe.log_error(
            title="S206 seed report write failed",
            message=str(exc),
        )
        return ""


def execute() -> dict:
    """Create Due From / Due To accounts for every in-scope Company.

    Always-apply. Idempotent.
    """
    companies = _in_scope_companies()
    created_accounts: list[dict] = []
    existed_accounts: list[dict] = []
    missing_parents: list[dict] = []
    errors: list[dict] = []

    frappe.db.savepoint(SAVEPOINT_NAME)
    try:
        for co in companies:
            name = co["name"]
            abbr = co["abbr"]

            due_from_name = DUE_FROM_ACCOUNT_NAME.format(abbr=abbr)
            due_to_name = DUE_TO_ACCOUNT_NAME.format(abbr=abbr)

            # Parent groups
            parent_rec = _find_parent_group(name, PARENT_RECEIVABLE_GROUP_PATTERNS)
            parent_pay = _find_parent_group(name, PARENT_PAYABLE_GROUP_PATTERNS)
            if not parent_rec:
                missing_parents.append({"company": name, "missing": "Receivable group"})
                continue
            if not parent_pay:
                missing_parents.append({"company": name, "missing": "Payable group"})
                continue

            try:
                df_name, df_status = _ensure_account(
                    company=name,
                    abbr=abbr,
                    account_name=due_from_name,
                    account_type="Receivable",
                    root_type="Asset",
                    parent_group=parent_rec,
                )
                if df_status == "created":
                    created_accounts.append({"company": name, "account": df_name, "type": "Receivable"})
                else:
                    existed_accounts.append({"company": name, "account": df_name, "type": "Receivable"})

                dt_name, dt_status = _ensure_account(
                    company=name,
                    abbr=abbr,
                    account_name=due_to_name,
                    account_type="Payable",
                    root_type="Liability",
                    parent_group=parent_pay,
                )
                if dt_status == "created":
                    created_accounts.append({"company": name, "account": dt_name, "type": "Payable"})
                else:
                    existed_accounts.append({"company": name, "account": dt_name, "type": "Payable"})
            except Exception as exc:
                errors.append({"company": name, "error": str(exc)})

        if errors or missing_parents:
            frappe.db.rollback(save_point=SAVEPOINT_NAME)
            frappe.log_error(
                title="S206 intercompany account seed rolled back",
                message=(
                    f"errors={len(errors)}, missing_parents={len(missing_parents)}; "
                    f"first_error={errors[0] if errors else None}; "
                    f"first_missing={missing_parents[0] if missing_parents else None}"
                ),
            )
        else:
            frappe.db.release_savepoint(SAVEPOINT_NAME)
            frappe.db.commit()
    except Exception as exc:
        frappe.db.rollback(save_point=SAVEPOINT_NAME)
        errors.append({"stage": "batch", "error": str(exc)})
        frappe.log_error(title="S206 intercompany account seed batch failure", message=str(exc))

    summary = {
        "companies_in_scope": len(companies),
        "created_count": len(created_accounts),
        "existed_count": len(existed_accounts),
        "missing_parents_count": len(missing_parents),
        "errors_count": len(errors),
        "created": created_accounts,
        "existed": existed_accounts,
        "missing_parents": missing_parents,
        "errors": errors,
    }
    report_path = _write_report(summary)
    summary["report_path"] = report_path

    status = "rolled_back" if (errors or missing_parents) else "ok"
    frappe.logger().info(
        f"[S206 seed] {status}: created={len(created_accounts)}, "
        f"existed={len(existed_accounts)}, missing_parents={len(missing_parents)}, "
        f"errors={len(errors)}. report={report_path}"
    )
    return summary

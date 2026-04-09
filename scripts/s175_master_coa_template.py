#!/usr/bin/env python3
"""S175 Master Sales COA Template.

27-row canonical Sales tree per data/_CLEANROOM/2026-04-09_s175_coa_restructure/
01_CANONICAL_COA_TEMPLATE.md Section A.2. Source of truth for Phase 2 & Phase 8
template builders.

Each tuple: (number, name, parent_number, is_group, root_type, account_type)
- parent_number=None means "attach to company's top-level (parent_account=NULL)"
- account_type is None for group accounts and the 4000000 root
"""
from __future__ import annotations

MASTER_SALES_TEMPLATE = [
    # number, name, parent_number, is_group, root_type, account_type
    ("4000000", "SALES",                                      None,        1, "Income", None),
    ("4000100", "STORE SALES",                                "4000000",   1, "Income", None),
    ("4000110", "IN-STORE SALES",                             "4000100",   0, "Income", "Income Account"),
    ("4000120", "ONLINE SALES",                               "4000100",   1, "Income", None),
    ("4000121", "BEI WEBSITE",                                "4000120",   0, "Income", "Income Account"),
    ("4000122", "FOOD PANDA",                                 "4000120",   0, "Income", "Income Account"),
    ("4000123", "GRAB",                                       "4000120",   0, "Income", "Income Account"),
    ("4000200", "BKI SALES",                                  "4000000",   1, "Income", None),
    ("4000210", "DELIVERIES",                                 "4000200",   0, "Income", "Income Account"),
    ("4000220", "LOGISTICS",                                  "4000200",   1, "Income", None),
    ("4000221", "DELIVERY INCOME",                            "4000220",   0, "Income", "Income Account"),
    ("4000222", "LOGISTICS INCOME",                           "4000220",   0, "Income", "Income Account"),
    ("4000230", "FEES",                                       "4000000",   1, "Income", None),
    ("4000231", "ROYALTY FEES",                               "4000230",   0, "Income", "Income Account"),
    ("4000232", "MANAGEMENT FEES",                            "4000230",   0, "Income", "Income Account"),
    ("4000233", "FRANCHISE FEES",                             "4000230",   0, "Income", "Income Account"),
    ("4000234", "MARKETING FEES",                             "4000230",   0, "Income", "Income Account"),
    ("4000235", "E-COMMERCE FEES",                            "4000230",   0, "Income", "Income Account"),
    ("4000900", "DISCOUNTS AND PROMO",                        "4000000",   1, "Income", None),
    ("4000901", "SALES DISCOUNT DUE TO FREE HALOHALO",        "4000900",   0, "Income", "Income Account"),
    ("4000902", "SALES DISCOUNT OF SENIOR CITIZENS",          "4000900",   0, "Income", "Income Account"),
    ("4000903", "SALES DISCOUNTS OF PWDS",                    "4000900",   0, "Income", "Income Account"),
    ("4000904", "SALES DISCOUNTS OF STAFFS AND EMPLOYEES",    "4000900",   0, "Income", "Income Account"),
    ("4000905", "SALES DISCOUNTS FROM VAT OF PWD",            "4000900",   0, "Income", "Income Account"),
    ("4000906", "SALES DISCOUNTS FROM VAT OF SENIOR CITIZENS", "4000900",  0, "Income", "Income Account"),
    ("4000907", "SALES REFUNDS TO CUSTOMER",                  "4000900",   0, "Income", "Income Account"),
    ("4000908", "SALES DISCOUNTS - EMPLOYEE DISC",            "4000900",   0, "Income", "Income Account"),
]

assert len(MASTER_SALES_TEMPLATE) == 27, f"Expected 27 template accounts, got {len(MASTER_SALES_TEMPLATE)}"

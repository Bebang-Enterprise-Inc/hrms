# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

from __future__ import annotations

import frappe


def test_user_oauth_token_doctype_exists():
    assert frappe.get_meta("User OAuth Token").name == "User OAuth Token"

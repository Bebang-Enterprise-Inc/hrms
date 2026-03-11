# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from frappe.model.base_document import get_controller
from frappe.tests.utils import FrappeTestCase

from hrms.hr.doctype.bei_statement_of_account.bei_statement_of_account import BEIStatementofAccount


class TestBEIStatementOfAccount(FrappeTestCase):
	def test_controller_name_matches_frappe_resolution(self):
		controller = get_controller("BEI Statement of Account")
		self.assertIs(controller, BEIStatementofAccount)

import frappe

try:
	from erpnext.tests.utils import ERPNextTestSuite
except ImportError:
	from frappe.tests import IntegrationTestCase

	class ERPNextTestSuite(IntegrationTestCase):
		"""Compatibility fallback for ERPNext branches without ERPNextTestSuite."""

		@classmethod
		def setUpClass(cls):
			super().setUpClass()

		@classmethod
		def make_employees(cls):
			records = [
				{
					"company": "_Test Company",
					"date_of_birth": "1980-01-01",
					"date_of_joining": "2010-01-01",
					"department": "_Test Department - _TC",
					"doctype": "Employee",
					"first_name": "_Test Employee",
					"gender": "Female",
					"naming_series": "_T-Employee-",
					"status": "Active",
					"user_id": "test@example.com",
				},
				{
					"company": "_Test Company",
					"date_of_birth": "1980-01-01",
					"date_of_joining": "2010-01-01",
					"department": "_Test Department 1 - _TC",
					"doctype": "Employee",
					"first_name": "_Test Employee 1",
					"gender": "Male",
					"naming_series": "_T-Employee-",
					"status": "Active",
					"user_id": "test1@example.com",
				},
				{
					"company": "_Test Company",
					"date_of_birth": "1980-01-01",
					"date_of_joining": "2010-01-01",
					"department": "_Test Department 1 - _TC",
					"doctype": "Employee",
					"first_name": "_Test Employee 2",
					"gender": "Male",
					"naming_series": "_T-Employee-",
					"status": "Active",
					"user_id": "test2@example.com",
				},
			]
			cls.employees = []
			for record in records:
				if not frappe.db.exists("Employee", {"first_name": record.get("first_name")}):
					cls.employees.append(frappe.get_doc(record).insert())
				else:
					cls.employees.append(
						frappe.get_doc("Employee", {"first_name": record.get("first_name")})
					)


class HRMSTestSuite(ERPNextTestSuite):
	"""Class for creating HRMS test records"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

	@classmethod
	def make_employees(cls):
		"""Create test employees"""
		# Create test employees here
		super().make_employees()

	@classmethod
	def make_departments(cls):
		"""Create test departments"""
		# Create test departments here
		records = [
			{
				"doctype": "Department",
				"department_name": "_Test Department",
				"company": "_Test Company",
				"parent_department": "All Departments",
			},
			{
				"doctype": "Department",
				"department_name": "_Test Department 1",
				"company": "_Test Company",
				"parent_department": "All Departments",
			},
		]
		cls.departments = []
		for x in records:
			if not frappe.db.exists("Department", x.get("department_name")):
				cls.departments.append(frappe.get_doc(x).insert())
			else:
				cls.departments.append(frappe.get_doc("Department", x.get("department_name")))

	@classmethod
	def make_leave_types(cls):
		"""Create test leave types"""
		# Create test leave types here
		records = [
			{"doctype": "Leave Type", "leave_type_name": "_Test Leave Type", "include_holiday": 1},
			{
				"doctype": "Leave Type",
				"is_lwp": 1,
				"leave_type_name": "_Test Leave Type LWP",
				"include_holiday": 1,
			},
			{
				"doctype": "Leave Type",
				"leave_type_name": "_Test Leave Type Encashment",
				"include_holiday": 1,
				"allow_encashment": 1,
				"non_encashable_leaves": 5,
				"earning_component": "Leave Encashment",
			},
			{
				"doctype": "Leave Type",
				"leave_type_name": "_Test Leave Type Earned",
				"include_holiday": 1,
				"is_earned_leave": 1,
			},
		]
		cls.leave_types = []
		for x in records:
			if not frappe.db.exists("Leave Type", x.get("leave_type_name")):
				cls.leave_types.append(frappe.get_doc(x).insert())
			else:
				cls.leave_types.append(frappe.get_doc("Leave Type", x.get("leave_type_name")))

	@classmethod
	def make_leave_allocations(cls):
		"""Create test leave applications"""
		# Create test leave applications here
		records = [
			{
				"docstatus": 1,
				"doctype": "Leave Allocation",
				"employee": "_T-Employee-00001",
				"from_date": "2013-01-01",
				"to_date": "2013-12-31",
				"leave_type": "_Test Leave Type",
				"new_leaves_allocated": 15,
			},
			{
				"docstatus": 1,
				"doctype": "Leave Allocation",
				"employee": "_T-Employee-00002",
				"from_date": "2013-01-01",
				"to_date": "2013-12-31",
				"leave_type": "_Test Leave Type",
				"new_leaves_allocated": 15,
			},
		]

		cls.leave_allocations = []
		for x in records:
			if not frappe.db.exists(
				"Leave Allocation",
				{"employee": x.get("employee"), "from_date": x.get("from_date"), "to_date": x.get("to_date")},
			):
				cls.leave_allocations.append(frappe.get_doc(x).insert())
			else:
				cls.leave_allocations.append(
					frappe.get_doc(
						"Employee",
						{
							"employee": x.get("employee"),
							"from_date": x.get("from_date"),
							"to_date": x.get("to_date"),
						},
					)
				)

# Testing Strategy & Patterns

This document outlines the testing frameworks, patterns, and best practices used in the BEI ERP codebase.

## Table of Contents

1. [Python Backend Testing](#python-backend-testing)
2. [Frontend Testing](#frontend-testing)
3. [Test Structure](#test-structure)
4. [Mocking Patterns](#mocking-patterns)
5. [Test Coverage](#test-coverage)
6. [Running Tests](#running-tests)

---

## Python Backend Testing

### Framework & Configuration

**Framework:** Frappe's built-in testing framework (based on unittest)
**Configuration:** `pyproject.toml`

```toml
[tool.frappe.testing.function_type_validation]
max_module_depth = 0
```

**Key Files:**
- Test files located alongside DocType in `hrms/hr/doctype/*/test_*.py`
- Controller tests in `hrms/controllers/tests/test_*.py`
- Import patterns shown in `pyproject.toml` for custom modules

### Test Base Class

**Pattern:** Inherit from `IntegrationTestCase`

```python
# Location: hrms/hr/doctype/employee_advance/test_employee_advance.py

import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import flt, nowdate

import erpnext
from erpnext.accounts.doctype.account.test_account import create_account
from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.employee_advance.employee_advance import (
	EmployeeAdvanceOverPayment,
	create_return_through_additional_salary,
	make_bank_entry,
	make_return_entry,
)


class TestEmployeeAdvance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# One-time setup shared across all tests in class
		# Create test data once
		# Attach to class

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		# One-time cleanup after all tests

	def setUp(self):
		# Run before EACH test
		# Isolation: clean state for each test
		# Clean database of test docs

	def tearDown(self):
		# Run after EACH test
		# Restore default settings
		frappe.set_value("Company", "_Test Company", "field", "value")
```

**Conventions:**
- Use `setUpClass()` for expensive one-time setup (creating employees, companies, etc.)
- Use `setUp()` for test isolation (clean database, reset settings)
- Use `tearDown()` to restore default state between tests
- Call `super().setUpClass()` and `super().tearDownClass()`

### Test Lifecycle Example

**File:** `hrms/controllers/tests/test_employee_reminders.py`

```python
class TestEmployeeReminders(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.holiday_list.test_holiday_list import make_holiday_list

		# Create test holiday list once
		test_holiday_dates = cls.get_test_holiday_dates()
		test_holiday_list = make_holiday_list(
			"TestHolidayRemindersList",
			holiday_dates=[...],
		)

		# Create test employee once
		test_employee = frappe.get_doc("Employee", make_employee("test@gopher.io"))
		test_employee.holiday_list = test_holiday_list.name
		test_employee.save()

		# Attach to class for use in all tests
		cls.test_employee = test_employee
		cls.test_holiday_dates = test_holiday_dates

	def setUp(self):
		# Run before EACH test
		# Clear shared resources that change during tests
		frappe.db.sql("delete from `tabEmail Queue`")
		frappe.db.sql("delete from `tabEmail Queue Recipient`")

	def tearDown(self):
		# Restore defaults
		frappe.db.set_value(
			"Employee",
			self.test_employee_2.name,
			{"status": "Active", "holiday_list": self.holiday_list_2.name},
		)
```

### Test Method Patterns

**Pattern 1: State transitions and assertions**

```python
def test_paid_amount_and_status(self):
	# Arrange: Create test data
	employee_name = make_employee("_T@employee.advance", "_Test Company")
	advance = make_employee_advance(employee_name)

	# Act: Perform action
	journal_entry = make_journal_entry_for_advance(advance)
	journal_entry.submit()

	# Assert: Verify state changed
	advance.reload()
	self.assertEqual(advance.paid_amount, 1000)
	self.assertEqual(advance.status, "Paid")
```

**Pattern 2: Exception handling**

```python
def test_paid_amount_and_status(self):
	# ... setup ...
	journal_entry1 = make_journal_entry_for_advance(advance)
	# Assert that exception is raised
	self.assertRaises(EmployeeAdvanceOverPayment, journal_entry1.submit)
```

**Pattern 3: Complex multi-step workflows**

```python
def test_claimed_status(self):
	# Step 1
	payable_account = get_payable_account("_Test Company")
	claim = make_expense_claim(employee_name, payable_account)

	# Step 2
	against_advance = make_employee_advance(employee_name)
	journal_entry = make_journal_entry_for_advance(against_advance)
	journal_entry.submit()

	# Step 3 - claim is against advance
	claim.reload()
	self.assertEqual(claim.status, "Claimed")

	# Step 4
	advance.reload()
	self.assertEqual(advance.status, "Claimed")
```

### Factory / Helper Functions

**Pattern:** Create helper functions for complex test data setup

```python
def make_employee_advance(employee, advance_amount=1000, company="_Test Company"):
	"""Create test employee advance."""
	doc = frappe.new_doc("Employee Advance")
	doc.employee = employee
	doc.advance_amount = advance_amount
	doc.company = company
	doc.insert()
	return doc


def make_journal_entry_for_advance(advance, amount=None):
	"""Create journal entry to mark advance as paid."""
	amount = amount or advance.advance_amount
	# ... create JE with proper accounts ...
	return je
```

### Test Data Setup

**Using Frappe test utilities:**

```python
from erpnext.setup.doctype.employee.test_employee import make_employee
from erpnext.setup.doctype.holiday_list.test_holiday_list import make_holiday_list
from hrms.payroll.doctype.salary_component.test_salary_component import create_salary_component

# Create employee
employee = make_employee("test@example.com", company="_Test Company")

# Create holiday list
holiday_list = make_holiday_list(
	"TestList",
	holiday_dates=[
		{"holiday_date": "2026-01-01", "description": "New Year"},
	],
)

# Create salary component
salary_component = create_salary_component("Test Component")
```

### Assertions

**Common patterns:**

```python
# Equality
self.assertEqual(advance.paid_amount, 1000)
self.assertEqual(advance.status, "Paid")

# Boolean
self.assertTrue(is_holiday(employee.name))
self.assertFalse(is_holiday(employee.name, date=past_date))

# Exception
self.assertRaises(EmployeeAdvanceOverPayment, journal_entry.submit)

# Membership
self.assertIn("Subject: Birthday Reminder", email_message)
self.assertTrue("test@example.com" in recipients)

# None/Empty
self.assertIsNone(value)
self.assertEqual(len(email_queue), 0)
```

### Test Decorators

**@change_settings decorator:** Temporarily override settings

```python
from frappe.tests import change_settings

@change_settings({"salary_component_name": "Custom Component"})
def test_with_setting():
	# Test runs with the setting changed
	# Automatically restored after test
	pass
```

---

## Frontend Testing

### Current State

**Status:** Frontend tests not currently implemented in main codebase.

**QA Testing:** Manual testing via Chrome DevTools MCP (documented in `.claude/skills/qa-testing/`)

**Test Scripts:** Available in `.claude/skills/qa-testing/scripts/test_runner.py`

### Recommended Frontend Testing Setup

#### Testing Framework Recommendations

| Framework | Use Case | Status |
|-----------|----------|--------|
| Vitest | Vue component unit tests | Not configured |
| Playwright/Cypress | E2E browser automation | Not configured |
| Testing Library | Component integration tests | Not configured |

#### Component Unit Testing (Vitest)

**Recommended pattern for Vue components:**

```javascript
// frontend/src/components/__tests__/AttendanceCalendar.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AttendanceCalendar from '../AttendanceCalendar.vue'

describe('AttendanceCalendar', () => {
	let wrapper

	beforeEach(() => {
		wrapper = mount(AttendanceCalendar, {
			props: {
				events: []
			},
			global: {
				mocks: {
					__: (text) => text // Mock i18n
				}
			}
		})
	})

	it('renders calendar structure', () => {
		expect(wrapper.find('.grid').exists()).toBe(true)
	})

	it('navigates to next month', async () => {
		const nextButton = wrapper.find('button[icon="chevron-right"]')
		await nextButton.trigger('click')
		// Assert month changed
	})

	it('displays summary statistics', () => {
		expect(wrapper.text()).toContain('Present')
	})
})
```

#### E2E Testing Pattern (Playwright/Cypress)

**Recommended pattern:**

```javascript
// frontend/e2e/attendance.spec.js
import { test, expect } from '@playwright/test'

test('User can view attendance calendar', async ({ page }) => {
	await page.goto('/dashboard/attendance')
	await expect(page.locator('text=Attendance Calendar')).toBeVisible()
})

test('Calendar navigation works', async ({ page }) => {
	await page.goto('/dashboard/attendance')
	const nextButton = page.locator('button:has-text(">")')
	await nextButton.click()
	// Verify month changed
})
```

---

## Test Structure

### Python Test Directory Layout

```
hrms/
├── hr/
│   └── doctype/
│       ├── employee_advance/
│       │   ├── employee_advance.py
│       │   ├── employee_advance.js
│       │   ├── employee_advance.json
│       │   └── test_employee_advance.py  ← Test file
│       └── attendance/
│           └── test_attendance.py
│
├── payroll/
│   └── doctype/
│       ├── salary_structure/
│       │   └── test_salary_structure.py
│       └── salary_slip/
│           └── test_salary_slip.py
│
└── controllers/
    └── tests/
        ├── __init__.py
        ├── test_employee_reminders.py
        └── test_other_controller.py
```

**Naming conventions:**
- Test files: `test_*.py` (prefix with `test_`)
- Test classes: `Test<DocTypeName>` (inherit from `IntegrationTestCase`)
- Test methods: `test_<scenario_description>()` (describe the specific scenario)

### Test Isolation

**Patterns to ensure tests don't interfere:**

```python
def setUp(self):
	# Clean database before each test
	frappe.db.delete("Employee Advance")
	frappe.db.sql("delete from `tabEmail Queue`")
	frappe.db.sql("delete from `tabEmail Queue Recipient`")

	# Reset settings to defaults
	frappe.db.set_value(
		"Account",
		"Employee Advances - _TC",
		"account_type",
		"Receivable"
	)
```

**Use test company:** Prefix with `_Test` or `_TC`

```python
test_company = "_Test Company"
test_employee = make_employee("test@email.com", company="_Test Company")
```

---

## Mocking Patterns

### Mocking External APIs (Python)

**Pattern: Mock HTTP requests**

```python
import frappe
from unittest.mock import patch, MagicMock

class TestGoogleIntegration(IntegrationTestCase):
	@patch("requests.get")
	def test_search_drive_files_success(self, mock_get):
		# Mock the response
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.json.return_value = {
			"files": [
				{"id": "123", "name": "test.xlsx"}
			]
		}
		mock_get.return_value = mock_response

		# Call function
		result = search_drive_files("test")

		# Assert
		self.assertTrue(result["success"])
		mock_get.assert_called_once()
```

### Mocking Frappe Operations (Python)

```python
@patch("frappe.db.get_value")
def test_cycle_count_with_mocked_stock(self, mock_get_value):
	# Mock stock lookup
	mock_get_value.return_value = 100  # System qty

	# Call function
	result = submit_cycle_count("STORE001", [{"item_code": "SKU001", "counted_qty": 95}])

	# Assert variance calculated correctly
	self.assertEqual(result["total_variance"], 5)
```

### Mocking Vue Components (Frontend - if implemented)

```javascript
import { vi } from 'vitest'

// Mock Frappe API calls
vi.mock('frappe-ui', () => ({
	FrappeUI: {},
	useToast: () => ({
		toast: vi.fn()
	})
}))

// Mock router
const mockRouter = {
	push: vi.fn(),
	back: vi.fn()
}
```

---

## Test Coverage

### Coverage Analysis

**Tools:** Ruff (linting) + manual review

**Current coverage:** No automated coverage reporting configured

**Recommended approach:**

```bash
# If using pytest coverage
pytest --cov=hrms --cov-report=html

# Generate coverage report
# View in htmlcov/index.html
```

### Coverage Goals

| Module | Target | Notes |
|--------|--------|-------|
| API endpoints | 80%+ | Critical user-facing code |
| DocType logic | 70%+ | Core business logic |
| Utilities | 70%+ | Reusable functions |
| Controllers | 60%+ | Base functionality |

### Critical Paths to Test

1. **API Endpoints** (`hrms/api/`)
   - Authentication checks (`has_valid_token()`)
   - Input validation
   - Error responses
   - Success responses

2. **DocType Submit/Cancel Logic**
   - State transitions
   - Field validations
   - Child table handling
   - Journal entry generation

3. **Google OAuth Integration**
   - Token exchange
   - Token refresh
   - Failure scenarios (401, 403, timeout)

4. **Inventory Operations**
   - Stock variance calculations
   - Bin updates
   - Multi-store scenarios

---

## Running Tests

### Frappe Test Command

```bash
# Run all tests in site
bench test-site

# Run tests for specific app
bench --site site_name test-site --app hrms

# Run specific test file
bench --site site_name test-site --doctype "Employee Advance"

# Run with verbose output
bench test-site --verbose
```

### Test Execution Flow

```bash
# 1. Create temporary test database (_test_db)
# 2. Load schema and fixtures
# 3. Run setUpClass() for each test class
# 4. For each test method:
#    - Run setUp()
#    - Run test_method()
#    - Run tearDown()
# 5. Run tearDownClass()
# 6. Drop test database
```

### Manual Testing (QA)

**Location:** `.claude/skills/qa-testing/scripts/test_runner.py`

**Available test flows:**
- Leave request approval workflow
- Employee clearance process
- Expense claim submission
- Salary slip retrieval
- Profile updates

**Run with:**
```bash
python .claude/skills/qa-testing/scripts/test_runner.py --help
```

---

## Test Data and Fixtures

### Using Test Companies and Employees

```python
# Use standard Frappe test company
TEST_COMPANY = "_Test Company"
TEST_EMPLOYEE = make_employee("test@example.com", company=TEST_COMPANY)

# Create related test docs
TEST_ACCOUNT = create_account(
	account_name="Test Account",
	company=TEST_COMPANY
)
```

### Fixture Pattern

```python
@classmethod
def setUpClass(cls):
	super().setUpClass()
	# Create reusable test data once
	cls.employees = [
		make_employee(f"emp{i}@test.com", company="_Test Company")
		for i in range(5)
	]
	cls.holiday_list = make_holiday_list("TestList", holiday_dates=[...])
```

### Cleanup Pattern

```python
def tearDown(self):
	# Explicit cleanup
	frappe.db.delete("Employee Advance")

	# Reset settings
	frappe.set_value(
		"Company",
		"_Test Company",
		"field_name",
		"default_value"
	)
```

---

## Common Test Scenarios

### Testing Database State Changes

```python
def test_state_transition(self):
	# Before
	doc = frappe.new_doc("Employee Advance")
	doc.employee = employee
	doc.insert()
	self.assertEqual(doc.status, "Draft")

	# Action
	doc.submit()

	# After - must reload to get DB state
	doc.reload()
	self.assertEqual(doc.status, "Submitted")
```

### Testing Calculations

```python
def test_variance_calculation(self):
	result = submit_cycle_count("STORE", [{
		"item_code": "SKU001",
		"counted_qty": 95,
		"item_price": 100
	}])

	# System qty assumed to be 100
	# Variance qty = 95 - 100 = -5
	# Variance value = -5 * 100 = -500
	self.assertEqual(result["total_variance"], -500)
```

### Testing List Queries

```python
def test_get_filtered_records(self):
	# Create test data
	make_employee_advance(emp1, 1000)
	make_employee_advance(emp1, 500)
	make_employee_advance(emp2, 2000)

	# Query
	result = get_cycle_counts(store="STORE1", status="Submitted")

	# Should return filtered subset
	self.assertEqual(len(result["counts"]), 2)
```

### Testing Error Conditions

```python
def test_missing_required_field(self):
	with self.assertRaises(frappe.ValidationError) as ctx:
		result = submit_cycle_count(store=None, items=[])

	self.assertIn("Store is required", str(ctx.exception))
```

---

## Performance Testing Notes

**Currently not implemented**

**Recommendations:**
- Load test: Monitor response times with multiple concurrent requests
- Database query profiling: Check N+1 query problems
- Memory profiling: For long-running processes
- Code coverage: Aim for 80%+ on critical paths

---

## Continuous Integration

**Pipeline:** GitHub Actions (not currently configured for test runs)

**Recommended setup:**

```yaml
name: Tests
on: [push, pull_request]

jobs:
	test:
		runs-on: ubuntu-latest
		steps:
			- uses: actions/checkout@v3
			- name: Run Frappe tests
			  run: bench test-site --app hrms
```

---

## Known Limitations

1. **Frontend testing:** No automated unit or E2E tests configured
2. **Coverage reporting:** No coverage metrics tracked
3. **API testing:** Limited test coverage for Google OAuth integration
4. **Load testing:** No performance benchmarks
5. **Mocking:** Limited use of mocks for external services

---

## Future Recommendations

1. Set up Vitest for Vue component unit tests
2. Implement Playwright for critical E2E flows
3. Add coverage tracking to CI/CD pipeline
4. Create shared test fixtures library
5. Document common test data patterns
6. Add performance regression tests for critical paths

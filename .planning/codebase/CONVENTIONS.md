# Coding Conventions

This document outlines the code style, naming patterns, and architectural conventions used throughout the BEI ERP codebase.

## Table of Contents

1. [Python Backend (Frappe/HRMS)](#python-backend)
2. [Vue 3 / Ionic Frontend](#vue-frontend)
3. [Error Handling](#error-handling)
4. [Documentation](#documentation)
5. [Naming Conventions](#naming-conventions)

---

## Python Backend

### File Organization

**Location:** `hrms/` directory
**Key modules:**
- `hrms/api/` - Whitelisted API endpoints
- `hrms/utils/` - Utility functions
- `hrms/hr/doctype/*/` - DocType definitions and logic
- `hrms/payroll/` - Payroll-related functionality
- `hrms/controllers/` - Base controllers and mixins

### Code Style

**Configuration:** `pyproject.toml`

```toml
[tool.ruff]
line-length = 110
target-version = "py310"

[tool.ruff.format]
quote-style = "double"
indent-style = "tab"
docstring-code-format = true
```

**Key Rules:**
- Line length: 110 characters
- String quotes: double quotes (`"`)
- Indentation: tabs (NOT spaces)
- Python 3.10+ required
- Linting tools: Ruff (lint + format combined)

### Import Organization

**Order:** Enforced by isort configuration in `pyproject.toml`:

```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import json
import os
import re
import time

# 3. Third-party
import frappe
import requests

# 4. Frappe framework
from frappe import _
from frappe.utils import nowdate, flt

# 5. ERPNext
from erpnext.accounts.doctype.account.test_account import create_account

# 6. HRMS (custom project)
from hrms.utils.google_oauth import (
	get_valid_access_token,
	has_valid_token,
)

# 7. First-party (other modules in project)
# 8. Local folder relative imports
```

### API Endpoint Pattern

**Location:** `hrms/api/*.py`
**Structure:** Whitelisted functions exposed via `@frappe.whitelist()` decorator

**Example from `hrms/api/hello.py`:**

```python
# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
Module docstring describing purpose.

Flow:
1. Step 1 description
2. Step 2 description
"""

from __future__ import annotations

import frappe

BUILD_VERSION = "2026-01-29T12:16:00+08:00"


@frappe.whitelist(allow_guest=True)
def hello() -> dict:
	"""Return hello world message.

	Accessible without login for testing purposes.

	Returns:
		dict: Message and timestamp
	"""
	return {
		"message": "Hello from Frappe HRMS!",
		"timestamp": frappe.utils.now(),
		"build_version": BUILD_VERSION,
	}
```

**Conventions:**
- Module docstring with flow description
- Function docstring with `Args`, `Returns`, and `Raises` sections
- Type hints on return values (`-> dict`)
- Explicit `allow_guest=True` when endpoint is public
- Constants in UPPER_SNAKE_CASE at module level

### Database Operations

**Pattern:** Use Frappe ORM for type safety

```python
# ✓ Good
filters = {"store": store, "status": status}
counts = frappe.get_all(
	"BEI Cycle Count",
	filters=filters,
	fields=["name", "store", "count_date"],
	order_by="count_date desc",
	limit=int(limit)
)

# Get single value
value = frappe.db.get_value("Item", item_code, "valuation_rate") or 0

# Create new doc
doc = frappe.new_doc("BEI Cycle Count")
doc.store = store
doc.count_date = nowdate()
```

**Key practices:**
- Use dictionary filters over raw SQL when possible
- Cast limit/count to int explicitly
- Use `or` for default values on None results
- Use `frappe.new_doc()` for creating documents
- Append child table rows with `doc.append(fieldname, {row_data})`

### Type Hints

**Pattern:** Used on return types and complex function signatures

```python
def login_with_google(code: str, redirect_uri: str):
	"""Login with Google OAuth."""
	# Return type not specified - inferred from docstring
	...

def search_drive_files(
	query: str = "",
	folder_id: str | None = None,
	page_token: str | None = None
) -> dict:
	"""Search Google Drive files."""
	...
```

**Practices:**
- Use `|` syntax for unions (Python 3.10+)
- Document return types in docstrings
- Use `str | None` not `Optional[str]`

---

## Vue 3 / Ionic Frontend

### File Organization

**Location:** `frontend/src/`

```
frontend/src/
├── components/       # Reusable Vue components
├── views/           # Page components (routed)
├── router/          # Vue Router configuration
├── composables/     # Composition API hooks
├── utils/           # Utility functions
├── App.vue          # Root component
└── main.js          # Entry point
```

### Code Style

**Configuration:** `.eslintrc.js` and `.prettierrc.json`

```json
{
	"semi": false,
	"tabWidth": 2,
	"useTabs": true
}
```

**Linting Rules:**
- Vue 3 essential rules
- ESLint recommended
- Prettier integration
- Tabs for indentation (2-width tab stop)
- No semicolons

### Component Structure

**Pattern:** Vue 3 `<script setup>` with Composition API

```vue
<template>
	<div class="flex flex-col w-full gap-5" v-if="calendarEvents.data">
		<div class="text-lg text-gray-800 font-bold">{{ __("Attendance Calendar") }}</div>

		<!-- Content -->
	</div>
</template>

<script setup>
import { onMounted, ref, computed } from "vue"
import { Button } from "frappe-ui"

// Props
const props = defineProps({
	doctype: String,
	id: String,
})

// State
const activeTab = ref("tab1")
const firstOfMonth = ref(dayjs())

// Computed
const summary = computed(() => {
	// Logic
	return {}
})

// Lifecycle
onMounted(() => {
	// Initialize
})

// Methods
function handleClick() {
	// Handler
}
</script>

<style scoped>
/* Component-specific styles using Tailwind classes (inline preferred) */
</style>
```

**Conventions:**
- Use `<script setup>` (implicit expose of all top-level bindings)
- Import components from `frappe-ui` or Ionic
- Use `ref()` for reactive state, `computed()` for derived values
- Use `__()` function for i18n translation (from Frappe)
- Inline Tailwind classes preferred over scoped styles

### Component Naming

- PascalCase for file names and component names
- File name matches component name
- Single component per file (except related helpers)

**Examples:**
- `AttendanceCalendar.vue` - `<AttendanceCalendar />`
- `FormField.vue` - `<FormField />`
- `CheckInPanel.vue` - `<CheckInPanel />`

### Router Configuration

**Location:** `frontend/src/router/index.js`

```javascript
const routes = [
	{
		path: "/",
		redirect: "/home",
	},
	{
		path: "/",
		component: TabbedView,
		children: [
			{
				path: "/home",
				name: "Home",
				component: () => import("@/views/Home.vue"),
			},
		],
	},
]

const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes,
})

export default router
```

**Conventions:**
- Lazy loading with dynamic `import()`
- Route names in PascalCase
- Nested routes under parent layouts
- Path starts with `/`

### CSS / Styling

**Framework:** Tailwind CSS 3.4.3 (utility-first)
**Plugins:** PostCSS, Autoprefixer

**Conventions:**
- Use Tailwind utility classes directly in templates
- Avoid inline `<style>` blocks when possible
- Scoped styles only for component-specific needs
- Use responsive prefixes: `sm:`, `md:`, `lg:`

**Example:**
```vue
<div class="flex flex-col gap-4 sm:flex-row md:gap-6 lg:p-8">
	<span class="text-gray-800 text-sm font-medium leading-6">
		{{ label }}
	</span>
</div>
```

### Composables (Reusable Logic)

**Location:** `frontend/src/composables/`
**Pattern:** Functions returning reactive state and methods

```javascript
// composables/useAttendance.js
import { ref, computed } from "vue"

export function useAttendance() {
	const attendance = ref([])
	const status = ref("pending")

	const isPresent = computed(() => {
		return attendance.value.some(a => a.status === "Present")
	})

	async function fetchAttendance() {
		// Fetch logic
	}

	return {
		attendance,
		status,
		isPresent,
		fetchAttendance,
	}
}

// Usage in component
import { useAttendance } from "@/composables"

export default {
	setup() {
		const { attendance, isPresent, fetchAttendance } = useAttendance()
		return { attendance, isPresent, fetchAttendance }
	}
}
```

---

## Error Handling

### Python Error Patterns

**User-facing errors:** Use `frappe.throw()`

```python
if not store:
	frappe.throw(_("Store is required"))

if not code:
	return {"success": False, "error": "Authorization code is required"}
```

**Logging errors:** Use `frappe.log_error()`

```python
try:
	access_token = get_valid_access_token(user)
except frappe.AuthenticationError as e:
	return {"success": False, "error": str(e), "needs_auth": True}
except Exception as e:
	frappe.log_error(
		title="Google Drive Token Error",
		message=f"User: {user}, Error: {str(e)}"
	)
	return {"success": False, "error": "Failed to get access token"}
```

**Response Pattern:** Return dict with `success` and optional `error` fields

```python
return {
	"success": True,
	"name": doc.name,
	"total_variance": total_variance,
}

# or

return {
	"success": False,
	"error": "User not authenticated",
	"needs_auth": True
}
```

### Frontend Error Patterns

**API error handling:**

```javascript
try {
	const response = await frappe.call({
		method: "hrms.api.inventory.submit_cycle_count",
		args: { store, items },
	})
	if (response.message.success) {
		// Handle success
	}
} catch (error) {
	console.error("Cycle count failed:", error)
	// Show toast/notification
}
```

### Validation Patterns

**Pre-condition validation:**

```python
if not store or not item_code:
	frappe.throw(_("Store and item are required"))

if isinstance(items, str):
	items = json.loads(items)
```

---

## Documentation

### Module Docstrings

**Required for:** API modules, utility modules
**Format:** Module-level docstring with flow description

```python
"""
Google OAuth Login Handler

This endpoint handles Google OAuth login while capturing and storing
the OAuth tokens for later use (Google Chat, Drive integration).

Flow:
1. Exchange authorization code for tokens
2. Get user info from Google
3. Find/create Frappe user
4. Store OAuth tokens in User OAuth Token doctype
5. Establish Frappe session
"""
```

### Function Docstrings

**Format:** Google-style docstrings

```python
def submit_cycle_count(store, items):
	"""Submit inventory cycle count.

	Args:
		store: Warehouse/store name
		items: List of {item_code, counted_qty, remarks}

	Returns:
		dict: {success, name, total_variance}

	Raises:
		frappe.ValidationError: If store or items are invalid
	"""
```

### Comments

**Usage:** Explain WHY, not WHAT

```python
# ✓ Good - explains intent
# NOTE: Don't log the auth code. It is sensitive and short-lived.
ru = urlparse(redirect_uri)

# ✗ Bad - describes obvious code
# Set the store field to store
doc.store = store
```

---

## Naming Conventions

### Python

| Category | Pattern | Example |
|----------|---------|---------|
| Module names | `snake_case` | `google_oauth.py`, `employee_clearance.py` |
| Function names | `snake_case` | `get_valid_access_token()`, `submit_cycle_count()` |
| Class names | `PascalCase` | `EmployeeAdvanceOverPayment`, `TestEmployeeAdvance` |
| Constants | `UPPER_SNAKE_CASE` | `BUILD_VERSION`, `_DEFAULT_ALLOWED_DOMAINS` |
| Private functions | `_snake_case` prefix | `_fetch_space_memberships()`, `_agent_log()` |
| Database fields | `snake_case` | `store`, `counted_qty`, `variance_value` |

### Vue / JavaScript

| Category | Pattern | Example |
|----------|---------|---------|
| File names | `PascalCase.vue` | `AttendanceCalendar.vue`, `FormView.vue` |
| Component names | `PascalCase` | `<AttendanceCalendar />`, `<FormField />` |
| Variable names | `camelCase` | `activeTab`, `firstOfMonth`, `calendarEvents` |
| Constants | `UPPER_SNAKE_CASE` | `DAYS`, `DEFAULT_ROLES` |
| Composable names | `useXxxx` | `useAttendance()`, `useRouter()` |
| Method names | `camelCase` | `handleClick()`, `fetchData()` |
| Event handlers | `handleXxxx` or `onXxxx` | `handleDelete()`, `onMounted()` |

### Database / Frappe

| Category | Pattern | Example |
|----------|---------|---------|
| DocType names | `PascalCase` with spaces | `BEI Cycle Count`, `Employee Clearance` |
| Field names | `snake_case` | `store`, `variance_qty`, `counted_by` |
| Custom field names | `custom_` prefix | (auto-generated by Frappe) |

---

## Key Dependencies

### Frontend

- **Vue:** 3.5.12 (Composition API)
- **Ionic Vue:** 7.4.3 (Mobile components)
- **Frappe UI:** 0.1.105 (Frappe integration components)
- **Tailwind CSS:** 3.4.3 (utility styling)
- **Vite:** 5.4.10 (build tool)
- **Firebase:** 10.8.0 (push notifications)

### Backend

- **Frappe:** >=15.0.0,<16.0.0
- **ERPNext:** >=15.0.0,<16.0.0
- **Python:** >=3.10
- **Ruff:** for linting and formatting

---

## Architectural Patterns

### API Endpoint Pattern

1. Accept JSON payload (auto-converted by Frappe)
2. Validate inputs with `frappe.throw()` for errors
3. Execute business logic
4. Return dict with `success` boolean
5. Log errors with `frappe.log_error()`

### Component Pattern (Vue)

1. Define props for inputs
2. Use `ref()` for mutable state
3. Use `computed()` for derived values
4. Use Composition API hooks for lifecycle
5. Emit events for parent communication
6. Use Tailwind classes directly in template

### Test Pattern (Python)

- Inherit from `IntegrationTestCase`
- Use `setUpClass()` for setup, `setUp()` for isolation
- Use `frappe.db` for cleanup
- Use descriptive test method names `test_xxx_scenario()`
- Use `self.assertEqual()`, `self.assertTrue()` assertions

---

## Performance Notes

- Frontend: Lazy load routes with `import()` in Vue Router
- Backend: Use `frappe.get_all()` with specific fields to minimize data
- Database: Index commonly filtered fields
- Caching: Use Frappe's built-in caching for repeated queries

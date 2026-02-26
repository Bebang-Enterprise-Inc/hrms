# Research: Hello World API Endpoint

## Summary

This research documents how to add API endpoints in the Frappe HRMS project and identifies quality commands for testing/linting.

---

## 1. API Endpoint Patterns

### Location
API files are in `hrms/api/` directory.

### Pattern: `@frappe.whitelist()` Decorator

All public API endpoints use the `@frappe.whitelist()` decorator. This makes the function callable via HTTP.

**Minimal Example (from `hrms/api/__init__.py`):**
```python
import frappe

@frappe.whitelist()
def get_current_user_info() -> dict:
    current_user = frappe.session.user
    user = frappe.db.get_value(
        "User", current_user, ["name", "first_name", "full_name", "user_image"], as_dict=True
    )
    user["roles"] = frappe.get_roles(current_user)
    return user
```

### Existing API Files

| File | Purpose | Notable Patterns |
|------|---------|------------------|
| `__init__.py` | Core HRMS APIs (employee, attendance, leaves) | 40+ whitelisted functions |
| `onboarding.py` | QR-based onboarding sessions | Returns `{success: bool, data/error}` pattern |
| `enrichment.py` | Employee data verification | SQL queries, role-based access |
| `oauth.py` | OAuth token management | Google Workspace integration |
| `google_chat.py` | Google Chat webhooks | Service account auth |
| `google_drive.py` | Drive file access | Domain-wide delegation |
| `mcp.py` | MCP tool endpoints | Claude Code integration |

### URL Convention

API endpoints are accessed via:
```
POST /api/method/hrms.api.<module>.<function_name>
```

Example:
```
POST /api/method/hrms.api.get_current_user_info
POST /api/method/hrms.api.onboarding.create_session
```

### Return Patterns

Two patterns observed:

1. **Direct return** (simpler endpoints):
   ```python
   @frappe.whitelist()
   def get_hr_settings() -> dict:
       return frappe._dict(allow_employee_checkin=True)
   ```

2. **Success/error envelope** (complex endpoints like `onboarding.py`):
   ```python
   @frappe.whitelist()
   def get_session(token: str) -> Dict[str, Any]:
       if not token:
           return {"success": False, "error": "Token required", "code": "MISSING_TOKEN"}
       return {"success": True, "data": {...}}
   ```

---

## 2. Quality Commands

### Package Scripts (`package.json`)

| Command | Description |
|---------|-------------|
| `yarn dev-pwa` | Run frontend dev server |
| `yarn build` | Build both PWA and roster |
| `yarn build-pwa` | Build PWA only |

### Pre-commit Hooks (`.pre-commit-config.yaml`)

| Hook | Tool | Purpose |
|------|------|---------|
| `ruff` | Linter | Python linting with auto-fix |
| `ruff-format` | Formatter | Python code formatting |
| `prettier` | Formatter | JS/TS/Vue/CSS formatting |
| `trailing-whitespace` | Check | Remove trailing whitespace |
| `check-ast` | Check | Validate Python syntax |
| `check-merge-conflict` | Check | Detect merge conflict markers |
| `no-commit-to-branch` | Check | Block direct commits to develop |

### Run Pre-commit Locally
```bash
pre-commit run --all-files
```

### CI/CD Workflows (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR + daily | Python unit tests with coverage |
| `linters.yml` | PR | Pre-commit + Semgrep security |
| `build_image.yml` | Manual/release | Docker image build |
| `deploy-aws.yml` | Manual | AWS deployment |

### Test Commands

```bash
# Run all tests (in bench context)
bench --site test_site run-tests --app hrms

# Run parallel tests
bench --site test_site run-parallel-tests --app hrms

# Python syntax check
python -m compileall -f .

# Ruff lint check
ruff check hrms/

# Ruff format check
ruff format --check hrms/
```

---

## 3. Recommended Implementation

### File Location
Create: `hrms/api/hello.py`

### Minimal Implementation
```python
"""Hello World API - test endpoint for Smart Ralph workflow."""
import frappe

@frappe.whitelist(allow_guest=True)
def hello() -> dict:
    """Return hello world message.

    Accessible without login for testing purposes.
    """
    return {
        "message": "Hello from Frappe HRMS!",
        "timestamp": frappe.utils.now(),
    }
```

### URL
```
POST /api/method/hrms.api.hello.hello
GET  /api/method/hrms.api.hello.hello  # also works for whitelisted
```

### Optional: Authenticated Version
```python
@frappe.whitelist()
def hello_authenticated() -> dict:
    """Return hello with user context."""
    return {
        "message": "Hello, " + frappe.session.user,
        "timestamp": frappe.utils.now(),
    }
```

---

## 4. Quality Checklist

Before merging:
- [ ] Run `pre-commit run --all-files`
- [ ] Run `ruff check hrms/api/hello.py`
- [ ] Test endpoint manually via curl/Postman
- [ ] Verify no secrets/credentials in code

---

## Sources

| File | Lines Referenced |
|------|------------------|
| `hrms/api/__init__.py` | 1-100 (patterns) |
| `hrms/api/onboarding.py` | 1-100 (envelope pattern) |
| `hrms/api/enrichment.py` | 1-50 (clean example) |
| `.pre-commit-config.yaml` | All (hooks) |
| `.github/workflows/ci.yml` | All (test commands) |
| `.github/workflows/linters.yml` | All (lint commands) |
| `pyproject.toml` | All (ruff config) |
| `package.json` | All (scripts) |

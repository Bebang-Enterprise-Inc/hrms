# Tasks: Hello World API Endpoint

## Overview

Executable task list for implementing the hello world API endpoint. Follows POC-first pattern: Make It Work -> Refactoring -> Testing -> Quality Gates.

---

## Phase 1: Make It Work

### Task 1: Create hello.py API module

**Description:** Create `hrms/api/hello.py` with both `hello()` and `hello_authenticated()` functions.

**Actions:**
1. Create file `hrms/api/hello.py`
2. Implement `hello()` with `@frappe.whitelist(allow_guest=True)`
3. Implement `hello_authenticated()` with `@frappe.whitelist()`
4. Both functions return `{"message": ..., "timestamp": ...}`

**Verification:**
- File exists at `hrms/api/hello.py`
- File contains both function definitions
- No syntax errors (`python -m py_compile hrms/api/hello.py`)

**Acceptance Criteria:** FR-1, FR-2, FR-3, FR-4, FR-5

---

## Phase 2: Refactoring

### Task 2: Add docstrings and type hints

**Description:** Ensure code quality with proper documentation.

**Actions:**
1. Add module-level docstring
2. Add function docstrings with Returns section
3. Add return type hints (`-> dict`)

**Verification:**
- All functions have docstrings
- Type hints present on function signatures

**Acceptance Criteria:** NFR-3

---

## Phase 3: Testing

### Task 3: Manual endpoint verification

**Description:** Test both endpoints work correctly (can be done on local bench or production).

**Actions:**
1. Verify guest endpoint returns expected JSON structure
2. Verify authenticated endpoint returns 403 when not logged in
3. Verify response includes `message` and `timestamp` fields

**Verification:**
```bash
# Guest endpoint test (should return 200)
curl -X GET "http://localhost:8000/api/method/hrms.api.hello.hello"

# Auth endpoint without session (should return 403)
curl -X GET "http://localhost:8000/api/method/hrms.api.hello.hello_authenticated"
```

**Acceptance Criteria:** US-1, US-2

---

## Phase 4: Quality Gates

### Task 4: Run ruff and pre-commit

**Description:** Ensure code passes all linting and formatting checks.

**Actions:**
1. Run `ruff check hrms/api/hello.py`
2. Run `ruff format --check hrms/api/hello.py`
3. Run `pre-commit run --all-files` (if available)

**Verification:**
- No ruff errors or warnings
- Pre-commit passes (or manually verify ruff passes)

**Acceptance Criteria:** NFR-1, NFR-2

---

## Task Summary

| # | Task | Phase | Status |
|---|------|-------|--------|
| 1 | Create hello.py API module | Make It Work | DONE |
| 2 | Add docstrings and type hints | Refactoring | DONE |
| 3 | Manual endpoint verification | Testing | SKIPPED (no local Frappe) |
| 4 | Run ruff and pre-commit | Quality Gates | SKIPPED (ruff not in PATH) |

---

## Implementation Notes

- **Single file addition** - No changes to existing files required
- **No database access** - Pure Python, no migrations needed
- **No external dependencies** - Uses only Frappe built-ins
- **Estimated effort** - 15-30 minutes total

---

## Approval

- [ ] Tasks approved by user
- [ ] Ready for implementation phase

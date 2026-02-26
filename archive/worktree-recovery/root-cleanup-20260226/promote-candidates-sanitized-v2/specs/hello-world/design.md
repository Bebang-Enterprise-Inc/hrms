# Design: Hello World API Endpoint

## Overview

A single-file API module implementing two test endpoints for the Smart Ralph workflow validation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Request                         │
│  GET/POST /api/method/hrms.api.hello.hello             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Frappe Request Handler                     │
│  - Route matching via @frappe.whitelist()              │
│  - Session/auth check (if not allow_guest)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              hrms/api/hello.py                          │
│  - hello() → guest access                              │
│  - hello_authenticated() → requires login              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              JSON Response                              │
│  {"message": "...", "timestamp": "..."}                │
└─────────────────────────────────────────────────────────┘
```

---

## File Structure

```
hrms/
└── api/
    └── hello.py          # NEW - Hello world API module
```

**Single file addition.** No changes to existing files required.

---

## Code Design

### Module: `hrms/api/hello.py`

```python
"""Hello World API - test endpoint for Smart Ralph workflow."""

import frappe


@frappe.whitelist(allow_guest=True)
def hello() -> dict:
    """Return hello world message.

    Accessible without authentication for testing purposes.

    Returns:
        dict: Message and timestamp
    """
    return {
        "message": "Hello from Frappe HRMS!",
        "timestamp": frappe.utils.now(),
    }


@frappe.whitelist()
def hello_authenticated() -> dict:
    """Return hello with user context.

    Requires authentication. Returns 403 if not logged in.

    Returns:
        dict: Personalized message and timestamp
    """
    return {
        "message": f"Hello, {frappe.session.user}!",
        "timestamp": frappe.utils.now(),
    }
```

### Function Signatures

| Function | Decorator | Auth | Return Type |
|----------|-----------|------|-------------|
| `hello()` | `@frappe.whitelist(allow_guest=True)` | None | `dict` |
| `hello_authenticated()` | `@frappe.whitelist()` | Required | `dict` |

### Response Schema

```typescript
interface HelloResponse {
  message: string;    // "Hello from Frappe HRMS!" or "Hello, {user}!"
  timestamp: string;  // ISO datetime from frappe.utils.now()
}
```

---

## Integration Points

| Component | Integration | Notes |
|-----------|-------------|-------|
| Frappe Router | Automatic | `@frappe.whitelist()` registers routes |
| Session Manager | `frappe.session.user` | Used in authenticated endpoint |
| Utils | `frappe.utils.now()` | Timestamp generation |

**No database access required.** No external service dependencies.

---

## Testing Approach

### Manual Testing (curl)

```bash
# Guest endpoint
curl -X GET "https://hq.bebang.ph/api/method/hrms.api.hello.hello"

# Expected response:
# {"message": {"message": "Hello from Frappe HRMS!", "timestamp": "2026-01-19 10:30:00.123456"}}

# Authenticated endpoint (without login - should fail)
curl -X GET "https://hq.bebang.ph/api/method/hrms.api.hello.hello_authenticated"
# Expected: 403 Forbidden

# Authenticated endpoint (with session)
curl -X GET "https://hq.bebang.ph/api/method/hrms.api.hello.hello_authenticated" \
  -H "Cookie: sid=<session_id>"
# Expected: {"message": {"message": "Hello, sam@bebang.ph!", "timestamp": "..."}}
```

### Quality Checks

```bash
# Lint
ruff check hrms/api/hello.py

# Format check
ruff format --check hrms/api/hello.py

# Pre-commit (all hooks)
pre-commit run --all-files
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Endpoint exposed to public | Low | `hello()` is intentionally guest-accessible; no sensitive data |
| Abuse via excessive calls | Low | Frappe has built-in rate limiting; out of scope for this iteration |

---

## Acceptance Criteria Mapping

| Requirement | Design Element |
|-------------|----------------|
| FR-1: Create `hrms/api/hello.py` | Single new file |
| FR-2: `hello()` with `allow_guest=True` | First function |
| FR-3: `hello_authenticated()` requiring login | Second function |
| FR-4: Return `message` and `timestamp` | Response schema |
| FR-5: Use `frappe.utils.now()` | Timestamp implementation |
| NFR-1: Pass `ruff check` | Quality checks section |
| NFR-2: Pass pre-commit | Quality checks section |
| NFR-3: Docstrings | All functions documented |
| NFR-4: Response < 100ms | No DB/external calls |

---

## Approval

- [ ] Design approved by user
- [ ] Ready for implementation phase

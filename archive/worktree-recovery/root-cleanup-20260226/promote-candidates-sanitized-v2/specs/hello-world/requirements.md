# Requirements: Hello World API Endpoint

## Overview

A simple test endpoint to validate the Smart Ralph development workflow and verify Frappe API patterns work correctly.

---

## User Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-1 | As a developer, I want to call a guest-accessible endpoint so I can verify the API is working without authentication | 1. Endpoint returns 200 OK<br>2. Response includes "message" and "timestamp"<br>3. No authentication required |
| US-2 | As a developer, I want to call an authenticated endpoint so I can verify session context works | 1. Returns 403 if not logged in<br>2. Returns user identifier when authenticated<br>3. Response includes "message" and "timestamp" |

---

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Create `hrms/api/hello.py` with API functions | Must |
| FR-2 | Implement `hello()` function with `allow_guest=True` | Must |
| FR-3 | Implement `hello_authenticated()` function requiring login | Should |
| FR-4 | Return JSON with `message` and `timestamp` fields | Must |
| FR-5 | Use `frappe.utils.now()` for timestamp | Must |

---

## Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-1 | Pass `ruff check` linting | Must |
| NFR-2 | Pass `pre-commit` hooks | Must |
| NFR-3 | Include docstrings for all functions | Should |
| NFR-4 | Response time < 100ms | Should |

---

## Out of Scope

- Database operations
- Complex business logic
- Frontend UI
- Unit tests (deferred to future iteration)
- Rate limiting

---

## API Specification

### Guest Endpoint

```
GET/POST /api/method/hrms.api.hello.hello
```

**Response:**
```json
{
  "message": "Hello from Frappe HRMS!",
  "timestamp": "2026-01-19 10:30:00.123456"
}
```

### Authenticated Endpoint

```
GET/POST /api/method/hrms.api.hello.hello_authenticated
```

**Response (authenticated):**
```json
{
  "message": "Hello, sam@bebang.ph!",
  "timestamp": "2026-01-19 10:30:00.123456"
}
```

**Response (unauthenticated):**
```
403 Forbidden
```

---

## Success Criteria

1. Both endpoints callable via curl
2. All pre-commit hooks pass
3. No ruff lint errors
4. Endpoint accessible at documented URLs

---

## Approval

- [ ] Requirements approved by user
- [ ] Ready for design phase

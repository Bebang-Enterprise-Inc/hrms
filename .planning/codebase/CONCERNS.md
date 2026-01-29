# Codebase Concerns & Technical Debt

**Last Scanned:** 2026-01-29
**Scope:** `hrms/`, `frontend/`, Core APIs
**Priority Level:** HIGH - Production issues identified

---

## 🔴 CRITICAL ISSUES

### 1. Git Conflict Files (Unresolved)
**Files:** Multiple conflicted copies from 2026-01-24 sync issue
- `hrms/api/__init__ (DESKTOP-28MNIP8's conflicted copy 2026-01-24).py`
- `frontend/src/router/index (DESKTOP-28MNIP8's conflicted copy 2026-01-24).js`
- `docker-dev/docker-compose (DESKTOP-28MNIP8's conflicted copy 2026-01-24).yml`
- `.git/COMMIT_EDITMSG (DESKTOP-28MNIP8's conflicted copy 2026-01-24)`

**Impact:** Duplicate code in repo, potential confusion during git operations
**Action:** Delete all conflicted files; verify main files are correct

---

### 2. Deleted File Not Properly Handled
**File:** `hrms/utils/page_renderers.py` (marked for deletion)
- **Status:** Staged deletion, not yet committed
- **Dependencies:** Check if any code imports this module
- **Impact:** Code may break if imports not yet removed

**Search Commands:**
```bash
grep -r "page_renderers" f:\Dropbox\Projects\BEI-ERP\hrms --include="*.py"
grep -r "from.*page_renderers\|import.*page_renderers" f:\Dropbox\Projects\BEI-ERP
```

---

### 3. Bare Exception Handlers (14+ instances)
**Location:** `hrms/api/` directory
**Examples:**
- `hrms/api/google_chat.py:37,53,126` - `except Exception: pass`
- `hrms/api/enrichment.py:172-174` - Silent exception swallow
- `hrms/api/supervisor.py:57-58` - `except Exception: pass  # Reference document may not exist`
- `hrms/api/mcp.py:36` - bare `pass`

**Problem:**
- Hides real errors; makes debugging impossible
- User won't know if their action actually succeeded
- May cause cascading failures

**Example from `supervisor.py:48-58`:**
```python
try:
    ref_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)
    if hasattr(ref_doc, 'status'):
        ref_doc.status = "Approved"
        ref_doc.save()
except Exception:
    pass  # Reference document may not exist
```

**Fix:** Log errors, return partial success indicator, or re-raise with context

---

### 4. Missing PDF Generation Implementation
**File:** `hrms/api/employee_clearance.py:656`
```python
# TODO: Generate actual PDF and return URL
```
**Impact:** Clearance PDF endpoint returns stub; users get null response
**Go-Live Risk:** HIGH (clearance workflows blocked without PDFs)

---

### 5. Unimplemented Notification System
**File:** `hrms/hr/doctype/bei_fqi_report/bei_fqi_report.py:29`
```python
# TODO: Send notifications to QA, SCM, AS, RM
```
**Impact:** Quality reports don't alert stakeholders
**Departments Affected:** QA, SCM, Area Supervisor, Regional Manager

---

## 🟠 HIGH-PRIORITY ISSUES

### 6. Raw Database Queries (SQL Injection Risk)
**Location:** `hrms/api/inventory.py` and throughout API files

**Vulnerable Pattern:**
```python
# inventory.py:32-35
system_qty = frappe.db.get_value(
    "Bin",
    {"warehouse": store, "item_code": item["item_code"]},
    "actual_qty"
) or 0
```

**While Frappe ORM is used**, the pattern of building dynamic warehouse/store queries with unvalidated user input could be vulnerable if:
- Store names contain special characters not escaped by Frappe
- Item codes are user-controlled and not validated

**Recommendation:** Add validation layer before all `frappe.db.get_value()` calls

---

### 7. Missing Error Context in API Responses
**Location:** All `@frappe.whitelist()` functions in `hrms/api/`

**Issue:** Most endpoints return generic `{"success": False}` without error detail
```python
# google_drive.py:64
return {"success": False, "error": "Failed to get access token"}
```

**Problem:**
- Frontend can't distinguish between token expired, network error, or auth failure
- Users see unhelpful error messages
- Debugging production issues is difficult

**Affected Functions:** 50+ endpoints

---

### 8. Google OAuth Token Storage Issues (Documented)
**Location:** `hrms/api/oauth_tokens.py`
**Known Issue:** `"Most probably your password is too long"` error
- OAuth tokens stored in encrypted Long Text fields (workaround applied)
- But no validation on token size before storage
- May silently truncate tokens on very long refresh flows

**Risk:** Silent token corruption; user locked out with no error message

---

### 9. Bare Service Account Dependency
**Location:** `credentials/task-manager-service.json` (referenced in Google Chat/Drive APIs)
**Issues:**
- Service account file required for all Google APIs
- No fallback if file missing or corrupted
- No validation on file load
- PEM parsing errors not caught gracefully

**From `hrms/api/google_chat.py:36-39`:**
```python
try:
    log_path = os.path.join(frappe.get_site_path("..", "..", ".cursor"), "debug.log")
except Exception:
    # Fallback for non-site contexts
    log_path = os.path.join(os.getcwd(), ".cursor", "debug.log")
```

**Better Approach:** Validate credentials on startup, not per-request

---

### 10. Large API Files with Single Responsibility Violations
**Files and Concerns:**
- `hrms/api/supervisor.py` (1,319 lines) - Handles: approvals, store visits, labor planning, team management
- `hrms/api/employee_clearance.py` (658 lines) - Handles: clearance workflow, DOLE forms, PDF generation
- `hrms/api/__init__.py` (1,018 lines) - Core routing logic

**Impact:**
- Hard to test individual features
- Side effects between functions unclear
- Onboarding developers is difficult

**Recommendation:** Split into modular files by feature

---

## 🟡 MEDIUM-PRIORITY ISSUES

### 11. Category Name Mapping Fragility
**Location:** `hrms/api/supervisor.py:94-107`
```python
CATEGORY_MAP = {
    "A": "A. Funds",
    "B": "B. Stocks",
    "Funds": "A. Funds",  # Duplicated logic
    "Stocks": "B. Stocks",
}
```

**Issue:**
- Frontend sends short codes or full names; backend normalizes
- If frontend changes naming convention, this breaks silently
- No validation that all categories are properly mapped

**Risk:** Store visit reports saved with wrong category labels

---

### 12. JSON Parsing Without Validation
**Multiple Files:** `inventory.py`, `supervisor.py`, `dispatch.py`

**Pattern:**
```python
if isinstance(items, str):
    items = json.loads(items)  # No try-catch, no schema validation
```

**Issues:**
- Invalid JSON crashes endpoint with 500 error
- No schema validation after parsing
- User sees generic error, not helpful message

**Fix Locations:**
- `inventory.py:22` - cycle count items
- `supervisor.py:121-124` - audit items, photos
- `dispatch.py` - multiple JSON fields

---

### 13. Silent Timestamp Failures
**Location:** `hrms/api/` - Multiple endpoints use `nowdate()` / `now_datetime()`
**Issue:** No validation that timestamps are set correctly
- Timezone-related bugs could cause data inconsistencies
- No logging of timestamp source

---

### 14. Access Control Without Scoping
**Location:** All supervisor approval functions
```python
@frappe.whitelist()
def get_pending_approvals(approver=None):
    if not approver:
        approver = frappe.session.user  # Falls back to current user
```

**Issue:**
- No check that `approver` parameter is actually the current user or their delegate
- Bypass: `?approver=cfo@bebang.ph` might return CFO's approvals for another user

**Fix:** Compare `approver` against `frappe.session.user` and RBAC role

---

### 15. Hardcoded Timeout Values
**Location:** `hrms/api/google_chat.py:99`, `google_drive.py:90`
```python
resp = requests.get(..., timeout=30)
```

**Issues:**
- 30 seconds may be too short for slow networks
- No exponential backoff for retries
- No circuit breaker for cascading failures

---

### 16. Photo Upload Without Size/Type Validation
**Location:** Multiple endpoints accept `photo` parameter
- `employee_clearance.py:495` - `photo_evidence` field
- `inventory.py:103` - `photo_evidence` field
- `supervisor.py:115` - `photos` parameter

**Issues:**
- No file size limit enforced
- No MIME type validation
- No malware scanning before storage
- Disk space exhaustion possible

---

### 17. Missing Audit Trail for Critical Changes
**Location:** All approval endpoints
- No logging of who changed what
- No versioning of approval changes
- Rejected items lose their change history

**Affected:**
- `approve_item()` - Line 42-45
- `reject_item()` - Line 64-74
- `escalate_item()` - Line 79-85

---

### 18. Unvalidated Date Ranges
**Location:** `inventory.py:65-71`
```python
if date_from:
    filters["count_date"] = [">=", date_from]
if date_to:
    if "count_date" in filters:
        filters["count_date"] = ["between", [date_from, date_to]]  # What if date_from > date_to?
```

**Issue:** No validation that date ranges are sensible
- `date_to < date_from` returns empty results silently
- No user feedback

---

### 19. Uncontrolled Database Query Limits
**Location:** All `frappe.get_all()` calls
```python
limit=int(limit)  # No upper bound check
```

**Issue:**
- User can request `?limit=1000000` causing DB strain
- No pagination enforcement for large datasets

**Fix:** Add `limit = min(int(limit), 500)` to all list endpoints

---

### 20. Frappe Inventory Valuation Assumptions
**Location:** `inventory.py:47-48`, `97-98`
```python
item_price = frappe.db.get_value("Item", item["item_code"], "valuation_rate") or 0
row.variance_value = row.variance_qty * item_price
```

**Issues:**
- Assumes `valuation_rate` is always available
- Doesn't account for batch-level pricing
- Doesn't use actual cost of goods, just current rate
- Could cause wrong variance valuations

---

## 🔵 LOWER-PRIORITY ISSUES

### 21. Incomplete TODO Comments
**Locations:**
- `hrms/hr/doctype/leave_encashment/leave_encashment.py:101` - "Remove this weird setting if possible"
- `hrms/payroll/doctype/payroll_period/payroll_period.py:112` - "if both deduct checked update factor"
- `hrms/regional/india/utils.py:129,191` - "make this configurable"

**Impact:** Technical debt accumulating; unclear what's blocking fixes

---

### 22. Convoluted Expense Claim Code
**Location:** `hrms/hr/doctype/expense_claim/expense_claim.py:864`
```python
# TODO: refactor convoluted code after erpnext payment entry becomes extensible
```

**Issue:** Complex business logic that was noted for refactoring but not done

---

### 23. Missing Health Check Endpoints
**Location:** No dedicated health check API
- `hello.py` has a build_version check, but no comprehensive health check
- External monitors have no way to verify all systems are working

---

### 24. Logging Infrastructure Gaps
**Location:** `hrms/api/google_chat.py:30-55` - Custom NDJSON logging to Cursor
**Issues:**
- Logs to local `.cursor/debug.log` instead of centralized logging
- No log rotation
- No structured logging framework
- Difficult to aggregate logs from multiple services

---

### 25. Version Incompatibilities Undocumented
**Frontend:**
- `frontend/package.json` uses various versions without pinning
- Vue 3 PWA (legacy) vs React Next.js (my.bebang.ph) creates maintenance burden

**Backend:**
- Frappe v15 assumed but not documented in requirements
- Regional customizations (India) mixed with BEI customizations

---

## 🚀 RECOMMENDATIONS (Priority Order)

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Delete conflicted files | 5 min | Cleanup git noise |
| 2 | Implement PDF generation stub return (not just TODO) | 2 hrs | Unblock go-live |
| 3 | Add proper exception logging to all `except Exception: pass` blocks | 3 hrs | Visibility into failures |
| 4 | Add request validation middleware (JSON schema, file size, limits) | 4 hrs | Security/stability |
| 5 | Implement comprehensive error responses with context | 6 hrs | Better debugging |
| 6 | Split large API files (`supervisor.py`, `employee_clearance.py`) | 8 hrs | Maintainability |
| 7 | Add audit trail for all approval changes | 4 hrs | Compliance/debugging |
| 8 | Implement health check endpoint | 2 hrs | Production monitoring |
| 9 | Validate OAuth token size on storage | 1 hr | Prevent silent failures |
| 10 | Add RBAC scoping checks to approval endpoints | 2 hrs | Security |

---

## Database & Performance Concerns

### 26. N+1 Query Patterns
**Example:** `inventory.py:30-49` - Loop with DB calls
```python
for item in items:
    system_qty = frappe.db.get_value("Bin", {"warehouse": store, "item_code": item["item_code"]}, "actual_qty")
    item_price = frappe.db.get_value("Item", item["item_code"], "valuation_rate")
```

**Fix:** Pre-fetch all Bins and Items in one query, then loop

---

### 27. Missing Indexes on Foreign Keys
**Concern:** Multiple API endpoints query by `store`, `item_code`, `user`
- If these columns aren't indexed, queries will full-table scan
- Database performance will degrade with scale

**Action:** Review database schema migration files for index creation

---

## Deployment & Infrastructure

### 28. Docker Volume Attachment Issue (Resolved but Risk Remains)
**Status:** Resolved (2026-01-26 audit complete)
- **Root Cause:** Database wipe, not volume disconnection
- **Recovery:** Backups exist
- **Risk:** Future deployments could have similar issues if volume management isn't automated

**Reference:** `progress/DOCKER_VOLUME_AUDIT_2026-01-26.md`

---

## Testing Gaps

### 29. Missing Unit Test Coverage
**API Layer:** No dedicated test files for `hrms/api/` endpoints
**Concern:**
- Each API has ~50 lines of code but no unit tests
- Integration tests may exist in `test_*.py` files but not discovered
- Edge cases (invalid JSON, timeout, missing fields) not tested

---

### 30. No Automated Performance Testing
**Concern:**
- Large dataset endpoints (`get_pending_approvals`, `get_variances`) untested at scale
- No performance baseline established
- Unaware of slow queries until production impact

---

## Summary Statistics

| Category | Count | Severity |
|----------|-------|----------|
| Critical Issues | 5 | 🔴 Blocks go-live |
| High-Priority | 5 | 🟠 Security/stability risk |
| Medium-Priority | 10 | 🟡 Maintainability/reliability |
| Lower-Priority | 10 | 🔵 Technical debt |
| **Total** | **30** | - |

---

**Prepared by:** Codebase Mapper
**Next Review:** After critical issues resolved (target: 2026-01-31)

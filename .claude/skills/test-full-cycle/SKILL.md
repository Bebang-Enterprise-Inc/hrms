# E2E Full Cycle Testing - Autonomous QA Agent

## Purpose

Execute **autonomous end-to-end QA testing** for any Frappe-backed feature using Chrome DevTools MCP. This agent has a **built-in loop mechanism** that continues until all tests pass.

---

## ⚠️ BUILT-IN AUTONOMOUS LOOP - NO EXTERNAL DEPENDENCIES ⚠️

This skill has its own loop mechanism. It does NOT require Ralph Wiggum or any external hooks.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS LOOP PROTOCOL                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────────────┐   │
│   │ DISCOVER│───▶│  CREATE  │───▶│ EXECUTE │───▶│ ALL TASKS DONE?  │   │
│   │ elements│    │  tasks   │    │  tests  │    │                  │   │
│   └─────────┘    └──────────┘    └─────────┘    └────────┬─────────┘   │
│                                                          │             │
│                          ┌───────────────────────────────┤             │
│                          │                               │             │
│                          ▼ NO                            ▼ YES         │
│                   ┌──────────────┐              ┌────────────────┐     │
│                   │ CHECK TASKS  │              │ OUTPUT PROMISE │     │
│                   │ Fix bugs     │              │ Generate report│     │
│                   │ Re-test      │              └────────────────┘     │
│                   │ CONTINUE     │                                     │
│                   └──────┬───────┘                                     │
│                          │                                             │
│                          └─────────────▶ (back to EXECUTE)             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## PHASE 0: Initialize Loop State

### 0.1 Create State File

**IMMEDIATELY on invocation, create the loop state file:**

```bash
# Create state file
mkdir -p .claude
cat > .claude/qa-loop-state.json << 'EOF'
{
  "status": "active",
  "feature": "FEATURE_PATH_HERE",
  "iteration": 1,
  "started_at": "TIMESTAMP",
  "phase": "discovery",
  "tests_created": 0,
  "tests_passed": 0,
  "tests_failed": 0,
  "bugs_found": 0,
  "bugs_fixed": 0
}
EOF
```

### 0.2 State Transitions

```
discovery → testing → fixing → testing → ... → complete
```

### 0.3 Loop Check Function

**After EVERY action, check if loop should continue:**

```python
# PSEUDOCODE - Claude must do this check after every action:

def should_continue():
    state = read_json(".claude/qa-loop-state.json")
    tasks = TaskList()

    pending_tests = [t for t in tasks if t.subject.startswith("[TEST]") and t.status != "completed"]
    pending_bugs = [t for t in tasks if t.subject.startswith("[BUG]") and t.status != "completed"]
    pending_verify = [t for t in tasks if t.subject.startswith("[VERIFY]") and t.status != "completed"]
    in_progress_tasks = [t for t in tasks if t.status == "in_progress"]
    blocked_tests = [t for t in pending_tests if len(t.blockedBy) > 0]

    # If tests are blocked by deployments, WAIT for deployments
    if blocked_tests and deployment_pending():
        wait_for_deployments()  # MANDATORY - DO NOT SKIP
        return True  # Continue after deployments complete

    # CRITICAL: Check ALL pending work
    all_pending = pending_tests + pending_bugs + pending_verify + in_progress_tasks

    # If ANY work remains, continue
    if len(all_pending) > 0:
        return True  # KEEP GOING - DO NOT STOP

    # Only stop when EVERYTHING is complete
    return False  # ALL DONE

# After EVERY action:
if should_continue():
    # Pick next task and work on it
    next_task = get_next_pending_task()
    execute_task(next_task)
else:
    # Output completion promise ONLY when truly done
    print("<promise>ALL TESTS PASSED</promise>")
    generate_final_report()
```

---

## PHASE 0.4: Deployment Polling Protocol ⚠️ CRITICAL ⚠️

**NEVER STOP AT A "DEPLOYMENT GATE"**

If tests are blocked by deployments, you MUST:

### Step 1: Trigger Deployments

```bash
# Trigger Frappe migration
python scripts/trigger_migrate_deployment.py

# Commit and push frontend changes
cd bei-tasks && git add . && git commit -m "..." && git push origin main
```

### Step 2: WAIT for Deployments (Mandatory Polling)

**DO NOT PROCEED WITHOUT WAITING**

```python
# Use the polling utility
import sys
sys.path.append('scripts')
from wait_for_deployment import wait_for_frappe_migration, wait_for_vercel_deployment

# Wait for Frappe migration (max 5 minutes)
if deployment_type == "frappe":
    success = wait_for_frappe_migration(
        doctype="BEI Payment Request",
        field="rfp_type",
        api_key=FRAPPE_API_KEY,
        api_secret=FRAPPE_API_SECRET,
        max_wait_seconds=300,
        poll_interval=30
    )
    if not success:
        # Timeout - document and continue anyway
        create_task("[BUG] Migration timeout - needs manual verification")

# Wait for Vercel deployment (max 2 minutes)
if deployment_type == "vercel":
    success = wait_for_vercel_deployment(
        url="https://my.bebang.ph/dashboard/accounting",
        max_wait_seconds=120,
        poll_interval=15
    )
    if not success:
        # Timeout - document and continue anyway
        create_task("[BUG] Vercel deployment timeout - needs manual verification")
```

### Step 3: Verify and Continue

After polling completes:
- **If successful:** Unblock tests and continue execution
- **If timeout:** Document issue, create bug task, continue with other tests

### Step 4: Never Output "PAUSED" Promise

**WRONG:**
```
<promise>PAUSED AT DEPLOYMENT GATE</promise>
```

**CORRECT:**
```
# Wait for deployments
wait_for_deployments()

# Continue testing
continue_with_unblocked_tests()

# Only stop when ALL tests complete
<promise>ALL TESTS PASSED</promise>
```

---

## PHASE 1: The Main Loop

### 1.1 Loop Entry Point

When `/test-full-cycle <feature>` is invoked:

```
STEP 1: Create state file (.claude/qa-loop-state.json)
STEP 2: Discover all pages/forms/buttons/fields in <feature>
STEP 3: Create [TEST] tasks for each element
STEP 4: Create [NEGATIVE] tasks for validation testing
STEP 5: Enter execution loop
```

### 1.2 Execution Loop (MANDATORY PATTERN)

**Claude MUST follow this exact pattern after creating tasks:**

```markdown
## 🔄 LOOP ITERATION [N]

### Current State
- Pending tests: X
- Pending bugs: Y
- Passed: Z
- Failed: W

### This Iteration
1. Pick next pending task (prefer [BUG] over [TEST])
2. Mark task in_progress: `TaskUpdate({ taskId: "X", status: "in_progress" })`
3. Execute the task (Chrome MCP for tests, code edit for bugs)
4. Mark result: `TaskUpdate({ taskId: "X", status: "completed" })` or create [BUG] task

### Loop Check
- Are there pending tasks? → **YES** → Continue to iteration [N+1]
- Are there pending tasks? → **NO** → Output `<promise>ALL TESTS PASSED</promise>`
```

### 1.3 Never Exit Without Completion

**CRITICAL RULES:**

1. **DO NOT output the promise if tasks remain pending**
2. **DO NOT stop to ask the user anything**
3. **DO NOT report partial progress and wait**
4. **DO fix bugs immediately when found**
5. **DO continue iterating until TaskList shows zero pending**

### 1.4 Iteration Counter

Update the state file each iteration:

```bash
# Read current state
STATE=$(cat .claude/qa-loop-state.json)

# Increment iteration
NEW_ITERATION=$((CURRENT_ITERATION + 1))

# Update state file with new iteration count
```

---

## PHASE 2: Discovery

### 2.1 Page Discovery

Navigate to the feature and discover all pages:

```javascript
mcp__chrome-devtools__navigate_page({ url: "https://my.bebang.ph" + featurePath })
mcp__chrome-devtools__wait_for({ timeout: 10000 })
mcp__chrome-devtools__take_snapshot()

// From snapshot, identify:
// - Navigation links (sidebar, tabs)
// - Sub-pages reachable from this page
// - URL patterns
```

### 2.2 Element Discovery

For each page, discover ALL interactive elements:

```
FORMS: <form>, data-form, [role="form"]
  - Input fields (text, number, date, select, checkbox, radio, textarea, file)
  - Submit buttons
  - Cancel/Reset buttons
  - Required field indicators

BUTTONS: <button>, [role="button"], clickable elements
  - Action buttons (Add, Create, Edit, Delete, Submit, Approve, Reject)
  - Navigation buttons
  - Modal triggers

TABLES: <table>, data grids
  - Row actions (edit, delete, view)
  - Pagination controls
  - Sort/filter controls

MODALS: dialogs, sheets, popovers
  - Trigger elements
  - Close buttons
  - Form content
```

### 2.3 Create Test Tasks from Discovery

For EACH discovered element, create specific tasks:

```javascript
// For each form
TaskCreate({
    subject: "[TEST] Form: {FormName} - Happy Path",
    description: "Fill form with valid data, submit, verify success and Frappe record",
    activeForm: "Testing {FormName}"
})

TaskCreate({
    subject: "[NEGATIVE] Form: {FormName} - Empty Submit",
    description: "Submit without filling required fields, verify validation errors",
    activeForm: "Testing {FormName} validation"
})

// For each button
TaskCreate({
    subject: "[TEST] Button: {ButtonText} - Click Action",
    description: "Click button, verify expected action occurs",
    activeForm: "Testing {ButtonText} button"
})

// For each field
TaskCreate({
    subject: "[NEGATIVE] Field: {FieldName} - Invalid Input",
    description: "Enter invalid data, verify validation error",
    activeForm: "Testing {FieldName} validation"
})
```

---

## PHASE 3: Test Execution

### 3.1 Test Execution Pattern

For each [TEST] or [NEGATIVE] task:

```javascript
// 1. Get task details
const task = TaskGet(taskId)

// 2. Mark as in progress
TaskUpdate({ taskId: task.id, status: "in_progress" })

// 3. Navigate to the page
mcp__chrome-devtools__navigate_page({ url: pageUrl })
mcp__chrome-devtools__wait_for({ timeout: 10000 })

// 4. Take snapshot to find elements
mcp__chrome-devtools__take_snapshot()

// 5. Execute test steps
// - Fill forms
// - Click buttons
// - Wait for responses

// 6. Verify results
// - Check UI state
// - Call Frappe API to verify records
// - Check console for errors

// 7. Take screenshot evidence
mcp__chrome-devtools__take_screenshot({ filePath: "scratchpad/qa/test_XXX.png" })

// 8. Determine result
if (testPassed) {
    TaskUpdate({ taskId: task.id, status: "completed" })
    // Update state: tests_passed++
} else {
    // Create bug task
    const bugTask = TaskCreate({
        subject: "[BUG] " + errorSummary,
        description: `
            Failed test: ${task.subject}
            Error: ${errorDetails}
            Screenshot: scratchpad/qa/test_XXX.png
        `,
        activeForm: "Fixing " + errorSummary
    })

    // Link bug to test
    TaskUpdate({ taskId: task.id, addBlockedBy: [bugTask.id] })
    // Update state: tests_failed++, bugs_found++
}

// 9. Continue loop (MANDATORY)
// Check for next task and continue
```

### 3.2 Frappe Backend Verification

After any form submission, verify in Frappe:

```bash
# Get credentials
FRAPPE_KEY=$(doppler secrets get FRAPPE_API_KEY --project bei-erp --config dev --plain)
FRAPPE_SECRET=$(doppler secrets get FRAPPE_API_SECRET --project bei-erp --config dev --plain)

# Query for created record
curl -s "https://hq.bebang.ph/api/resource/DOCTYPE?order_by=creation%20desc&limit=1" \
  -H "Authorization: token $FRAPPE_KEY:$FRAPPE_SECRET"
```

---

## PHASE 4: Bug Fixing

### 4.1 Bug Fix Protocol

When a [BUG] task is the next pending task:

```javascript
// 1. Get bug details
const bug = TaskGet(bugId)

// 2. Mark as in progress
TaskUpdate({ taskId: bug.id, status: "in_progress" })

// 3. Analyze the error
// - Read error messages
// - Check console logs
// - Review screenshot

// 4. Identify fix location
// - Frontend (bei-tasks): React/Next.js components
// - Backend (hrms): Python/Frappe API

// 5. Read the relevant file
Read({ file_path: "path/to/file" })

// 6. Fix the bug
Edit({
    file_path: "path/to/file",
    old_string: "buggy code",
    new_string: "fixed code"
})

// 7. Commit the fix
Bash({ command: "git add -A && git commit -m 'fix: Description'" })

// 8. Deploy
// - bei-tasks: Vercel auto-deploys on commit
// - hrms: Use /deploy-frappe

// 9. Wait for deployment (30-60 seconds)

// 10. Mark bug as fixed
TaskUpdate({ taskId: bug.id, status: "completed" })
// Update state: bugs_fixed++

// 11. The blocked test will now be unblocked and re-run
// Continue loop
```

---

## PHASE 5: Completion

### 5.1 Completion Check

After each action, check:

```javascript
const tasks = TaskList()
const pending = tasks.filter(t =>
    (t.subject.startsWith("[TEST]") || t.subject.startsWith("[BUG]") || t.subject.startsWith("[NEGATIVE]"))
    && t.status !== "completed"
)

if (pending.length === 0) {
    // ALL DONE - Output promise and report
    outputCompletionPromise()
    generateFinalReport()
} else {
    // Continue to next iteration
    continueLoop()
}
```

### 5.2 Completion Promise

**ONLY output when ALL tasks are completed:**

```
<promise>ALL TESTS PASSED</promise>
```

### 5.3 Final Report

```markdown
# QA Test Report: [Feature Name]

**Date:** YYYY-MM-DD HH:MM
**Feature:** /dashboard/feature
**Total Iterations:** N
**Status:** ✅ ALL TESTS PASSED

## Summary

| Metric | Count |
|--------|-------|
| Elements Discovered | X |
| Tests Created | Y |
| Tests Passed | Y |
| Bugs Found | Z |
| Bugs Fixed | Z |

## Test Results

| Test | Result |
|------|--------|
| [TEST] Form: X - Happy Path | ✅ PASS |
| [TEST] Button: Y - Click | ✅ PASS |
| [NEGATIVE] Field: Z - Invalid | ✅ PASS |
| ... | ... |

## Bugs Fixed

| Bug | Fix |
|-----|-----|
| [BUG] Submit not working | Added async handler |
| [BUG] Validation missing | Added required check |

## Evidence

Screenshots: scratchpad/qa/YYYY-MM-DD/

---
<promise>ALL TESTS PASSED</promise>
```

---

## Invocation

```bash
# Test a specific feature
/test-full-cycle /dashboard/commissary
/test-full-cycle /dashboard/hr/leave
/test-full-cycle /dashboard/inventory

# Test with specific user
/test-full-cycle /dashboard/commissary --user=test.warehouse@bebang.ph
```

---

## Test Accounts

**⚠️ CRITICAL: USE DIRECT LOGIN, NOT GOOGLE OAUTH ⚠️**

For E2E testing, **ALWAYS use direct username/password login** to switch between test users. Do NOT use Google OAuth flow.

### Direct Login URL
```
https://hq.bebang.ph/login
```

### Available Test Accounts

| Username | Password | Role | Use For |
|----------|----------|------|---------|
| test.crew1@bebang.ph | BeiTest2026! | Store Staff (Store OIC) | Store operations, POS, opening/closing |
| test.supervisor@bebang.ph | BeiTest2026! | Store Supervisor | Store operations, team management |
| test.area@bebang.ph | BeiTest2026! | Area Supervisor | Multi-store oversight, approvals, visits |
| test.hr@bebang.ph | BeiTest2026! | HR User | Leave, clearance, employee management |
| test.warehouse@bebang.ph | BeiTest2026! | Warehouse/Commissary | Inventory, receiving, dispatch |
| test.procurement@bebang.ph | BeiTest2026! | Procurement | Supplier management, PO approval |
| test.admin@bebang.ph | BeiTest2026! | Admin | Full system access |

### Login Procedure

**To switch users during testing:**

```javascript
// 1. Navigate to Frappe backend login (NOT my.bebang.ph OAuth)
mcp__chrome-devtools__navigate_page({ url: "https://hq.bebang.ph/login" })

// 2. Wait for login form
mcp__chrome-devtools__wait_for({ text: "Login", timeout: 10000 })

// 3. Take snapshot to find email and password fields
mcp__chrome-devtools__take_snapshot()

// 4. Fill email field
mcp__chrome-devtools__fill({ uid: "EMAIL_FIELD_UID", value: "test.supervisor@bebang.ph" })

// 5. Fill password field
mcp__chrome-devtools__fill({ uid: "PASSWORD_FIELD_UID", value: "BeiTest2026!" })

// 6. Click login button
mcp__chrome-devtools__click({ uid: "LOGIN_BUTTON_UID" })

// 7. Wait for redirect to desk
mcp__chrome-devtools__wait_for({ timeout: 10000 })

// 8. Navigate to my.bebang.ph - session will be shared
mcp__chrome-devtools__navigate_page({ url: "https://my.bebang.ph/dashboard" })
```

### Why Direct Login?

- **Google OAuth is for production users only**
- **Test accounts use direct Frappe authentication**
- **Session persists across hq.bebang.ph and my.bebang.ph (same domain)**
- **Allows automated user switching without OAuth complications**

### Creating Additional Test Users

If you need more test users, create them via Frappe API:

```bash
FRAPPE_KEY=$(doppler secrets get FRAPPE_API_KEY --project bei-erp --config dev --plain)
FRAPPE_SECRET=$(doppler secrets get FRAPPE_API_SECRET --project bei-erp --config dev --plain)

curl -X POST "https://hq.bebang.ph/api/resource/User" \
  -H "Authorization: token $FRAPPE_KEY:$FRAPPE_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test.newrole@bebang.ph",
    "first_name": "Test",
    "last_name": "NewRole",
    "enabled": 1,
    "new_password": "BeiTest2026!",
    "roles": [{"role": "Store Supervisor"}]
  }'
```

---

## Chrome MCP Reference

```javascript
// Navigate
mcp__chrome-devtools__navigate_page({ url: "..." })
mcp__chrome-devtools__wait_for({ text: "...", timeout: 10000 })

// Discover
mcp__chrome-devtools__take_snapshot()

// Interact
mcp__chrome-devtools__click({ uid: "..." })
mcp__chrome-devtools__fill({ uid: "...", value: "..." })
mcp__chrome-devtools__press_key({ key: "Enter" })

// Evidence
mcp__chrome-devtools__take_screenshot({ filePath: "..." })
mcp__chrome-devtools__list_console_messages()
```

---

## Authorization

**You ARE authorized to:**
- Discover all elements in any feature
- Create unlimited test tasks
- Create test users via Frappe API
- Edit code to fix bugs
- Commit and deploy fixes
- Run indefinitely until complete

**You MUST NOT:**
- Output `<promise>ALL TESTS PASSED</promise>` if tasks remain pending
- Stop and ask "should I continue?"
- Report partial results and wait
- Skip difficult tests
- Leave bugs unfixed

---

## The Golden Rule

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   AFTER EVERY ACTION, CHECK: ARE THERE PENDING TASKS?            ║
║                                                                  ║
║   YES → Pick next task, execute it, repeat                       ║
║   NO  → Output <promise>ALL TESTS PASSED</promise>               ║
║                                                                  ║
║   DO NOT STOP UNTIL THE ANSWER IS "NO"                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## ⚠️ CRITICAL: Never Stop Prematurely ⚠️

**THIS IS A BLOCKING ERROR - NEVER DO THIS:**

```
❌ WRONG:
1. Create 8 tests
2. Complete 3 tests
3. Find 5 tests blocked
4. Generate report
5. Output <promise>COMPLETE</promise>
6. Stop and wait for user

PROBLEM: Tasks #22 [VERIFY] and #24 [BUG] are still pending!
```

**CORRECT BEHAVIOR:**

```
✅ RIGHT:
1. Create 8 tests
2. Complete 3 tests
3. Find 5 tests blocked
4. Work on Task #22 [VERIFY] - Check migration status
5. Work on Task #24 [BUG] - Debug data loading
6. If blocked, trigger deployment and POLL
7. Continue until TaskList shows ZERO pending
8. THEN output <promise>COMPLETE</promise>
```

**MANDATORY CHECK BEFORE COMPLETION:**

```python
tasks = TaskList()
pending = [t for t in tasks if t.status != "completed"]

if len(pending) > 0:
    # STOP - YOU CANNOT COMPLETE YET
    # Pick next pending task and work on it
    continue_loop()
else:
    # OK - All tasks complete
    output_completion_promise()
```

**Task Types That Count As Pending:**
- [TEST] - Test tasks
- [BUG] - Bug fixes
- [VERIFY] - Verification tasks (CAN be worked on!)
- [NEGATIVE] - Negative test cases
- ANY task with status != "completed"

**The ONLY valid reason to stop:**
- TaskList shows ZERO pending/in_progress tasks
- ALL work is genuinely complete
- No verification, bugs, or tests remain
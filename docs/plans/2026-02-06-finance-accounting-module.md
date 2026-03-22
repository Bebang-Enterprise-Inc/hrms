# Finance & Accounting Module Implementation Plan (REVISED)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build franchise billing automation for my.bebang.ph and extend existing Payment Request/Closing Report features. **NO DUPLICATION** - consolidate with existing Module 10 (Procurement).

**Architecture:** React frontend (Next.js 15 + Shadcn UI) consuming Frappe REST APIs. **Reuse existing** BEI Payment Request (4-level approval), BEI Store Closing Report (cash tracking), and BEI Invoice (3-way match).

**Tech Stack:** Next.js 15, React 19, Shadcn UI, TanStack Query, Zod, Frappe Framework (Python), MariaDB

**Source:** Questionnaire completed 2026-02-05 + Plan audit 2026-02-06 (see `scratchpad/finance_accounting_plan_audit.md`)

**Reference Documents:**
- Audit report: `scratchpad/finance_accounting_plan_audit.md` (**CRITICAL - 60% duplication avoided**)
- Questionnaire responses: `scratchpad/accounting_answers_summary.md`
- Key findings: `scratchpad/accounting_key_findings.md`
- Existing features: `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md` (Module 10: Procurement)

**Master Data Sources:**
- Store Type Classification: https://docs.google.com/spreadsheets/d/1gJojjZ3CeYxGoA2Aw0EqPuWejmmwTI6qmN8LDQFVxCs/edit?gid=0#gid=0
- Price List (with markups): https://docs.google.com/spreadsheets/d/1NVKcsJo-txF5gQ7XI0bLHQpF4Ip4b03dfgBZFe6CSeI/edit?gid=0#gid=0
- RFP Template: https://docs.google.com/spreadsheets/d/1yrp1MUluFyZp6Tu527tWRzON4gASblFAjGpnrMtDgjs/edit?gid=1682879916#gid=1682879916
- Chart of Accounts: https://docs.google.com/spreadsheets/d/1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g/edit?usp=drive_link
- Cash Monitoring Tracker: https://docs.google.com/spreadsheets/d/1HUd22NwfkoQJJVKGUCUSdad91f7Km0HB3KuhTss2hjg/edit?pli=1&gid=847170043#gid=847170043

---

## CRITICAL AUDIT FINDINGS

**⚠️ DO NOT BUILD:**
1. **BEI RFP DocType** → Use **BEI Payment Request** (already has 4-level approval)
2. **BEI Cash Monitor DocType** → Use **BEI Store Closing Report** (already tracks PCF/DF)
3. **RFP APIs** → Use **existing payment request APIs** (`hrms/api/procurement.py`)

**✅ BUILD ONLY:**
1. **BEI Billing Schedule** - Genuinely new (franchise billing by store type)
2. **BEI Store Type Master** - Needed for billing calculations
3. **Extensions to existing DocTypes** - Add fields/thresholds to Payment Request and Closing Report

**Cost Savings:** 2-3 weeks development time + eliminated technical debt

---

## Top Automation Priorities (from Questionnaire)

Based on Accounting team feedback, these are the highest-impact automations:

1. **PURCHASE ORDER PROCESSING** - Stores request PO → Warehouse reviews → ERP issues DR → Store verifies → Bill trucker for discrepancies
   - **Status:** ✅ Already implemented in Module 10 (Procurement)
   - **No action needed** - uses existing BEI Purchase Order, BEI Goods Receipt, BEI Invoice

2. **PAYMENTS APPLICATION** - Upload proof of payment → auto-apply to invoices → auto-update SOA
   - **Status:** ⚠️ Partial - existing BEI Payment Request, needs auto-application logic
   - **Action:** Add payment application endpoint (Phase 1, Task 3 extension)

3. **AUTOMATED ACKNOWLEDGEMENT RECEIPT** - Auto-generate AR upon receiving store payment proof
   - **Status:** ⏳ Not started
   - **Action:** Add AR generation to billing workflow (Phase 2, Task 5 extension)

4. **AUTOMATED STATEMENT OF ACCOUNT** - Eliminate manual entry for DR#, raw material costs by store type, expenses, totals
   - **Status:** ⏳ Not started
   - **Action:** Implement in BEI Billing Schedule (Phase 2, Task 5)

5. **AUTOMATIC ACCOUNT TITLES** - Auto-assign correct account titles for invoices/expenses/reimbursements
   - **Status:** ⚠️ Needs account mapping rules
   - **Action:** Add account code mapping to Payment Request types (Phase 1, Task 1 extension)

6. **FIXED BILLING CUTOFF** - Deliveries: Monday, Royalties/Marketing/Management/eCommerce/Logistics: 1st week of month
   - **Status:** ⏳ Not started
   - **Action:** Add billing schedule automation (Phase 2, Task 5 extension)

**Implementation Priority:** Focus on #2, #3, #4, #6 (tied to new Billing Schedule DocType)

---

## Development Workflow (MANDATORY - /build Rules)

**This plan MUST be executed following `/build` workflow rules:**

### Phase 0: Setup (Before Starting Implementation)

1. **Create tasks** for all work items:
   ```bash
   /tasks add "Extend BEI Payment Request for RFP types"
   /tasks add "Extend BEI Store Closing Report for variance alerts"
   /tasks add "Add AP aging endpoint to procurement API"
   /tasks add "Create BEI Store Type master"
   /tasks add "Create BEI Billing Schedule DocType"
   /tasks add "Create Accounting Dashboard frontend"
   ```

2. **Create feature branch** (optional, for isolation):
   ```bash
   /feature-branch accounting-module
   ```

### During Implementation (Every Task)

**For Python/API changes:**
1. ✅ **Use `/local-frappe`** to test changes BEFORE committing
   - Never commit untested Python code
   - Verify migrations work locally first
   - Test API endpoints with sample data

**For Frontend changes (bei-tasks repo):**
1. ✅ Test locally with `npm run dev`
2. ✅ Verify API integration works
3. ✅ Check responsive design

**For Commits:**
1. ❌ **NEVER use `git commit` directly**
2. ✅ **ALWAYS use `/pr-deploy`** (creates PR and triggers deployment)
3. ✅ Follow commit message conventions (feat/fix/refactor)
4. ✅ Include Co-Authored-By tag

**When Issues Found:**
1. ✅ **Create subtasks immediately** with `/tasks add "Fix [issue]"`
2. ✅ **Don't stop to ask** - operate autonomously
3. ✅ Fix issues inline, mark subtasks complete

### Phase Completion (After All Tasks Done)

1. **Run comprehensive E2E testing:**
   ```bash
   /test-full-cycle
   ```
   - Tests all 4 roles (Area Supervisor, Store Supervisor, Store Staff, HR User)
   - Audits all pages for UI/UX issues
   - Verifies RBAC (role-based access control)
   - Executes approval workflows

2. **Deploy to production:**
   ```bash
   /pr-deploy --auto-merge
   ```
   - Creates PR to production branch
   - Triggers GitHub Actions build
   - Auto-merges if CI passes

3. **Mark all tasks complete:**
   ```bash
   /tasks done <task-id>
   ```

### Autonomous Operation Rules

- ✅ **Fix issues without stopping** - create subtasks for unexpected work
- ✅ **Use existing patterns** - don't reinvent (see audit findings)
- ✅ **Test before commit** - use `/local-frappe` for all Python changes
- ✅ **Deploy via PR** - never push to production directly
- ❌ **Don't duplicate** - extend existing features (Payment Request, Closing Report)

### Quick Reference Commands

| Task | Command |
|------|---------|
| Test Python locally | `/local-frappe` |
| Deploy changes | `/pr-deploy` or `/pr-deploy --auto-merge` |
| Create task | `/tasks add "Description"` |
| Mark task done | `/tasks done <id>` |
| Run E2E tests | `/test-full-cycle` |
| Check workflow | `/workflow` |

---

## Overview

### Module Scope

**Module 11: Finance & Accounting** - Three workstreams (consolidated):

1. **Workstream A: RFP Workflow** (**EXTEND EXISTING**)
   - Use Module 10's **BEI Payment Request** (already has 4-level approval)
   - Add RFP-specific fields (TIN, address, purpose)
   - Add RFP types: Transpo, Rentals (PCF/DF already supported)

2. **Workstream B: Cash Monitoring** (**EXTEND EXISTING**)
   - Use Module 1's **BEI Store Closing Report** (already tracks PCF, DF, Change Fund)
   - Add variance threshold fields (PCF: PHP 7,500, DF: PHP 15,000)
   - Add alert notification when thresholds exceeded

3. **Workstream C: Franchise Billing** (**BUILD NEW**)
   - Create **BEI Billing Schedule** DocType
   - Create **BEI Store Type** master (JV/Managed/Franchise)
   - Automated billing by store type with fee calculations
   - AR aging and dispute tracking

### User Roles

| Role | Access | Primary Functions |
|------|--------|-------------------|
| Store Staff | Submit payment requests | Use existing BEI Payment Request |
| Store Supervisor | Approve payments | Use existing approval workflow |
| Accounting Analyst | Validate, Bill | Validate payments, generate billing |
| Accounting Manager | Approve, Reports | First approval tier, AR/AP reports |
| CFO | Final Approval | Final approval on all transactions |

### Business Rules

**Variance Thresholds** (extend Closing Report):
- PCF: PHP 7,500
- Delivery Fund: PHP 15,000

**Approval Matrix** (use existing Payment Request):
- 4-level approval already exists: Reviewer → Budget → CFO → CEO
- No changes needed - questionnaire shows same approval structure

**Account Codes** (GL):
- 1113000: Petty Cash Fund
- 1115000: Delivery Fund
- 4000003: Royalty Income (HO)
- 4000004: Management Fee Income (HO)
- 4000006: Marketing Fee Income (HO)

**Billing Cycles (from Questionnaire):**
- **Deliveries:** Weekly (Monday cutoff for Mon-Wed processing)
- **Royalties:** Monthly (1st week of month)
- **Marketing Fee:** Monthly (1st week of month)
- **Management Fee:** Monthly (1st week of month)
- **eCommerce Fee:** Monthly (1st week of month)
- **Logistics:** Monthly (1st week of month)
- **Repairs and Maintenance:** Monthly
- **Preventive Maintenance:** Monthly
- **Payroll:** Bi-weekly (existing HRMS process)
- **Taxes:** Monthly/Quarterly (per Eddie Ramboyo - BIR compliance)

---

## Phase 1: Extend Existing DocTypes

### Task 1: Extend BEI Payment Request for RFP Types

**Goal:** Add RFP-specific fields to existing Payment Request DocType. **DO NOT CREATE NEW DOCTYPE.**

**Files:**
- Modify: `hrms/hr/doctype/bei_payment_request/bei_payment_request.json`
- Modify: `hrms/hr/doctype/bei_payment_request/bei_payment_request.py`
- Modify: `hrms/hr/doctype/bei_payment_request/test_bei_payment_request.py`

**Step 1: Read existing Payment Request DocType**

Read: `hrms/hr/doctype/bei_payment_request/bei_payment_request.json`

**Step 2: Add RFP-specific fields to JSON**

Add these fields to field_order and fields array:

```json
{
  "fieldname": "rfp_purpose",
  "fieldtype": "Small Text",
  "label": "RFP Purpose",
  "description": "Detailed purpose for payment request"
},
{
  "fieldname": "payee_tin",
  "fieldtype": "Data",
  "label": "Payee TIN",
  "description": "Tax Identification Number of payee"
},
{
  "fieldname": "payee_address",
  "fieldtype": "Small Text",
  "label": "Payee Address"
},
{
  "fieldname": "rfp_type",
  "fieldtype": "Select",
  "label": "RFP Type",
  "options": "\nPCF Replenishment\nDelivery Fund\nTranspo Allowance\nRentals\nVendor Invoice\nCash Advance\nReimbursement\nCredit Card Transaction",
  "description": "Type of payment request for validation rules"
}
```

**Step 3: Run migration and test locally**

Use `/local-frappe` to test changes:

```bash
/local-frappe
# This will:
# 1. Run migration to add fields
# 2. Run existing tests to verify nothing broke
# 3. Test manually in local Frappe instance
```

**Step 4: Verify tests pass**

Expected output from `/local-frappe`:
- ✅ Migration successful (4 fields added)
- ✅ All existing tests PASS (approval workflow unchanged)
- ✅ Manual testing shows new fields in form

**Step 5: Deploy via PR**

```bash
/pr-deploy

# Commit message (auto-generated):
# "feat(accounting): extend Payment Request for RFP use cases

- Add rfp_purpose, payee_tin, payee_address fields
- Add rfp_type selector (8 types: PCF, DF, Transpo, Rentals, etc.)
- Reuse existing 4-level approval workflow (no duplication)
- NO new DocType created - extends existing Module 10 feature

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 2: Extend BEI Store Closing Report for Variance Alerts

**Goal:** Add variance threshold fields and alert logic to existing Closing Report DocType. **DO NOT CREATE NEW DOCTYPE.**

**Files:**
- Modify: `hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.json`
- Modify: `hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.py`

**Step 1: Read existing Closing Report DocType**

Read: `hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.json`

**Step 2: Add variance threshold fields to JSON**

Add these fields to field_order and fields array:

```json
{
  "fieldname": "pcf_variance_threshold",
  "fieldtype": "Currency",
  "label": "PCF Variance Threshold",
  "default": "7500",
  "precision": "2",
  "description": "Alert if PCF variance exceeds this amount"
},
{
  "fieldname": "df_variance_threshold",
  "fieldtype": "Currency",
  "label": "DF Variance Threshold",
  "default": "15000",
  "precision": "2",
  "description": "Alert if Delivery Fund variance exceeds this amount"
},
{
  "fieldname": "pcf_variance_alert",
  "fieldtype": "Check",
  "label": "PCF Variance Alert",
  "read_only": 1,
  "description": "Auto-set if PCF variance exceeds threshold"
},
{
  "fieldname": "df_variance_alert",
  "fieldtype": "Check",
  "label": "DF Variance Alert",
  "read_only": 1,
  "description": "Auto-set if DF variance exceeds threshold"
}
```

**Step 3: Add alert logic to controller**

Modify: `hrms/hr/doctype/bei_store_closing_report/bei_store_closing_report.py`

Add method:

```python
def check_cash_variance_alerts(self):
    """Check if cash variances exceed thresholds and set alerts."""
    # PCF variance check
    if self.pcf_variance and self.pcf_variance_threshold:
        if abs(self.pcf_variance) > self.pcf_variance_threshold:
            self.pcf_variance_alert = 1
            # TODO: Send Google Chat notification to Accounting Manager
        else:
            self.pcf_variance_alert = 0

    # DF variance check
    if self.df_variance and self.df_variance_threshold:
        if abs(self.df_variance) > self.df_variance_threshold:
            self.df_variance_alert = 1
            # TODO: Send Google Chat notification to Accounting Manager
        else:
            self.df_variance_alert = 0
```

Call in `validate()` method:

```python
def validate(self):
    # ... existing validation ...
    self.check_cash_variance_alerts()
```

**Step 4: Test locally**

Use `/local-frappe` to test changes:

```bash
/local-frappe
# This will:
# 1. Run migration to add variance threshold fields
# 2. Run tests to verify alert logic works
# 3. Test manually with sample closing reports
```

Expected: Alert flags set correctly when thresholds exceeded

**Step 5: Deploy via PR**

```bash
/pr-deploy

# Commit message (auto-generated):
# "feat(accounting): add variance alerts to Closing Report

- Add pcf_variance_threshold (default PHP 7,500)
- Add df_variance_threshold (default PHP 15,000)
- Auto-set alert flags when thresholds exceeded
- Reuse existing cash tracking (no duplication)
- NO new DocType created - extends existing Module 1 feature

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 3: Add AP Aging Dashboard

**Goal:** Create API endpoint for AP aging report using existing BEI Invoice DocType.

**Files:**
- Modify: `hrms/api/procurement.py` (extend existing API module)
- Create: `hrms/api/tests/test_accounting_api.py`

**Step 1: Read existing procurement API**

Read: `hrms/api/procurement.py`

**Step 2: Add AP aging endpoint to procurement.py**

```python
@frappe.whitelist()
def get_ap_aging_report(aging_buckets: Optional[List[int]] = None) -> Dict:
    """
    Get AP aging report using existing BEI Invoice DocType.

    Args:
        aging_buckets: Custom aging buckets (default: [30, 60, 90, 120, 150])

    Returns:
        Dict with aging summary by bucket
    """
    if not aging_buckets:
        aging_buckets = [30, 60, 90, 120, 150]

    from datetime import datetime, timedelta
    from frappe.utils import getdate

    today = getdate()

    # Get all unpaid invoices
    invoices = frappe.get_all(
        "BEI Invoice",
        filters={"status": ["in", ["Pending Payment", "Partially Paid"]]},
        fields=["name", "posting_date", "total_amount", "paid_amount", "supplier"]
    )

    # Initialize aging buckets
    aging_summary = {
        "0-30": {"count": 0, "amount": 0},
        "31-60": {"count": 0, "amount": 0},
        "61-90": {"count": 0, "amount": 0},
        "91-120": {"count": 0, "amount": 0},
        "121-150": {"count": 0, "amount": 0},
        "Over 150": {"count": 0, "amount": 0}
    }

    total_payables = 0

    for inv in invoices:
        # Calculate outstanding
        outstanding = (inv.total_amount or 0) - (inv.paid_amount or 0)
        if outstanding <= 0:
            continue

        # Calculate age
        age_days = (today - getdate(inv.posting_date)).days

        # Classify into bucket
        if age_days <= 30:
            bucket = "0-30"
        elif age_days <= 60:
            bucket = "31-60"
        elif age_days <= 90:
            bucket = "61-90"
        elif age_days <= 120:
            bucket = "91-120"
        elif age_days <= 150:
            bucket = "121-150"
        else:
            bucket = "Over 150"

        aging_summary[bucket]["count"] += 1
        aging_summary[bucket]["amount"] += outstanding
        total_payables += outstanding

    return {
        "aging_summary": aging_summary,
        "total_payables": total_payables
    }
```

**Step 3: Write test for AP aging**

Create: `hrms/api/tests/test_accounting_api.py`

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from datetime import date, timedelta

class TestAccountingAPI(FrappeTestCase):
    def test_ap_aging_report(self):
        """Test AP aging report with sample invoices."""
        from hrms.api.procurement import get_ap_aging_report

        # Create test invoices with different ages
        today = date.today()

        # 0-30 days old
        inv1 = frappe.get_doc({
            "doctype": "BEI Invoice",
            "posting_date": today - timedelta(days=15),
            "total_amount": 10000,
            "paid_amount": 0,
            "status": "Pending Payment"
        }).insert()

        # 31-60 days old
        inv2 = frappe.get_doc({
            "doctype": "BEI Invoice",
            "posting_date": today - timedelta(days=45),
            "total_amount": 20000,
            "paid_amount": 0,
            "status": "Pending Payment"
        }).insert()

        # Get report
        result = get_ap_aging_report()

        self.assertEqual(result["aging_summary"]["0-30"]["count"], 1)
        self.assertEqual(result["aging_summary"]["0-30"]["amount"], 10000)
        self.assertEqual(result["aging_summary"]["31-60"]["count"], 1)
        self.assertEqual(result["aging_summary"]["31-60"]["amount"], 20000)
        self.assertEqual(result["total_payables"], 30000)
```

**Step 4: Test locally**

Use `/local-frappe` to test the new endpoint:

```bash
/local-frappe
# This will:
# 1. Run test_accounting_api tests
# 2. Start local server for manual API testing
# 3. Verify aging buckets calculate correctly
```

Expected: All tests PASS, API returns correct aging summary

**Step 5: Deploy via PR**

```bash
/pr-deploy

# Commit message (auto-generated):
# "feat(accounting): add AP aging report using existing Invoice

- Get AP aging from BEI Invoice DocType (no duplication)
- 6 buckets: 0-30, 31-60, 61-90, 91-120, 121-150, 150+
- Calculate outstanding by posting_date (per Izza's requirement)
- Reuse existing Module 10 infrastructure

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 2: Build New Billing Module

### Task 4: BEI Store Type Master

**Goal:** Create Store Type master for billing classification. **THIS IS GENUINELY NEW.**

**Files:**
- Create: `hrms/hr/doctype/bei_store_type/bei_store_type.json`
- Create: `hrms/hr/doctype/bei_store_type/bei_store_type.py`

**Step 1: Create BEI Store Type DocType JSON**

```json
{
 "actions": [],
 "creation": "2026-02-06 12:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "store",
  "store_type",
  "price_list_multiplier"
 ],
 "fields": [
  {
   "fieldname": "store",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Store",
   "options": "Department",
   "reqd": 1,
   "unique": 1
  },
  {
   "fieldname": "store_type",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Store Type",
   "options": "JV\nManaged Franchise\nFull Franchise",
   "reqd": 1
  },
  {
   "description": "Markup percentage for this store type (e.g., 8 for 8%)",
   "fieldname": "price_list_multiplier",
   "fieldtype": "Percent",
   "label": "Price List Multiplier"
  }
 ],
 "modified": "2026-02-06 12:00:00.000000",
 "modified_by": "Administrator",
 "module": "HR",
 "name": "BEI Store Type",
 "naming_rule": "By fieldname",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Accounting Analyst",
   "share": 1,
   "write": 1
  }
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

**Step 2: Create controller**

```python
import frappe
from frappe.model.document import Document

class BEIStoreType(Document):
    def validate(self):
        """Validate store type configuration."""
        # Ensure store exists
        if not frappe.db.exists("Department", self.store):
            frappe.throw(f"Department {self.store} does not exist")
```

**Step 3: Test and import master data**

Use `/local-frappe` to test DocType and import data:

```bash
/local-frappe
# This will:
# 1. Create DocType in local instance
# 2. Import master data from Google Sheet
# 3. Verify store type validation works
```

Import from: `https://docs.google.com/spreadsheets/d/1gJojjZ3CeYxGoA2Aw0EqPuWejmmwTI6qmN8LDQFVxCs/edit?gid=0#gid=0`

**Step 4: Deploy via PR**

```bash
/pr-deploy

# Commit message (auto-generated):
# "feat(accounting): add Store Type master for billing

- Created BEI Store Type DocType (JV/Managed/Franchise)
- Link to Department (store)
- Price list multiplier for delivery/logistics markup
- Genuinely new feature - no duplication

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### Task 5: BEI Billing Schedule DocType

**Goal:** Create Billing Schedule DocType for franchise billing automation. **THIS IS GENUINELY NEW.**

**Files:**
- Create: `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py`
- Create: `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json`
- Create: `hrms/hr/doctype/bei_billing_schedule/test_bei_billing_schedule.py`
- Create: `hrms/hr/doctype/bei_billing_line_item/bei_billing_line_item.json`

**Step 1: Write failing test for billing calculation**

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from datetime import date

class TestBEIBillingSchedule(FrappeTestCase):
    def setUp(self):
        """Set up test data."""
        # Create store type master
        if not frappe.db.exists("BEI Store Type", "BGC"):
            frappe.get_doc({
                "doctype": "BEI Store Type",
                "store": "BGC",
                "store_type": "Managed Franchise"
            }).insert()

    def test_managed_franchise_billing(self):
        """Test billing calculation for Managed Franchise."""
        billing = frappe.get_doc({
            "doctype": "BEI Billing Schedule",
            "billing_period": "2026-02",
            "store": "BGC",
            "store_type": "Managed Franchise",
            "gross_sales": 500000.00,
            "net_sales": 450000.00,
            "online_sales": 50000.00,
            "delivery_cost": 80000.00,
            "logistics_cost": 30000.00
        })
        billing.insert()

        # Managed Franchise formulas from questionnaire:
        # Deliveries = (Cost + 12% VAT) + 8%
        # Royalty = 7% gross + 12% VAT
        # Management = 2.5% gross + 12% VAT
        # Marketing = 5% gross
        # eCommerce = 5% online

        expected_royalty = 500000 * 0.07 * 1.12  # 39,200
        expected_management = 500000 * 0.025 * 1.12  # 14,000
        expected_marketing = 500000 * 0.05  # 25,000

        self.assertEqual(billing.royalty_fee, expected_royalty)
        self.assertEqual(billing.management_fee, expected_management)
        self.assertEqual(billing.marketing_fee, expected_marketing)
```

**Step 2: Run test to verify it fails**

Use `/local-frappe` to run test:

```bash
/local-frappe
# Run: bench --site hrms.bebang.ph run-tests --module bei_billing_schedule
```

Expected: FAIL with "DocType BEI Billing Schedule not found"

**Step 3: Create DocType JSON with all fields**

Create full DocType JSON (fields: billing_period, store, store_type, gross_sales, net_sales, online_sales, delivery_cost, logistics_cost, royalty_fee, management_fee, marketing_fee, ecommerce_fee, delivery_fee, logistics_fee, repairs_maintenance, preventive_maintenance, line_items, subtotal, vat_amount, total_amount, status, generated_on, sent_on, paid_on)

**Step 4: Create controller with billing logic**

```python
import frappe
from frappe.model.document import Document
from frappe import _

class BEIBillingSchedule(Document):
    def validate(self):
        """Calculate all fees based on store type."""
        self.calculate_fees()
        self.calculate_line_items()
        self.calculate_totals()

    def calculate_fees(self):
        """Calculate fees based on store type and sales data."""
        VAT_RATE = 0.12

        # Get store type from master
        if not self.store_type:
            store_type_doc = frappe.get_value(
                "BEI Store Type",
                {"store": self.store},
                "store_type"
            )
            self.store_type = store_type_doc

        # Billing matrix by store type
        if self.store_type == "JV":
            # JV Stores
            self.royalty_fee = 0
            self.management_fee = 0
            self.marketing_fee = self.net_sales * 0.05 if self.net_sales else 0
            self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

            # Deliveries: Cost + 12% VAT
            if self.delivery_cost:
                self.delivery_fee = self.delivery_cost * (1 + VAT_RATE)

            # Logistics: Cost + 12% VAT
            if self.logistics_cost:
                self.logistics_fee = self.logistics_cost * (1 + VAT_RATE)

        elif self.store_type == "Managed Franchise":
            # Managed Franchise
            # Royalty: 7% gross + 12% VAT
            self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

            # Management: 2.5% gross + 12% VAT
            self.management_fee = self.gross_sales * 0.025 * (1 + VAT_RATE) if self.gross_sales else 0

            # Marketing: 5% gross
            self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

            # eCommerce: 5% online
            self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

            # Deliveries: (Cost + 12% VAT) + 8%
            if self.delivery_cost:
                base_delivery = self.delivery_cost * (1 + VAT_RATE)
                self.delivery_fee = base_delivery * 1.08

            # Logistics: (Cost + 12% VAT) + 8%
            if self.logistics_cost:
                base_logistics = self.logistics_cost * (1 + VAT_RATE)
                self.logistics_fee = base_logistics * 1.08

        elif self.store_type == "Full Franchise":
            # Full Franchise
            # Royalty: 7% gross + 12% VAT
            self.royalty_fee = self.gross_sales * 0.07 * (1 + VAT_RATE) if self.gross_sales else 0

            # Management: N/A
            self.management_fee = 0

            # Marketing: 5% gross
            self.marketing_fee = self.gross_sales * 0.05 if self.gross_sales else 0

            # eCommerce: 5% online
            self.ecommerce_fee = self.online_sales * 0.05 if self.online_sales else 0

            # Deliveries: (Cost + 12% VAT) + 8%
            if self.delivery_cost:
                base_delivery = self.delivery_cost * (1 + VAT_RATE)
                self.delivery_fee = base_delivery * 1.08

            # Logistics: (Cost + 12% VAT) + 8%
            if self.logistics_cost:
                base_logistics = self.logistics_cost * (1 + VAT_RATE)
                self.logistics_fee = base_logistics * 1.08

    def calculate_line_items(self):
        """Update line item amounts."""
        for item in self.line_items:
            item.amount = (item.quantity or 0) * (item.unit_price or 0)

    def calculate_totals(self):
        """Calculate subtotal, VAT, and total."""
        # Sum all fees
        fees = [
            self.royalty_fee or 0,
            self.management_fee or 0,
            self.marketing_fee or 0,
            self.ecommerce_fee or 0,
            self.delivery_fee or 0,
            self.logistics_fee or 0,
            self.repairs_maintenance or 0,
            self.preventive_maintenance or 0
        ]

        # Add line items
        for item in self.line_items:
            fees.append(item.amount or 0)

        self.subtotal = sum(fees)

        # VAT already included in most fees, but calculate for line items
        vat_amount = 0
        for item in self.line_items:
            if item.vat_applicable:
                vat_amount += (item.amount or 0) * 0.12

        self.vat_amount = vat_amount
        self.total_amount = self.subtotal + self.vat_amount

    def send_to_store(self):
        """Generate and send Statement of Account to store."""
        self.status = "Sent"
        self.sent_on = frappe.utils.now()
        self.save()

        # TODO: Generate PDF and send via email
        frappe.msgprint(_("Billing statement sent to {0}").format(self.store))
```

**Step 5: Test locally**

Use `/local-frappe` to test billing calculations:

```bash
/local-frappe
# This will:
# 1. Run billing schedule tests
# 2. Create sample billing with test data
# 3. Verify formulas calculate correctly for each store type
```

Expected: All tests PASS, billing formulas match questionnaire requirements

**Step 6: Deploy via PR**

```bash
/pr-deploy

# Commit message (auto-generated):
# "feat(accounting): add Billing Schedule for franchise billing

- Created BEI Billing Schedule DocType
- Automated billing calculation by store type:
  - JV: Marketing 5% net, eCommerce 5%
  - Managed: Royalty 7%, Management 2.5%, Marketing 5%, 8% markup
  - Full Franchise: Royalty 7%, Marketing 5%, 8% markup
- Track billing status (Draft → Sent → Paid/Disputed)
- Line item support for custom charges
- Genuinely new feature - no duplication

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Phase 3: Frontend Integration (my.bebang.ph)

### Task 6: Accounting Dashboard Page

**Goal:** Create accounting dashboard showing RFP queue, cash alerts, and billing summary.

**Files:**
- Create: `bei-tasks/app/accounting/page.tsx`
- Create: `bei-tasks/components/accounting/accounting-dashboard.tsx`
- Create: `bei-tasks/lib/api/accounting.ts`

**Step 1: Create API client for accounting**

Create: `bei-tasks/lib/api/accounting.ts`

```typescript
import { apiClient } from './client'

export const accountingApi = {
  // RFP endpoints (use existing Payment Request APIs)
  async getPendingPaymentRequests() {
    return apiClient.get('/api/method/hrms.api.procurement.get_pending_payment_approvals')
  },

  // Cash monitoring endpoints
  async getClosingReportsWithAlerts(store?: string) {
    return apiClient.get('/api/method/hrms.api.store.get_closing_report_status', {
      params: { store, with_alerts: 1 }
    })
  },

  // Billing endpoints
  async getBillingList(store?: string, status?: string) {
    return apiClient.get('/api/method/hrms.api.accounting.get_billing_list', {
      params: { store, status }
    })
  },

  async generateBilling(billingPeriod: string, store: string) {
    return apiClient.post('/api/method/hrms.api.accounting.generate_billing', {
      billing_period: billingPeriod,
      store
    })
  },

  // AP aging endpoint
  async getAPAgingReport() {
    return apiClient.get('/api/method/hrms.api.procurement.get_ap_aging_report')
  }
}
```

**Step 2: Create dashboard component**

Create: `bei-tasks/components/accounting/accounting-dashboard.tsx`

```typescript
'use client'

import { useQuery } from '@tanstack/react-query'
import { accountingApi } from '@/lib/api/accounting'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, FileText, TrendingUp } from 'lucide-react'

export function AccountingDashboard() {
  const { data: pendingRFPs } = useQuery({
    queryKey: ['pending-rfps'],
    queryFn: () => accountingApi.getPendingPaymentRequests()
  })

  const { data: cashAlerts } = useQuery({
    queryKey: ['cash-alerts'],
    queryFn: () => accountingApi.getClosingReportsWithAlerts()
  })

  const { data: apAging } = useQuery({
    queryKey: ['ap-aging'],
    queryFn: () => accountingApi.getAPAgingReport()
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Accounting Dashboard</h2>
        <p className="text-muted-foreground">
          Monitor payment requests, cash variances, and franchise billing
        </p>
      </div>

      {/* Cash Variance Alerts */}
      {cashAlerts && cashAlerts.alerts?.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Cash Variance Alerts</AlertTitle>
          <AlertDescription>
            {cashAlerts.alerts.length} store(s) have cash variances exceeding thresholds
          </AlertDescription>
        </Alert>
      )}

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Pending RFPs
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {pendingRFPs?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Awaiting validation/approval
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Cash Alerts
            </CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {cashAlerts?.alerts?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              PCF/DF variance alerts
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total AP
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ₱{(apAging?.total_payables || 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Accounts payable
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

**Step 3: Create dashboard page**

Create: `bei-tasks/app/accounting/page.tsx`

```typescript
import { Metadata } from 'next'
import { AccountingDashboard } from '@/components/accounting/accounting-dashboard'

export const metadata: Metadata = {
  title: 'Accounting Dashboard | Finance & Accounting',
  description: 'Monitor payment requests, cash variances, and billing'
}

export default function AccountingPage() {
  return (
    <div className="container py-10">
      <AccountingDashboard />
    </div>
  )
}
```

**Step 4: Test dashboard locally**

```bash
cd ../bei-tasks
npm run dev
```

Navigate to: `http://localhost:3000/accounting`

Expected: Dashboard renders with metrics from Frappe APIs

**Step 5: Commit dashboard feature**

```bash
cd ../bei-tasks
git add app/accounting/ components/accounting/ lib/api/accounting.ts
git commit -m "feat(accounting): add Accounting Dashboard

- Created accounting dashboard page
- Show pending RFPs (using existing Payment Request)
- Show cash variance alerts (using existing Closing Report)
- Show AP aging summary
- No duplication - reuses Module 10 & Module 1 APIs

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary of Changes

### What Was REMOVED (Avoided Duplication)

1. ❌ **BEI RFP DocType** → Use **BEI Payment Request** instead
2. ❌ **BEI Cash Monitor DocType** → Use **BEI Store Closing Report** instead
3. ❌ **RFP submission/approval APIs** → Use **existing payment APIs** instead
4. ❌ **Cash monitoring APIs** → Use **existing closing report APIs** instead

### What Was EXTENDED (Reused Existing)

1. ✅ **BEI Payment Request** - Added rfp_purpose, payee_tin, payee_address, rfp_type fields
2. ✅ **BEI Store Closing Report** - Added variance threshold fields and alert logic
3. ✅ **Procurement API** - Added AP aging endpoint using existing Invoice DocType

### What Was BUILT (Genuinely New)

1. ✅ **BEI Store Type** - Master data for store classification (JV/Managed/Franchise)
2. ✅ **BEI Billing Schedule** - Automated billing by store type with fee calculations
3. ✅ **Accounting Dashboard** - Frontend page consolidating existing + new features

### Cost Savings

| Metric | Original Plan | Revised Plan | Savings |
|--------|---------------|--------------|---------|
| New DocTypes | 4 (RFP, RFP Attachment, Cash Monitor, Billing Schedule) | 2 (Billing Schedule, Store Type) | **2 DocTypes** |
| New APIs | ~15 endpoints | ~8 endpoints | **~7 endpoints** |
| New Pages | ~7 pages | ~3 pages | **~4 pages** |
| **Estimated Effort** | **6-7 weeks** | **4 weeks** | **2-3 weeks** |
| **Duplication Risk** | **🔴 HIGH (60%)** | **🟢 NONE (0%)** | **Eliminated** |

---

## Execution Status: ✅ COMPLETE (2026-02-06) - ALL KNOWN LIMITATIONS RESOLVED

**All phases implemented, deployed, and E2E tested. All 4 post-launch known limitations addressed (Tasks #8-#11).**

### Implementation Timeline

| Phase | Task | Status | Deployment |
|-------|------|--------|------------|
| Phase 1 | Task 1: Extend BEI Payment Request for RFP | ✅ Complete | Build #21741693154 |
| Phase 1 | Task 2: Extend BEI Store Closing Report for variance alerts | ✅ Complete | Build #21741693154 |
| Phase 1 | Task 3: AP Aging Dashboard endpoint | ✅ Complete | Build #21741693154 |
| Phase 2 | Task 4: BEI Store Type master | ✅ Complete | Build #21741693154 |
| Phase 2 | Task 5: BEI Billing Schedule DocType | ✅ Complete | Build #21741693154 + #21742533442 (fetch_from fix) |
| Phase 3 | Task 6: Accounting Dashboard frontend | ✅ Complete | Vercel (bei-tasks main) |
| Post-launch | Task 9: Test Billing Schedule line_items child table | ✅ Complete | 3 new tests (mixed VAT, zero values, JV store) |
| Post-launch | Task 10: Connect send_billing_statement to email delivery | ✅ Complete | HTML SOA via frappe.sendmail + API wrapper |
| Post-launch | Task 8: Create /dashboard/procurement/payments/new page | ✅ Complete | Branch `feat/payment-request-form` - pending PR merge to main for Vercel deploy |
| Post-launch | Task 11: Bulk import Store Type master data (~42 stores) | ✅ Complete | 52 stores mapped (24 JV, 26 Managed Franchise, 2 Full Franchise) via `scripts/import_store_types.py` |

### E2E Test Report

**Test Run:** 2026-02-06 15:45 PHT
**Result:** 8/8 PASS, 7 bugs found and fixed during testing

| Test | Result | Evidence |
|------|--------|----------|
| Payment Request RFP Happy Path | ✅ | PAY-2026-00049 |
| Payment Request Missing Fields (negative) | ✅ | Mandatory field validation |
| Store Closing Report Variance Alert | ✅ | BEI-CLOSE-2026-00012 |
| AP Aging 6-Bucket Dashboard | ✅ | API verified |
| Store Type Managed Franchise Rates | ✅ | Default rates auto-populated |
| Billing Schedule Automated Calculation | ✅ | BILL-2026-01-Operations - BEI |
| RBAC Accounting Dashboard | ✅ | HQ User role access |
| Payment Approval 4-Level Chain | ✅ | PAY-2026-00050 (3-level), PAY-2026-00051 (4-level with CEO) |

### Production Builds

| Build | Commit | Changes |
|-------|--------|---------|
| #21741693154 | `5f6f6564e` | Missing billing_line_item.py + Docker -T flag fix |
| #21742533442 | `b56e9af60` | Billing Schedule fetch_from fix |
| Vercel (bei-tasks) | CORS proxy | Next.js API routes for accounting dashboard |

### Known Limitations

1. ~~`/dashboard/procurement/payments/new` page doesn't exist yet~~ **RESOLVED** - Form built with all RFP fields, Zod validation, 4-level approval preview, CEO warning for >PHP 1M. Branch `feat/payment-request-form` pending PR merge to Vercel.
2. ~~Billing Schedule line_items table not tested~~ **RESOLVED** - 3 new tests added (mixed VAT, zero values, JV store); total 10 tests
3. ~~`send_billing_statement` API not yet connected to email delivery~~ **RESOLVED** - HTML SOA generated and sent via `frappe.sendmail`; `get_billing_list` API also added
4. ~~Store Type master data needs bulk import from Google Sheet for all ~42 stores~~ **RESOLVED** - 52 stores imported (24 JV, 26 Managed Franchise, 2 Full Franchise) via `scripts/import_store_types.py`

**All known limitations addressed 2026-02-06.**

---

## Post-Launch Code Review & Testing (2026-02-06)

### Code Review (Opus)

**Backend review (Task #1):** COMPLETE - Reviewed all Python files for Tasks 1-5 (Payment Request, Closing Report, AP Aging, Store Type, Billing Schedule). Found bugs in AP aging query (wrong column name) and Store Type permissions (too restrictive).

**Frontend review (Task #2):** COMPLETE - Reviewed payment request form page (616 lines). Checked for XSS, Zod validation, error handling, accessibility, Shadcn patterns.

| File | Critical | Warning | Suggestion |
|------|----------|---------|------------|
| hrms/api/procurement.py (AP aging SQL) | 1 | 0 | 0 |
| hrms/api/procurement.py (role guards) | 3 | 0 | 0 |
| hrms/api/procurement.py (input sanitization) | 3 | 0 | 0 |
| hrms/api/accounting.py (HTML injection) | 1 | 0 | 0 |
| hrms/api/accounting.py (N+1 query) | 0 | 1 | 0 |
| hrms/hr/doctype/bei_store_type/*.json (perms) | 0 | 1 | 0 |
| hrms/hr/doctype/bei_billing_schedule/*.py (flt, VAT) | 0 | 2 | 0 |
| hrms/hr/doctype/bei_billing_line_item/*.py (bare except) | 0 | 1 | 0 |
| bei-tasks app/.../payments/new/page.tsx | 0 | 0 | TBD |
| **TOTALS** | **8** | **5** | **TBD** |

**Summary:** 8 critical security issues found and fixed (role guards, input sanitization, HTML injection). 5 warnings fixed (SQL columns, permissions, floating-point, N+1, bare except). All fixes included in [PR #11](https://github.com/Bebang-Enterprise-Inc/hrms/pull/11).

### Deployment

| PR | Repo | Status | Build |
|----|------|--------|-------|
| [#6](https://github.com/Bebang-Enterprise-Inc/bei-tasks/pull/6) | bei-tasks | MERGED (2026-02-06 13:05 UTC) | Vercel auto-deploy |
| [#7](https://github.com/Bebang-Enterprise-Inc/bei-tasks/pull/7) | bei-tasks | MERGED (2026-02-06 13:12 UTC) | Auth checks, AP aging transform, payment form type fixes |
| [#10](https://github.com/Bebang-Enterprise-Inc/hrms/pull/10) | hrms | MERGED (earlier) | Build #21741693154, #21742533442 |
| [#11](https://github.com/Bebang-Enterprise-Inc/hrms/pull/11) | hrms | MERGED (2026-02-06 13:23 UTC) | DEPLOYED - Build #21752100263 all jobs SUCCESS |

### E2E Test Results

| # | Test | Result | Evidence |
|---|------|--------|----------|
| 1 | Payment Request RFP fields visible | PASS | test01_payment_request_rfp_fields.png |
| 2 | Store Closing Report variance alert | PASS | test02_variance_alert.png |
| 3 | AP Aging dashboard data | PASS (re-test) | test03_ap_aging_PASS.png - 6 buckets returned correctly |
| 4 | Store Type master query | PASS (re-test after fix) | Bug #20 fixed, 52 records seeded, verified after fresh no_cache build #21754002360 |
| 5 | Billing Schedule (JV) | PASS (re-test after fix) | Bug #19 fixed, DocType permissions updated, verified after fresh no_cache build #21754002360 |
| 6 | Billing Schedule (Managed Franchise) | PASS (re-test) | test06_billing_managed.png - BILL-2026-01, gross 1M, net 892K |
| 7 | Accounting Dashboard page | PASS | test07_accounting_dashboard.png |
| 8 | Payment Request form page | PASS | test08_payment_request_form.png, test08_form_complete_enabled.png |
| 9 | RBAC - staff blocked from accounting | PASS | test09_rbac_staff_blocked.png, test09_rbac_staff_payments_accessible.png |
| 10 | Approval workflow (4-level chain) | PASS (re-test) | test10_approval_chain_4level.png, test10_ceo_required_1.5M.png, test10_no_ceo_500k.png |

### Bug Fixes

| Bug | Severity | Fixer | Status |
|-----|----------|-------|--------|
| AP Aging Report: Unknown column 'posting_date' in SQL query (Task #14) | Critical | backend-fixer | FIXED |
| Backend not deployed: billing endpoints missing in prod (Task #15) | Critical | deployer | FIXED - PR #11 merged + deployed (build #21752100263) |
| Store Type Master: permission denied for test.hr, only 1 record (Task #16) | Medium | backend-fixer | FIXED |
| Frontend: Payment detail page 404 on /payments/PAY-xxx (Task #17) | Medium | frontend-fixer | FIXED - Dynamic route [id] page added |
| Security: Missing role guards on 6 payment approval methods | Critical | backend-fixer | FIXED (PR #11) |
| Security: Input sanitization missing on 7 create/update endpoints | Critical | backend-fixer | FIXED (PR #11) |
| Security: HTML injection in billing emails | Critical | backend-fixer | FIXED (PR #11) |
| Floating-point comparison without flt() | Low | backend-fixer | FIXED (PR #11) |
| N+1 query in invoice and payment request | Low | backend-fixer | FIXED (PR #11) |
| VAT-exempt rate bug (0 is falsy) | Medium | backend-fixer | FIXED (PR #11) |
| Bare except clause | Low | backend-fixer | FIXED (PR #11) |
| Frontend: Procurement Reports and Settings pages 404 (Task #18) | Low | frontend-fixer | FIXED - Stub pages added for reports and settings |
| Billing Schedule list: 403 Not Permitted on Frappe desk (Task #19) | Medium | backend-fixer | FIXED - DocType permissions updated |
| Store Type query returns only 1 record, expected 52 (Task #20) | Low | backend-fixer | FIXED - All 52 store type records seeded in production |

### Final Status

**Status:** COMPLETE -- 10/10 E2E PASS. All 15 bugs fixed and deployed. Frontend (Vercel, commits a84e70b + 11a59a6). Backend PR #12 merged + fresh no_cache build #21754002360 deployed. Store type seeded (52 records).

#### Completed
- [x] Code review: Backend (Tasks 1-5) -- 8 critical, 5 warnings found and fixed
- [x] Code review: Frontend (Task 8) -- Payment request form reviewed
- [x] Deployment: bei-tasks PRs #6 + #7 merged (2026-02-06 13:05/13:12 UTC)
- [x] Deployment: hrms PRs #10 + #11 merged + deployed (build #21752100263)
- [x] Backend bug fixes: AP Aging column (Task #14), Store Type perms (Task #16), security hardening (PR #11)
- [x] Frontend bug fixes: Auth checks, AP aging transform, type coercion (PR #7)
- [x] E2E testing: 10/10 PASS (Tests 4, 5 re-tested after fresh no_cache deploy)
- [x] Follow-up deployment: bei-tasks frontend fixes from commits a84e70b + 11a59a6 (Vercel build #21753626825, 2026-02-06 14:14 UTC)
- [x] Follow-up deployment: hrms PR #12 merged to production. NOTE: auto-triggered build (run #21753580742) used Docker cache and did NOT pick up new code. Fresh no_cache build (run #21754002360) deployed successfully (build 5m14s + deploy 4m28s)
- [x] All 4 follow-up bug code fixes complete (Tasks #17-#20)
- [x] Store type seeding: 52 records seeded in production after fresh build deploy

**Note:** Build #21753580742 used Docker cache and did NOT pick up new code (build_version still 2026-01-29). Build #21754002360 was a fresh no_cache build that includes all fixes.

#### Follow-up Bugs (ALL FIXED AND VERIFIED)
- [x] Task #17: Frontend payment detail page 404 (/payments/PAY-xxx route missing) -- FIXED
- [x] Task #18: Frontend reports/settings pages 404 (low priority, secondary pages) -- FIXED
- [x] Task #19: Billing Schedule desk view 403 (API works, DocType permission issue) -- FIXED
- [x] Task #20: Store Type returns 1 record instead of 52 (data or query filter issue) -- FIXED, all 52 records seeded and verified

#### Key Metrics
| Metric | Value |
|--------|-------|
| Critical security issues found | 8 (all fixed) |
| Warnings found | 5 (all fixed) |
| Bugs found during E2E | 6 (all 6 fixed in code) |
| Follow-up bugs | 4 (all 4 fixed in code: Tasks #17-#20) |
| PRs merged | 6 (bei-tasks #6, #7, commits a84e70b+11a59a6; hrms #10, #11, #12) |
| Docker deploys | 3 (builds #21741693154, #21752100263, #21754002360 fresh no_cache) |
| Vercel deploys | 3 (bei-tasks #6, #7, follow-up #21753626825) |
| E2E pass rate | 100% (10/10 PASS after follow-up fixes deployed and verified) |

#### Sprint A Evidence Status (2026-02-28)
- [x] Runtime checker script added: `scripts/finance/check_finance_runtime.py`
- [x] Restore drill verifier script added: `scripts/finance/verify_restore_drill.py`
- [x] Runtime evidence artifact generated: `output/agent-runs/20260228-finance-config-a/runtime-frappe-checks-finance.json`
- [x] Restore drill report generated: `output/agent-runs/20260228-finance-config-a/DB_RESTORE_DRILL_REPORT.json`
- [ ] Backup manifest present in this worktree at run time: `output/agent-runs/20260228-finance-config-a/PRE_DEPLOY_DEPENDENCY_CHECK.json`

---
---

# Phase 4: Finish Remaining Automation APIs (v2.1)

**Version:** 2.1 (Round 2 audit fixes — 4 blockers resolved)
**Audit Round 1:** 2026-02-12 — 12 CRITICAL, 15 WARNING de-duplicated across 4 domains
**Audit Round 2:** 2026-02-12 — 4 CRITICAL (all quick fixes), 14 WARNING. CONDITIONAL-GO → now GO.
**Questionnaire Sources:** Butch CFO answers (2026-02-10), Accounting team interview (2026-02-05), Process mapping extraction
**Audit Reports:** `scratchpad/plan-audit/finance-automation-v2/`

---

## Context

Phase 1-3 completed on 2026-02-06 with 10/10 E2E tests passing. However, 4 of 6 "Top Automation Priorities" from the accounting team questionnaire remain unbuilt:

- **#2** Payment Application (upload proof → auto-apply to invoices)
- **#3** Automated Acknowledgement Receipt (auto-generate AR on payment)
- **#5** Complete Account Titles (gaps in GL mapping)
- **#6** Fixed Billing Cutoff (auto-generate monthly billing)

**What already exists** (reuse, don't duplicate):
- `BEI Billing Schedule` DocType with fee calculations + `send_to_store()` HTML SOA email
- `BEI Invoice.record_payment(amount, date, ref)` method (updates amount_paid, balance_due, payment_status)
- `BEI Payment Request.mark_as_paid()` → creates Frappe Payment Entry with GL
- `BEI Payment Request.auto_assign_gl_account()` with RFP type→GL map (partial gaps)
- `tag_advance_to_gr()` / `mark_advance_undeliverable()` with DM-1/DM-2 JV patterns
- `get_ap_aging_report()`, `get_billing_list()`, `send_billing_statement()` endpoints
- OR tracking fields on Payment Request (`or_number`, `or_date`, `or_status`, etc.)
- 52 store types seeded (24 JV, 26 Managed, 2 Full Franchise)

---

## Questionnaire-Derived Business Rules

These rules come directly from Butch (CFO) and the accounting team (Ivy, Izza, Liezel, Alyssa). All plan tasks MUST respect them.

### GL Account Codes (from Butch Q8/Q9 + Accounting Team)

| Purpose | Account Number | Full Frappe Name (lookup via account_number) |
|---------|---------------|----------------------------------------------|
| Petty Cash Fund | 1113000 | `1113000 - Petty Cash Fund - BEI` |
| Delivery Fund | 1115000 | `1115000 - Delivery Fund - BEI` |
| Royalty Income | 4000003 | `4000003 - Royalty Income - BEI` |
| Marketing Income | 4000006 | `4000006 - Marketing Income - BEI` |
| Management Fee Income | 4000004 | `4000004 - Management Fee Income - BEI` |
| eCommerce Fee Income | (verify) | (verify during implementation) |
| AR-Others | 1103102 | `1103102 - Accounts Receivable Others - BEI` |
| Advances to Suppliers | 1105203 | NEW — create under 1105200 Prepaid Expenses |

**CRITICAL (Butch Q8):** Account 1103102 stays as AR-Others. Do NOT use for supplier advances. Advances go to NEW 1105203.

### GL Account Lookup Pattern (BLOCKER 8 fix)

Frappe Account names are NOT bare codes. Always look up by `account_number`:

```python
def _get_account_by_code(code, company="Bebang Enterprise Inc."):
    """Get full Frappe account name from account number."""
    return frappe.db.get_value("Account", {"account_number": code, "company": company}, "name")

# Usage: account = _get_account_by_code("1113000")
# Returns: "1113000 - Petty Cash Fund - BEI"
```

### Billing by Store Type Matrix (from Ivy + Process Extraction Image 1)

| Fee Type | JV Stores | Managed Franchise | Full Franchise |
|----------|-----------|-------------------|----------------|
| Deliveries | YES (cost + 8% markup + VAT) | YES (cost + 8% markup + VAT) | YES (cost + 8% markup + VAT) |
| Logistics | YES | YES | YES |
| Royalty Fee | NO | YES (% of gross) | YES (% of gross) |
| Marketing Fee | YES (5% of net sales) | YES (5% of gross sales) | YES (5% of gross sales) |
| Management Fee | NO | YES (2.5% of gross + 12% VAT; Vista Mall = 2%) | NO |
| eCommerce Fee | YES | YES | YES |
| Payroll | YES (JV only) | NO | NO |

**Key formula differences:**
- JV: VAT-inclusive pricing, Marketing Fee = 5% of **net** sales
- Managed/Full Franchise: VAT + 8% Markup on deliveries, Marketing Fee = 5% of **gross** sales
- Management Fee: Only Managed Franchise, 2.5% standard (2% for Vista Mall stores)

### Billing Cutoff Rules (from Ivy + Butch)

| Fee Type | Cycle | Cutoff |
|----------|-------|--------|
| Deliveries | Weekly | Monday-Tuesday (Mon cutoff, Ivy bills Mon-Tue) |
| Logistics | Monthly | 1st week of following month |
| Royalties | Monthly | 1st week, once POS data available |
| Marketing Fee | Monthly | 1st week, once POS data available |
| Management Fee | Monthly | 1st week, once POS data available |
| eCommerce Fee | Monthly | 1st week, once POS data available |

**This plan covers MONTHLY billing only.** Delivery billing (weekly) is a separate scope handled by existing delivery tracking.

### EWT Rules (from Butch Q1-Q4)

| Supplier Type | Rate | Required? |
|---------------|------|-----------|
| Goods (raw materials, food) | 1% | **OPTIONAL** — BEI is regular agent, not Top Agent |
| Services (contractors, maintenance) | 2% | **OPTIONAL** — per supplier agreement |
| Professional Fees (consultants, lawyers) | 5-15% | **MANDATORY** — 5-10% Individual, 10-15% Corporate |
| Rentals | 5% | **MANDATORY** |

**Key:** EWT on goods/services is NOT auto-applied. Only auto-apply for Professional Fees and Rentals. Add `ewt_exempt` flag to Supplier Master for BIR-exempt or internal-party suppliers.

**Form 2307:** Auto-generate per payment. Add monthly print option (not just quarterly).

### AR Terminology (from Butch Q6 + Finance C3 audit)

BEI uses "Acknowledgement Receipt" (AR) as an **internal document** — proof that payment was received and recorded. This is NOT a BIR Official Receipt (OR). Per EOPT Law, the primary BIR document is now the Invoice, not the OR.

**Impact:** The BEI Acknowledgement Receipt DocType is an internal tracking document. No BIR compliance needed for this specific document.

### Payment Priority (from Izza)

Supplier payments are prioritized by **GR date** (delivery date), NOT by invoice date. Oldest deliveries paid first.

### AP Aging Buckets (from Accounting Team)

`[0-30, 31-60, 61-90, 91-120, 121-150, Over 150 days]`

Already implemented in `get_ap_aging_report()` — no changes needed.

### Approval Matrix (from Alyssa)

| Action | Approver 1 | Final Approver |
|--------|-----------|----------------|
| Accounting Transactions | Accounting Manager (Alyssa) | CFO (Butch) |
| Finance Transactions | Finance Manager | CFO (Butch) |

**For new endpoints:** Payment application requires Accounts User or Accounts Manager role. Billing generation requires Accounts Manager role.

---

## Implementation Plan (5 tasks)

### Task 1: Complete GL Account Mapping (~30 lines)

**File:** `hrms/hr/doctype/bei_payment_request/bei_payment_request.py` (modify `auto_assign_gl_account()` at L67-100)

**Changes:**

1. Add `_get_account_by_code(code, company)` helper that looks up full Frappe account name via `account_number` field (BLOCKER 8)
2. Fix `"Vendor Invoice": None` gap — use item-based mapping from existing `_get_expense_account()` in `bei_invoice.py` (BLOCKER 5). Do NOT add `default_expense_account` to BEI Supplier.
3. Update all hardcoded account strings to use `_get_account_by_code()`:
   - PCF: `_get_account_by_code("1113000")`
   - Delivery Fund: `_get_account_by_code("1115000")`
4. Verify accounts `5300`, `5400`, `1200` exist via lookup — if not, use parent accounts
5. Add fallback: if `rfp_type` not in map, log warning via `frappe.log_error()` + leave for manual assignment
6. **NO `account_code_description` stored field** (BLOCKER 3 — DM-5 violation). Account name fetched dynamically in frontend.

**Files:**
- Modify: `hrms/hr/doctype/bei_payment_request/bei_payment_request.py` (~L67-100, ~30 lines changed)
- No JSON changes needed (removed stored field per BLOCKER 3)

---

### Task 2: BEI Acknowledgement Receipt DocType (~80 lines)

**New DocType:** `BEI Acknowledgement Receipt` (simple, no child tables)

**DocType JSON properties:**
```json
{
  "autoname": "naming_series:",
  "module": "HR",
  "fields": [
    {
      "fieldname": "naming_series",
      "fieldtype": "Select",
      "options": "AR-.YYYY.-.#####",
      "default": "AR-.YYYY.-.#####",
      "hidden": 1
    }
  ]
}
```
*R2-FIX: Changed from invalid `format:AR-{YYYY}-{#####}` to valid `naming_series:` pattern.*

**Fields:**
| Fieldname | Fieldtype | Options/Notes |
|-----------|-----------|---------------|
| `billing_schedule` | Link | Options: "BEI Billing Schedule", mandatory |
| `store` | Link | Options: "Department", fetch_from: "billing_schedule.store" |
| `amount` | Currency | Mandatory |
| `payment_date` | Date | Mandatory |
| `payment_reference` | Data | |
| `generated_on` | Datetime | default: "Now", read_only |
| `generated_by` | Link | Options: "User", default: "__user", read_only |
| `status` | Select | Options: "Generated\nSent\nAcknowledged", default: "Generated" |

**Permissions (BLOCKER 7):**
| Role | Read | Write | Create | Delete |
|------|------|-------|--------|--------|
| Accounts Manager | Yes | Yes | Yes | Yes |
| Accounts User | Yes | Yes | Yes | No |
| Store Manager | Yes | No | No | No |
| System Manager | Yes | Yes | Yes | Yes |

**API endpoint:** `generate_acknowledgement_receipt(billing_name)`
- Called automatically by Task 3 after payment applied
- Also callable standalone for manual AR generation
- Creates the AR doc, returns AR name
- Permission check: `frappe.has_permission("BEI Acknowledgement Receipt", "create")` (BLOCKER 7)

**Notification:** Send Google Chat message to Accounting Private space (`spaces/AAAA9RN0JZQ`) with AR details.
- **MUST wrap in try/except** (BLOCKER 10) — Chat failure must NOT block AR creation

**Files:**
- Create: `hrms/hr/doctype/bei_acknowledgement_receipt/bei_acknowledgement_receipt.json`
- Create: `hrms/hr/doctype/bei_acknowledgement_receipt/bei_acknowledgement_receipt.py`
- Create: `hrms/hr/doctype/bei_acknowledgement_receipt/__init__.py`
- Modify: `hrms/api/procurement.py` (new endpoint)

---

### Task 3: Payment Application API (~55 lines)

**Endpoint:** `apply_franchise_payment(billing_name, amount_paid, payment_date, payment_reference, payment_proof=None)`

**Key patterns:**
- Permission check: `frappe.has_permission("BEI Billing Schedule", "write")`
- Savepoint: `frappe.db.savepoint("apply_payment")` (DM-2)
- Accumulate: `flt(billing.amount_paid) + flt(amount_paid)` — NEVER overwrite (BLOCKER 4)
- Overpayment validation: reject if new_total_paid > total_amount
- FIFO invoice application: oldest `posting_date` first (R2-FIX BLOCKER 3)
- Auto-generate AR after payment (Task 2)
- NO `frappe.db.commit()` — Frappe auto-commits (R2-FIX BLOCKER 2)

**Fields added to BEI Billing Schedule JSON:**
| Fieldname | Fieldtype | Notes |
|-----------|-----------|-------|
| `amount_paid` | Currency | read_only, default 0 |
| `balance_due` | Currency | read_only, computed: total_amount - amount_paid |
| `payment_reference` | Data | |
| `payment_proof` | Attach | |
| `paid_on` | Datetime | read_only |

**Status field update (BLOCKER 2):**
`Draft\nSent\nPartially Paid\nPaid\nDisputed\nCancelled`

**Files:**
- Modify: `hrms/api/procurement.py` (new endpoint)
- Modify: `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json` (5 new fields + status update)

---

### Task 4: Auto-generate Monthly Billing (~70 lines)

**Endpoint:** `generate_monthly_billing(billing_period, store=None)`

**Key patterns:**
- Permission check: `frappe.has_permission("BEI Billing Schedule", "create")`
- Per-store savepoint (DM-2)
- Duplicate check: skip if billing exists for period+store (exclude Cancelled)
- Aggregate sales from submitted Store Closing Reports (docstatus=1)
- Skip stores with no POS data + log warning
- Fee calculation delegated to existing `calculate_fees()` in `BEI Billing Schedule.validate()`
- NO `frappe.db.commit()` — Frappe auto-commits (R2-FIX)

**File:** `hrms/api/procurement.py` (new endpoint)

---

### Task 5: Test Scenarios for TEST_SCENARIOS.md

15 scenarios added under `## Finance` section:
- 7 happy path (FIN-001 through FIN-007)
- 6 edge cases (FIN-NEG-001 through FIN-NEG-006)
- 2 RBAC (FIN-RBAC-001, FIN-RBAC-002)

**File:** `docs/testing/TEST_SCENARIOS.md`

---

## Execution Order

1. **Task 1** first (GL mapping fix — smallest, no dependencies)
2. **Task 2** next (AR DocType — needed by Task 3)
3. **Task 3** next (payment application — calls Task 2's function)
4. **Task 4** last (monthly billing — standalone)
5. **Task 5** anytime (test scenarios — can be written in parallel)

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `hrms/hr/doctype/bei_payment_request/bei_payment_request.py` | Fix GL mapping (~30 lines) | 1 |
| `hrms/hr/doctype/bei_acknowledgement_receipt/` (new) | New DocType (3 files) | 2 |
| `hrms/api/procurement.py` | Add 3 endpoints (~200 lines total) | 2, 3, 4 |
| `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.json` | Add 5 fields + update status options | 3 |
| `docs/testing/TEST_SCENARIOS.md` | Add 15 finance scenarios | 5 |

## Pre-Implementation Checklist

Before writing any code, verify:

- [ ] **AUDIT-1:** BEI Billing Schedule status field has "Partially Paid" option added to DocType JSON
- [ ] **AUDIT-2:** `_get_account_by_code()` helper exists and works (test with `_get_account_by_code("1113000")`)
- [ ] **AUDIT-3:** GL accounts 4000003, 4000006, 4000004 exist in Frappe (verify via API)
- [ ] **AUDIT-4:** `save_base64_image()` import available from store.py
- [ ] **AUDIT-5:** Google Chat space `spaces/AAAA9RN0JZQ` (Accounting Private) is accessible
- [ ] **AUDIT-6:** `BEI Store Type` records exist for stores to be billed
- [ ] **AUDIT-7:** `calculate_fees()` in BEI Billing Schedule correctly handles net vs gross sales per store type
- [ ] **AUDIT-8:** Test scenarios FIN-001 through FIN-007 written to TEST_SCENARIOS.md before deployment
- [ ] **AUDIT-9:** `BEI Store Type` DocType exists with `store_type_category` field (JV/Managed Franchise/Full Franchise) *(R2 questionnaire audit)*
- [ ] **AUDIT-10:** Naming Series "AR-.YYYY.-.#####" registered in Frappe (System Settings -> Naming Series) *(R2 backend audit)*

---

## Deferred Items (Separate Project, Needs Accounting Team Sign-off)

### R2-FIX: Explicitly Deferred (Butch requested but out of scope)

| Item | Questionnaire Source | Why Deferred |
|------|---------------------|-------------|
| **BIR Form 2307 generation** | Butch Q3: "Auto-generate per payment + monthly print" | Requires BIR format validation, Alphanumeric Tax Type series, CPA review of withholding schedules. EWT on goods/services is OPTIONAL (BEI is regular agent). Separate project with proper BIR template design. |
| `ewt_exempt` flag on Supplier Master | Butch Q4 | Per-supplier field. Add during EWT/Form 2307 project (not billing). |
| `ewt_applicable` flag on Supplier Master | Butch Q16 | Same — part of EWT project. |
| GL account 1105203 (Advances to Suppliers) | Butch Q9 | Advance payment workflow (procurement scope), not billing. Already exists in procurement plan. |
| Approval workflow states (Manager->CFO sequential) | Alyssa Q33 | Current plan uses role-based permission checks. Sequential approval states require Frappe Workflow DocType — separate enhancement. |

### Previously Deferred (Round 1 — existing production code)

| Item | Issue | Why Deferred |
|------|-------|-------------|
| Output VAT calculation on franchise fees | May be calculated incorrectly in existing billing | Needs Butch/CPA review of current live calculations |
| PFRS 9 impairment assessment | No aged receivables provisioning | Needs loss rate data from accounting team |
| PFRS 15 revenue recognition timing | Unclear for franchise fees | Needs accounting policy decision |
| BIR OR vs AR terminology | AR is internal, OR requires BIR ATP application | If BIR OR needed, separate ATP registration project |

### Post-Launch Backlog (from Round 2 audit — implement after go-live)

| Item | Source | Priority |
|------|--------|----------|
| Vista Mall 2% management fee rate (vs 2.5% standard) | Finance W1 | HIGH — overcharges Vista |
| AR aging report endpoint (`get_ar_aging_report()`) | Finance W4 | HIGH — month-end close |
| Payment tracking child table (individual payment audit trail) | Backend C1 | MEDIUM — audit compliance |
| Automated billing cutoff enforcement (scheduled job) | Finance W2 | MEDIUM |
| BIR 2550M Output VAT export | Finance W5 | MEDIUM |
| Dispute credit memo generation | Finance W3 | LOW |
| Store VAT status check for VAT-exempt stores | Finance W6 | LOW |

---

## Audit Amendments (v2.1) — 2026-02-12

### Audit Methodology

Five specialized agents audited this plan across two rounds, each writing detailed findings to disk.

| Domain | Round 1 | Round 2 | Findings File |
|--------|---------|---------|---------------|
| Frappe Backend | 3 CRITICAL, 4 WARNING | 3 CRITICAL (new), 6 WARNING | `scratchpad/plan-audit/finance-automation-v2/frappe_backend_findings.md` |
| PH Finance | 5 CRITICAL, 6 WARNING | 0 CRITICAL, 6 WARNING (94/100) | `scratchpad/plan-audit/finance-automation-v2/ph_finance_findings.md` |
| Deployment/QA | 2 CRITICAL, 3 WARNING | 1 MEDIUM, 5 WARNING | `scratchpad/plan-audit/finance-automation-v2/deployment_qa_findings.md` |
| Questionnaire | N/A | 1 CRITICAL, 4 WARNING (87.5%) | `scratchpad/plan-audit/finance-automation-v2/questionnaire_compliance_findings.md` |

### Round 1 Blockers (10 found, all fixed in v2.0)

| # | Issue | Fix |
|---|-------|-----|
| B1 | Missing savepoint on multi-doc payment update | Added `frappe.db.savepoint()` |
| B2 | Missing "Partially Paid" status option | Added to Select field |
| B3 | Stored `account_code_description` field (DM-5) | Removed field |
| B4 | Payment overwrites instead of accumulates | Changed to `flt() + flt()` |
| B5 | Non-existent `BEI Supplier.default_expense_account` | Item-based mapping |
| B6 | AR autoname format unspecified | Added naming_series spec |
| B7 | Missing permission checks on all endpoints | Added `frappe.has_permission()` |
| B8 | Bare GL codes don't match Frappe account names | `_get_account_by_code()` helper |
| B9 | No test scenarios | Added 14 scenarios (Task 5) |
| B10 | Chat notification failure blocks AR creation | try/except with log_error |

### Round 2 Blockers (4 found, all fixed in v2.1)

| # | Issue | Fix |
|---|-------|-----|
| C1 | AR autoname `format:AR-{YYYY}-{#####}` is invalid Frappe syntax | Changed to `naming_series:` |
| C2 | `frappe.db.commit()` after savepoint breaks atomicity | Removed — Frappe auto-commits |
| C3 | FIFO order unspecified for invoice payment application | Added `posting_date ASC` |
| C4 | Form 2307 silently omitted despite Butch requesting it | Explicitly deferred with justification |

### Questionnaire Compliance: 87.5% (21/24 in-scope requirements)

Verified against: Butch CFO answers (Q1-Q9, Q12, Q16-Q17), Ivy (billing matrix), Izza (AP aging, payment priority), Alyssa (approval matrix), Liezel (variance thresholds).

**3 items deferred** (Form 2307, ewt_exempt, GL 1105203) — all justified in Deferred Items section above.

### GO/NO-GO Gate

| Metric | Round 1 | Round 2 |
|--------|---------|---------|
| Verdict | NO-GO | **GO** (all 4 blockers fixed) |
| CRITICAL findings | 12 | 4 (all quick fixes, resolved) |
| PH Finance score | 31/100 | 94/100 |
| Questionnaire compliance | N/A | 87.5% |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-12 | Initial plan — 4 tasks |
| v2.0 | 2026-02-12 | Round 1 amendment: 10 blocker fixes + questionnaire alignment |
| v2.1 | 2026-02-12 | Round 2 amendment: Fixed AR autoname, removed db.commit(), added FIFO, deferred Form 2307 |

## Implementation Status

- [x] Task 1: GL Account Mapping — COMPLETE (code written)
- [x] Task 2: BEI Acknowledgement Receipt DocType — COMPLETE (code written)
- [x] Task 3: Payment Application API — COMPLETE (code written)
- [x] Task 4: Monthly Billing Generation — COMPLETE (code written)
- [x] Task 5: Test Scenarios — COMPLETE (15 scenarios added)
- [ ] Deployment: Requires full Docker build (new DocType) — NOT YET DEPLOYED

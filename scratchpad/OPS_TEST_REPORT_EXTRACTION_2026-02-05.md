# my.bebang.ph Ops Test Report - Complete Extraction
**Source:** Google Doc - my.bebang.ph Complete Ops Training Guide (Feedback)
**Extracted:** 2026-02-05
**Images Analyzed:** 26 screenshots

---

## EXECUTIVE SUMMARY

### Critical Issues Found (BLOCKERS)
| # | Module | Issue | Severity |
|---|--------|-------|----------|
| 1 | Opening Report | "Failed to submit report - Request failed" error | **CRITICAL** |
| 2 | Closing Report | Cannot proceed even if checklist complete | **CRITICAL** |
| 3 | Maintenance Request | pymysql.err.DataError: (1406, "Data too long for column 'photo' at row 1") | **CRITICAL** |
| 4 | FQI Report | Link validation error: "Could not find Store: TEST-STORE-BBC" | **CRITICAL** |
| 5 | POS Upload | "Failed to upload POS files - User does not have doctype access via role permission for document BEI POS Upload" | **CRITICAL** |
| 6 | Cycle Count | Cannot Submit the file | **CRITICAL** |
| 7 | Coverage Request | "Failed to create coverage request" error | **CRITICAL** |
| 8 | Leave Approval | Approved leave not reflected in crew account | **HIGH** |
| 9 | Store Visits | Cannot "submit visit" due to no store available | **HIGH** |
| 10 | Labor Planning | Cannot test - no stores assigned | **HIGH** |

### Features Working Correctly
| Module | Status |
|--------|--------|
| My Profile | Working completely |
| Store Ordering (Submission) | Working - Order ID: BEI-ORD-2026-00009 submitted |
| Leave Application (Submission) | Working |
| Supervisor Queue | Working - shows pending leave requests |
| Team Overview | Working - shows attendance summary |
| Store Visit Scoring | Working - 100-point audit scoring functional |

---

## DETAILED FINDINGS BY MODULE

---

### STORE OPERATIONS MODULE

#### 1. Opening Report (/dashboard/store-ops/opening)
**Status:** CRITICAL ISSUES

**Screenshot Evidence (kix.4fkamgo2n05y):**
- Mobile view showing "Cold Storage Temperature" section
- **Error displayed:** Red banner "Failed to submit report - Request failed"
- Test note entered: "TEST:// letter C - equipment with defective chiller"
- "Submit Opening Report" button visible at bottom

**Feedback from Ops Team:**
- Checklist can still be submitted if incomplete, unchecked items will be raised/notified to Area Supervisor, Regional Manager
- Notes/Remarks shall explain incomplete checklists
- **ISSUE:** Report cannot proceed even if completed, no error flagged for store crew and supervisor

**Recommended Changes:**
| Item | Current | Recommended Change |
|------|---------|-------------------|
| B. Staff Readiness | Store Opening Huddle Conducted | **REMOVE ENTIRELY** |
| D. Funds - Petty Cash | Opening shift | **MOVE to Closing Shift** |
| D. Funds - Sales Deposit | Opening shift | **MOVE to Mid Shift** |
| E. Backup Station | "Stocks are Available" | Change to "All Stock Sufficient, Expired Items Logged" |
| F. Frozen Milk | "Stored at proper temperature (-18C or below)" | **REMOVE** - Cold Storage picture replaces this |
| G. Toppings Station | "Stocks are Available" | Change to "All Stock Sufficient, Expired Items Logged" |
| H. Dispatch - Pre-order schedule | Opening | **MOVE to Closing shift checklist** |
| H. Dispatch Stocks | "Stocks are Available" | Change to "All Stock Sufficient" |
| C. Equipment | Exists | **REMOVE** (redundant process) |
| D. Food Quality | Exists | **REMOVE** (redundant process) |
| Cold Storage Temp | Single upload | **Allow multiple picture uploads** |

---

#### 2. Closing Report (/dashboard/store-ops/closing)
**Status:** CRITICAL ISSUE

**Screenshot Evidence (kix.dx061eblriq8 - Desktop, kix.p8amp8luws8i - Mobile):**

**Desktop View:**
- Shows "Cash Fund Count" section
- Fields: Petty Cash Fund (₱15,000), Delivery Fund (₱45,000), Change Fund (₱20,000)
- Total Funds: ₱80,000.00
- Notes: "No Funds Shortage"
- "POS Down Mode" toggle visible (disabled)
- User: test.crew1@bebang.ph

**Mobile View (POS Down Mode Active):**
- "POS Down Mode" toggle is ON
- Yellow warning: "Manual Entry Mode Active - Enter estimated sales data below. Upload POS files when system is restored."
- Estimated Total Sales: ₱20,000
- Transaction Count: 7
- POS Down Notes: "Electric issues"
- "Next: Checklist" button at bottom

**Issues Found:**
- **Cannot proceed with next step (checklist) even if checklist complete** - for both store crew and supervisor access

**Recommended Changes:**
| Current | Recommended |
|---------|-------------|
| Cash input fields | Add **denomination breakdown** for Petty Cash Fund, Delivery Fund, and Change Fund |
| N/A | Include declared amount for Petty Cash Voucher and Delivery Fund Voucher (depleted amounts) |

---

#### 3. Midshift Report (/dashboard/store-ops/midshift)
**Status:** NEEDS REDESIGN

**Recommended Complete Replacement of Checklist:**
| New Checklist Item | Type |
|--------------------|------|
| Scheduled Maintenance are with Permits | Checklist |
| Scheduled Delivery of materials are with Permits | Checklist |
| Practice Clean as you Go | Checklist |
| FIFO and FEFO are being observed | Checklist |
| 5S are being followed | Checklist |
| Cold Storage Temperature submission (all cold storage) | Photo upload |

**Remove:** Cleanliness Status section

**New Rule:**
- Checklist submission can be incomplete (as schedule for delivery/maintenance can be with or without)
- Midshift Checklist shall only be done during **3pm-4pm window time** - otherwise will lock and store must explain why undone

---

#### 4. Handover Report (/dashboard/store-ops/handover)
**Status:** NEEDS UPDATES

**Recommended Changes:**
| Current Label | New Label |
|---------------|-----------|
| "Expected Cash (from X-reading)" | "X-reading Cash" |
| "Actual Cash Count" | "Sales Cash Deposit" |

**Access Change:** Currently limited to Store Supervisor → **Change to Store Crew / OIC**

---

#### 5. Cash Deposit (/dashboard/store-ops/deposit)
**Status:** NEEDS UPDATES

**Recommended Changes:**
| Item | Change |
|------|--------|
| N/A | Add button to select Bank Deposit details if Pickup / Bank Deposit |
| Dates Covered | Change from date range to **single day only** |
| Deposit Slip Photos | Allow **maximum 4 uploads** |

---

#### 6. POS Report (/dashboard/store-ops/pos)
**Status:** CRITICAL ERROR

**Screenshot Evidence (kix.88e3b99q4zjc - Mobile, kix.vpu0818gj3ri - Desktop):**

**Mobile View:**
- Sales Date: Feb 4, 2026
- POS System: MOSAIC
- "POS Files Upload" section showing 0/5 uploaded
- Required files: Discount Report, Transaction Report, Product Mix, Daily Sales Revenue - Summary, Sales Summary

**Desktop View:**
- Shows uploaded files with green checkmarks:
  - Transaction Report (20260203184625).xlsx - 26.8 KB
  - productmix_2026-02-03 6_46_14 pm.xlsx - 9.7 KB
  - Daily Sales Revenue - Summary (2026-02-02) (20260203184429).xlsx - 23.8 KB
  - Sales Summary (2026-02-02) (20260203184413).xlsx - 7.1 KB
- **ERROR:** Red toast "Failed to upload POS files"
  - "User <strong>test.crew1@bebang.ph</strong> does not have doctype access via role permission for document <strong>BEI POS Upload</strong>"

**Access Issue:** Currently limited to Store Supervisor → **Change to Store Crew / OIC**

**New Validation Rule:** File upload shall reject if date submitted is not the same with the file uploaded

---

#### 7. Maintenance Request (/dashboard/store-ops/maintenance)
**Status:** CRITICAL DATABASE ERROR

**Screenshot Evidence (kix.3hg653p06ie1 - Mobile, kix.mrz2n9imlofi - Desktop):**

**Mobile View:**
- Location: Kitchen
- **Error:** Red banner "Failed to submit request"
- Technical error: `pymysql.err.DataError: (1406, "Data too long for column 'photo' at row 1")`
- Photo Evidence section shows 1/5 photos uploaded
- "Urgent Request" toggle visible

**Desktop View:**
- Same error displayed
- Photo uploaded shows a person's face (test photo)
- "Submit Request" button at bottom

**Root Cause:** Database column 'photo' too small for image data

---

### INVENTORY MODULE

#### 8. Store Ordering (/dashboard/inventory/ordering)
**Status:** WORKING with recommendations

**Screenshot Evidence (kix.essndqo4qr6t):**
- Shows "Order Submitted" success screen
- Green checkmark icon
- Message: "Your order has been submitted and is pending supervisor approval."
- Order ID: BEI-ORD-2026-00009
- Toast: "Order submitted for approval"
- "Back to Inventory" button

**Recommended Changes:**
| Item | Recommendation |
|------|----------------|
| Items list | Seclude to **store SKU only** - eliminate wrong ordering |
| Quantity display | Show **quantity per UOM per item** (e.g., "Long Spoon minimum order quantity is 3400 pcs" or "1 Box of Crushed Graham is 24 packs") |
| Item sorting | Most ordered items at TOP, least ordered at BOTTOM |
| After submit | Show **confirmatory list** (remove items without orders) before final proceed |
| User access | Change from Store Supervisor to **Store Staff / OIC** |
| Approver | Change from Store Supervisor to **Area Supervisor** |

---

#### 9. Cycle Count (/dashboard/inventory/counts)
**Status:** CRITICAL - CANNOT SUBMIT

**Screenshot Evidence (kix.u7iy6l5dc06o):**
- Page: Dashboard > Inventory > Counts
- Store: TEST-STORE-BGC
- Header: "Cycle Count"
- Instruction: "Count all physical inventory for each item below. The system will automatically flag any variances greater than 10%."
- Section: "Today's Count Items - Enter actual physical counts"
- Sample items shown:
  - 365 Clean P 1303 1 gallon x 4/case (KL004 | GAL) - Count: 0 GAL
  - 365 Clean P 1303 1 gallon x 4/case (KL004-A | CASE) - Count: 4 CASE (highlighted yellow with remarks option)
  - ALUMINUM PIZZA SCREEN (OS107 | PCS) - Count: 0 PCS
  - BALL VALVE 3/4 - Count: 0 PIECE
- "Submit Cycle Count" button at bottom
- **ISSUE:** Cannot Submit the file

**Recommended Changes:**
| Item | Recommendation |
|------|----------------|
| Header | Add **date picker button** to inform inventory date |
| Input validation | **Prevent negative entries** - current button still allows negative count |
| After submit | Show confirmatory list (remove items without counts) before proceed |
| Resubmission | Allow **override/resubmit** to correct wrong counts |

---

#### 10. Variance Report (/dashboard/inventory/variances)
**Status:** NOT AVAILABLE - "Not yet Available on the buttons"

---

#### 11. Shelf Life Check (/dashboard/inventory/shelf-life)
**Status:** NOT AVAILABLE - "Not yet Available on the buttons"

---

#### 12. Returns (/dashboard/inventory/returns)
**Status:** NOT TESTABLE

**Screenshot Evidence (kix.km5mt2ci9b8s):**
- Page: Dashboard > Inventory > Returns
- Header: "Item Returns - Process returns to commissary"
- Store dropdown shows: "No stores assigned. Contact your manager."

---

### RECEIVING MODULE

#### 13. Dispatch Receive (/dashboard/receiving/dispatch)
**Status:** NO DATA - "No information as of the moment"

---

#### 14. FQI Report (/dashboard/receiving/fqi)
**Status:** CRITICAL ERROR

**Screenshot Evidence (kix.66p3mf6z3vyh - Desktop, kix.bh5s83vc17 - Mobile):**

**Desktop View:**
- Shows error stack trace
- Error: `frappe.exceptions.LinkValidationError: Could not find Store: TEST-STORE-BBC`
- Full traceback visible

**Mobile View:**
- "Photo Evidence" section visible
- Same LinkValidationError displayed
- "Submit FQI Report" button at bottom

**Recommended Changes:**
| Current | Recommended |
|---------|-------------|
| Item Name | Should be **dropdown list** instead of manual typing |
| "Other" selection | Should trigger **manual encoding prompt** |

---

### HR SELF-SERVICE MODULE

#### 15. Leave Application (/dashboard/hr/leave)
**Status:** PARTIAL WORKING - Approval not reflecting

**Screenshot Evidence (kix.l7iexd1p98to):**
- Page: Dashboard > Hr > Leave
- Header: "Leave Management - View balances, request leave, and track history"
- "+ Request Leave" button visible
- Leave balances shown:
  - Casual Leave: 15 days (Used: 0, Total: 15)
  - Sick Leave: 10 days (Used: 0, Total: 15, **Pending: 5 days**)
  - Privilege Leave: 5 days (Used: 0, Total: 5)
- Tabs: Pending (1) | History
- Pending request: Sick Leave, Feb 9 - Feb 13, 2026 (5 days), "Leave due to annual checkup" - Status: Pending

**Feedback:**
- A. No Problem in submission
- B. HR shall provide guidelines/lead time for leave application (especially vacation leave)
- C. Leave can be seen using supervisor account
- D. **Upon Approval - leave has not been reflected as approved**
- E. **Approved Leave has not been reflected in the crew account**

---

#### 16. Attendance (/dashboard/hr/attendance)
**Status:** NO DATA - "A. No Data Yet"

---

#### 17. Schedule (/dashboard/hr/schedule)
**Status:** NEEDS CONFIGURATION

**Recommendation:** Schedule shall only comprise of the following shifts:
- 7am - 4pm
- 8am - 5pm
- 9am - 6pm
- 10am - 7pm
- 12nn - 9pm
- 1pm - 10pm
- 2pm - 11pm

---

#### 18. Payslip (/dashboard/hr/payslip)
**Status:** NO DATA - "A. No Data Yet"

---

#### 19. Coverage Request (/dashboard/hr/coverage)
**Status:** CRITICAL ERROR

**Screenshot Evidence (kix.xjvkq4bvb0i2 - Crew View, kix.y4jr7yfhakwb - Area Supervisor View):**

**Store Crew View:**
- Page: Dashboard > Hr > Coverage
- Modal: "Request Coverage"
- Fields filled:
  - Store: Ayala Fairview Terraces
  - Coverage Date: 06/02/2026
  - Shift: Afternoon (2PM - 10PM)
  - Absent Employee: Lebron James
  - Reason: Sick Leave
  - Notes (Optional): empty
- **ERROR:** Red toast "Failed to create coverage request"

**Area Supervisor View:**
- Page: Dashboard > Hr > Coverage
- Header: "Coverage Requests - Request and manage staff coverage for shifts"
- Summary cards: Open (0), Assigned (0), Completed (0)
- Tabs: Open (0) | Assigned (0) | History
- Message: "No open coverage requests"
- User: test.area@bebang.ph

**Recommended Changes:**
| Current | Recommended |
|---------|-------------|
| Store name | Should be **dropdown list** |
| Employee name | Should be **dropdown list** |
| N/A | Area Supervisor/Store Supervisor account should **connect to coverage requests** for approval |

---

### COMMUNICATION MODULE

#### 20. Kudos (/dashboard/communication/kudos)
**Status:** NO DATA - "A. No Data Yet"

---

#### 21. CEO Complaint (/dashboard/communication/complaint)
**Status:** NO DATA - "A. No Data Yet"

---

#### 22. Help & Support (/dashboard/communication/support)
**Status:** NO DATA - "A. No Data Yet"

---

#### 23. Announcements (/dashboard/communication/announcements)
**Status:** NO DATA - "A. No Data Yet"

---

### OTHER MODULES

#### 24. My Profile (/dashboard/my-profile)
**Status:** WORKING

**Screenshot Evidence (kix.ta32lhs0l87l):**
- Page: My Profile
- User: Pedro Garcia (TEST-CREW-001)
- Role: Crew, Store: TEST-STORE-BGC
- Status: 13 Pending items
- Profile Complete: 33%
- "Profile Incomplete (33%)" warning with "Complete My Profile" button
- Sections:
  - Personal Information: 100% complete
  - Contact Details: 0% complete (+3 missing)
    - Mobile Number: Not-set (09123123123) - Pending
    - Personal Email: Not-set (lebronjamesaltronofdio@gmail.com) - Pending
    - Current Address: Not-set (Anahaw St, Los Angeles, USA) - Pending
    - Permanent Address: Not-set - Pending

**Feedback:** "A. No Problem in submission / Completely Working"

---

#### 25. Clearance (/clearance)
**Status:** NO DATA - "A. No Data Yet"

---

#### 26. Expense Submission (/dashboard/expense)
**Status:** WORKING with recommendation

**Screenshot Evidence (kix.rd66newh3iuq):**
- Page: Dashboard > Expense
- Header: "My Expenses - Submit and track expense requests"
- "+ Submit Expense" button
- Expense entry shown:
  - Vendor: Ace Hardware
  - Description: Hammer for repair at the store
  - Date: Feb 4, 2026
  - Amount: ₱2,000.00
  - Status: Processing (yellow badge)

**Feedback:** "A. Can the purchase be pre-approved by Area Supervisor/immediate supervisor to control as funds replenishment will be done by area supervisor"

---

### SUPERVISOR TOOLS

#### 27. Queue (/dashboard/queue)
**Status:** WORKING

**Screenshot Evidence (kix.sfcf4gjz611 - Before Approval, kix.ru4rbvt2nnrt - After Approval):**

**Before Approval:**
- Page: Dashboard > Queue
- Header: "Supervisor Queue - Review pending onboarding requests and data verification issues"
- Refresh button visible
- Summary cards: Total Pending (1), Onboarding (0), Data Issues (0), Escalations (0)
- Search field: "Search by employee name, ID..."
- Filters: All Types, All stores
- Pending item: Pedro Garcia - Leave Request, 24 minutes ago, Sick Leave: 5 day(s)

**After Approval:**
- Same layout
- Toast notification (green): "Leave Approved - Pedro Garcia's Sick Leave request has been approved."
- Pedro Garcia still showing in list (25 minutes ago)

**Issue:** Cannot proceed with store order testing as store crew experiencing issues with ordering process

---

#### 28. Team Overview (/dashboard/team)
**Status:** WORKING

**Screenshot Evidence (kix.24824cm0hfqg):**
- Page: Dashboard > Team (mobile view)
- Store: TEST-STORE-BGC
- Header: "My Team"
- Summary: Total: 2, Present: 0, Absent: 0, On Leave: 0
- "Today's Attendance" section:
  - Pedro Garcia (Crew) - Not Marked
  - Test Staff (Team Member) - Not Marked

**Feedback:**
- Can view today's attendance and overall attendance summary of stores
- **Suggestion:** On summary, supervisor should be able to view **who is present, absent and on leave**

---

#### 29. 100-Point Store Visits (/dashboard/team/visits)
**Status:** PARTIAL - Cannot submit (no store available)

**Screenshot Evidence (kix.howjmwl874dh - Scoring, kix.xwqym6mevfk - Form):**

**Scoring View (Mobile):**
- Funds (Cash fund, documentation): 10/20
- Stocks (Expiry, FIFO, temperature): 20/20
- Organization (Cleanliness, equipment, waste): 20/20
- Staffing (Equipment, uniform, service): 20/20
- Coaching (Improvements, on-the-spot coaching): 20/20
- Critical Findings: "Na test"
- Action Items: "Na test"
- "Submit Visit" and "Cancel" buttons

**Form View (Mobile):**
- "New Store Visit" header
- "Record a store visit with 100-point audit scoring"
- Store: Select store (dropdown)
- Visit Type: Audit (dropdown)
- Store Supervisor Present?: Toggle (ON)
- Audit Scores: 91/100 - EXCELLENT (green)
- Same scoring sliders visible

**Issue:** Cannot "submit visit" due to no store available

**Feedback:**
- Audit scoring should clearly show how a store achieves score of 20/20
- Each category must have **specific criteria** with point breakdown
  - Example for Funds: Cash fund intact (5 pts), all documents complete (5 pts), deposits up to date (5 pts), shortages logged (5 pts)
- **Store visit and audit should NOT be available to store supervisors** since they handle only one store

---

#### 30. Reports Feed (/dashboard/supervisor/reports-feed)
**Status:** NOT TESTABLE - "Cannot test since no store reports available"

---

#### 31. Labor Planning (/dashboard/supervisor/labor-plan)
**Status:** NOT TESTABLE

**Screenshot Evidence (kix.q6a6m3xwt1ux):**
- Page: Dashboard > Supervisor > Labor-plan
- Header: "Weekly Labor Plan - Plan and manage weekly shift schedules"
- Store: "No stores assigned. Contact your manager."
- Week: Feb 2 - Feb 8, 2026
- Budget (hrs): 320
- "Shift Schedule - Within budget" section with "+ Add Shift" button

**Issue:** Cannot test since no stores assigned

---

#### 32. Completeness Tracker (/dashboard/completeness)
**Status:** WORKING with recommendation

**Screenshot Evidence (kix.tbmfedhikuym):**
- Mobile view showing:
- Banking: 0% (0 of 697 complete)
- Gov IDs: 0% (1 of 697 complete)
- Reminder Status: Automated reminders at Day 3, 7, and 14
  - Pending 3+ days: 0
  - Need Reminder: 0
  - Escalated (14d): 0
- Store Completeness:
  - Unassigned: 0% (0/294)
  - TEST-STORE-BGC: 0% (0/2)
- "Employees with Gaps (50)" section:
  - CABAGNOT, CAYLA NICOLE N. (96015685) - Unassigned - Missing: Personal, Contact, Emergency, Banking, Gov IDs - 21% complete
  - CRUZ, ANGELICA V. (96019196) - Unassigned - Missing: Personal, Contact, Emergency, Banking, Gov IDs - 21% complete

**Feedback:** The supervisor should be able to view completeness data **exclusively for the store they are handling**

---

#### 33. Enrichment Tracker (/dashboard/enrichment)
**Status:** NOT AVAILABLE - "Unavailable in dashboard"

---

### ANALYTICS MODULE

#### 34. Store Dashboard (/dashboard/analytics/store)
**Status:** NOT AVAILABLE - "Unavailable in dashboard"

---

### AREA SUPERVISOR FEATURES

#### 35. Area Dashboard (/dashboard/analytics/area)
**Status:** NO DATA

**Screenshot Evidence (kix.607p15n245ia):**
- Page: Dashboard > Analytics > Area
- Header: "Area Dashboard - No stores assigned"
- Filter: Last 7 days
- Message icon in center
- Text: "No stores assigned to your area - Contact your manager to be assigned as area supervisor"

---

#### 36. Analytics Overview (/dashboard/analytics)
**Status:** WORKING

**Screenshot Evidence (kix.lc5gubthgyr7):**
- Page: Dashboard > Analytics
- Header: "Analytics & Dashboards - Performance metrics and business intelligence"
- Two cards:
  1. Store Dashboard - "Daily and weekly KPIs for your store"
  2. Area Dashboard - "Aggregated metrics across all stores in your area"
- Navigation: Home, Analytics, Stores, Approvals, Search

---

## ROLE-SPECIFIC FEEDBACK

### STORE STAFF / STORE CREW
**Recommendation:** Change role name from "Store Crew" to "Store OIC"

### Suggested Name Label: "Store Crew" → "Store OIC"

---

## TEST ACCOUNTS REFERENCE

| Role | Email | Name | Password |
|------|-------|------|----------|
| Area Supervisor | test.area@bebang.ph | Maria Santos | BeiTest2026! |
| Store Supervisor | test.supervisor@bebang.ph | Juan Dela Cruz | BeiTest2026! |
| Store Crew | test.crew1@bebang.ph | Pedro Garcia | BeiTest2026! |
| HR User | test.hr@bebang.ph | Patricia Santos | BeiTest2026! |

---

## IMAGE REFERENCE INDEX

| Image ID | Context/Module | Description |
|----------|---------------|-------------|
| kix.4fkamgo2n05y | Opening Report | Mobile - Failed to submit error |
| kix.dx061eblriq8 | Closing Report | Desktop - Cash Fund Count form |
| kix.p8amp8luws8i | Closing Report | Mobile - POS Down Mode active |
| kix.3hg653p06ie1 | Maintenance Request | Mobile - Database error |
| kix.mrz2n9imlofi | Maintenance Request | Desktop - Same database error |
| kix.88e3b99q4zjc | POS Report | Mobile - File upload form |
| kix.vpu0818gj3ri | POS Report | Desktop - Permission error |
| kix.essndqo4qr6t | Store Ordering | Desktop - Order submitted success |
| kix.u7iy6l5dc06o | Cycle Count | Desktop - Count form |
| kix.km5mt2ci9b8s | Returns | Desktop - No stores assigned |
| kix.66p3mf6z3vyh | FQI Report | Desktop - LinkValidation error |
| kix.bh5s83vc17 | FQI Report | Mobile - Same error |
| kix.sfcf4gjz611 | Supervisor Queue | Desktop - Before leave approval |
| kix.ru4rbvt2nnrt | Supervisor Queue | Desktop - After approval toast |
| kix.l7iexd1p98to | Leave Management | Desktop - Leave balances |
| kix.xjvkq4bvb0i2 | Coverage Request | Desktop - Failed to create error |
| kix.y4jr7yfhakwb | Coverage Request | Area Supervisor view |
| kix.24824cm0hfqg | Team Overview | Mobile - Attendance summary |
| kix.howjmwl874dh | Store Visits | Mobile - Scoring sliders |
| kix.xwqym6mevfk | Store Visits | Mobile - Form with 91/100 |
| kix.q6a6m3xwt1ux | Labor Planning | Desktop - No stores assigned |
| kix.tbmfedhikuym | Completeness | Mobile - Employee gaps |
| kix.607p15n245ia | Area Dashboard | Mobile - No stores |
| kix.lc5gubthgyr7 | Analytics Overview | Mobile - Dashboard cards |
| kix.rd66newh3iuq | Expenses | Desktop - Processing expense |
| kix.ta32lhs0l87l | My Profile | Desktop - Profile 33% complete |

---

## PRIORITIZED ACTION ITEMS

### P0 - Critical (Fix Immediately)
1. **Maintenance Request** - Fix database column size for 'photo' field
2. **Opening Report** - Fix "Request failed" submission error
3. **Closing Report** - Fix checklist progression blocker
4. **FQI Report** - Fix store link validation
5. **POS Upload** - Grant role permission for BEI POS Upload doctype
6. **Cycle Count** - Enable file submission
7. **Coverage Request** - Fix creation error

### P1 - High Priority
1. **Leave Approval** - Ensure approved status reflects in employee account
2. **Store Visits** - Assign test stores
3. **Labor Planning** - Assign test stores
4. **Store/Area assignment** - Configure test accounts with stores

### P2 - Medium Priority (Enhancements)
1. Rename "Store Crew" to "Store OIC"
2. Add denomination breakdown for cash counts
3. Add date picker to Cycle Count header
4. Change Store Ordering approver to Area Supervisor
5. Add pre-approval workflow for expenses
6. Implement midshift time window lock (3pm-4pm)
7. Add specific criteria for 100-point audit scoring

### P3 - Low Priority (Nice to Have)
1. Sort ordering items by frequency
2. Allow multiple cold storage photo uploads
3. Add confirmatory lists before submissions
4. Restrict schedule options to defined shifts

---

*Extraction completed: 2026-02-05*
*Total screenshots analyzed: 26*
*Total issues identified: 10 critical, 5 high, 10+ enhancements*

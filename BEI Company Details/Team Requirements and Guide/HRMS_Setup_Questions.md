# Frappe HRMS Setup - Complete Questions List
## For Finance & HR Teams - Philippines Labor Law Compliant (2025)

This document contains ALL questions that need to be answered to properly configure Frappe HRMS for your multi-company structure. Please answer each question systematically.

**⚠️ IMPORTANT: This document has been updated with 2025 Philippine Labor Law requirements including:**
- 2025 SSS rates (15% total, MSC ₱5,000-₱35,000, WISP threshold)
- 2025 PhilHealth rates (5%, Floor ₱10,000, Ceiling ₱100,000)
- 2025 Pag-IBIG rates (MFS ₱10,000, ₱200/₱200 standard)
- Updated De Minimis benefits (Clothing ₱7,000/year)
- TRAIN Law 2025 tax brackets
- All mandatory leave types with specific entitlements
- Daily rate divisors (313/261/365)
- Comprehensive overtime and premium pay matrix

---

## 🔴 **CRITICAL DECISIONS - ANSWER FIRST**

### 1. Store Entity Structure Decision
**Question 1.1**: How should individual store entities be configured in the system?
- [ ] Option A: Each store as a separate Company (if different legal entities/payroll)
- [ ] Option B: Stores as Branches under main companies (if same payroll/HR policies)
- [ ] Option C: Hybrid approach (some as companies, some as branches)
- [ ] **Your Decision**: _______________________________

**Question 1.2**: If stores are separate companies, how many store companies need to be set up?
- [ ] Total number of store entities: _______________

**Question 1.3**: Should stores be grouped by type?
- [ ] Company-owned stores: Separate companies or branches?
- [ ] Joint Venture stores: Separate companies or branches?
- [ ] Franchise stores: Separate companies or branches?
- [ ] Managed Franchise stores: Separate companies or branches?

**Question 1.4**: Do stores have different payroll policies than BEI or Bebang Kitchen Inc.?
- [ ] Yes, stores have different payroll policies
- [ ] No, stores share payroll policies with main companies
- [ ] Some stores differ, some are the same

---

## 📋 **SECTION 1: COMPANY INFORMATION**

### Irrisistable Infusions Inc. (Triple I) - Holding Company

**Question 1.1**: What is the complete legal name?
- [ ] Answer: _______________________________

**Question 1.2**: What abbreviation should be used? (Triple I, III, or other?)
- [ ] Answer: _______________________________

**Question 1.3**: What is the SEC Registration Number?
- [ ] Answer: _______________________________

**Question 1.4**: What is the TIN (Tax Identification Number)?
- [ ] Answer: _______________________________

**Question 1.5**: What is the complete registered address?
- [ ] Answer: _______________________________

**Question 1.6**: What is the phone number?
- [ ] Answer: _______________________________

**Question 1.7**: What is the main email address?
- [ ] Answer: _______________________________

**Question 1.8**: What is the website URL?
- [ ] Answer: _______________________________

**Question 1.9**: What is the fiscal year start date? (e.g., January 1)
- [ ] Answer: _______________________________

**Question 1.10**: What is the fiscal year end date? (e.g., December 31)
- [ ] Answer: _______________________________

**Question 1.11**: Do you have a company logo file? (Provide file path or confirm if needed)
- [ ] Answer: _______________________________

---

### Bebang Enterprise Inc. (BEI) - Head Office

**Question 2.1**: What is the complete legal name?
- [ ] Answer: _______________________________

**Question 2.2**: What abbreviation should be used? (BEI or other?)
- [ ] Answer: _______________________________

**Question 2.3**: What is the SEC Registration Number?
- [ ] Answer: _______________________________

**Question 2.4**: What is the TIN (Tax Identification Number)?
- [ ] Answer: _______________________________

**Question 2.5**: What is the complete registered address?
- [ ] Answer: _______________________________

**Question 2.6**: What is the Capital House BGC address? (Main office)
- [ ] Answer: _______________________________

**Question 2.7**: What is the Brittany Hotel BGC address? (Secondary office - from mid-June 2025)
- [ ] Answer: _______________________________

**Question 2.8**: What is the phone number?
- [ ] Answer: _______________________________

**Question 2.9**: What is the main email address?
- [ ] Answer: _______________________________

**Question 2.10**: What is the website URL?
- [ ] Answer: _______________________________

**Question 2.11**: What is the fiscal year start date?
- [ ] Answer: _______________________________

**Question 2.12**: What is the fiscal year end date?
- [ ] Answer: _______________________________

**Question 2.13**: What Chart of Accounts template should be used? (Standard or custom)

**📊 What This Means (For CFO/Finance Team):**
- **Chart of Accounts** = Your company's list of all accounting accounts (like a master list of categories for your financial transactions)
- Examples: "Payroll Payable", "Employee Advances", "SSS Payable", "PhilHealth Payable", "Salary Expense", etc.
- **Why We Need This**: When Frappe HR processes payroll, it needs to know which accounting accounts to use for:
  - Recording salary expenses
  - Recording payroll liabilities (money owed to employees)
  - Recording statutory deductions (SSS, PhilHealth, Pag-IBIG payables)
  - Creating accounting journal entries automatically

**Options:**
- **Standard Template**: ERPNext provides a pre-built Chart of Accounts with common accounts already set up (faster setup, may need minor adjustments)
- **Custom Template**: You provide your existing Chart of Accounts structure (matches your current accounting system exactly, but requires manual setup)

**💡 Recommendation**: If you already have an accounting system (QuickBooks, Xero, SAP, etc.), use **Custom** and provide your Chart of Accounts. If starting fresh, **Standard** is easier.

- [ ] Answer: **Standard** / **Custom** (circle one)
- [ ] If Custom, do you have your Chart of Accounts in Excel/CSV format? Yes/No

**Question 2.14**: What is the exact employee count for BEI head office?
- [ ] Answer: _______________________________

---

### Bebang Kitchen Inc. - Commissary

**Question 3.1**: What is the complete legal name?
- [ ] Answer: _______________________________

**Question 3.2**: What abbreviation should be used? (BKI, Bebang Kitchen, or other?)
- [ ] Answer: _______________________________

**Question 3.3**: What is the SEC Registration Number?
- [ ] Answer: _______________________________

**Question 3.4**: What is the TIN (Tax Identification Number)?
- [ ] Answer: _______________________________

**Question 3.5**: What is the complete registered address?
- [ ] Answer: _______________________________

**Question 3.6**: What is the exact commissary address at Shaw Blvd, Mandaluyong?
- [ ] Answer: _______________________________

**Question 3.7**: What is the phone number?
- [ ] Answer: _______________________________

**Question 3.8**: What is the main email address?
- [ ] Answer: _______________________________

**Question 3.9**: What is the fiscal year start date?
- [ ] Answer: _______________________________

**Question 3.10**: What is the fiscal year end date?
- [ ] Answer: _______________________________

**Question 3.11**: What Chart of Accounts template should be used?

**📊 What This Means (For CFO/Finance Team):**
- **Chart of Accounts** = Your company's list of all accounting accounts (like a master list of categories for your financial transactions)
- Examples: "Payroll Payable", "Employee Advances", "SSS Payable", "PhilHealth Payable", "Salary Expense", etc.
- **Why We Need This**: When Frappe HR processes payroll, it needs to know which accounting accounts to use for:
  - Recording salary expenses
  - Recording payroll liabilities (money owed to employees)
  - Recording statutory deductions (SSS, PhilHealth, Pag-IBIG payables)
  - Creating accounting journal entries automatically

**Options:**
- **Standard Template**: ERPNext provides a pre-built Chart of Accounts with common accounts already set up (faster setup, may need minor adjustments)
- **Custom Template**: You provide your existing Chart of Accounts structure (matches your current accounting system exactly, but requires manual setup)

**💡 Recommendation**: If you already have an accounting system (QuickBooks, Xero, SAP, etc.), use **Custom** and provide your Chart of Accounts. If starting fresh, **Standard** is easier.

- [ ] Answer: **Standard** / **Custom** (circle one)
- [ ] If Custom, do you have your Chart of Accounts in Excel/CSV format? Yes/No

**Question 3.12**: What is the exact employee count for Bebang Kitchen Inc.?
- [ ] Answer: _______________________________

---

### Store Entities

**Question 4.1**: How many store entities need to be set up as separate companies? (If applicable)
- [ ] Answer: _______________________________

**Question 4.2**: For each store entity that will be a separate company, provide:
- [ ] Store Entity Name: _______________________________
- [ ] Legal Company Name: _______________________________
- [ ] SEC Registration Number: _______________________________
- [ ] TIN: _______________________________
- [ ] Store Address: _______________________________
- [ ] Phone Number: _______________________________
- [ ] Email Address: _______________________________
- [ ] Employee Count: _______________________________

**Question 4.3**: If stores are branches, how many store branches need to be created?
- [ ] Answer: _______________________________

**Question 4.4**: For each store branch, provide:
- [ ] Store Name: _______________________________
- [ ] Store Address: _______________________________
- [ ] Store Type: (Company-owned / JV / Franchise / Managed Franchise)
- [ ] Which Company it belongs to: (BEI / Bebang Kitchen / Other)
- [ ] Employee Count: _______________________________

---

## 🏢 **SECTION 2: ORGANIZATIONAL STRUCTURE**

### Branches/Offices

**Question 5.1**: For BEI - Capital House BGC:
- [ ] Complete address: _______________________________
- [ ] Phone number: _______________________________
- [ ] Contact person: _______________________________
- [ ] Which teams are located here? (Marketing, Tech, etc.)
- [ ] Answer: _______________________________

**Question 5.2**: For BEI - Brittany Hotel BGC (from mid-June 2025):
- [ ] Complete address: _______________________________
- [ ] Phone number: _______________________________
- [ ] Contact person: _______________________________
- [ ] Which teams will move here? (Specify)
- [ ] Answer: _______________________________

**Question 5.3**: For Bebang Kitchen Inc. - Shaw Blvd Commissary:
- [ ] Complete address: _______________________________
- [ ] Phone number: _______________________________
- [ ] Contact person: _______________________________

**Question 5.4**: Do you have a complete list of all 51+ store locations with addresses?
- [ ] Yes, list provided
- [ ] No, need to compile
- [ ] Partial list available

---

### Departments

**Question 6.1**: Should departments be shared across all companies or company-specific?
- [ ] Shared across all companies
- [ ] Company-specific
- [ ] Mix of both

**Question 6.2**: List all departments for BEI Head Office:
- [ ] Department 1: _______________________________
- [ ] Department 2: _______________________________
- [ ] Department 3: _______________________________
- [ ] (Continue list...)

**Question 6.3**: List all departments for Bebang Kitchen Inc. (Commissary):
- [ ] Department 1: _______________________________
- [ ] Department 2: _______________________________
- [ ] (Continue list...)

**Question 6.4**: Are there any departments that exist in multiple companies?
- [ ] Yes, list: _______________________________
- [ ] No

**Question 6.5**: For each department, who is the department head/manager?
- [ ] Department: _______________________ Manager: _______________________

**Question 6.6**: Are departments hierarchical? (e.g., Sales > Regional Sales > Store Sales)
- [ ] Yes, provide hierarchy structure
- [ ] No, all are at the same level

---

### Designations/Job Titles

**Question 7.1**: Should designations be shared across all companies or company-specific?
- [ ] Shared across all companies
- [ ] Company-specific
- [ ] Mix of both

**Question 7.2**: List all designations for BEI Head Office:
- [ ] CEO/President
- [ ] Chief Product Officer (CPO)
- [ ] Chief Financial Officer (CFO)
- [ ] Chief of Staff
- [ ] Executive Assistant
- [ ] VP of Operations
- [ ] Director of Business Development
- [ ] Director of Projects
- [ ] HR Manager
- [ ] Marketing Manager
- [ ] (List all others...)

**Question 7.3**: List all designations for Bebang Kitchen Inc. (Commissary):
- [ ] Designation 1: _______________________________
- [ ] Designation 2: _______________________________
- [ ] (Continue list...)

**Question 7.4**: List all designations for Store employees:
- [ ] Store Manager
- [ ] Assistant Store Manager
- [ ] CSR (Customer Service Representative)
- [ ] CSR (Admin/Refund)
- [ ] CSR (Logistics)
- [ ] CSR (Escalation)
- [ ] CSR (Online Delivery)
- [ ] CSR (Trainee)
- [ ] (List all others...)

**Question 7.5**: For each designation, which department(s) does it belong to?
- [ ] Designation: _______________________ Department(s): _______________________

---

### Employee Grades

**Question 8.1**: Do you use employee grades/levels? (e.g., Grade 1, Grade 2, etc.)
- [ ] Yes
- [ ] No

**Question 8.2**: If yes, list all employee grades:
- [ ] Grade 1: _______________________________
- [ ] Grade 2: _______________________________
- [ ] (Continue list...)

**Question 8.3**: How are grades assigned? (By designation, by salary range, by experience?)
- [ ] Answer: _______________________________

---

## 👥 **SECTION 3: EMPLOYMENT TYPES & POLICIES**

### Employment Types

**Question 9.1**: List all employment types used across all companies:
- [ ] Full-time
- [ ] Part-time
- [ ] Contract
- [ ] Probation
- [ ] Intern
- [ ] Apprentice
- [ ] Others: _______________________________

**Question 9.2**: Are employment types the same across all companies?
- [ ] Yes, all companies use the same types
- [ ] No, some companies have different types

**Question 9.3**: If different, specify which employment types are used in which company:
- [ ] BEI: _______________________________
- [ ] Bebang Kitchen Inc.: _______________________________
- [ ] Stores: _______________________________

---

### HR Policies - Philippines Labor Code Compliant

**Question 10.1**: What is the probation period? (in months/days)
- [ ] Answer: _______________________________

**Question 10.2**: Is probation period the same for all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

**Question 10.3**: What is the notice period for resignation? (in days)
- [ ] Answer: _______________________________

**Question 10.4**: What is the standard working hours per day?
- [ ] Answer: _______________________________ hours

**Question 10.5**: What is the standard working days per week?
- [ ] Answer: _______________________________ days

**Question 10.6**: What is the standard work schedule? (e.g., Monday-Friday, Monday-Saturday)
- [ ] Answer: _______________________________

**Question 10.6a**: What Daily Rate Divisor should be used? (CRITICAL for payroll accuracy)
- [ ] **Factor 313**: For 6 days/week (Monday-Saturday) - Manufacturing/Retail/Operations
  - Formula: (Monthly Basic Salary × 12) ÷ 313
- [ ] **Factor 261**: For 5 days/week (Monday-Friday) - Head Office/Admin/Corporate
  - Formula: (Monthly Basic Salary × 12) ÷ 261
- [ ] **Factor 365**: For daily-paid employees (paid every day including rest days) - Rare
  - Formula: (Monthly Basic Salary × 12) ÷ 365
- [ ] **Different divisor per company/designation?** Specify: _______________________________
- [ ] **Legal Risk Warning**: Using wrong divisor (e.g., 365 for 5-day workers) violates non-diminution of benefits

**Question 10.7**: What is your overtime policy?
- [ ] Overtime rate: _______________________________
- [ ] Approval required? Yes/No
- [ ] Who approves overtime? _______________________________

**Question 10.8**: Do you pay night shift differential? (10% premium for 10 PM - 6 AM per Labor Code)
- [ ] Yes, 10% premium
- [ ] Yes, different rate: _______________________________
- [ ] No

**Question 10.9**: What employee benefits do you provide?
- [ ] Health Insurance (specify provider): _______________________________
- [ ] Retirement Plan: _______________________________
- [ ] Life Insurance: _______________________________
- [ ] Others: _______________________________

**Question 10.10**: Are benefits the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

---

## 🏖️ **SECTION 4: LEAVE MANAGEMENT - PHILIPPINES**

### Leave Types

**Question 11.1**: What leave types do you offer? (List all - including mandatory statutory leaves)

**Mandatory Statutory Leaves (2025):**
- [ ] **Service Incentive Leave (SIL)** - Article 95, Labor Code
  - 5 days after 1 year (mandatory)
  - Convertible to cash (mandatory)
- [ ] **Expanded Solo Parent Leave** - RA 11861 (2025 Update)
  - 7 working days (after 6 months service)
  - Requires Solo Parent ID (LGU/DSWD)
  - Forfeitable (not convertible to cash)
- [ ] **VAWC Leave** - RA 9262
  - 10 days (for female victims of violence)
  - Requires certification (Barangay/Police/Prosecutor)
  - Forfeitable (not convertible to cash)
- [ ] **Magna Carta of Women Leave** - RA 9710
  - Up to 60 days (for gynecological surgery)
  - After 6 months aggregate service
  - Forfeitable (not convertible to cash)
- [ ] **Paternity Leave** - RA 8187
  - 7 days (first 4 deliveries)
  - Can be extended to 14 days if mother transfers 7 days (RA 11210)
- [ ] **Maternity Leave** - RA 11210
  - 105 days (Live Birth), 60 days (Miscarriage)
  - 120 days for solo parents
  - SSS-funded, employer advances payment

**Company Leave Types:**
- [ ] Vacation Leave
- [ ] Sick Leave
- [ ] Emergency Leave
- [ ] Others: _______________________________

**Question 11.2**: For Vacation Leave:
- [ ] How many days per year? _______________________________
- [ ] Can it be carried forward? Yes/No
- [ ] Maximum carry forward days: _______________________________
- [ ] Can it be encashed? Yes/No
- [ ] Maximum consecutive days allowed: _______________________________

**Question 11.3**: For Sick Leave:
- [ ] How many days per year? _______________________________
- [ ] Can it be carried forward? Yes/No
- [ ] Requires medical certificate? Yes/No
- [ ] After how many days? _______________________________

**Question 11.4**: For Service Incentive Leave (SIL):
- [ ] Do you provide the mandatory 5 days after 1 year? Yes/No
- [ ] Can it be encashed? Yes/No
- [ ] Can it be carried forward? Yes/No

**Question 11.5**: Are leave types the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

**Question 11.6**: Do you have different leave allocations for different designations/levels?
- [ ] Yes, specify: _______________________________
- [ ] No, same for everyone

---

### Holiday Lists - Philippines

**Question 12.1**: Do you have a complete list of Philippines public holidays for 2025?
- [ ] Yes, provide list
- [ ] No, need to compile

**Question 12.2**: List all Regular Holidays (200% pay per Labor Code):
- [ ] New Year's Day (January 1)
- [ ] EDSA People Power Revolution Anniversary (February 25)
- [ ] Maundy Thursday (date varies)
- [ ] Good Friday (date varies)
- [ ] Araw ng Kagitingan (April 9)
- [ ] Labor Day (May 1)
- [ ] Independence Day (June 12)
- [ ] National Heroes Day (last Monday of August)
- [ ] Bonifacio Day (November 30)
- [ ] Rizal Day (December 30)
- [ ] Christmas Day (December 25)
- [ ] Others: _______________________________

**Question 12.3**: List all Special Non-Working Days (130% pay per Labor Code):
- [ ] Chinese New Year
- [ ] Black Saturday
- [ ] Ninoy Aquino Day (August 21)
- [ ] All Saints' Day (November 1)
- [ ] All Souls' Day (November 2)
- [ ] New Year's Eve (December 31)
- [ ] Others (as declared by President): _______________________________

**Question 12.4**: Do you have company-specific holidays? (List with dates)
- [ ] Holiday 1: _______________________ Date: _______________________
- [ ] Holiday 2: _______________________ Date: _______________________

**Question 12.5**: Are holidays the same for all companies/branches?
- [ ] Yes
- [ ] No, specify differences: _______________________________

**Question 12.6**: Do you observe optional holidays? (Employees can choose to work or take leave)
- [ ] Yes, list: _______________________________
- [ ] No

---

### Leave Policies

**Question 13.1**: Do you have different leave policies for different groups? (e.g., by department, designation, grade)
- [ ] Yes, specify: _______________________________
- [ ] No, same policy for all

**Question 13.2**: What is your leave period? (Calendar year, fiscal year, or anniversary date?)
- [ ] Calendar year (January 1 - December 31)
- [ ] Fiscal year (specify dates): _______________________________
- [ ] Anniversary date (based on joining date)
- [ ] Other: _______________________________

**Question 13.3**: When are leave allocations granted?
- [ ] At the start of the leave period (lump sum)
- [ ] Pro-rated based on joining date
- [ ] Accrued monthly
- [ ] Other: _______________________________

---

## ⏰ **SECTION 5: ATTENDANCE & SHIFTS - PHILIPPINES LABOR CODE**

### Shift Types

**Question 14.1**: How many shift types do you have?
- [ ] Answer: _______________________________

**Question 14.2**: For each shift, provide:
- [ ] Shift Name: _______________________________
- [ ] Start Time: _______________________________
- [ ] End Time: _______________________________
- [ ] Break Duration: _______________________________ minutes
- [ ] Working Hours per day: _______________________________
- [ ] Days of Week: (Monday-Sunday, specify)
- [ ] Which company/branch uses this shift: _______________________________

**Question 14.3**: Do you have night shifts? (10 PM - 6 AM)
- [ ] Yes, list shifts: _______________________________
- [ ] No

**Question 14.4**: Confirm night shift differential is configured correctly:
- [ ] Rate: 10% premium (per Labor Code Article 86)
- [ ] Time Period: Work between 10:00 PM - 6:00 AM
- [ ] Calculation Method: 10% of hourly rate (stacks on top of overtime/holiday rates)
- [ ] Example: OT on Holiday at 11 PM = (Hourly Rate × 2.60) × 1.10 = 286%
- [ ] If different rate, specify: _______________________________

**Question 14.5**: Are shifts the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

---

### Attendance Settings

**Question 15.1**: How do employees check in/check out?
- [ ] Manual (time sheet)
- [ ] Biometric (fingerprint/face)
- [ ] GPS/Mobile app
- [ ] Card swipe
- [ ] Other: _______________________________

**Question 15.2**: What is the late entry grace period? (in minutes)
- [ ] Answer: _______________________________ minutes

**Question 15.3**: What is the early exit grace period? (in minutes)
- [ ] Answer: _______________________________ minutes

**Question 15.4**: Confirm overtime rates are configured correctly (Philippines Labor Code):
- [ ] Regular Day Overtime: 125% of hourly rate
- [ ] Rest Day: 130% of hourly rate
- [ ] Rest Day Overtime: 169% of hourly rate
- [ ] Special Non-Working Day: 130% of hourly rate
- [ ] Special Day Overtime: 169% of hourly rate
- [ ] Special Day + Rest Day: 150% of hourly rate
- [ ] Special + Rest Day Overtime: 195% of hourly rate
- [ ] Regular Holiday: 200% of hourly rate
- [ ] Regular Holiday Overtime: 260% of hourly rate
- [ ] Double Holiday: 300% of hourly rate
- [ ] Night Shift Differential: 10% stacks on top of all rates

**Question 15.4a**: How is overtime calculated?
- [ ] Automatic based on shift end time
- [ ] Manual entry required
- [ ] Approval-based

**Question 15.5**: Who approves overtime?
- [ ] Immediate supervisor
- [ ] Department manager
- [ ] HR
- [ ] Other: _______________________________

**Question 15.6**: Are half-day leaves allowed?
- [ ] Yes
- [ ] No

**Question 15.7**: If half-day is allowed, what are the rules?
- [ ] Morning half-day: _______________________ to _______________________
- [ ] Afternoon half-day: _______________________ to _______________________

**Question 15.8**: Do you track attendance for remote workers?
- [ ] Yes, how? _______________________________
- [ ] No

---

## 💰 **SECTION 6: PAYROLL SETUP - PHILIPPINES STATUTORY REQUIREMENTS**

### Company-Specific Payroll Configuration

**Question 16.1**: What is the payroll frequency for BEI Head Office?
- [ ] Monthly
- [ ] Semi-monthly (15th and last day)
- [ ] Bi-weekly
- [ ] Weekly
- [ ] Other: _______________________________

**Question 16.2**: What is the payroll frequency for Bebang Kitchen Inc.?
- [ ] Monthly
- [ ] Semi-monthly
- [ ] Bi-weekly
- [ ] Weekly
- [ ] Other: _______________________________

**Question 16.3**: What is the payroll frequency for stores?
- [ ] Monthly
- [ ] Semi-monthly
- [ ] Bi-weekly
- [ ] Weekly
- [ ] Other: _______________________________
- [ ] Varies by store

**Question 16.4**: What is the payroll processing date? (e.g., 25th of each month)
- [ ] BEI: _______________________________
- [ ] Bebang Kitchen: _______________________________
- [ ] Stores: _______________________________

**Question 16.5**: What is the payroll payment date? (e.g., 1st of each month)
- [ ] BEI: _______________________________
- [ ] Bebang Kitchen: _______________________________
- [ ] Stores: _______________________________

---

### Salary Components - Earnings

**Question 17.1**: List all earning components for BEI Head Office:
- [ ] Basic Salary
- [ ] Allowances (specify types): _______________________________
- [ ] Transportation Allowance
- [ ] Meal Allowance
- [ ] Communication Allowance
- [ ] Others: _______________________________

**Question 17.2**: List all earning components for Bebang Kitchen Inc.:
- [ ] Basic Salary
- [ ] Allowances: _______________________________
- [ ] Others: _______________________________

**Question 17.3**: List all earning components for stores:
- [ ] Basic Salary
- [ ] Commission (if applicable)
- [ ] Allowances: _______________________________
- [ ] Others: _______________________________

**Question 17.4**: For each allowance, specify:
- [ ] Allowance Name: _______________________________
- [ ] Type: Fixed Amount / Percentage / Formula-based
- [ ] Amount/Percentage/Formula: _______________________________
- [ ] Is Taxable? Yes/No
- [ ] Which company? (BEI / Bebang Kitchen / Stores / All)

**Question 17.5**: Do you provide 13th Month Pay? (Mandatory per Labor Code - PD 851)
- [ ] Yes (Mandatory)
- [ ] No

**Question 17.6**: Confirm 13th Month Pay calculation is configured correctly:
- [ ] Formula: Total Basic Salary Earned During Calendar Year ÷ 12
- [ ] Exclusions from Basic Salary:
  - [ ] Overtime Pay (excluded)
  - [ ] Night Shift Differential (excluded)
  - [ ] Holiday Pay (excluded)
  - [ ] Cost of Living Allowance/COLA (excluded)
  - [ ] Profit-sharing payments (excluded)
  - [ ] Cash equivalent of unused leaves (excluded)
- [ ] Commission Inclusion: Generally excluded unless part of basic wage structure (per employment contract)
- [ ] Prorated Calculation: For resigned employees, sum of Basic Salary (Jan 1 to Separation Date) ÷ 12

**Question 17.7**: When is 13th Month Pay paid?
- [ ] December (full amount)
- [ ] Split (May and December)
- [ ] Other: _______________________________

**Question 17.8**: Do you provide De Minimis Benefits? (Tax-exempt allowances)
- [ ] Yes, specify which ones:
  - [ ] Uniform/Clothing Allowance: ₱7,000/year (Updated 2025)
  - [ ] Rice Subsidy: ₱2,000/month or 50kg sack
  - [ ] Medical Cash Allowance: ₱1,500/semester (₱250/month)
  - [ ] Actual Medical Assistance: ₱10,000/year
  - [ ] Laundry Allowance: ₱300/month
  - [ ] Employee Achievement Awards: ₱10,000/year (tangible property only)
  - [ ] Christmas/Anniversary Gifts: ₱5,000/year
  - [ ] Daily Meal Allowance: 25% of minimum wage (OT/night shift only)
- [ ] No

---

### Salary Components - Deductions

**Question 18.1**: Do you deduct SSS (Social Security System)?
- [ ] Yes (Mandatory)
- [ ] No

**Question 18.2**: Confirm 2025 SSS contribution rates are configured correctly:
- [ ] Total Rate: 15% (Effective January 2025)
- [ ] Employee Share: 5.0%
- [ ] Employer Share: 10.0%
- [ ] MSC Range: ₱5,000 (minimum) to ₱35,000 (maximum)
- [ ] WISP/Pension Booster Threshold: MSC > ₱20,000 (split calculation)
- [ ] EC Contribution: ₱10 (MSC ≤ ₱14,500) or ₱30 (MSC ≥ ₱15,000) - employer only
- [ ] MSC Lookup Table: Configured based on monthly compensation ranges

**Question 18.3**: Do you deduct PhilHealth?
- [ ] Yes (Mandatory)
- [ ] No

**Question 18.4**: Confirm 2025 PhilHealth contribution rates are configured correctly:
- [ ] Premium Rate: 5.0% of Monthly Basic Salary (MBS)
- [ ] Employee Share: 2.5%
- [ ] Employer Share: 2.5%
- [ ] Income Floor: ₱10,000.00 (minimum premium: ₱500.00 total)
- [ ] Income Ceiling: ₱100,000.00 (maximum premium: ₱5,000.00 total)
- [ ] Calculation Base: Monthly Basic Salary ONLY (excludes commissions, OT, NSD, non-integrated allowances)

**Question 18.5**: Do you deduct Pag-IBIG (HDMF)?
- [ ] Yes (Mandatory)
- [ ] No

**Question 18.6**: Confirm 2025 Pag-IBIG contribution rates are configured correctly:
- [ ] Employee Rate: 2% (for compensation > ₱1,500)
- [ ] Employer Rate: 2% (universal)
- [ ] Maximum Fund Salary (MFS): ₱10,000.00 (doubled from ₱5,000 in 2024)
- [ ] Standard Deduction (Salary ≥ ₱10,000): ₱200.00 employee, ₱200.00 employer (₱400.00 total)
- [ ] Voluntary Contributions: Employees may opt for higher (MP2), but mandatory is capped at ₱200

**Question 18.7**: Do you deduct income tax (BIR withholding tax)?
- [ ] Yes
- [ ] No

**Question 18.8**: What other deductions do you have?
- [ ] Loan deductions
- [ ] Advance deductions
- [ ] Insurance premiums
- [ ] Others: _______________________________

**Question 18.9**: For each deduction, specify:
- [ ] Deduction Name: _______________________________
- [ ] Type: Fixed / Percentage / Formula
- [ ] Amount/Percentage/Formula: _______________________________
- [ ] Is Tax Exempt? Yes/No
- [ ] Which company? (BEI / Bebang Kitchen / Stores / All)

---

### Salary Structures

**Question 19.1**: How many different salary structures do you need?
- [ ] Answer: _______________________________

**Question 19.2**: For each salary structure, provide:
- [ ] Structure Name: _______________________________
- [ ] Company: (BEI / Bebang Kitchen / Store Entity)
- [ ] Applicable to: (Designation/Department/Grade)
- [ ] Payroll Frequency: _______________________________
- [ ] Base Salary Range: _______________________________
- [ ] Earnings Components included: _______________________________
- [ ] Deductions Components included: _______________________________

**Question 19.3**: Do you have different salary structures for:
- [ ] Different designations? Yes/No
- [ ] Different departments? Yes/No
- [ ] Different employee grades? Yes/No
- [ ] Different companies? Yes/No

**Question 19.4**: Are salary structures the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

---

### Income Tax Configuration - BIR

**Question 20.1**: Confirm 2025 BIR tax table is configured correctly:
- [ ] Annual Income Tax Brackets (TRAIN Law 2025):
  - [ ] Not over ₱250,000: 0% (Exempt)
  - [ ] Over ₱250,000 but not over ₱400,000: 15% of excess over ₱250,000
  - [ ] Over ₱400,000 but not over ₱800,000: ₱22,500 + 20% of excess over ₱400,000
  - [ ] Over ₱800,000 but not over ₱2,000,000: ₱102,500 + 25% of excess over ₱800,000
  - [ ] Over ₱2,000,000 but not over ₱8,000,000: ₱402,500 + 30% of excess over ₱2,000,000
  - [ ] Over ₱8,000,000: ₱2,202,500 + 35% of excess over ₱8,000,000
- [ ] Semi-Monthly Withholding Tax Table configured
- [ ] Tax Exemption Threshold: ₱250,000 annual (≈₱20,833 monthly after deductions)
- [ ] Bonus Exemption Cap: ₱90,000 (13th Month Pay + Other Benefits)

**Question 20.2**: What is your tax calculation method?
- [ ] Annualized (recommended)
- [ ] Monthly
- [ ] Other: _______________________________

**Question 20.3**: Do employees submit BIR Form 2307 (Certificate of Creditable Tax Withheld)?
- [ ] Yes
- [ ] No

**Question 20.4**: What tax exemptions do you apply?
- [ ] Personal exemption
- [ ] Additional exemption (dependents)
- [ ] Others: _______________________________

**Question 20.5**: Are tax rules the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

---

### Payroll Accounts (Chart of Accounts)

**Question 21.1**: For BEI, what is the Payroll Payable Account name?
- [ ] Answer: _______________________________

**Question 21.2**: For Bebang Kitchen Inc., what is the Payroll Payable Account name?
- [ ] Answer: _______________________________

**Question 21.3**: For each store entity, what is the Payroll Payable Account name?
- [ ] Store: _______________________ Account: _______________________

**Question 21.4**: Do you use cost centers for payroll allocation?
- [ ] Yes, list cost centers: _______________________________
- [ ] No

**Question 21.5**: What bank account is used for payroll payments?
- [ ] BEI: Bank Name: _______________________ Account Number: _______________________
- [ ] Bebang Kitchen: Bank Name: _______________________ Account Number: _______________________
- [ ] Stores: (specify per store or if shared)

---

## 👤 **SECTION 7: EMPLOYEE DATA**

### Employee Master Data

**Question 22.1**: Do you have a complete employee list in Excel/CSV format?
- [ ] Yes
- [ ] No, need to compile

**Question 22.2**: For each employee, we need the following information. Do you have this data?
- [ ] Company Assignment (BEI / Bebang Kitchen / Store Entity) - **CRITICAL**
- [ ] Employee ID (if existing)
- [ ] Full Name
- [ ] Date of Birth
- [ ] Gender
- [ ] Email Address
- [ ] Phone Number
- [ ] Current Address
- [ ] Permanent Address
- [ ] Emergency Contact (Name, Relationship, Phone)
- [ ] Date of Joining
- [ ] Employment Type
- [ ] Department
- [ ] Designation
- [ ] Branch/Store Location
- [ ] Grade (if applicable)
- [ ] Reporting Manager (Name and Company)
- [ ] TIN (Tax Identification Number)
- [ ] SSS Number
- [ ] PhilHealth Number
- [ ] Pag-IBIG Number
- [ ] Bank Account Details (Account Number, Bank Name)
- [ ] Salary Structure Assignment
- [ ] Default Shift
- [ ] Leave Approver
- [ ] Expense Approver

**Question 22.3**: How many employees are in BEI Head Office? (Exact count)
- [ ] Answer: _______________________________

**Question 22.4**: How many employees are in Bebang Kitchen Inc.? (Exact count)
- [ ] Answer: _______________________________

**Question 22.5**: How many employees are in each store? (Provide list or total)
- [ ] Total store employees: _______________________________
- [ ] Per store breakdown: (if available)

**Question 22.6**: Do you have employee photos?
- [ ] Yes, where are they stored? _______________________________
- [ ] No

---

### Inter-Company Considerations

**Question 23.1**: Do employees transfer between companies? (e.g., Head Office to Commissary)
- [ ] Yes, how often? _______________________________
- [ ] No

**Question 23.2**: Are there any employees who work for multiple companies?
- [ ] Yes, list: _______________________________
- [ ] No

**Question 23.3**: How are costs allocated when employees work for multiple companies?
- [ ] Answer: _______________________________

**Question 23.4**: Do reporting relationships cross companies? (e.g., Store employee reports to BEI manager)
- [ ] Yes, specify: _______________________________
- [ ] No

---

## 📊 **SECTION 8: APPROVAL WORKFLOWS**

### Leave Approval

**Question 24.1**: Who approves leave applications?
- [ ] Immediate supervisor/manager
- [ ] Department head
- [ ] HR Manager
- [ ] Multi-level (specify): _______________________________

**Question 24.2**: Is leave approval the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

**Question 24.3**: What is the maximum leave days that can be approved by:
- [ ] Immediate supervisor: _______________________ days
- [ ] Department head: _______________________ days
- [ ] HR Manager: _______________________ days
- [ ] CEO: _______________________ days

**Question 24.4**: Do you have different approval workflows for different leave types?
- [ ] Yes, specify: _______________________________
- [ ] No

---

### Expense Approval

**Question 25.1**: Who approves expense claims?
- [ ] Immediate supervisor
- [ ] Department head
- [ ] Finance Manager
- [ ] Multi-level (specify): _______________________________

**Question 25.2**: What is the approval limit for:
- [ ] Immediate supervisor: PHP _______________________
- [ ] Department head: PHP _______________________
- [ ] Finance Manager: PHP _______________________
- [ ] CEO: PHP _______________________

**Question 25.3**: Is expense approval the same across all companies?
- [ ] Yes
- [ ] No, specify differences: _______________________________

---

### Attendance/Overtime Approval

**Question 26.1**: Who approves overtime?
- [ ] Immediate supervisor
- [ ] Department head
- [ ] HR
- [ ] Other: _______________________________

**Question 26.2**: Who approves attendance corrections/adjustments?
- [ ] Immediate supervisor
- [ ] HR
- [ ] Other: _______________________________

---

## 👥 **SECTION 9: SYSTEM USERS & ROLES**

**Question 27.1**: Who will be the HR Manager(s)? (Name and email)
- [ ] BEI: Name: _______________________ Email: _______________________
- [ ] Bebang Kitchen: Name: _______________________ Email: _______________________
- [ ] Stores: Name: _______________________ Email: _______________________

**Question 27.2**: Who will be the Payroll User(s)? (Name and email)
- [ ] BEI: Name: _______________________ Email: _______________________
- [ ] Bebang Kitchen: Name: _______________________ Email: _______________________
- [ ] Stores: Name: _______________________ Email: _______________________

**Question 27.3**: Who will be the Finance Manager(s)? (Name and email)
- [ ] BEI: Name: _______________________ Email: _______________________
- [ ] Bebang Kitchen: Name: _______________________ Email: _______________________

**Question 27.4**: List all department managers who need approval access:
- [ ] Manager Name: _______________________ Department: _______________________ Company: _______________________

**Question 27.5**: Who needs read-only access to HR data? (e.g., executives)
- [ ] Name: _______________________ Role: _______________________

---

## 📧 **SECTION 10: EMAIL & NOTIFICATIONS**

**Question 28.1**: Do you have SMTP email server configured?
- [ ] Yes, provide details: _______________________________
- [ ] No, need to set up

**Question 28.2**: What email notifications should be sent?
- [ ] Leave application submitted
- [ ] Leave application approved/rejected
- [ ] Expense claim submitted
- [ ] Expense claim approved/rejected
- [ ] Payroll processed
- [ ] Salary slip generated
- [ ] Attendance marked
- [ ] Others: _______________________________

**Question 28.3**: Who should receive payroll notifications?
- [ ] Answer: _______________________________

---

## 🔐 **SECTION 11: SECURITY & COMPLIANCE**

**Question 29.1**: What data retention policy do you follow?
- [ ] Answer: _______________________________

**Question 29.2**: Are there any specific compliance requirements? (GDPR, Data Privacy Act, etc.)
- [ ] Yes, specify: _______________________________
- [ ] No

**Question 29.3**: Who should have access to sensitive employee data? (Salary, personal info)
- [ ] Answer: _______________________________

**Question 29.4**: Do you need audit logs for HR actions?
- [ ] Yes
- [ ] No

---

## 📅 **SECTION 12: IMPORTANT DATES**

**Question 30.1**: What is the payroll processing date? (e.g., 25th of each month)
- [ ] BEI: _______________________________
- [ ] Bebang Kitchen: _______________________________
- [ ] Stores: _______________________________

**Question 30.2**: What is the payroll payment date? (e.g., 1st of next month)
- [ ] BEI: _______________________________
- [ ] Bebang Kitchen: _______________________________
- [ ] Stores: _______________________________

**Question 30.3**: When does the leave year start?
- [ ] Calendar year (January 1)
- [ ] Fiscal year (specify date): _______________________________
- [ ] Anniversary date (based on joining)

**Question 30.4**: When does the leave year end?
- [ ] Calendar year (December 31)
- [ ] Fiscal year (specify date): _______________________________
- [ ] Anniversary date (based on joining)

**Question 30.5**: When is 13th Month Pay paid?
- [ ] December (full)
- [ ] May and December (split)
- [ ] Other: _______________________________

**Question 30.6**: What are the BIR tax filing deadlines you need to track?
- [ ] Answer: _______________________________

**Question 30.7**: Final Pay Configuration - Philippines Labor Code:
- [ ] **30-Day Rule**: Final Pay must be released within 30 days from separation (Labor Advisory No. 06-2020)
- [ ] **Final Pay Components**:
  - [ ] Unpaid Wages (for final work period)
  - [ ] Prorated 13th Month Pay: (Basic Salary Earned ÷ 12)
  - [ ] Leave Monetization: Cash value of unused SIL (mandatory) and other convertible leaves
  - [ ] Tax Refund: Excess tax withheld if annualized tax due is less than total withheld
- [ ] **Authorized Deductions from Final Pay** (Article 113, Labor Code):
  - [ ] Withholding Tax
  - [ ] SSS/PhilHealth/Pag-IBIG premiums
  - [ ] Union Dues
  - [ ] Debts/Loans (requires written authorization)
  - [ ] Losses (only if due process followed, max 20% of wages, subject to employee consent)
- [ ] **Clearance Policy**: Cannot indefinitely withhold Final Pay beyond 30-day window

---

## 📎 **SECTION 13: DOCUMENTS & TEMPLATES**

**Question 31.1**: Do you have letter templates?
- [ ] Appointment Letter Template
- [ ] Offer Letter Template
- [ ] Experience Certificate Template
- [ ] Salary Certificate Template
- [ ] Exit Interview Template
- [ ] Others: _______________________________

**Question 31.2**: Do you have custom salary slip format?
- [ ] Yes, provide format requirements
- [ ] No, use default

**Question 31.3**: What information should appear on salary slips?
- [ ] Basic salary breakdown
- [ ] Allowances breakdown
- [ ] Deductions breakdown (SSS, PhilHealth, Pag-IBIG, Tax)
- [ ] Net pay
- [ ] Year-to-date totals
- [ ] Others: _______________________________

**Question 31.4**: Do you need custom reports?
- [ ] Yes, specify: _______________________________
- [ ] No

---

## 🎓 **SECTION 14: TRAINING & DEVELOPMENT** (Optional)

**Question 32.1**: Do you track employee training?
- [ ] Yes
- [ ] No

**Question 32.2**: If yes, what training programs do you have?
- [ ] Program 1: _______________________________
- [ ] Program 2: _______________________________

**Question 32.3**: Do you track employee skills?
- [ ] Yes
- [ ] No

---

## 📝 **SECTION 15: RECRUITMENT** (Optional)

**Question 33.1**: Do you use the system for recruitment?
- [ ] Yes
- [ ] No

**Question 33.2**: What are your current job openings? (if any)
- [ ] Position: _______________________ Department: _______________________ Company: _______________________

---

## ⚙️ **SECTION 16: SYSTEM SETTINGS**

**Question 34.1**: Do you want to enable Employee Self-Service? (Employees can view their own data, apply leaves, etc.)
- [ ] Yes
- [ ] No

**Question 34.2**: Do you want to enable mobile app access?
- [ ] Yes
- [ ] No

**Question 34.3**: What language should the system use?
- [ ] English
- [ ] Filipino/Tagalog
- [ ] Both

**Question 34.4**: What timezone should be used?
- [ ] Asia/Manila (Philippines Standard Time)

---

## 📊 **SECTION 17: DATA IMPORT**

**Question 35.1**: Do you have employee data in Excel/CSV format ready for import?
- [ ] Yes, file location: _______________________________
- [ ] No, need to prepare

**Question 35.2**: What format is your current employee data in?
- [ ] Excel
- [ ] CSV
- [ ] Database
- [ ] Paper files
- [ ] Other: _______________________________

**Question 35.3**: Do you need help mapping your current data format to Frappe HR format?
- [ ] Yes
- [ ] No

---

## ✅ **PRIORITY QUESTIONS - ANSWER THESE FIRST**

These questions are critical for initial setup:

1. **Store Entity Structure Decision** (Question 1.1)
2. **Company Information** for all entities (Questions 1.1-4.4)
3. **Employee Count** per company (Questions 2.14, 3.12, 22.3-22.5)
4. **Payroll Frequency** per company (Questions 16.1-16.3)
5. **2025 Statutory Deduction Rates** (CRITICAL - Questions 18.2, 18.4, 18.6):
   - SSS: 15% (10% ER, 5% EE), MSC ₱5,000-₱35,000, WISP threshold
   - PhilHealth: 5% (2.5% ER, 2.5% EE), Floor ₱10,000, Ceiling ₱100,000
   - Pag-IBIG: 2% EE, 2% ER, MFS ₱10,000 (₱200/₱200)
6. **Daily Rate Divisor** per salary structure (Question 10.6a) - 313 (6-day) or 261 (5-day)
7. **13th Month Pay** calculation and payment timing (Questions 17.5-17.7)
8. **Basic Salary Structures** per company (Question 19.2)
9. **Employee List with Company Assignment** (Question 22.2)
10. **Mandatory Leave Types** configuration (Question 11.1) - SIL, Solo Parent, Maternity, Paternity, etc.

---

## 📝 **HOW TO ANSWER**

1. **Fill in the blanks** directly in this document
2. **Check boxes** for yes/no or multiple choice questions
3. **Provide lists** in Excel/CSV format for bulk data
4. **Mark as "N/A"** if question doesn't apply
5. **Add notes** if clarification is needed

---

## 📞 **SUPPORT**

If you have questions about any of these questions, contact:
- Technical Setup: [Your IT Contact]
- HR Configuration: Ronald Caringal (HR Manager)
- Payroll Setup: Butch Formoso (CFO)

---

**Document Version**: 1.0
**Last Updated**: December 8, 2025
**Context**: Multi-Company Setup for BEI Group - Philippines Labor Law Compliant


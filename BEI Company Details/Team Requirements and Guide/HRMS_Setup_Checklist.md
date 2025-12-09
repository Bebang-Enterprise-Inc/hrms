# Frappe HRMS Setup Checklist
## Information Required from Finance & HR Teams - Philippines Labor Law Compliant (2025)

This document outlines all the information and data needed to fully configure and set up the Frappe HRMS system. Please provide this information to ensure a smooth implementation.

**⚠️ IMPORTANT: This checklist has been updated with 2025 Philippine Labor Law requirements based on the comprehensive Philippine Payroll & HR Configuration Guide, including:**
- 2025 SSS rates (15% total, MSC ₱5,000-₱35,000, WISP threshold ₱20,000, EC rates)
- 2025 PhilHealth rates (5%, Floor ₱10,000, Ceiling ₱100,000, MBS-based)
- 2025 Pag-IBIG rates (MFS ₱10,000, ₱200/₱200 standard)
- Updated De Minimis benefits (Clothing ₱7,000/year per RR 004-2025)
- TRAIN Law 2025 tax brackets and semi-monthly withholding tables
- All mandatory leave types with specific entitlements and eligibility
- Daily rate divisors (313 for 6-day, 261 for 5-day, 365 for daily-paid)
- Comprehensive overtime and premium pay matrix with stacking rules
- 13th Month Pay calculation with exclusions
- Final Pay 30-day rule and components

---

## 📋 **1. MULTI-COMPANY SETUP** ⚠️ **CRITICAL FOR BEI**

### Company Structure Overview
Your organization has a **multi-company structure** that needs to be set up in Frappe HR:

1. **Irrisistable Infusions Inc. (Triple I)** - Holding Company (no employees)
2. **Bebang Enterprise Inc. (BEI)** - Head Office employees
3. **Bebang Kitchen Inc.** - Commissary employees (~100 employees)
4. **Individual Store Entities** - Store employees (separate legal entities)

### Company Information - For EACH Company

#### **Company 1: Irrisistable Infusions Inc. (Triple I)**
- [ ] **Company Name**: Irrisistable Infusions Inc.
- [ ] **Company Abbreviation**: Triple I or III
- [ ] **Company Type**: Holding Company (Is Group Company: Yes)
- [ ] **Company Registration Number**
- [ ] **Tax ID / VAT Number**
- [ ] **Company Address**
- [ ] **Phone Number**
- [ ] **Email Address**
- [ ] **Default Currency**: PHP
- [ ] **Fiscal Year Start Date**
- [ ] **Fiscal Year End Date**
- [ ] **Chart of Accounts**

#### **Company 2: Bebang Enterprise Inc. (BEI)**
- [ ] **Company Name**: Bebang Enterprise Inc.
- [ ] **Company Abbreviation**: BEI
- [ ] **Parent Company**: Irrisistable Infusions Inc.
- [ ] **Company Registration Number**
- [ ] **Tax ID / VAT Number**
- [ ] **Company Address**: Capital House BGC (and Brittany Hotel BGC from mid-June 2025)
- [ ] **Phone Number**
- [ ] **Email Address**
- [ ] **Default Currency**: PHP
- [ ] **Fiscal Year Start Date**
- [ ] **Fiscal Year End Date**
- [ ] **Chart of Accounts**
- [ ] **Employee Count**: ~78 head office employees

#### **Company 3: Bebang Kitchen Inc.**
- [ ] **Company Name**: Bebang Kitchen Inc.
- [ ] **Company Abbreviation**: BKI (or preferred code)
- [ ] **Parent Company**: Irrisistable Infusions Inc.
- [ ] **Company Registration Number**
- [ ] **Tax ID / VAT Number**
- [ ] **Company Address**: Shaw Blvd, Mandaluyong (Commissary location)
- [ ] **Phone Number**
- [ ] **Email Address**
- [ ] **Default Currency**: PHP
- [ ] **Fiscal Year Start Date**
- [ ] **Fiscal Year End Date**
- [ ] **Chart of Accounts**
- [ ] **Employee Count**: ~100 commissary employees

#### **Company 4+: Individual Store Entities**
For each store entity, provide:
- [ ] **Company Name** (Legal entity name for each store)
- [ ] **Company Abbreviation**
- [ ] **Parent Company**: Irrisistable Infusions Inc. (or BEI, depending on structure)
- [ ] **Store Name** (e.g., "SM Megamall", "Ayala Market! Market!")
- [ ] **Store Location/Address**
- [ ] **Store Type**: Company-owned / Joint Venture / Franchise / Managed Franchise
- [ ] **Company Registration Number**
- [ ] **Tax ID / VAT Number**
- [ ] **Employee Count** (per store)
- [ ] **Default Currency**: PHP
- [ ] **Fiscal Year Dates**

**Note**: You have 51+ stores. Decide if you want to:
- Set up each store as a separate company in the system, OR
- Group stores by type (Company-owned, JV, Franchise) into fewer companies, OR
- Use Branches instead of separate companies for stores (recommended for stores with same payroll/HR policies)

### Organizational Structure

#### **Branches/Offices List** (For each Company)

**For BEI (Head Office):**
- [ ] **Capital House BGC** (Main office - Marketing & Tech teams)
  - Address
  - Contact information
  - Is it the main branch? Yes
- [ ] **Brittany Hotel BGC** (Secondary office - from mid-June 2025)
  - Address
  - Contact information
  - Teams moving here: (specify which teams)

**For Bebang Kitchen Inc. (Commissary):**
- [ ] **Shaw Blvd Commissary**
  - Address: Shaw Blvd, Mandaluyong
  - Contact information
  - Is it the main branch? Yes

**For Store Locations:**
- [ ] **Store Branches List** (51+ stores)
  - Store name (e.g., SM Megamall, Ayala Market! Market!)
  - Store address
  - Store type (Company-owned / JV / Franchise / Managed Franchise)
  - Company entity it belongs to
  - Contact information
  - Employee count per store

**Recommendation**: Consider using **Branches** for stores instead of separate companies if they share the same:
- Payroll policies
- HR policies
- Leave policies
- Tax structure

- [ ] **Departments List**
  - Department name
  - Department code (if any)
  - Parent department (if hierarchical)
  - Department head/manager

- [ ] **Designations/Job Titles List**
  - Designation name
  - Description
  - Department(s) it belongs to

- [ ] **Employee Grades** (if applicable)
  - Grade name
  - Grade level/number
  - Description

---

## 🔀 **1A. MULTI-COMPANY DECISION MATRIX**

### Critical Decision: Store Entities Setup

**Question**: How should individual store entities be configured?

**Option A: Separate Companies** (Recommended if stores have separate legal entities and payroll)
- ✅ Each store entity is a separate company in Frappe HR
- ✅ Separate payroll processing per store
- ✅ Separate financial reporting per store
- ✅ Better for stores with different owners (JV partners, franchisees)
- ❌ More complex setup and maintenance
- ❌ More payroll processing overhead

**Option B: Branches Under Main Companies** (Recommended if stores share payroll/HR policies)
- ✅ Stores are branches under BEI or Bebang Kitchen Inc.
- ✅ Simpler payroll processing
- ✅ Easier reporting and management
- ✅ Better for company-owned stores with same policies
- ❌ Less granular financial separation
- ❌ May not work if stores are separate legal entities

**Decision Required:**
- [ ] **Which stores should be separate companies?** (List store names/entities)
- [ ] **Which stores should be branches?** (List store names)
- [ ] **Grouping strategy**: 
  - All company-owned stores under BEI as branches?
  - JV stores as separate companies?
  - Franchise stores as separate companies?
  - Managed franchise stores as branches or companies?

---

## 👥 **2. EMPLOYMENT TYPES & POLICIES**

### Employment Types
- [ ] List all employment types used:
  - Full-time
  - Part-time
  - Contract
  - Probation
  - Intern
  - Apprentice
  - Commission-based
  - Piecework
  - Others (specify)

### HR Policies
- [ ] **Probation Period** (in months/days)
- [ ] **Notice Period** (in days)
- [ ] **Working Hours per Day**
- [ ] **Working Days per Week**
- [ ] **Overtime Policy** (rate, approval process)
- [ ] **Employee Benefits** (health insurance, retirement plans, etc.)

---

## 🏖️ **3. LEAVE MANAGEMENT SETUP**

### Leave Types - **Philippines Labor Law Mandatory Leaves**

#### **Mandatory Statutory Leaves (2025)**
- [ ] **Service Incentive Leave (SIL)** - Article 95, Labor Code
  - **Entitlement**: 5 days with pay
  - **Eligibility**: Employees with at least 1 year of service
  - **Cash Conversion**: MANDATORY - Unused SIL must be converted to cash at year-end or upon separation
  - **Note**: If company grants 15 days VL, first 5 days must be convertible to cash to comply with SIL

- [ ] **Expanded Solo Parent Leave** - Republic Act No. 11861 (2025 Update)
  - **Entitlement**: 7 working days with full pay
  - **Eligibility**: 
    - Valid Solo Parent ID (LGU/DSWD issued)
    - Service Requirement: 6 months (reduced from 1 year)
  - **Non-Convertibility**: FORFEITABLE - Not convertible to cash if unused
  - **System Requirement**: Validate Solo Parent ID expiry date before allowing leave

- [ ] **VAWC Leave** - Republic Act No. 9262
  - **Target**: Female employees who are victims of violence
  - **Entitlement**: 10 days with full pay
  - **Conditions**: Requires certification (Barangay, Police, or Prosecutor Protection Order)
  - **Extendibility**: Can be extended beyond 10 days if specified in Protection Order
  - **Non-Convertibility**: FORFEITABLE and non-convertible to cash

- [ ] **Magna Carta of Women Leave** - Republic Act No. 9710
  - **Target**: Female employees requiring gynecological surgery (hysterectomy, ovariectomy, mastectomy)
  - **Entitlement**: Up to 2 months (60 days) with full pay
  - **Eligibility**: At least 6 months aggregate service in last 12 months
  - **Non-Convertibility**: Non-cumulative and non-convertible
  - **Interaction**: If during Maternity Leave, employee receives difference (if any)

- [ ] **Paternity Leave** - Republic Act No. 8187
  - **Target**: Married male employees
  - **Entitlement**: 7 days with full pay (first 4 deliveries of legitimate spouse)
  - **Transferability**: Under RA 11210, mother can transfer 7 days to father (total 14 days possible)
  - **Funding**: First 7 days (RA 8187) employer-shouldered; transferred 7 days (RA 11210) reimbursed by SSS

- [ ] **Maternity Leave** - Republic Act No. 11210
  - **Entitlement**: 
    - 105 days (Live Birth)
    - 60 days (Miscarriage)
  - **Solo Parent Bonus**: Additional 15 days (Total 120 days for solo parents)
  - **Funding**: Paid by SSS, but employer must advance payment
  - **Differential Pay**: Employer must pay salary differential between SSS benefit and actual basic salary

#### **Company Leave Types**
For each additional leave type, provide:
- [ ] **Leave Type Name** (e.g., Vacation Leave, Sick Leave, Emergency Leave)
- [ ] **Maximum Leaves Allowed** per year/period
- [ ] **Maximum Consecutive Days** allowed
- [ ] **Can be Carried Forward?** (Yes/No)
- [ ] **Maximum Carry Forward Days**
- [ ] **Allow Encashment?** (Yes/No)
- [ ] **Is Leave Without Pay?** (Yes/No)
- [ ] **Is Compensatory Leave?** (Yes/No)
- [ ] **Applicable After** (minimum working days before eligible)
- [ ] **Include Holidays?** (count holidays as leave days)

### Holiday Lists - **Philippines Specific**
- [ ] **Holiday List Name** (e.g., "Philippines Holidays 2025")
- [ ] **All Philippine Public Holidays** with dates (Regular and Special Non-Working Days)
  - New Year's Day
  - EDSA People Power Revolution Anniversary
  - Maundy Thursday, Good Friday
  - Araw ng Kagitingan
  - Labor Day
  - Independence Day
  - National Heroes Day
  - Bonifacio Day
  - Rizal Day
  - Christmas Day, New Year's Eve
  - And all Special Non-Working Days declared by the President
- [ ] **Company-Specific Holidays** with dates
- [ ] **Optional Holidays** (if applicable)
- [ ] **Holiday List for each Branch/Company** (if different by location)
- [ ] **Holiday Pay Rules**: Regular holidays (200% pay), Special non-working days (130% pay)

### Leave Policies (Optional)
- [ ] **Leave Policy Name**
- [ ] **Applicable to** (Department/Designation/Grade)
- [ ] **Leave Allocations** (how many days of each leave type)

### Leave Periods
- [ ] **Leave Period Start Date**
- [ ] **Leave Period End Date**
- [ ] **Is Active?** (Yes/No)

---

## ⏰ **4. ATTENDANCE & SHIFT MANAGEMENT**

### Shift Types
For each shift, provide:
- [ ] **Shift Name** (e.g., "Day Shift", "Night Shift")
- [ ] **Start Time** (e.g., 9:00 AM)
- [ ] **End Time** (e.g., 6:00 PM)
- [ ] **Break Duration** (in minutes)
- [ ] **Working Hours** per day
- [ ] **Days of Week** (Monday-Sunday)
- [ ] **Enable Auto Attendance?** (Yes/No)
- [ ] **Location/Geofence** (if GPS tracking required)

### Attendance Settings - **Philippines Labor Code Compliance**

#### **Daily Rate Calculation - CRITICAL**
- [ ] **Daily Rate Divisor Selection** (per salary structure):
  - **Factor 313**: For employees working **6 days/week** (Monday-Saturday)
    - Formula: (Monthly Basic Salary × 12) ÷ 313
    - Use for: Manufacturing, Retail, Operations staff
  - **Factor 261**: For employees working **5 days/week** (Monday-Friday)
    - Formula: (Monthly Basic Salary × 12) ÷ 261
    - Use for: Head Office, Admin, Corporate staff
  - **Factor 365**: For daily-paid employees (rare, only if paid for every day including rest days)
- [ ] **Hourly Rate**: Daily Rate ÷ 8 hours
- [ ] **Legal Risk Warning**: Using wrong divisor (e.g., 365 for 5-day workers) violates non-diminution of benefits

#### **Overtime & Premium Pay Configuration**
- [ ] **Check-in/Check-out Method** (Manual, GPS, Biometric, etc.)
- [ ] **Late Entry Grace Period** (in minutes)
- [ ] **Early Exit Grace Period** (in minutes)
- [ ] **Overtime Calculation Method** (Philippines Labor Code - 2025):
  - Regular Day Overtime: 125% of hourly rate
  - Rest Day: 130% of hourly rate
  - Rest Day Overtime: 169% of hourly rate
  - Special Non-Working Day: 130% of hourly rate
  - Special Day Overtime: 169% of hourly rate
  - Special Day + Rest Day: 150% of hourly rate
  - Special + Rest Day Overtime: 195% of hourly rate
  - Regular Holiday: 200% of hourly rate
  - Regular Holiday Overtime: 260% of hourly rate
  - Double Holiday: 300% of hourly rate
- [ ] **Night Shift Differential (NSD)**: 10% premium for work between 10:00 PM - 6:00 AM
  - Stacks multiplicatively on overtime/holiday rates
  - Example: OT on Holiday at 11 PM = (Hourly Rate × 2.60) × 1.10 = 286%
- [ ] **Half Day Settings** (allowed or not)
- [ ] **Service Incentive Leave (SIL)**: 5 days after 1 year of service (mandatory, convertible to cash)

---

## 💰 **5. PAYROLL SETUP** (Finance Team) ⚠️ **MULTI-COMPANY CONFIGURATION**

### Company-Specific Payroll Configuration

**Important**: Each company may have different payroll policies. Configure for EACH company:

#### **For Bebang Enterprise Inc. (BEI) - Head Office**
- [ ] **Payroll Payable Account** (Chart of Accounts for BEI)
- [ ] **Payroll Cost Center** (if applicable)
- [ ] **Payroll Frequency** (Monthly/Weekly/Fortnightly)
- [ ] **Salary Components** (see below - BEI-specific)
- [ ] **Salary Structures** (see below - BEI-specific)
- [ ] **Tax Configuration** (see below)

#### **For Bebang Kitchen Inc. - Commissary**
- [ ] **Payroll Payable Account** (Chart of Accounts for BKI)
- [ ] **Payroll Cost Center** (if applicable)
- [ ] **Payroll Frequency** (Monthly/Weekly/Fortnightly)
- [ ] **Salary Components** (Commissary-specific - may differ from Head Office)
- [ ] **Salary Structures** (Commissary-specific)
- [ ] **Tax Configuration**

#### **For Store Entities**
- [ ] **Payroll Configuration per Store Entity** (if stores have separate payroll)
- [ ] **OR**: Confirm if stores share payroll structure with BEI or BKI

### Salary Components - Earnings
For each earning component, specify which **Company** it applies to:
- [ ] **Component Name** (e.g., Basic Salary, HRA, Allowances)
- [ ] **Company** (BEI / Bebang Kitchen Inc. / Store Entity / All)
- [ ] **Type** (Fixed Amount / Formula-based / Variable)
- [ ] **Amount or Formula**
- [ ] **Is Taxable?** (Yes/No)
- [ ] **Is Included in Gross Pay?** (Yes/No)
- [ ] **Condition** (if applicable, e.g., based on designation/company)

### Salary Components - Deductions
For each deduction component, specify which **Company** it applies to:
- [ ] **Component Name** (e.g., Provident Fund, Tax, Insurance, SSS, PhilHealth, Pag-IBIG)
- [ ] **Company** (BEI / Bebang Kitchen Inc. / Store Entity / All)
- [ ] **Type** (Fixed Amount / Percentage / Formula-based)
- [ ] **Amount/Percentage/Formula**
- [ ] **Is Tax Exempt?** (Yes/No)
- [ ] **Condition** (if applicable)

### Salary Structures
For each salary structure, specify which **Company** it applies to:
- [ ] **Structure Name** (e.g., "BEI Manager Salary Structure", "Commissary Worker Structure")
- [ ] **Company** (BEI / Bebang Kitchen Inc. / Store Entity)
- [ ] **Applicable to** (Designation/Department/Grade)
- [ ] **Payroll Frequency** (Monthly, Weekly, Fortnightly, etc.)
- [ ] **Earnings Components** included
- [ ] **Deductions Components** included
- [ ] **Base Salary** amount

### Income Tax Configuration - **TRAIN Law 2025**

#### **Annual Income Tax Brackets (2025)**
- [ ] **Tax Table Configuration**:
  - Not over ₱250,000: **0% (Exempt)**
  - Over ₱250,000 but not over ₱400,000: **15%** of excess over ₱250,000
  - Over ₱400,000 but not over ₱800,000: ₱22,500 + **20%** of excess over ₱400,000
  - Over ₱800,000 but not over ₱2,000,000: ₱102,500 + **25%** of excess over ₱800,000
  - Over ₱2,000,000 but not over ₱8,000,000: ₱402,500 + **30%** of excess over ₱2,000,000
  - Over ₱8,000,000: ₱2,202,500 + **35%** of excess over ₱8,000,000

#### **Semi-Monthly Withholding Tax (2025)**
- [ ] **Withholding Tax Table Logic** (for semi-monthly payroll):
  - Exempt Bracket: Compensation ≤ ₱10,417 (no withholding)
  - 15% Bracket: > ₱10,417 up to ₱16,667
  - 20% Bracket: > ₱16,667 up to ₱33,333
  - 25% Bracket: > ₱33,333 up to ₱83,333
  - 30% Bracket: > ₱83,333 up to ₱333,333
  - 35% Bracket: > ₱333,333
- [ ] **Tax Calculation Method**: Annualized (recommended) OR Monthly
- [ ] **Tax Exemption Threshold**: ₱250,000 annual net income (≈₱20,833 monthly after deductions)
- [ ] **Bonus Exemption Cap**: ₱90,000 (13th Month Pay + Other Benefits)

#### **De Minimis Benefits - 2025 Updated Ceilings**
- [ ] **Uniform and Clothing Allowance**: ₱7,000.00 per annum (Updated via RR 004-2025)
- [ ] **Rice Subsidy**: ₱2,000.00 or one sack (50kg) per month
- [ ] **Medical Cash Allowance to Dependents**: ₱1,500.00 per semester (₱250/month)
- [ ] **Actual Medical Assistance**: ₱10,000.00 per annum
- [ ] **Laundry Allowance**: ₱300.00 per month
- [ ] **Employee Achievement Awards**: ₱10,000.00 per annum (tangible property only, not cash/GC)
- [ ] **Christmas and Major Anniversary Gifts**: ₱5,000.00 per annum
- [ ] **Daily Meal Allowance**: 25% of basic minimum wage per region (for OT/night shift only)
- [ ] **Excess Rule**: Amounts exceeding ceilings added to ₱90,000 bonus exemption bucket

#### **Tax Configuration Settings**
- [ ] **Tax Declaration Period** (Annual/Quarterly)
- [ ] **Company-Specific Tax Rules** (if any company has different tax treatment)
- [ ] **BIR Form 2307**: Track if employees submit Certificate of Creditable Tax Withheld

### Philippine Statutory Deductions - **2025 RATES (CRITICAL)**

#### **SSS (Social Security System) - 2025 Configuration**
**Effective January 2025:**
- [ ] **Total Contribution Rate**: 15% of Monthly Salary Credit (MSC)
  - **Employer Share**: 10.0%
  - **Employee Share**: 5.0%
- [ ] **MSC Range**: ₱5,000 (minimum) to ₱35,000 (maximum)
- [ ] **WISP/Pension Booster Threshold**: MSC > ₱20,000 (split calculation required)
  - Regular SS: Up to ₱20,000 MSC
  - MPF/Pension Booster: Excess from ₱20,000 to ₱35,000
- [ ] **Employees' Compensation (EC) Program**:
  - MSC ≤ ₱14,500: ₱10.00 (employer only)
  - MSC ≥ ₱15,000: ₱30.00 (employer only)
- [ ] **MSC Lookup Table**: Configure based on monthly compensation ranges
- [ ] **Contribution Base**: Basic salary + COLA (excludes overtime, separation pay)

#### **PhilHealth (PHIC) - 2025 Configuration**
**Effective January 2025:**
- [ ] **Premium Rate**: 5.0% of Monthly Basic Salary (MBS)
  - **Employer Share**: 2.5%
  - **Employee Share**: 2.5%
- [ ] **Income Floor**: ₱10,000.00 (minimum premium: ₱500.00 total)
- [ ] **Income Ceiling**: ₱100,000.00 (maximum premium: ₱5,000.00 total)
- [ ] **Calculation Base**: Monthly Basic Salary ONLY (excludes commissions, OT, NSD, non-integrated allowances)
- [ ] **Formula Logic**: 
  - MBS ≤ ₱10,000: Fixed ₱500.00 (₱250.00 each)
  - ₱10,000 < MBS < ₱100,000: MBS × 5%
  - MBS ≥ ₱100,000: Fixed ₱5,000.00 (₱2,500.00 each)

#### **Pag-IBIG (HDMF) - 2025 Configuration**
**Effective February 2024 (continuing in 2025):**
- [ ] **Employee Rate**: 2% (for compensation > ₱1,500)
- [ ] **Employer Rate**: 2% (universal)
- [ ] **Maximum Fund Salary (MFS)**: ₱10,000.00 (doubled from ₱5,000)
- [ ] **Standard Calculation** (Salary ≥ ₱10,000):
  - Employee Deduction: ₱200.00 (₱10,000 × 2%)
  - Employer Contribution: ₱200.00 (₱10,000 × 2%)
  - Total Remittance: ₱400.00
- [ ] **Voluntary Contributions**: Employees may opt for higher (MP2), but mandatory is capped at ₱200

#### **13th Month Pay - Mandatory Calculation**
- [ ] **Formula**: Total Basic Salary Earned During Calendar Year ÷ 12
- [ ] **Exclusions from Basic Salary**:
  - Overtime Pay
  - Night Shift Differential
  - Holiday Pay
  - Cost of Living Allowance (COLA)
  - Profit-sharing payments
  - Cash equivalent of unused leaves
- [ ] **Commission Inclusion**: Generally excluded unless part of basic wage structure (per employment contract)
- [ ] **Prorated Calculation**: For resigned employees, sum of Basic Salary (Jan 1 to Separation Date) ÷ 12
- [ ] **Payment Timing**: December (full) OR split (May and December) - specify preference
- [ ] **Release Deadline**: Must be included in Final Pay if employee resigns mid-year

#### **Holiday Pay Rules - Philippines Labor Code**
- [ ] **Regular Holidays**: 200% pay (100% if unworked, 200% if worked)
- [ ] **Special Non-Working Days**: 130% pay (if worked)
- [ ] **Double Holiday**: 300% pay (if both regular holidays fall on same day)
- [ ] **Holiday + Rest Day**: 150% pay
- [ ] **Holiday + Rest Day + Overtime**: 195% pay

#### **Overtime Rates - Philippines Labor Code**
- [ ] **Regular Day Overtime**: 125% of hourly rate (100% base + 25% premium)
- [ ] **Rest Day Overtime**: 169% of hourly rate (130% base + 30% premium on top)
- [ ] **Holiday Overtime**: 260% of hourly rate (200% base + 30% premium on top)
- [ ] **Rest Day + Holiday Overtime**: 260% base + 30% premium = 260% total
- [ ] **Night Shift Differential (NSD)**: 10% of hourly rate (stacks on top of overtime/holiday rates)
  - Applies to work between 10:00 PM - 6:00 AM
  - Calculated on the rate of the hour (e.g., OT on Holiday at 11 PM: 260% × 1.10 = 286%)

### Payroll Settings (Per Company)
- [ ] **Payroll Payable Account** (Chart of Accounts - per company)
- [ ] **Payroll Cost Center** (if applicable - per company)
- [ ] **Payroll Frequency** (Monthly/Weekly/Fortnightly - per company)
- [ ] **Salary Slip Email Template** (if custom - per company)
- [ ] **Bank Account for Payroll** (per company)

---

## 👤 **6. EMPLOYEE DATA** (HR Team)

### Employee Master Data - **CRITICAL: Company Assignment Required**

For each employee, provide:
- [ ] **Company Assignment** ⚠️ **MOST IMPORTANT**
  - Which company does this employee belong to?
    - Irrisistable Infusions Inc. (Triple I) - Holding (no employees)
    - Bebang Enterprise Inc. (BEI) - Head Office
    - Bebang Kitchen Inc. - Commissary
    - [Store Entity Name] - Individual store entity
- [ ] **Employee ID** (if existing system)
- [ ] **Full Name**
- [ ] **Date of Birth**
- [ ] **Gender**
- [ ] **Email Address**
- [ ] **Phone Number**
- [ ] **Address** (Current and Permanent)
- [ ] **Emergency Contact** (Name, Relationship, Phone)
- [ ] **Date of Joining**
- [ ] **Employment Type**
- [ ] **Department**
- [ ] **Designation**
- [ ] **Branch** (Office/Store location)
- [ ] **Grade** (if applicable)
- [ ] **Reporting Manager** (Name and Company)
- [ ] **Holiday List** assigned
- [ ] **Default Shift**
- [ ] **Leave Approver** (Manager/HR - specify company)
- [ ] **Expense Approver** (Manager/Finance - specify company)
- [ ] **Salary Structure Assignment** (Company-specific)
- [ ] **Bank Account Details** (Account Number, Bank Name, SWIFT/BIC Code)
- [ ] **TIN (Tax Identification Number)** - Philippines TIN
- [ ] **SSS Number** - Social Security System
- [ ] **PhilHealth Number**
- [ ] **Pag-IBIG (HDMF) Number**
- [ ] **Identification Documents** (Passport, Driver's License, National ID, etc.)
- [ ] **Skills** (if tracking)
- [ ] **Previous Work Experience** (if needed)

### Employee Distribution by Company
- [ ] **BEI Head Office Employees**: ~78 employees (list with company assignment)
- [ ] **Bebang Kitchen Inc. Employees**: ~100 commissary employees (list with company assignment)
- [ ] **Store Employees**: List by store/entity (list with company assignment for each)

### Inter-Company Considerations
- [ ] **Employee Transfers**: Do employees move between companies? (e.g., Head Office to Commissary)
- [ ] **Shared Employees**: Any employees working for multiple companies?
- [ ] **Cost Allocation**: How are shared costs allocated between companies?

### Employee Onboarding
- [ ] **Onboarding Checklist Template**
- [ ] **Required Documents List**
- [ ] **Training Programs** for new employees

### Final Pay Configuration - **Philippines Labor Code**
- [ ] **30-Day Rule**: Final Pay must be released within 30 days from separation date (Labor Advisory No. 06-2020)
- [ ] **Final Pay Components**:
  - Unpaid Wages (for final work period)
  - Prorated 13th Month Pay: (Basic Salary Earned ÷ 12)
  - Leave Monetization: Cash value of unused SIL (mandatory) and other convertible leaves
  - Tax Refund: Excess tax withheld if annualized tax due is less than total withheld
- [ ] **Authorized Deductions from Final Pay** (Article 113, Labor Code):
  - Withholding Tax
  - SSS/PhilHealth/Pag-IBIG premiums
  - Union Dues
  - Debts/Loans (requires written authorization)
  - Losses (only if due process followed, max 20% of wages, subject to employee consent)
- [ ] **Clearance Policy**: Cannot indefinitely withhold Final Pay beyond 30-day window

---

## 📊 **7. PERFORMANCE MANAGEMENT** (HR Team)

### Appraisal Setup
- [ ] **Appraisal Cycle Name** (e.g., "Annual Review 2025")
- [ ] **Start Date**
- [ ] **End Date**
- [ ] **Appraisal Template** (if using templates)
- [ ] **Key Result Areas (KRAs)** for each designation
- [ ] **Performance Goals** structure

### Goals & KRAs
- [ ] **Goal Categories**
- [ ] **KRA Templates** by designation
- [ ] **Rating Scale** (e.g., 1-5, Poor to Excellent)

---

## 💳 **8. EXPENSE MANAGEMENT** (Finance Team)

### Expense Claim Types
- [ ] **Expense Types** (e.g., Travel, Food, Medical, Others)
- [ ] **Approval Workflow** (who approves at each level)
- [ ] **Maximum Amount Limits** (if any)
- [ ] **Required Documents** for each expense type

### Employee Advances
- [ ] **Advance Policy** (when allowed, maximum amount)
- [ ] **Repayment Terms**

---

## 🎓 **9. TRAINING & DEVELOPMENT** (HR Team)

### Training Programs
- [ ] **Training Program Names**
- [ ] **Description**
- [ ] **Duration**
- [ ] **Trainer Details**
- [ ] **Cost** (if applicable)

### Skills Management
- [ ] **Skill Categories**
- [ ] **Required Skills** by designation
- [ ] **Skill Assessment Method**

---

## 📝 **10. RECRUITMENT SETUP** (HR Team)

### Recruitment Sources
- [ ] **Job Applicant Sources** (Website, Referral, Walk-in, etc.)

### Job Openings
- [ ] **Current Job Openings** (if any)
  - Job Title
  - Department
  - Designation
  - Number of Positions
  - Job Description
  - Requirements
  - Salary Range

---

## ⚙️ **11. SYSTEM SETTINGS & CONFIGURATION**

### HR Settings
- [ ] **Email Notifications** (Enable/Disable)
- [ ] **Auto Leave Allocation** (Yes/No)
- [ ] **Auto Attendance** (Yes/No)
- [ ] **Employee Self-Service** (Enable/Disable)
- [ ] **Mobile App Access** (Enable/Disable)

### Approval Workflows
- [ ] **Leave Approval Hierarchy**
- [ ] **Expense Approval Hierarchy**
- [ ] **Attendance Request Approval**
- [ ] **Shift Request Approval**

### User Roles & Permissions
- [ ] **List of HR Users** (names and email addresses)
- [ ] **List of HR Managers** (names and email addresses)
- [ ] **List of Payroll Users** (names and email addresses)
- [ ] **Department Managers** (for approvals)

---

## 📧 **12. EMAIL & NOTIFICATION SETUP**

### Email Configuration
- [ ] **SMTP Server Details** (if using custom email)
- [ ] **Email Templates** (if custom templates needed)
- [ ] **Notification Preferences** (what emails to send)

---

## 🔐 **13. SECURITY & COMPLIANCE**

### Data Privacy
- [ ] **Data Retention Policy**
- [ ] **GDPR/Privacy Compliance Requirements** (if applicable)
- [ ] **Access Control Requirements**

### Backup & Recovery
- [ ] **Backup Schedule Preferences**
- [ ] **Data Export Requirements**

---

## 📅 **14. IMPORTANT DATES & DEADLINES**

- [ ] **Payroll Processing Date** (e.g., 25th of each month)
- [ ] **Payroll Payment Date** (e.g., 1st of each month)
- [ ] **Leave Year Start Date**
- [ ] **Leave Year End Date**
- [ ] **Performance Review Cycle Dates**
- [ ] **Tax Filing Deadlines**

---

## 📎 **15. DOCUMENTS & TEMPLATES**

### Letter Templates
- [ ] **Appointment Letter Template**
- [ ] **Offer Letter Template**
- [ ] **Experience Certificate Template**
- [ ] **Salary Certificate Template**
- [ ] **Exit Interview Template**

### Report Formats
- [ ] **Salary Slip Format** (if custom)
- [ ] **Attendance Report Format**
- [ ] **Leave Balance Report Format**

---

## ✅ **PRIORITY ITEMS** (Required for Initial Setup)

### Must Have (Minimum Viable Setup):
1. ✅ **Multi-Company Setup** ⚠️ **CRITICAL**
   - Irrisistable Infusions Inc. (Holding Company - Group Company)
   - Bebang Enterprise Inc. (BEI) - Head Office
   - Bebang Kitchen Inc. - Commissary
   - Decision: Store entities as separate companies OR branches
2. ✅ At least 1 Branch per Company
3. ✅ At least 1 Department per Company (or shared)
4. ✅ At least 1 Designation per Company (or shared)
5. ✅ Employment Types (shared or company-specific)
6. ✅ Basic Leave Types (at least 2-3) - shared or company-specific
7. ✅ Holiday List for current year (Philippines holidays)
8. ✅ Basic Salary Components (Basic, Tax, SSS, PhilHealth, Pag-IBIG) - per company
9. ✅ At least 1 Salary Structure per Company
10. ✅ Employee Data with **Company Assignment** (at least 1 employee per company for testing)

### Nice to Have (Can be added later):
- Performance Management
- Training Programs
- Recruitment
- Advanced Leave Policies
- Custom Reports

---

## 📞 **CONTACT INFORMATION**

**For Questions or Clarifications:**
- Technical Setup: [Your IT/Technical Contact]
- HR Configuration: [HR Team Lead]
- Payroll Setup: [Finance/Payroll Manager]

---

## 📝 **NOTES**

- Please provide data in Excel/CSV format where possible for bulk import
- Mark items as "Not Applicable" if they don't apply to your organization
- Provide sample data for testing if full data is not ready
- All dates should be in YYYY-MM-DD format
- All monetary values should include currency code

---

**Last Updated:** December 8, 2025
**Version:** 2.0 - Multi-Company Setup

---

## 📝 **WHAT CHANGED AFTER COMPANY STRUCTURE INFORMATION**

### Key Updates Based on Your Multi-Company Structure:

1. **Multi-Company Setup Added** ⚠️
   - Added configuration for Irrisistable Infusions Inc. (Holding Company)
   - Added Bebang Enterprise Inc. (BEI) - Head Office setup
   - Added Bebang Kitchen Inc. - Commissary setup
   - Added decision matrix for store entities (separate companies vs. branches)

2. **Company-Specific Configuration**
   - All payroll, leave, and HR policies now require company assignment
   - Employee data must include company assignment
   - Salary structures are company-specific
   - Payroll accounts are per company

3. **Philippines-Specific Requirements Added**
   - SSS (Social Security System) contributions
   - PhilHealth contributions
   - Pag-IBIG (HDMF) contributions
   - 13th Month Pay calculation
   - Philippine holiday list (Regular and Special Non-Working Days)
   - Philippine Labor Code overtime rates
   - Night shift differential (10% premium)
   - Service Incentive Leave (5 days after 1 year)
   - TIN instead of PAN/Tax ID

4. **Store Entity Decision Required**
   - Need to decide: Separate companies OR branches for stores
   - Consideration: Legal entity structure vs. operational simplicity
   - Impact on payroll processing and reporting

5. **Employee Distribution**
   - BEI Head Office: ~78 employees
   - Bebang Kitchen Inc.: ~100 employees
   - Store employees: Varies by store (need count per store)

6. **Inter-Company Considerations**
   - Employee transfers between companies
   - Shared employees (if any)
   - Cost allocation between companies

### Next Steps:
1. **Decision Required**: How to handle store entities (companies vs. branches)
2. **Data Collection**: Employee list with company assignment
3. **Payroll Setup**: Company-specific salary structures and components
4. **Philippine Compliance**: Ensure all statutory deductions are configured


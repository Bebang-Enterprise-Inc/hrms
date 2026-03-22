# Frappe HRMS Setup - Quick Reference Guide
## Philippines Labor Law Compliant (2025)

## 🎯 **What You Need to Provide**

This is a simplified version of the full checklist. See `HRMS_Setup_Checklist.md` for complete details.

**⚠️ IMPORTANT: Updated with 2025 Philippine Labor Law requirements including all statutory rates, mandatory leaves, and calculation formulas.**

---

## **ESSENTIAL (Must Have for Initial Setup)**

### 1. Multi-Company Setup ⚠️ **CRITICAL**
- **Irrisistable Infusions Inc. (Triple I)** - Holding Company (Group Company)
- **Bebang Enterprise Inc. (BEI)** - Head Office (~78 employees)
- **Bebang Kitchen Inc.** - Commissary (~100 employees)
- **Store Entities** - Decision needed: Separate companies OR branches?
- For each company: name, address, tax ID, currency (PHP), fiscal year dates

### 2. Organization Structure
- **Branches** (Capital House BGC, Brittany Hotel BGC, Commissary Shaw Blvd, 51+ stores)
- **Departments** (Sales, HR, IT, Operations, Marketing, etc.)
- **Designations** (Manager, Executive, CSR, etc.)
- **Employment Types** (Full-time, Part-time, Contract, etc.)

### 3. Leave Setup
- **Leave Types** (Casual, Sick, Vacation) with rules
- **Holiday List** (all public and company holidays for the year)

### 4. Payroll Setup (Finance Team) - **Per Company - 2025 RATES**

#### **Salary Components**
- **Basic Salary**
- **Allowances** (De Minimis: Clothing ₱7,000/yr, Rice ₱2,000/mo, etc.)
- **Tax** (TRAIN Law 2025 brackets)
- **SSS, PhilHealth, Pag-IBIG** (2025 rates - see below)

#### **2025 Statutory Deductions - CRITICAL**
- **SSS**: 15% total (10% ER, 5% EE), MSC ₱5,000-₱35,000, WISP threshold ₱20,000, EC ₱10-₱30
- **PhilHealth**: 5% (2.5% ER, 2.5% EE), Floor ₱10,000, Ceiling ₱100,000, MBS-based
- **Pag-IBIG**: 2% EE, 2% ER, MFS ₱10,000 (standard ₱200/₱200)

#### **Salary Structures** (templates per company: BEI, Commissary, Stores)
- **Daily Rate Divisors**: 313 (6-day), 261 (5-day), 365 (daily-paid)
- **Overtime Rates**: Regular 125%, Rest Day 169%, Holiday 260%, NSD 10% stacks
- **13th Month Pay**: Total Basic Salary ÷ 12 (excludes OT/NSD/holiday/COLA/commissions)

### 5. Employee Data - **Company Assignment Required**
- Employee list with: **Company** (BEI/Bebang Kitchen/Store Entity), Name, Email, Department, Designation, Joining Date, Manager, Bank Details, Salary Structure
- **BEI Head Office**: ~78 employees
- **Bebang Kitchen Inc.**: ~100 employees
- **Store Employees**: List by store/entity

### 6. Attendance/Shifts
- **Shift Types** (Day Shift: 9 AM - 6 PM, Night Shift, etc.)
- Working hours and break times

---

## **IMPORTANT (Needed Soon)**

### 7. Approval Workflows
- Who approves leaves? (Manager → HR)
- Who approves expenses? (Manager → Finance)

### 8. System Users
- HR Manager email
- Payroll User email
- Department Managers for approvals

---

## **OPTIONAL (Can Add Later)**

- Performance Management (Appraisals, Goals)
- Training Programs
- Recruitment (Job Openings)
- Advanced Leave Policies
- Custom Reports

---

## **FORMAT FOR DATA SUBMISSION**

✅ **Preferred Format:** Excel/CSV files
✅ **Date Format:** YYYY-MM-DD (e.g., 2025-01-15)
✅ **Currency:** Include currency code (e.g., USD, PHP, INR)

---

## **PRIORITY ORDER**

1. **Week 1:** Company setup, Organization structure, Basic leave types
2. **Week 2:** Payroll components, Salary structures, Employee data
3. **Week 3:** Shifts, Approval workflows, User setup
4. **Week 4:** Testing, Refinements, Advanced features

---

**Need Help?** Refer to the detailed checklist: `HRMS_Setup_Checklist.md`

---

## ⚠️ **MULTI-COMPANY SETUP - CRITICAL**

Your organization has a **multi-company structure**:
- **Irrisistable Infusions Inc. (Triple I)** - Holding Company
- **Bebang Enterprise Inc. (BEI)** - Head Office (~78 employees)
- **Bebang Kitchen Inc.** - Commissary (~100 employees)
- **Store Entities** - Individual store legal entities

**Key Requirement**: Every employee, payroll structure, and configuration must specify which **Company** it belongs to.

**Decision Needed**: Should stores be set up as:
- **Separate Companies** (if different legal entities/payroll), OR
- **Branches** (if same payroll/HR policies as main company)?

---

## 🇵🇭 **PHILIPPINES-SPECIFIC REQUIREMENTS - 2025**

### **Statutory Deductions (2025 Rates)**
- **SSS**: 15% (10% ER, 5% EE), MSC ₱5,000-₱35,000, WISP threshold ₱20,000
- **PhilHealth**: 5% (2.5% ER, 2.5% EE), Floor ₱10,000, Ceiling ₱100,000
- **Pag-IBIG**: 2% EE, 2% ER, MFS ₱10,000 (₱200/₱200 standard)

### **Mandatory Benefits**
- **13th Month Pay**: Total Basic Salary ÷ 12 (excludes OT/NSD/holiday/COLA)
- **Service Incentive Leave (SIL)**: 5 days after 1 year (convertible to cash)
- **Solo Parent Leave**: 7 days (after 6 months, forfeitable)
- **Maternity Leave**: 105 days (120 for solo parents), SSS-funded
- **Paternity Leave**: 7 days (can be 14 if mother transfers 7 days)
- **VAWC Leave**: 10 days (for female victims)
- **Magna Carta of Women Leave**: Up to 60 days (gynecological surgery)

### **Payroll Calculations**
- **Daily Rate Divisors**: 313 (6-day), 261 (5-day), 365 (daily-paid)
- **Overtime**: Regular 125%, Rest Day 169%, Holiday 260%, NSD 10% stacks
- **Holiday Pay**: Regular 200%, Special 130%, Double 300%
- **Tax**: TRAIN Law 2025 brackets, ₱250,000 exemption, ₱90,000 bonus cap
- **De Minimis**: Clothing ₱7,000/yr, Rice ₱2,000/mo, Medical ₱10,000/yr

### **Other Requirements**
- **Philippine Holiday List** (Regular & Special Non-Working Days)
- **TIN** (Tax Identification Number)
- **Final Pay**: 30-day release rule, includes prorated 13th month, SIL monetization


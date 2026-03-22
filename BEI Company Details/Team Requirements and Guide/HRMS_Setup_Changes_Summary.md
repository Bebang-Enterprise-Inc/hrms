# Summary of Changes to HRMS Setup Checklist
## After Multi-Company Structure Information

---

## 🎯 **WHAT CHANGED**

### 1. **Multi-Company Setup - NEW CRITICAL SECTION** ⚠️

**Before**: Single company setup
**After**: Multi-company structure with:

- **Irrisistable Infusions Inc. (Triple I)**
  - Type: Holding Company (Group Company)
  - Employees: None (holding company only)
  - Purpose: Parent company in the hierarchy

- **Bebang Enterprise Inc. (BEI)**
  - Type: Operating Company
  - Employees: ~78 head office employees
  - Locations: Capital House BGC, Brittany Hotel BGC (from mid-June 2025)
  - Parent: Irrisistable Infusions Inc.

- **Bebang Kitchen Inc.**
  - Type: Operating Company
  - Employees: ~100 commissary employees
  - Location: Shaw Blvd, Mandaluyong
  - Parent: Irrisistable Infusions Inc.

- **Store Entities**
  - Type: Individual legal entities (51+ stores)
  - Decision Required: Separate companies OR branches?
  - Considerations: Legal structure vs. operational simplicity

---

### 2. **Company Assignment Required for Everything**

**Before**: Single company context
**After**: Every configuration item needs company assignment:

- ✅ Employee records → Must specify company
- ✅ Salary structures → Company-specific
- ✅ Payroll accounts → Per company
- ✅ Leave policies → Can be shared or company-specific
- ✅ Departments → Can be shared or company-specific
- ✅ Designations → Can be shared or company-specific

---

### 3. **Philippines-Specific Requirements Added** 🇵🇭

**New Requirements**:

#### Statutory Deductions:
- ✅ **SSS (Social Security System)** - Contribution rates and brackets
- ✅ **PhilHealth** - Health insurance contributions
- ✅ **Pag-IBIG (HDMF)** - Home Development Mutual Fund contributions
- ✅ **13th Month Pay** - Mandatory year-end bonus calculation

#### Philippine Labor Code Compliance:
- ✅ **Holiday Pay Rules**:
  - Regular holidays: 200% of daily rate
  - Special non-working days: 130% of daily rate
- ✅ **Overtime Rates**:
  - Regular overtime: 125% of hourly rate
  - Rest day overtime: 169% of hourly rate
  - Holiday overtime: 200% of hourly rate
  - Rest day + Holiday: 260% of hourly rate
- ✅ **Night Shift Differential**: 10% premium (10 PM - 6 AM)
- ✅ **Service Incentive Leave**: 5 days after 1 year of service

#### Philippine Holidays:
- ✅ Complete list of Regular Holidays
- ✅ Special Non-Working Days (as declared by President)
- ✅ Company-specific holidays

#### Tax & Identification:
- ✅ **TIN (Tax Identification Number)** - Replaces PAN/Tax ID
- ✅ **BIR Tax Slabs** - Philippines income tax brackets
- ✅ **Tax Calculation** - As per BIR regulations

---

### 4. **Store Entity Decision Matrix Added**

**New Section**: Decision matrix to help determine:
- Should stores be separate companies?
- Should stores be branches?
- Grouping strategy (Company-owned vs. JV vs. Franchise)

**Factors to Consider**:
- Legal entity structure
- Payroll policies (same or different)
- Financial reporting needs
- Operational simplicity

---

### 5. **Employee Data Structure Updated**

**Before**: Employee list with basic info
**After**: Employee list with:

- ✅ **Company Assignment** (MOST IMPORTANT)
- ✅ **SSS Number**
- ✅ **PhilHealth Number**
- ✅ **Pag-IBIG Number**
- ✅ **TIN** (instead of PAN)
- ✅ **Reporting Manager** (with company specified)
- ✅ **Inter-company transfer** considerations

**Employee Distribution**:
- BEI Head Office: ~78 employees
- Bebang Kitchen Inc.: ~100 employees
- Store employees: Varies (need count per store)

---

### 6. **Payroll Configuration - Per Company**

**Before**: Single payroll setup
**After**: Company-specific payroll:

- ✅ **Payroll Payable Account** - Per company
- ✅ **Salary Components** - Company-specific or shared
- ✅ **Salary Structures** - Per company (BEI, Commissary, Stores)
- ✅ **Payroll Frequency** - Can differ by company
- ✅ **Cost Centers** - Per company

---

### 7. **Branches Updated**

**Before**: Generic branch list
**After**: Specific branches:

- ✅ **Capital House BGC** - BEI main office (Marketing & Tech)
- ✅ **Brittany Hotel BGC** - BEI secondary office (from mid-June 2025)
- ✅ **Shaw Blvd Commissary** - Bebang Kitchen Inc.
- ✅ **51+ Store Locations** - Need to map to companies/branches

---

### 8. **Priority Items Updated**

**Before**: Single company priority list
**After**: Multi-company priority:

1. ⚠️ **Multi-Company Setup** (NEW - CRITICAL)
2. Company-specific branches
3. Company-specific or shared departments
4. Company-specific or shared designations
5. Employment types (shared or company-specific)
6. Leave types (shared or company-specific)
7. **Philippines Holiday List** (NEW)
8. **Salary Components with SSS/PhilHealth/Pag-IBIG** (NEW)
9. **Salary Structures per Company** (UPDATED)
10. **Employee Data with Company Assignment** (UPDATED)

---

## 📊 **IMPACT ON SETUP PROCESS**

### Additional Steps Required:

1. **Week 0 (NEW)**: Multi-company decision and setup
   - Set up holding company (Triple I)
   - Set up BEI and Bebang Kitchen Inc.
   - Decide on store entity structure
   - Configure company hierarchy

2. **Week 1**: Company-specific organization setup
   - Branches per company
   - Departments (shared or company-specific)
   - Designations (shared or company-specific)

3. **Week 2**: Company-specific payroll setup
   - Salary components per company
   - Salary structures per company
   - Philippine statutory deductions (SSS, PhilHealth, Pag-IBIG)

4. **Week 3**: Employee data with company assignment
   - Import employees with correct company
   - Assign company-specific salary structures
   - Set up reporting relationships (may cross companies)

---

## ⚠️ **CRITICAL DECISIONS NEEDED**

1. **Store Entity Structure**
   - [ ] Separate companies for each store entity?
   - [ ] Branches under main companies?
   - [ ] Hybrid approach (some as companies, some as branches)?

2. **Shared vs. Company-Specific Policies**
   - [ ] Leave policies: Shared or company-specific?
   - [ ] Departments: Shared or company-specific?
   - [ ] Designations: Shared or company-specific?

3. **Inter-Company Operations**
   - [ ] Do employees transfer between companies?
   - [ ] Are there shared employees?
   - [ ] How are costs allocated between companies?

---

## 📋 **DATA COLLECTION UPDATES**

### New Data Required:

1. **Company Information** (for each company):
   - Legal name, registration, tax ID
   - Address, contact info
   - Fiscal year dates
   - Chart of accounts

2. **Employee Company Assignment**:
   - Which company does each employee belong to?
   - Current employee distribution:
     - BEI: ~78 employees
     - Bebang Kitchen: ~100 employees
     - Stores: [Need count per store]

3. **Philippine Statutory Information**:
   - SSS contribution rates
   - PhilHealth rates
   - Pag-IBIG rates
   - BIR tax slabs
   - Holiday list (2025 and beyond)

4. **Store Entity Mapping**:
   - List of all 51+ stores
   - Which company/branch each belongs to
   - Store type (Company-owned / JV / Franchise / Managed Franchise)

---

## ✅ **BENEFITS OF UPDATED CHECKLIST**

1. **Accurate Multi-Company Setup** - Reflects your actual organizational structure
2. **Philippines Compliance** - Includes all statutory requirements
3. **Clear Decision Framework** - Helps decide on store entity structure
4. **Company-Specific Configuration** - Ensures proper payroll and HR setup per company
5. **Scalability** - Easy to add new companies or stores later

---

## 🎯 **NEXT STEPS**

1. **Review the updated checklist** with your finance and HR teams
2. **Make the store entity decision** (companies vs. branches)
3. **Collect company information** for all entities
4. **Gather employee data** with company assignments
5. **Prepare Philippine statutory information** (SSS, PhilHealth, Pag-IBIG rates)
6. **Map store locations** to companies/branches

---

**Version**: 2.0
**Last Updated**: December 8, 2025
**Updated By**: Based on company structure information from BEI Master Prompt


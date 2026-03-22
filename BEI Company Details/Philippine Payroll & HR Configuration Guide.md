# **Comprehensive Configuration and Compliance Report for Philippine Payroll Architecture (FY 2025\)**

## **1\. Strategic Compliance Framework for Philippine Enterprise Payroll**

The configuration of a payroll and Human Resource Information System (HRIS) for a Philippine corporation operating at scale—specifically one with over 700 employees across diverse sectors such as manufacturing, retail, and field operations—requires a sophisticated understanding of the intersection between labor law, tax jurisprudence, and mathematical logic. The fiscal year 2025 represents a watershed moment in Philippine statutory compliance. It marks the culmination of multi-year adjustment schedules for social security, the stabilization of universal health care funding, and the modernization of tax exemption thresholds. For an enterprise utilizing platforms like Frappe HR or ERPNext, the challenge lies not merely in data entry but in the architectural design of salary components and formulas that can withstand the scrutiny of a Department of Labor and Employment (DOLE) audit while ensuring accurate, timely compensation for a workforce with varied shift schedules and pay grades.

The operational landscape of 2025 is governed by three primary regulatory pillars: the full implementation of the contribution hikes mandated by the Social Security Act of 2018 (Republic Act No. 11199), the continued premium adjustments under the Universal Health Care Act (Republic Act No. 11223), and the revised contribution ceilings for the Home Development Mutual Fund (Pag-IBIG). Furthermore, the income tax regime continues to operate under the graduated schedules introduced by the Tax Reform for Acceleration and Inclusion (TRAIN) Law, which necessitates precise annualized withholding tax calculations to prevent year-end tax shocks for employees.

This report serves as an exhaustive technical and legal manual for configuring a compliant payroll system. It is designed to provide the precise "Golden Formulas" required for calculation engines, dissect the nuances of leave management policies including the Expanded Solo Parents Welfare Act, and establish rigorous protocols for separation pay. The analysis moves beyond surface-level rates to explore the deep mechanics of these provisions, ensuring that the configured system handles edge cases—such as "double holiday" overtime in manufacturing or commission-based 13th-month pay in retail—with absolute legal fidelity.

## **2\. Statutory Contribution Architecture: The 2025 Tri-Bureau Mandate**

The Philippine payroll system is anchored by mandatory deductions payable to three government agencies: the Social Security System (SSS), the Philippine Health Insurance Corporation (PhilHealth), and the Home Development Mutual Fund (Pag-IBIG). In 2025, the convergence of scheduled rate increases and ceiling adjustments necessitates a complete recalibration of payroll deduction formulas.

### **2.1 Social Security System (SSS): The Final Tranche of Republic Act No. 11199**

The fiscal year 2025 is definitive for the Social Security System as it implements the final scheduled contribution rate increase mandated by Republic Act No. 11199, also known as the Social Security Act of 2018\.1 This legislative roadmap was designed to extend the actuarial life of the SSS fund, ensuring its viability until 2053\.3 For payroll configuration, this translates to a new contribution matrix that is significantly different from the 2024 schedules.

#### **2.1.1 The 15% Contribution Regime**

Effective January 2025, the total monthly contribution rate has ascended to **15%** of the Monthly Salary Credit (MSC).1 This represents a 1% increase from the previous year's 14% rate. It is imperative to note that this burden is not shared equally. The legislative framework places a heavier responsibility on the employer.

The distribution of the 15% rate is structured as follows:

* **Employer (ER) Share:** 10.0%  
* **Employee (EE) Share:** 5.0%.3

This 2:1 ratio is a hard-coded parameter that must be reflected in the salary component formulas. For every peso contributed to the Regular SS fund, the employer pays two-thirds, and the employee pays one-third.

#### **2.1.2 Re-engineering the Monthly Salary Credit (MSC) Table**

The SSS contribution is not a flat percentage of the actual gross salary; rather, it is a percentage of the Monthly Salary Credit (MSC), which is a tiered proxy for compensation. The 2025 update expands the range of this table, affecting both the lowest-paid workers and the managerial class.

* **Minimum MSC:** The floor has been raised to **₱5,000.00** (up from ₱4,000.00).1 This means that even if an employee earns less than ₱5,000 (e.g., a part-time worker), their contribution is calculated as if they earned ₱5,000.  
* **Maximum MSC:** The ceiling has been increased to **₱35,000.00** (up from ₱30,000.00).1 This is a critical adjustment for high-income earners. In 2024, an employee earning ₱50,000 would pay contributions capped at the ₱30,000 MSC level. In 2025, that same employee will pay contributions based on ₱35,000, resulting in a higher net deduction and a higher employer expense.

#### **2.1.3 The Mandatory Provident Fund (WISP and MySSS Pension Booster)**

A sophisticated component of the 2025 SSS architecture is the handling of the Mandatory Provident Fund (MPF), historically known as the Workers' Investment and Savings Program (WISP) and recently rebranded under the "MySSS Pension Booster" initiative.6

The logic for SSS contributions is bifurcated for employees earning above a certain threshold. The "Regular Social Security" program covers compensation up to an MSC of **₱20,000.00**. Any compensation exceeding this ₱20,000 threshold, up to the new maximum of ₱35,000, falls under the MPF/WISP category.1

The Calculation Logic for High Earners (Salary $\\ge$ ₱35,000):  
For an employee with a monthly compensation of ₱35,000 or more, the contribution is split into two distinct calculation buckets:

1. **Regular SS Bucket (Base ₱20,000):**  
   * Employer Share: $20,000 \\times 10.0\\% \= \\text{₱2,000.00}$  
   * Employee Share: $20,000 \\times 5.0\\% \= \\text{₱1,000.00}$  
2. **MPF/Pension Booster Bucket (Excess ₱15,000):**  
   * Employer Share: $(35,000 \- 20,000) \\times 10.0\\% \= \\text{₱1,500.00}$  
   * Employee Share: $(35,000 \- 20,000) \\times 5.0\\% \= \\text{₱750.00}$

This bifurcation is critical because the funds go to different accounts. The Regular SS contributions fund the defined benefit pension (pooled), while the MPF contributions go into an individual savings account for the member, yielding tax-free investment income.1 In payroll reporting, these amounts are often consolidated for remittance but must be tracked separately for accounting transparency.

#### **2.1.4 The Employees' Compensation (EC) Program**

The EC contribution remains a fixed cost borne entirely by the employer. It provides coverage for work-related sickness, injury, or death. The 2025 logic maintains a two-tier flat rate system based on the MSC:

* **Tier 1:** If MSC $\\le$ ₱14,500, EC Contribution \= **₱10.00**.  
* **Tier 2:** If MSC $\\ge$ ₱15,000, EC Contribution \= **₱30.00**.3

For a corporation with a largely manufacturing and retail workforce, the vast majority of employees will likely fall into Tier 2\.

#### **2.1.5 Consolidated SSS Contribution Matrix (2025)**

To configure the lookup table in Frappe HR or ERPNext, the following matrix consolidates the Regular SS, MPF, and EC components for key salary brackets.

**Table 1: 2025 SSS Contribution Schedule (Selected Brackets)**

| Monthly Salary Range | MSC | ER Regular | ER MPF | ER EC | Total ER | EE Regular | EE MPF | Total EE | Total Remittance |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Below ₱5,250 | 5,000 | 500.00 | 0.00 | 10.00 | **510.00** | 250.00 | 0.00 | **250.00** | 760.00 |
| ₱19,750 \- ₱20,249 | 20,000 | 2,000.00 | 0.00 | 30.00 | **2,030.00** | 1,000.00 | 0.00 | **1,000.00** | 3,030.00 |
| ₱24,750 \- ₱25,249 | 25,000 | 2,000.00 | 500.00 | 30.00 | **2,530.00** | 1,000.00 | 250.00 | **1,250.00** | 3,780.00 |
| ₱29,750 \- ₱30,249 | 30,000 | 2,000.00 | 1,000.00 | 30.00 | **3,030.00** | 1,000.00 | 500.00 | **1,500.00** | 4,530.00 |
| ₱34,750 and Above | 35,000 | 2,000.00 | 1,500.00 | 30.00 | **3,530.00** | 1,000.00 | 750.00 | **1,750.00** | 5,280.00 |

Source Data: 1

**Implementation Note:** The ERP formula must look up the MSC based on the employee's "Monthly Compensation." It is vital to define what constitutes compensation. SSS includes basic salary plus most cash allowances (COLA). However, overtime and separation pay are generally excluded from the contribution base.

### **2.2 PhilHealth (PHIC): The Universal Health Care Stabilization**

The Philippine Health Insurance Corporation (PhilHealth) continues to implement the premium schedule mandated by the Universal Health Care (UHC) Act (Republic Act No. 11223). For the calendar year 2025, the premium rate has stabilized at the ceiling prescribed by the law, requiring careful attention to the income floor and ceiling parameters.10

#### **2.2.1 The 5% Premium Rate**

Effective January 2025, the PhilHealth premium rate remains at **5.0%** of the Monthly Basic Salary (MBS).10 This rate is shared equally between the employer and the employee.

* **Employer Share:** 2.5%  
* **Employee Share:** 2.5%

This direct 50-50 split simplifies the formulaic logic compared to SSS, but the definition of the base creates complexity. PhilHealth strictly utilizes the **Monthly Basic Salary (MBS)** as the computation base. This excludes sales commissions, overtime pay, night shift differentials, and non-integrated allowances.10 For a retail workforce with high commission components, this distinction is financially significant; the PhilHealth deduction should not spike merely because an employee had a high sales month, provided the basic salary remains constant.

#### **2.2.2 Floors, Ceilings, and Mathematical Logic**

The 2025 schedule enforces a wide disparity between the income floor and ceiling, capturing a broader range of salaries within the percentage-based calculation.

* **Income Floor:** ₱10,000.00  
* **Income Ceiling:** ₱100,000.00.10

Payroll Formula Logic:  
The calculation for the total premium ($P\_{Total}$) must follow this conditional logic:

1. Minimum Range (MBS $\\le$ ₱10,000):

   $$P\_{Total} \= 500.00$$  
   $$P\_{EE} \= 250.00$$  
   $$P\_{ER} \= 250.00$$  
2. Percentage Range (₱10,000 \< MBS \< ₱100,000):

   $$P\_{Total} \= MBS \\times 0.05$$  
   $$P\_{EE} \= P\_{Total} / 2$$  
   $$P\_{ER} \= P\_{Total} / 2$$  
3. Maximum Range (MBS $\\ge$ ₱100,000):

   $$P\_{Total} \= 5,000.00$$  
   $$P\_{EE} \= 2,500.00$$  
   $$P\_{ER} \= 2,500.00$$  
   .10

**Configuration Warning:** In previous years, the ceiling was lower (e.g., ₱80,000 or ₱90,000). Systems migrating to 2025 must explicitly update the ceiling variable to **100,000**. Failing to do so will result in under-deduction for executives earning between ₱90,000 and ₱100,000, leading to penalties during remittance.

### **2.3 Pag-IBIG (HDMF): The Adjusted Maximum Fund Salary**

The Home Development Mutual Fund (Pag-IBIG) had maintained a static contribution cap for decades, but recent adjustments effective February 2024 (and continuing into 2025\) have doubled the Maximum Fund Salary (MFS). This change serves to increase the member's savings and loanable amounts but also doubles the mandatory deduction for most regular employees.15

#### **2.3.1 The Contribution Formula**

The Pag-IBIG contribution structure is relatively flat but relies on the MFS cap.

* **Employee Rate:** 1% (for compensation $\\le$ ₱1,500) or 2% (for compensation \> ₱1,500).  
* **Employer Rate:** 2% (universal).  
* **Maximum Fund Salary (MFS):** Increased to **₱10,000.00** (previously ₱5,000.00).5

#### **2.3.2 The "Golden Cap" for 2025**

Since the minimum wage in the Philippines is universally above ₱1,500 per month, the effective formula for almost all corporate employees is the 2% rate capped at the ₱10,000 MFS.

**Standard Calculation (Salary $\\ge$ ₱10,000):**

* **Employee Deduction:** $10,000 \\times 2\\% \= \\text{₱200.00}$  
* **Employer Expense:** $10,000 \\times 2\\% \= \\text{₱200.00}$  
* **Total Remittance:** **₱400.00**.15

**Implication:** Prior to this adjustment, the standard deduction was ₱100.00 per party. The HR system must be updated to reflect this ₱200.00 cap. While employees are permitted to contribute more than the minimum (Voluntary Housing Savings or MP2), the *mandatory* configuration must adhere to this ₱200 limit unless the employee explicitly opts for a higher deduction.

## **3\. Taxation Architecture: TRAIN Law and De Minimis Benefits**

The 2025 income tax landscape is governed by the consolidated rules of the Tax Reform for Acceleration and Inclusion (TRAIN) Law (Republic Act No. 10963). Specifically, the graduated income tax schedule that took effect on January 1, 2023, remains the operational standard for 2025\. This schedule lowered tax rates for middle-income earners compared to the original 2018 TRAIN transition period.

### **3.1 The Annualized Income Tax Schedule (2025)**

The foundation of Philippine tax computation is the Annualized Net Taxable Income. All withholding tax deductions made during payroll periods are essentially estimates attempting to approximate the final annual tax due.

**Table 2: 2025 Annual Income Tax Brackets**

| Net Taxable Income (Annual) | Tax Rate / Formula |
| :---- | :---- |
| Not over ₱250,000 | **0% (Exempt)** |
| Over ₱250,000 but not over ₱400,000 | **15%** of excess over ₱250,000 |
| Over ₱400,000 but not over ₱800,000 | ₱22,500 \+ **20%** of excess over ₱400,000 |
| Over ₱800,000 but not over ₱2,000,000 | ₱102,500 \+ **25%** of excess over ₱800,000 |
| Over ₱2,000,000 but not over ₱8,000,000 | ₱402,500 \+ **30%** of excess over ₱2,000,000 |
| Over ₱8,000,000 | ₱2,202,500 \+ **35%** of excess over ₱8,000,000 |

Source Data: 17

**Strategic Insight:** The ₱250,000 exempt threshold implies that an employee earning approximately ₱20,833 monthly (net of mandatory contributions) pays zero income tax. For a manufacturing workforce where many operators may hover around this level, accurate calculation of non-taxable contributions (SSS/PhilHealth/Pag-IBIG) is crucial to keeping them within the exempt bracket effectively.

### **3.2 Withholding Tax Configuration (Semi-Monthly)**

Most Philippine corporations, particularly those in retail and manufacturing, operate on a semi-monthly payroll cycle (e.g., payouts on the 15th and 30th). The HR system must convert the annual table into a period-specific logic to determine the tax to withhold per payday.

The De-Annualization Method (Semi-Monthly):  
To configure the withholding tax formula, the annual brackets are divided by 24 (the number of pay periods in a year).  
**Semi-Monthly Withholding Tax Table Logic:**

1. **Exempt Bracket:** Compensation $\\le$ ₱10,417. No withholding tax.  
2. **15% Bracket:** Compensation \> ₱10,417 up to ₱16,667.  
   * $\\text{Tax} \= (\\text{Taxable Income} \- 10,417) \\times 15\\%$  
3. **20% Bracket:** Compensation \> ₱16,667 up to ₱33,333.  
   * $\\text{Tax} \= 937.50 \+ (\\text{Taxable Income} \- 16,667) \\times 20\\%$  
4. **25% Bracket:** Compensation \> ₱33,333 up to ₱83,333.  
   * $\\text{Tax} \= 4,270.83 \+ (\\text{Taxable Income} \- 33,333) \\times 25\\%$  
5. **30% Bracket:** Compensation \> ₱83,333 up to ₱333,333.  
   * $\\text{Tax} \= 16,770.83 \+ (\\text{Taxable Income} \- 83,333) \\times 30\\%$  
6. **35% Bracket:** Compensation \> ₱333,333.  
   * $\\text{Tax} \= 91,770.83 \+ (\\text{Taxable Income} \- 333,333) \\times 35\\%$

Source Data: Derived from Annual Table 17 and standard payroll de-annualization factors.

**Operational Note:** "Taxable Income" in this formula refers to Gross Pay minus Non-Taxable Allowances, Tardiness/Absences, and Mandatory Contributions (EE Share of SSS, PhilHealth, Pag-IBIG).

### **3.3 De Minimis Benefits: Maximizing Tax Efficiency**

A critical component of the 2025 compensation strategy is the proper utilization of De Minimis benefits. These are privileges of relatively small value offered by the employer that are **exempt** from both income tax and fringe benefit tax (FBT). They do not count towards the ₱90,000 tax-exempt bonus threshold unless they exceed their specific ceilings.

**Updated 2025 List of De Minimis Benefits and Ceilings:**

1. **Uniform and Clothing Allowance:** Increased to **₱7,000.00 per annum** (Updated via Revenue Regulation No. 004-2025).21 This is a key update; systems configured with the old ₱6,000 limit must be adjusted.  
2. **Rice Subsidy:** ₱2,000.00 or one sack (50kg) per month.21 This is frequently used in manufacturing as a non-taxable salary add-on.  
3. **Medical Cash Allowance to Dependents:** ₱1,500.00 per semester (₱250 per month).4  
4. **Actual Medical Assistance:** ₱10,000.00 per annum.21 This covers actual healthcare needs like annual check-ups or maternity assistance.  
5. **Laundry Allowance:** ₱300.00 per month.22  
6. **Employee Achievement Awards:** ₱10,000.00 per annum. *Condition:* Must be in the form of tangible personal property (e.g., a watch or plaque), never cash or gift certificates.21  
7. **Christmas and Major Anniversary Gifts:** ₱5,000.00 per annum.21  
8. **Daily Meal Allowance:** For overtime/night shift only. The limit is 25% of the basic minimum wage per region.22

The "Excess" Rule:  
Any amount given in excess of these specific ceilings is not automatically taxable. Instead, the excess is added to the "13th Month Pay and Other Benefits" bucket. Only if that aggregated bucket exceeds the ₱90,000.00 annual threshold does the remaining amount become subject to income tax.21  
**Example:** If an employer grants a ₱3,000 Rice Subsidy, the first ₱2,000 is De Minimis (tax-free). The excess ₱1,000 is added to the ₱90,000 exemption cap.

## **4\. The "Golden Formulas" of Philippine Payroll Operations**

For a corporation with 700+ employees involving field and factory operations, the calculation of daily rates and overtime is the most frequent source of labor disputes. Precision in these formulas is non-negotiable and must adhere to the Department of Labor and Employment (DOLE) standards.

### **4.1 The Daily Rate Divisor (The 261 vs. 313 Factor)**

In the Philippines, monthly-paid employees often have a "Daily Rate" derived from their monthly salary for the purpose of calculating overtime and deductions. The divisor used to convert Monthly to Daily is legally significant.

Formula:

$$Daily Rate \= \\frac{Monthly Basic Salary \\times 12}{\\text{Factor}}$$  
**Selecting the Correct Factor:**

* **Factor 313:** This is the standard for employees working **6 days a week** (Monday to Saturday). It accounts for 313 paid days (365 days \- 52 unpaid Sundays). This is the predominant factor for **Manufacturing and Retail** staff who work Saturdays.  
* **Factor 261:** This is the standard for employees working **5 days a week** (Monday to Friday). It accounts for 261 paid days (365 \- 52 Saturdays \- 52 Sundays). This is typical for **Head Office/Admin** staff.  
* **Factor 365:** Used for employees paid for every day of the year, including rest days. This is rare for private rank-and-file and is generally used for daily-paid employees converted to a monthly rate equivalent.

**Legal Risk:** Using Factor 365 for an employee who works 5 days a week artificially lowers the daily rate, resulting in lower overtime pay. This is a violation of the principle of non-diminution of benefits.26 The ERP system should allow different divisors for different Salary Structures (e.g., "Operations Structure" using 313, "Corporate Structure" using 261).

### **4.2 Overtime and Premium Pay Matrix (The "Stacking" Rules)**

Manufacturing environments frequently encounter complex scheduling where holidays fall on rest days, or overtime extends into the night shift. The rates stack multiplicatively in specific ways defined by the Labor Code.

Hourly Rate Basis:

$$Hourly Rate \= \\frac{Daily Rate}{8}$$  
**Table 3: Comprehensive Overtime and Premium Pay Multipliers**

| Work Scenario | Base Pay | Premium | Total Rate | Night Shift Diff (NSD) Base |
| :---- | :---- | :---- | :---- | :---- |
| **Ordinary Day** | 100% | 0% | **100%** | 10% of 100% |
| Ordinary Day OT | 100% | 25% | **125%** | 10% of 125% |
| **Rest Day** | 100% | 30% | **130%** | 10% of 130% |
| Rest Day OT | 100% | 69% (30% \+ 30% on top) | **169%** | 10% of 169% |
| **Special Non-Working Day** | 0% (No Work) | 30% (If Worked) | **130%** | 10% of 130% |
| Special Day OT | \- | 69% | **169%** | 10% of 169% |
| Special Day \+ Rest Day | \- | 50% | **150%** | 10% of 150% |
| Special \+ Rest Day OT | \- | 95% (50% \+ 30% on top) | **195%** | 10% of 195% |
| **Regular Holiday** | 100% (Unworked) | 100% (If Worked) | **200%** | 10% of 200% |
| Regular Holiday OT | \- | 160% (100% \+ 30% on 200%) | **260%** | 10% of 260% |
| Double Holiday (2 Regular) | 200% (Unworked) | 100% (If Worked) | **300%** | 10% of 300% |

Source Data: 29

Night Shift Differential (NSD) Engineering:  
The private sector rate is 10% of the hourly rate for work performed between 10:00 PM and 6:00 AM.

* **The Stacking Rule:** NSD is calculated on the *rate of the hour*. It is not a flat 10% of the basic hourly rate.  
* *Example:* If an employee works Overtime on a Regular Holiday at 11:00 PM, the NSD is 10% of the **260%** rate.  
  * Calculation: $Hourly Rate \\times 2.60 \\times 0.10$.  
  * Total Hourly Cost: $Hourly Rate \\times 2.86$ (286%).30

## **5\. The 13th Month Pay Logic**

The 13th Month Pay is a mandatory statutory benefit pursuant to Presidential Decree No. 851\. It is often misunderstood as a "Christmas Bonus," but legally, it is a deferred wage payment.

### **5.1 The Fundamental Formula**

$$\\text{13th Month Pay} \= \\frac{\\text{Total Basic Salary Earned During Calendar Year}}{12}$$

### **5.2 Defining "Basic Salary"**

For the purpose of 13th Month Pay, the definition of "Basic Salary" is restrictive. It **excludes**:

* Overtime Pay  
* Night Shift Differential  
* Holiday Pay  
* Cost of Living Allowance (COLA)  
* Profit-sharing payments  
* Cash equivalent of unused leaves.33

The Commission Conundrum (Retail Context):  
For retail employees paid via commissions, the inclusion of these commissions in the 13th Month Pay is a matter of jurisprudence.

* **General Rule:** Commissions are excluded if they are "productivity bonuses."  
* **Exception (San Miguel Corp vs. Inciong):** If commissions are an integral part of the basic wage structure (wage-commission hybrids) or if company practice has historically included them, they *must* be included.  
* **Configuration Advice:** To minimize liability, most conservative payroll setups exclude commissions unless explicitly mandated by the employment contract. However, for "Sales Employees" whose fixed wage is below minimum and rely on commissions to reach the floor, commissions must be included to meet the minimum wage compliance.33

### **5.3 Prorated Calculation for Resigned Employees**

If an employee resigns mid-year, the system must automatically calculate the pro-rated 13th month pay. This is a strict liability for the employer.

* **Formula:** Sum of Basic Salary (Jan 1 to Separation Date) $\\div$ 12\.  
* **Release:** This amount must be included in the Final Pay release, generally within 30 days of separation.38

## **6\. Leave Management Policies: The Expanded 2025 Portfolio**

The Philippine leave landscape has evolved significantly with the introduction of the Expanded Solo Parents Welfare Act. The HRIS must manage not just leave balances but also "employee attributes" (e.g., Solo Parent status, Gender, Civil Status) to trigger eligibility correctly.

### **6.1 Service Incentive Leave (SIL)**

* **Legal Basis:** Article 95 of the Labor Code.  
* **Entitlement:** **5 Days** with pay.  
* **Eligibility:** Employees with at least 1 year of service.40  
* **Cash Conversion:** Mandatory. Unused SIL must be converted to cash at the end of the year or upon separation.  
* **Configuration Note:** Most corporations grant 15 days of Vacation Leave (VL). The law considers the first 5 days of this VL as compliance with the SIL mandate. Therefore, at least 5 days of the company VL must be convertible to cash to remain compliant.42

### **6.2 Expanded Solo Parent Leave (Republic Act No. 11861\)**

This is a critical compliance checkpoint for 2025\.

* **Entitlement:** **7 Working Days** with full pay.44  
* **Eligibility:**  
  * Any employee (male or female) with a valid **Solo Parent ID** issued by the LGU/DSWD.  
  * Service Requirement: Reduced to **6 months** (previously 1 year).  
* **Non-Convertibility:** Unlike SIL, this leave is **forfeitable**. It is not convertible to cash if unused by the end of the year.46  
* **System Logic:** The system must validate the "Solo Parent ID Expiry" date before allowing the leave application.

### **6.3 VAWC Leave (Republic Act No. 9262\)**

* **Target:** Female employees who are victims of violence (physical, sexual, psychological, or economic).  
* **Entitlement:** **10 Days** with full pay.48  
* **Conditions:** Requires certification from the Barangay, Police, or Prosecutor (e.g., Protection Order).  
* **Extendibility:** Can be extended beyond 10 days if specified in a Protection Order.  
* **Non-Convertibility:** Forfeitable and non-convertible to cash.48

### **6.4 Magna Carta of Women Leave (Republic Act No. 9710\)**

* **Target:** Female employees requiring surgery for gynecological disorders (e.g., hysterectomy, ovariectomy, mastectomy).  
* **Entitlement:** Up to **2 Months (60 Days)** with full pay.50  
* **Eligibility:** At least 6 months of aggregate service in the last 12 months.  
* **Conversion:** Non-cumulative and non-convertible.  
* **Interaction:** If surgery occurs during Maternity Leave, the employee receives the difference (if any), but generally, Maternity Leave takes precedence for pregnancy-related surgeries.51

### **6.5 Paternity Leave (Republic Act No. 8187\)**

* **Target:** Married male employees.  
* **Entitlement:** **7 Days** with full pay for the first 4 deliveries of the legitimate spouse.52  
* **Transferability:** Under the Expanded Maternity Leave Law (RA 11210), the mother can transfer **7 days** of her paid leave to the father, potentially increasing his total leave to **14 days**.  
* **Funding:** The first 7 days (RA 8187\) are employer-shouldered. The transferred 7 days (RA 11210\) are reimbursed by SSS.54

### **6.6 Maternity Leave (Republic Act No. 11210\)**

While paid by SSS, the employer must advance the payment.

* **Entitlement:** 105 Days (Live Birth), 60 Days (Miscarriage).  
* **Solo Parent Bonus:** An additional **15 Days** (Total 120\) for solo parents.56  
* **Differential Pay:** Employers must pay the salary differential between the SSS benefit and the employee's actual basic salary, ensuring the employee receives full pay during the leave.56

## **7\. Separation and Final Pay Governance**

The "Final Pay" module is the last touchpoint of the employee lifecycle and a frequent source of litigation.

### **7.1 The 30-Day Rule**

Per Labor Advisory No. 06-2020, Final Pay must be released within **30 days** from the date of separation or termination.57

### **7.2 Components of Final Pay**

1. **Unpaid Wages:** For the final work period.  
2. **Prorated 13th Month Pay:** (Basic Salary Earned $\\div$ 12).  
3. **Leave Monetization:** Cash value of unused SIL (mandatory) and other convertible leaves (per company policy).57  
4. **Tax Refund:** If the tax withheld throughout the year exceeds the annualized tax due (common for employees separating mid-year), the excess must be refunded to the employee.59

### **7.3 Authorized Deductions (Article 113\)**

The system must restrict deductions from Final Pay to only those authorized by law or the employee.

* **Authorized:** Withholding Tax, SSS/PhilHealth/Pag-IBIG premiums, Union Dues.  
* **Conditional:** Debts/Loans (requires written authorization).  
* **Losses:** Deductions for lost tools or inventory are only legal if the employee is shown to be responsible through due process, and the deduction does not exceed 20% of wages (though for final pay, the 20% rule is often waived in favor of full settlement, subject to employee consent).60

**Clearance Policy:** While employers have the right to process clearance to ensure return of property, "Clearance" cannot be used to indefinitely withhold Final Pay beyond the reasonable 30-day window without risking a complaint for illegal withholding of wages.57

## **8\. Summary of Configuration Parameters (Frappe HR/ERPNext)**

To facilitate the immediate setup of the HRIS, the following table summarizes the key hard-coded parameters for 2025\.

| Parameter | Value / Formula | Statutory Reference |
| :---- | :---- | :---- |
| **SSS ER Contribution Rate** | 10.0% | RA 11199 |
| **SSS EE Contribution Rate** | 5.0% | RA 11199 |
| **SSS Max MSC** | 35,000 | RA 11199 |
| **WISP / Pension Booster Threshold** | MSC \> 20,000 | SSS Circulars |
| **PhilHealth Premium Rate** | 5.0% (Split 50-50) | RA 11223 |
| **PhilHealth Income Ceiling** | 100,000 MBS | RA 11223 |
| **Pag-IBIG Max Fund Salary** | 10,000 (Max Cont: 200/200) | HDMF Circular 460 |
| **Tax Exemption Threshold** | 250,000 Annual Net Income | TRAIN Law |
| **Bonus Exemption Cap** | 90,000 (13th Month \+ Other Benefits) | TRAIN Law |
| **De Minimis (Clothing)** | 7,000 / year | RR 004-2025 |
| **De Minimis (Rice)** | 2,000 / month | RR 11-2018 |
| **Daily Rate Divisor (Ops)** | 313 (Monday-Saturday) | Labor Code |
| **Daily Rate Divisor (Admin)** | 261 (Monday-Friday) | Labor Code |
| **Solo Parent Leave** | 7 Days (after 6 months service) | RA 11861 |
| **Night Shift Differential** | 10% of Hourly Rate | Labor Code Art. 86 |

This architecture ensures that the payroll system is robust, compliant, and ready to handle the complexities of a large-scale Philippine enterprise in 2025\.

#### **Works cited**

1. SSS Contribution Schedule for 2025 \- InCorp Philippines, accessed December 8, 2025, [https://philippines.incorp.asia/advisories/sss-contribution-schedule-for-2025/](https://philippines.incorp.asia/advisories/sss-contribution-schedule-for-2025/)  
2. SSS Implements Revised Contribution Rates for 2025 | Grant Thornton, accessed December 8, 2025, [https://www.grantthornton.com.ph/insights/articles-and-updates1/tax-notes/sss-implements-revised-contribution-rates-for-2025/](https://www.grantthornton.com.ph/insights/articles-and-updates1/tax-notes/sss-implements-revised-contribution-rates-for-2025/)  
3. How to Calculate Your SSS Monthly Contribution in 2025 \- Sprout Solutions, accessed December 8, 2025, [https://sprout.ph/articles/how-to-calculate-your-sss-monthly-contribution/](https://sprout.ph/articles/how-to-calculate-your-sss-monthly-contribution/)  
4. SSS contribution rates increased to 15% starting January 1, 2025, article from Forvis Mazars Payroll Services Philippines, accessed December 8, 2025, [https://www.forvismazars.com/ph/en/insights/hr-payroll-alerts/sss-contribution-rates-increased-to-15](https://www.forvismazars.com/ph/en/insights/hr-payroll-alerts/sss-contribution-rates-increased-to-15)  
5. Contribution For 2025 Employer and Employee | PDF \- Scribd, accessed December 8, 2025, [https://www.scribd.com/document/843965381/Contribution-for-2025-Employer-and-Employee](https://www.scribd.com/document/843965381/Contribution-for-2025-Employer-and-Employee)  
6. Understanding MySSS Pension Booster (SSS WISP): A Guide to Saving Your Money, accessed December 8, 2025, [https://babylon2k.org/understanding-mysss-pension-booster-sss-wisp-a-guide/](https://babylon2k.org/understanding-mysss-pension-booster-sss-wisp-a-guide/)  
7. MySSS Pension Booster | Republic of the Philippines Social Security System, accessed December 8, 2025, [https://www.sss.gov.ph/mysss-pension-booster/](https://www.sss.gov.ph/mysss-pension-booster/)  
8. Pay Contributions | Republic of the Philippines Social Security System \- SSS, accessed December 8, 2025, [https://www.sss.gov.ph/pay-contribution/](https://www.sss.gov.ph/pay-contribution/)  
9. SSS Contribution Table 2025: New Rates and How to Compute for Your Employees, accessed December 8, 2025, [https://www.tripleiconsulting.com/sss-contribution-table-2025-new-rates-how-compute-for-your-employees/](https://www.tripleiconsulting.com/sss-contribution-table-2025-new-rates-how-compute-for-your-employees/)  
10. Premium Contribution for All Direct Contributors for CY ... \- ADVISORY, accessed December 8, 2025, [https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf](https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf)  
11. PhilHealth 2025 Contribution Increase: What Employers Need to Know \- Payday PH, accessed December 8, 2025, [https://www.payday.ph/insights/philhealth-2025-contribution-increase-what-employers-need-to-know](https://www.payday.ph/insights/philhealth-2025-contribution-increase-what-employers-need-to-know)  
12. PhilHealth Contribution Table 2025: Comprehensive Guide for Members | GreatDay HR, accessed December 8, 2025, [https://greatdayhr.ph/blog/philhealth-contribution-2025/](https://greatdayhr.ph/blog/philhealth-contribution-2025/)  
13. Calculating and Understanding Philippine's PhilHealth Contribution for 2025 \- Omni HR, accessed December 8, 2025, [https://www.omnihr.co/blog/philhealth-contribution-2025](https://www.omnihr.co/blog/philhealth-contribution-2025)  
14. PhilHealth Keeps Premium Contribution Rate at 5% for 2025 \- NBS Payroll Solutions, accessed December 8, 2025, [https://www.payrollsolutions.ph/articles/68](https://www.payrollsolutions.ph/articles/68)  
15. Pag-IBIG Contribution Table 2025: How to Compute for Your Employees \- Triple i Consulting, accessed December 8, 2025, [https://www.tripleiconsulting.com/pag-ibig-contribution-table-2025-how-compute-for-your-employees/](https://www.tripleiconsulting.com/pag-ibig-contribution-table-2025-how-compute-for-your-employees/)  
16. Pag-IBIG 2025 Contributions \- Business Registration Philippines, accessed December 8, 2025, [https://businessregistrationphilippines.com/pag-ibig-contributions-2025-guide-for-computing-paying-contributions/](https://businessregistrationphilippines.com/pag-ibig-contributions-2025-guide-for-computing-paying-contributions/)  
17. BIR Tax Table and (SSS, Philhealth, & Pag-ibig) Contribution Updates for 2025 \- Taxumo, accessed December 8, 2025, [https://www.taxumo.com/blog/bir-tax-and-contribution-updates-for-2025/](https://www.taxumo.com/blog/bir-tax-and-contribution-updates-for-2025/)  
18. Latest Income Tax Table in the Philippines (2025) \- FilePino, accessed December 8, 2025, [https://www.filepino.com/income-tax-table-philippines/](https://www.filepino.com/income-tax-table-philippines/)  
19. Understanding the 2025 TRAIN Law: Updated Income Tax Rates and Their Impact, accessed December 8, 2025, [https://greatdayhr.ph/blog/train-law-income-tax-rates-2025/](https://greatdayhr.ph/blog/train-law-income-tax-rates-2025/)  
20. New BIR Tax Tables for 2023 Onwards \- MPM Consulting Services Inc., accessed December 8, 2025, [https://mpm.ph/bir-tax-tables-2023/](https://mpm.ph/bir-tax-tables-2023/)  
21. Better Perks for Happier Employees: Non-Taxability of Employee De Minimis Benefits, accessed December 8, 2025, [https://www.grantthornton.com.ph/insights/articles-and-updates1/lets-talk-tax/better-perks-for-happier-employees-non-taxability-of-employee-de-minimis-benefits/](https://www.grantthornton.com.ph/insights/articles-and-updates1/lets-talk-tax/better-perks-for-happier-employees-non-taxability-of-employee-de-minimis-benefits/)  
22. De Minimis Benefits in the Philippines: What Employers and Employees Need to Know, accessed December 8, 2025, [https://sprout.ph/articles/de-minimis-benefits/](https://sprout.ph/articles/de-minimis-benefits/)  
23. What are De Minimis Benefits? \- Accountable PH, accessed December 8, 2025, [https://www.accountable.ph/what-are-de-minimis-benefits](https://www.accountable.ph/what-are-de-minimis-benefits)  
24. A Guide to PH Holiday Bonuses & De Minimis Benefits (2025) \- NextPay, accessed December 8, 2025, [https://nextpay.world/blog/ph-holiday-bonuses-de-minimis-benefits](https://nextpay.world/blog/ph-holiday-bonuses-de-minimis-benefits)  
25. De Minimis Benefits Eligibility Rules Philippines \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/de-minimis-benefits-eligibility-rules-philippines](https://www.respicio.ph/commentaries/de-minimis-benefits-eligibility-rules-philippines)  
26. Daily Rate Conversion Factors in the Philippines: 313-Day, 261-Day, and 365-Day Methods Explained \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/daily-rate-conversion-factors-in-the-philippines-313-day-261-day-and-365-day-methods-explained](https://www.respicio.ph/commentaries/daily-rate-conversion-factors-in-the-philippines-313-day-261-day-and-365-day-methods-explained)  
27. Is It Legal to Pay Fixed Monthly Salary Based on Daily Rate in the Philippines, accessed December 8, 2025, [https://www.respicio.ph/commentaries/is-it-legal-to-pay-fixed-monthly-salary-based-on-daily-rate-in-the-philippines](https://www.respicio.ph/commentaries/is-it-legal-to-pay-fixed-monthly-salary-based-on-daily-rate-in-the-philippines)  
28. How to Calculate Your Employee's Daily Pay Rate \- AanyaHR, accessed December 8, 2025, [https://www.aanyahr.com/post/how-to-calculate-your-employee-s-daily-pay-rate](https://www.aanyahr.com/post/how-to-calculate-your-employee-s-daily-pay-rate)  
29. Computation of Overtime Pay \- Labor Law PH, accessed December 8, 2025, [https://laborlaw.ph/computation-of-overtime-pay/](https://laborlaw.ph/computation-of-overtime-pay/)  
30. Night Differential Pay in the Philippines: 2025 Guide for Employees and Employers, accessed December 8, 2025, [https://penbrothers.com/blog/night-differential-pay/](https://penbrothers.com/blog/night-differential-pay/)  
31. How to calculate Night-Shift Differential Pay in the Philippines? \- AanyaHR, accessed December 8, 2025, [https://www.aanyahr.com/post/calculating-night-shift-differential-pay-in-the-philippines](https://www.aanyahr.com/post/calculating-night-shift-differential-pay-in-the-philippines)  
32. Labor Laws on Overtime and Night Differential Pay in the Philippines \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/labor-laws-on-overtime-and-night-differential-pay-in-the-philippines](https://www.respicio.ph/commentaries/labor-laws-on-overtime-and-night-differential-pay-in-the-philippines)  
33. How to Compute 13th Month Pay in the Philippines \- Omni HR, accessed December 8, 2025, [https://www.omnihr.co/blog/13th-month-pay](https://www.omnihr.co/blog/13th-month-pay)  
34. 13th Month Pay \- Labor Law PH, accessed December 8, 2025, [https://laborlaw.ph/13th-month-pay/](https://laborlaw.ph/13th-month-pay/)  
35. A COMPREHENSIVE LEGAL DISCOURSE ON THE 13TH MONTH ..., accessed December 8, 2025, [https://www.respicio.ph/dear-attorney/a-comprehensive-legal-discourse-on-the-13th-month-pay-in-the-philippines](https://www.respicio.ph/dear-attorney/a-comprehensive-legal-discourse-on-the-13th-month-pay-in-the-philippines)  
36. Are Part-Time Commission-Based Workers Entitled to 13th Month Pay in the Philippines?, accessed December 8, 2025, [https://www.respicio.ph/commentaries/are-part-time-commission-based-workers-entitled-to-13th-month-pay-in-the-philippines](https://www.respicio.ph/commentaries/are-part-time-commission-based-workers-entitled-to-13th-month-pay-in-the-philippines)  
37. Case Digest: G.R. No. 110068 \- Philippine Duplicators, Inc. vs. National Labor Relations Commission \- Jur.ph, accessed December 8, 2025, [https://jur.ph/jurisprudence/digest/philippine-duplicators-inc-v-national-labor-relations-commission-16976](https://jur.ph/jurisprudence/digest/philippine-duplicators-inc-v-national-labor-relations-commission-16976)  
38. Prorated 13th Month Pay Eligibility After Resigned Employee \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/prorated-13th-month-pay-eligibility-after-resigned-employee](https://www.respicio.ph/commentaries/prorated-13th-month-pay-eligibility-after-resigned-employee)  
39. Thirteenth Month Pay in the Philippines \- Multiplier, accessed December 8, 2025, [https://www.usemultiplier.com/employee-benefits/guide-to-13th-month-pay-in-philippines](https://www.usemultiplier.com/employee-benefits/guide-to-13th-month-pay-in-philippines)  
40. When Do New Employees Become Entitled to Vacation Leave in the Philippines, accessed December 8, 2025, [https://www.respicio.ph/commentaries/when-do-new-employees-become-entitled-to-vacation-leave-in-the-philippines](https://www.respicio.ph/commentaries/when-do-new-employees-become-entitled-to-vacation-leave-in-the-philippines)  
41. Vacation Leave Entitlement After Probation in the Philippines, accessed December 8, 2025, [https://www.respicio.ph/commentaries/vacation-leave-entitlement-after-probation-in-the-philippines](https://www.respicio.ph/commentaries/vacation-leave-entitlement-after-probation-in-the-philippines)  
42. Comprehensive Guide to Vacation Leave & DOLE Rules in the Philippines (2025 Edition), accessed December 8, 2025, [https://dataon.ph/blog/comprehensive-guide-to-vacation-leave-dole-rules-in-the-philippines-2025-edition/](https://dataon.ph/blog/comprehensive-guide-to-vacation-leave-dole-rules-in-the-philippines-2025-edition/)  
43. Service Incentive Leave: A Complete 2025 Guide for Remote & Hybrid Employees, accessed December 8, 2025, [https://penbrothers.com/blog/service-leave-incentive/](https://penbrothers.com/blog/service-leave-incentive/)  
44. FREQUENTLY ASKED QUESTIONS (FAQs) \- TAPI.DOST.gov.ph, accessed December 8, 2025, [http://www.tapi.dost.gov.ph/resources/ol-women-s-desk/faqst](http://www.tapi.dost.gov.ph/resources/ol-women-s-desk/faqst)  
45. R.A. No. 8972, as amended by R.A. No. 11861 | Special Laws | Leaves | LABOR STANDARDS \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/bar/2025/labor-law-and-social-legislation/labor-standards/leaves/special-laws/ra-no-8972-as-amended-by-ra-no-11861](https://www.respicio.ph/bar/2025/labor-law-and-social-legislation/labor-standards/leaves/special-laws/ra-no-8972-as-amended-by-ra-no-11861)  
46. Expanded Solo Parents Benefits Under RA 11861 (2025 Guide) \- Sprout Solutions, accessed December 8, 2025, [https://sprout.ph/articles/solo-parents-benefits-philippines/](https://sprout.ph/articles/solo-parents-benefits-philippines/)  
47. Solo Parent Leave and Benefits Philippines \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/solo-parent-leave-and-benefits-philippines](https://www.respicio.ph/commentaries/solo-parent-leave-and-benefits-philippines)  
48. VAWC Leave in the Philippines: Who Is Entitled and How to Avail (RA 9262\) \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/vawc-leave-in-the-philippines-who-is-entitled-and-how-to-avail-ra-9262](https://www.respicio.ph/commentaries/vawc-leave-in-the-philippines-who-is-entitled-and-how-to-avail-ra-9262)  
49. VAWC Leave \- Labor Law PH, accessed December 8, 2025, [https://laborlaw.ph/vawc-leave/](https://laborlaw.ph/vawc-leave/)  
50. Availment of Special Leave Benefit FAQs | Philippine Commission on Women, accessed December 8, 2025, [https://pcw.gov.ph/faq-availment-of-special-leave-benefit/](https://pcw.gov.ph/faq-availment-of-special-leave-benefit/)  
51. Magna Carta of Women Leave Versus Maternity Leave Entitlement Philippines, accessed December 8, 2025, [https://www.respicio.ph/commentaries/magna-carta-of-women-leave-versus-maternity-leave-entitlement-philippines](https://www.respicio.ph/commentaries/magna-carta-of-women-leave-versus-maternity-leave-entitlement-philippines)  
52. IMPLEMENTING RULES AND REGULATIONS OF REPUBLIC ACT NO. 8187 FOR THE PRIVATE SECTOR \- Supreme Court E-Library, accessed December 8, 2025, [https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/43964](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/10/43964)  
53. Republic Act No. 8187 \- LawPhil, accessed December 8, 2025, [https://lawphil.net/statutes/repacts/ra1996/ra\_8187\_1996.html](https://lawphil.net/statutes/repacts/ra1996/ra_8187_1996.html)  
54. Paternity Leave in the Philippines: Rights, Benefits, and Due Process \- Sprout Solutions, accessed December 8, 2025, [https://sprout.ph/articles/paternity-leave-in-the-philippines/](https://sprout.ph/articles/paternity-leave-in-the-philippines/)  
55. Paternity Leave in the Philippines: 2025 Employment Laws \- Penbrothers, accessed December 8, 2025, [https://penbrothers.com/blog/paternity-leave/](https://penbrothers.com/blog/paternity-leave/)  
56. Leave Policy in the Philippines: 2025 Complete Compliance Guide | AYP Group, accessed December 8, 2025, [https://ayp-group.com/blog/leave-policy-in-philippines](https://ayp-group.com/blog/leave-policy-in-philippines)  
57. Final pay \- Labor Law PH, accessed December 8, 2025, [https://laborlaw.ph/final-pay/](https://laborlaw.ph/final-pay/)  
58. Unlawful deductions from final pay Philippines \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/unlawful-deductions-from-final-pay-philippines](https://www.respicio.ph/commentaries/unlawful-deductions-from-final-pay-philippines)  
59. Preparing for 2025 BIR Tax Annualization: Key Takeaways \- Sprout Solutions, accessed December 8, 2025, [https://sprout.ph/articles/preparing-for-2025-bir-tax/](https://sprout.ph/articles/preparing-for-2025-bir-tax/)  
60. Employer Deductions from Final Pay for Unpaid Bills in the Philippines \- respicio & co., accessed December 8, 2025, [https://www.respicio.ph/commentaries/employer-deductions-from-final-pay-for-unpaid-bills-in-the-philippines](https://www.respicio.ph/commentaries/employer-deductions-from-final-pay-for-unpaid-bills-in-the-philippines)  
61. Illegal Salary Deductions in the Philippines: What Employers Can ..., accessed December 8, 2025, [https://www.respicio.ph/commentaries/illegal-salary-deductions-in-the-philippines-what-employers-can-deduct-from-final-pay](https://www.respicio.ph/commentaries/illegal-salary-deductions-in-the-philippines-what-employers-can-deduct-from-final-pay)
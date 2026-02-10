"""Philippine statutory contributions for 2025.

SSS, PhilHealth, and Pag-IBIG contribution calculations based on official 2025 tables.

Sources:
- SSS: 15% total (10% employer, 5% employee), MSC P5,000-P35,000
- PhilHealth: 5% of basic salary (2.5% each), floor P500, ceiling P5,000
- Pag-IBIG: 1-2% employee, 2% employer, ceiling P10,000 base

References:
- https://www.sss.gov.ph/sss-contribution-table/
- https://www.philhealth.gov.ph/advisories/2025/PA2025-0002.pdf
- https://www.tripleiconsulting.com/pag-ibig-contribution-table-2025-how-compute-for-your-employees/
"""

from frappe.utils import flt


def get_sss_contribution(monthly_salary_credit):
    """Calculate SSS contribution based on 2025 contribution table.

    Args:
        monthly_salary_credit: Monthly salary for SSS computation (float)

    Returns:
        tuple: (employee_share, employer_share, ec_share)

    Based on SSS Circular 2024-006 (effective Jan 1, 2025):
    - Total rate: 15% (up from 14%)
    - Employee: 5% (up from 4.5%)
    - Employer: 10% (up from 9.5%)
    - EC (Employers' Compensation): P10 for MSC P15,000 and below, P30 above
    - MSC range: P5,000 (minimum) to P35,000 (maximum)
    """
    msc = flt(monthly_salary_credit)

    # 2025 SSS Contribution Table (Monthly Salary Credit brackets)
    # Format: (MSC_from, MSC_to, MSC_credit, employee_share, employer_share, EC)
    sss_table = [
        (0, 4999.99, 5000, 250.00, 500.00, 10.00),
        (5000, 5249.99, 5000, 250.00, 500.00, 10.00),
        (5250, 5749.99, 5500, 275.00, 550.00, 10.00),
        (5750, 6249.99, 6000, 300.00, 600.00, 10.00),
        (6250, 6749.99, 6500, 325.00, 650.00, 10.00),
        (6750, 7249.99, 7000, 350.00, 700.00, 10.00),
        (7250, 7749.99, 7500, 375.00, 750.00, 10.00),
        (7750, 8249.99, 8000, 400.00, 800.00, 10.00),
        (8250, 8749.99, 8500, 425.00, 850.00, 10.00),
        (8750, 9249.99, 9000, 450.00, 900.00, 10.00),
        (9250, 9749.99, 9500, 475.00, 950.00, 10.00),
        (9750, 10249.99, 10000, 500.00, 1000.00, 10.00),
        (10250, 10749.99, 10500, 525.00, 1050.00, 10.00),
        (10750, 11249.99, 11000, 550.00, 1100.00, 10.00),
        (11250, 11749.99, 11500, 575.00, 1150.00, 10.00),
        (11750, 12249.99, 12000, 600.00, 1200.00, 10.00),
        (12250, 12749.99, 12500, 625.00, 1250.00, 10.00),
        (12750, 13249.99, 13000, 650.00, 1300.00, 10.00),
        (13250, 13749.99, 13500, 675.00, 1350.00, 10.00),
        (13750, 14249.99, 14000, 700.00, 1400.00, 10.00),
        (14250, 14749.99, 14500, 725.00, 1450.00, 10.00),
        (14750, 15249.99, 15000, 750.00, 1500.00, 10.00),
        (15250, 15749.99, 15500, 775.00, 1550.00, 30.00),
        (15750, 16249.99, 16000, 800.00, 1600.00, 30.00),
        (16250, 16749.99, 16500, 825.00, 1650.00, 30.00),
        (16750, 17249.99, 17000, 850.00, 1700.00, 30.00),
        (17250, 17749.99, 17500, 875.00, 1750.00, 30.00),
        (17750, 18249.99, 18000, 900.00, 1800.00, 30.00),
        (18250, 18749.99, 18500, 925.00, 1850.00, 30.00),
        (18750, 19249.99, 19000, 950.00, 1900.00, 30.00),
        (19250, 19749.99, 19500, 975.00, 1950.00, 30.00),
        (19750, 20249.99, 20000, 1000.00, 2000.00, 30.00),
        (20250, 20749.99, 20500, 1025.00, 2050.00, 30.00),
        (20750, 21249.99, 21000, 1050.00, 2100.00, 30.00),
        (21250, 21749.99, 21500, 1075.00, 2150.00, 30.00),
        (21750, 22249.99, 22000, 1100.00, 2200.00, 30.00),
        (22250, 22749.99, 22500, 1125.00, 2250.00, 30.00),
        (22750, 23249.99, 23000, 1150.00, 2300.00, 30.00),
        (23250, 23749.99, 23500, 1175.00, 2350.00, 30.00),
        (23750, 24249.99, 24000, 1200.00, 2400.00, 30.00),
        (24250, 24749.99, 24500, 1225.00, 2450.00, 30.00),
        (24750, 25249.99, 25000, 1250.00, 2500.00, 30.00),
        (25250, 25749.99, 25500, 1275.00, 2550.00, 30.00),
        (25750, 26249.99, 26000, 1300.00, 2600.00, 30.00),
        (26250, 26749.99, 26500, 1325.00, 2650.00, 30.00),
        (26750, 27249.99, 27000, 1350.00, 2700.00, 30.00),
        (27250, 27749.99, 27500, 1375.00, 2750.00, 30.00),
        (27750, 28249.99, 28000, 1400.00, 2800.00, 30.00),
        (28250, 28749.99, 28500, 1425.00, 2850.00, 30.00),
        (28750, 29249.99, 29000, 1450.00, 2900.00, 30.00),
        (29250, 29749.99, 29500, 1475.00, 2950.00, 30.00),
        (29750, 30249.99, 30000, 1500.00, 3000.00, 30.00),
        (30250, 30749.99, 30500, 1525.00, 3050.00, 30.00),
        (30750, 31249.99, 31000, 1550.00, 3100.00, 30.00),
        (31250, 31749.99, 31500, 1575.00, 3150.00, 30.00),
        (31750, 32249.99, 32000, 1600.00, 3200.00, 30.00),
        (32250, 32749.99, 32500, 1625.00, 3250.00, 30.00),
        (32750, 33249.99, 33000, 1650.00, 3300.00, 30.00),
        (33250, 33749.99, 33500, 1675.00, 3350.00, 30.00),
        (33750, 34249.99, 34000, 1700.00, 3400.00, 30.00),
        (34250, 34749.99, 34500, 1725.00, 3450.00, 30.00),
        (34750, 99999999, 35000, 1750.00, 3500.00, 30.00),  # P35,000 is the ceiling
    ]

    # Find matching bracket
    for msc_from, msc_to, msc_credit, ee_share, er_share, ec in sss_table:
        if msc_from <= msc <= msc_to:
            return (flt(ee_share), flt(er_share), flt(ec))

    # Default to minimum if below range
    if msc < 5000:
        return (250.00, 500.00, 10.00)

    # Default to maximum if above range
    return (1750.00, 3500.00, 30.00)


def get_philhealth_contribution(basic_monthly_salary):
    """Calculate PhilHealth contribution based on 2025 premium rate.

    Args:
        basic_monthly_salary: Monthly basic salary (float)

    Returns:
        tuple: (employee_share, employer_share)

    Based on PhilHealth Advisory PA2025-0002 (effective Jan 1, 2025):
    - Premium rate: 5% of basic monthly salary
    - Split: 2.5% employee, 2.5% employer
    - Floor: P10,000 (minimum contribution P500 total, P250 each)
    - Ceiling: P100,000 (maximum contribution P5,000 total, P2,500 each)
    """
    basic = flt(basic_monthly_salary)

    # Apply floor and ceiling
    if basic < 10000:
        basic = 10000
    elif basic > 100000:
        basic = 100000

    # Calculate 5% premium (2.5% each)
    total_premium = basic * 0.05
    employee_share = total_premium / 2
    employer_share = total_premium / 2

    return (flt(employee_share, 2), flt(employer_share, 2))


def get_pagibig_contribution(basic_monthly_salary):
    """Calculate Pag-IBIG (HDMF) contribution based on 2025 table.

    Args:
        basic_monthly_salary: Monthly basic salary (float)

    Returns:
        tuple: (employee_share, employer_share)

    Based on Pag-IBIG Circular (effective Feb 2024, current through 2025):
    - Employee rate: 2% for all salary levels
    - Employer rate: 2% for all salary levels
    - Ceiling: P10,000 MFS (max contribution: P200 employee, P200 employer)
    """
    basic = flt(basic_monthly_salary)

    # Apply ceiling — Maximum Fund Salary (MFS) is P10,000 (updated Feb 2024)
    computation_base = min(basic, 10000)

    # Employee contribution: flat 2% for all salary levels (updated Feb 2024)
    employee_rate = 0.02

    # Employer contribution: flat 2% for all salary levels
    employer_rate = 0.02

    employee_share = computation_base * employee_rate
    employer_share = computation_base * employer_rate

    return (flt(employee_share, 2), flt(employer_share, 2))

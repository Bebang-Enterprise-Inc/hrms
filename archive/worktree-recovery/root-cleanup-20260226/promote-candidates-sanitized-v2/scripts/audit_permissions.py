"""Full audit: every folder x every person vs Alyssa's Excel matrix."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    'credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/drive']
).with_subject('sam@bebang.ph')
drive = build('drive', 'v3', credentials=creds)

FOLDERS = {
    "01_Revenue/Stores":         "1RrjcSwJxuWyV7eA2oMeiGAXi3spiBfqF",
    "01_Revenue/HO_Commissary":  "1jfq42O91nbnXOMBQ8jG7EmE6oqcs1etX",
    "02_COGS/Stores":            "1g4WPpNB-Pp6ke0TAzq8K0ovBNcLFlnYW",
    "02_COGS/HO_Commissary":     "1ftn0mZ49VcFxrDLM0MgPXqB9dvdj6pKU",
    "03_Payroll/Stores":         "1XJFrm7yOzVrg_23ImcSKWJx_JSrTnIzy",
    "03_Payroll/HO_Commissary":  "1SwT6-NOnseu7RKrOowj-Ruw51zjQLwEn",
    "04_OpEx/Stores":            "1QQkixBoIVXsmNzaAAig7PJdmZZrAJ9dQ",
    "04_OpEx/HO_Commissary":     "1SWBTvMYyZHQbu8aGLKk2dYDnZvWSdnVd",
    "04_OpEx/Rentals":           "1gKApRvn9vZKjE_wwyP_I5X5nNaBs1U5B",
    "04_OpEx/Utilities":         "1MLM_d-GrqnafId6sN1RdUCruYfMYJ20D",
    "04_OpEx/Revolving_Fund":    "15eDUH79Pvgd8CxErZuvcPHrzAY-EeLLm",
    "04_OpEx/SCM_Freight":       "1i8TK_D482RKUNxnegGn9xiZvvSO7ILGO",
    "04_OpEx/Petty_Cash":        "1MA4-EApl9Y9WcIqFnqWrf-TWkb3nyBGR",
    "05_Other/Stores":           "1uFpY960BWV4218LT63vlJfHjZIw_inxs",
    "05_Other/HO_Commissary":    "1BTf8gFiEiD9llg7m4-P29hp9c6d1rcGH",
    "Monthly_Review":            "1ow6dGAO5nUyBnebQLj3ITGOFXKy7XLQI",
    "Assets/Cash":               "1OpMM9UK7UvDFt1RYs1bYzUlXTN7yKmVO",
    "Assets/AR":                 "14bM7w853Mu8u6OwoL4my-7KmZU9dy513",
    "Assets/Other_Current":      "1XC5djWwbCPkJUa6ShohNV6fy7-eMjY2F",
    "Assets/Fixed_Assets":       "1pTMTtoVy8vgijOuK48vjfYDexU6n21Bj",
    "Liabilities/AP":            "1GWPEWQu8q08mr-RnixB5SVHxExvTN3uG",
    "Liabilities/Loans":         "1_fTI5YgdrLIAevADLz1P9cWpJUe__MkZ",
    "Partners":                  "1NvnbscirDTTwzZlImDbXm2mnTfq8vOcP",
    "Trial_Balance":             "1LTFcdweqzVkQgzH_c6szlKEWRqwWvGpZ",
    "Payment_Trackers":          "17GkTjzWhhcZGlAq8HjD4wyKjj-2L5HdQ",
    "Reference_Documents":       "1aRJtu53mcfPknVNWC6KAhuM5eXROyrwZ",
    "Ongoing_Operations":        "1VfgOYyaATkFQR6nz7451wHIkYGYvd1EY",
    "Policies":                  "1nxSbozRchqs18zsjlfYkgU_HFqtvOc7c",
}

# Expected from Alyssa's Excel, cell by cell
EXPECTED = {
    "accounting.bei@bebang.ph": {"Reference_Documents":"E","Ongoing_Operations":"E"},
    "denise@bebang.ph": {
        "01_Revenue/Stores":"E","01_Revenue/HO_Commissary":"E",
        "02_COGS/Stores":"E","02_COGS/HO_Commissary":"E",
        "03_Payroll/Stores":"E","03_Payroll/HO_Commissary":"E",
        "04_OpEx/Stores":"E","04_OpEx/HO_Commissary":"E","04_OpEx/Rentals":"E",
        "04_OpEx/Utilities":"E","04_OpEx/Revolving_Fund":"E","04_OpEx/SCM_Freight":"E",
        "04_OpEx/Petty_Cash":"E",
        "05_Other/Stores":"E","05_Other/HO_Commissary":"E",
        "Monthly_Review":"V",
        "Assets/Cash":"E","Liabilities/AP":"E","Liabilities/Loans":"E","Partners":"E",
        "Payment_Trackers":"E","Reference_Documents":"E","Ongoing_Operations":"E","Policies":"V",
    },
    "ivy@bebang.ph": {
        "01_Revenue/Stores":"E","01_Revenue/HO_Commissary":"E",
        "02_COGS/Stores":"E","02_COGS/HO_Commissary":"E",
        "04_OpEx/Stores":"E","04_OpEx/HO_Commissary":"E","04_OpEx/Rentals":"E",
        "04_OpEx/Utilities":"E","04_OpEx/Revolving_Fund":"E","04_OpEx/SCM_Freight":"E",
        "04_OpEx/Petty_Cash":"E",
        "05_Other/Stores":"E","05_Other/HO_Commissary":"E",
        "Monthly_Review":"V",
        "Assets/AR":"E","Reference_Documents":"E","Ongoing_Operations":"E","Policies":"V",
    },
    "accounting.shaw@bebang.ph": {"Reference_Documents":"E","Ongoing_Operations":"E"},
    "ronald@bebang.ph": {"03_Payroll/Stores":"V","03_Payroll/HO_Commissary":"V","Policies":"V"},
    "melissa@bebang.ph": {"03_Payroll/Stores":"V","03_Payroll/HO_Commissary":"V","Policies":"V"},
    "ian@bebang.ph": {"02_COGS/Stores":"V","04_OpEx/SCM_Freight":"E","Policies":"V"},
    "jeson@bebang.ph": {"02_COGS/Stores":"V","04_OpEx/SCM_Freight":"E","Policies":"V"},
    "admin@bebang.ph": {"Policies":"V"},
    "anthony@bebang.ph": {"01_Revenue/Stores":"E","02_COGS/Stores":"E","02_COGS/HO_Commissary":"E","Assets/AR":"E"},
    "liezel@bebang.ph": {
        "01_Revenue/Stores":"E",
        "04_OpEx/Stores":"E","04_OpEx/HO_Commissary":"E","04_OpEx/Rentals":"E",
        "04_OpEx/Utilities":"E","04_OpEx/Revolving_Fund":"E","04_OpEx/Petty_Cash":"E",
        "05_Other/Stores":"E",
        "Assets/Other_Current":"E","Assets/Fixed_Assets":"E",
        "Liabilities/AP":"E","Liabilities/Loans":"E",
        "Reference_Documents":"E","Ongoing_Operations":"E",
    },
    "angelamel@bebang.ph": {
        "04_OpEx/Stores":"E","04_OpEx/HO_Commissary":"E","04_OpEx/Rentals":"E",
        "04_OpEx/Utilities":"E","04_OpEx/Revolving_Fund":"E","04_OpEx/Petty_Cash":"E",
        "05_Other/Stores":"E","05_Other/HO_Commissary":"E",
        "Assets/Other_Current":"E","Assets/Fixed_Assets":"E",
        "Liabilities/AP":"E","Liabilities/Loans":"E",
    },
    "izza@bebang.ph": {
        "04_OpEx/Stores":"E","04_OpEx/HO_Commissary":"E","04_OpEx/Rentals":"E",
        "04_OpEx/Utilities":"E","04_OpEx/Revolving_Fund":"E","04_OpEx/Petty_Cash":"E",
        "05_Other/HO_Commissary":"E",
        "Assets/Other_Current":"E","Assets/Fixed_Assets":"E",
        "Liabilities/AP":"E","Liabilities/Loans":"E",
    },
    "je-ann@bebang.ph": {"Payment_Trackers":"E"},
}

CMS = {"sam@bebang.ph","alyssa@bebang.ph","butch@bebang.ph","juanna@bebang.ph"}
ROLE_MAP = {"writer":"E","reader":"V","fileOrganizer":"CM","organizer":"MGR"}
ABBREVS = {
    "accounting.bei@bebang.ph":"Angela","denise@bebang.ph":"Denise",
    "ivy@bebang.ph":"Ivy","accounting.shaw@bebang.ph":"Shaw",
    "ronald@bebang.ph":"Ronald","melissa@bebang.ph":"Melissa",
    "ian@bebang.ph":"Ian","jeson@bebang.ph":"Jeson",
    "admin@bebang.ph":"Noel","anthony@bebang.ph":"Anthony",
    "liezel@bebang.ph":"Liezel","angelamel@bebang.ph":"Anglml",
    "izza@bebang.ph":"Izza","je-ann@bebang.ph":"Je-Ann",
}

people = sorted(EXPECTED.keys(), key=lambda x: x.split("@")[0])

# Print header
hdr = f"{'FOLDER':<28s}"
for p in people:
    hdr += f"{ABBREVS[p]:>8s}"
print(hdr)
print("-" * len(hdr))

issues = []

for folder_name, folder_id in FOLDERS.items():
    time.sleep(0.25)
    perms = drive.permissions().list(
        fileId=folder_id, supportsAllDrives=True,
        fields="permissions(emailAddress,role,type,permissionDetails)"
    ).execute()

    # Build actual map (non-CM, non-inherited only)
    actual = {}
    unexpected_users = []
    for p in perms.get("permissions", []):
        em = (p.get("emailAddress") or "").lower()
        if not em or em in CMS:
            continue
        details = p.get("permissionDetails", [])
        inherited = any(d.get("inherited", False) for d in details) if details else False
        if not inherited:
            actual[em] = ROLE_MAP.get(p["role"], p["role"])
            if em not in EXPECTED:
                unexpected_users.append(f"{em}={ROLE_MAP.get(p['role'], p['role'])}")

    row = f"{folder_name:<28s}"
    for person in people:
        exp = EXPECTED.get(person, {}).get(folder_name, "-")
        act = actual.get(person, "-")

        if exp == act:
            cell = act if act != "-" else "."
        elif exp == "-" and act != "-":
            cell = f"!{act}"
            issues.append(f"EXTRA: {ABBREVS[person]} has {act} on {folder_name}")
        elif exp != "-" and act == "-":
            cell = f"X{exp}"
            issues.append(f"MISSING: {ABBREVS[person]} needs {exp} on {folder_name}")
        else:
            cell = f"{act}!{exp}"
            issues.append(f"WRONG: {ABBREVS[person]} has {act} want {exp} on {folder_name}")

        row += f"{cell:>8s}"

    print(row)

    for u in unexpected_users:
        issues.append(f"UNAUTHORIZED: {u} on {folder_name}")

print()
if issues:
    print(f"=== {len(issues)} ISSUES ===")
    for i in issues:
        print(f"  {i}")
else:
    print("=== ALL 28 FOLDERS x 14 USERS: PERFECT MATCH - ZERO ISSUES ===")

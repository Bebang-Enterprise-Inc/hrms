"""Shared helpers for the BEI DTR auto-generator.

Pure data/parse helpers used by generate_dtr.py and validate_dtr.py.
PHT = UTC+8. Bio IDs are 7-digit ints in the 9xxxxxx range.
"""
import csv
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PHT = timezone(timedelta(hours=8))

# 2026 PH regular holidays that fall in the cut-offs this tool targets.
PH_REGULAR_HOLIDAYS_2026 = {
    "2026-05-01": "Labor Day",
    "2026-06-12": "Independence Day",
}

# File-number prefix -> ADMS store_name (used ONLY for the
# "PUNCHED BUT NOT IN TEMPLATE" extras section; Worked is PIN-global).
FILE_NUM_TO_ADMS_STORE = {
    "03": "MARKET MARKET", "05": "SHAW COMMISSARY", "07": "SM MANILA",
    "08": "SM MEGAMALL", "09": "SM SOUTHMALL", "10": "AYALA FAIRVIEW",
    "11": "SM NORTH EDSA", "12": "SM VALENZUELA", "13": "LCT",
    "14": "ROBINSON ANTIPOLO", "16": "SM GRAND CENTRAL", "17": "THE TERMINAL",
    "18": "SM MARIKINA", "19": "SM EAST ORTIGAS", "20": "PASEO", "21": "PITX",
    "23": "VENICE GRAND CANAL", "24": "FESTIVAL MALL", "25": "SM MOA",
    "26": "BF HOMES", "27": "AYALA UP TOWN CENTER", "28": "SM SJDM",
    "29": "ROBINSONS IMUS", "30": "AYALA VERMOSA", "31": "SM TANZA",
    "32": "ROBINSON GENERAL TRIAS", "33": "AYALA EVO", "34": "SM BICUTAN",
    "35": "SM CALOOCAN", "36": "SM PULILAN", "37": "SM SANGANDAAN",
    "38": "SM MARILAO", "39": "ROBINSONS GALLERIA SOUTH", "40": "AYALA SOLENAD",
    "41": "SM CLARK", "42": "STA LUCIA GRAND MALL", "43": "SM TAYTAY",
    "44": "UPTOWN BGC", "45": "ARANETA GATEWAY", "46": "CTTM TOMAS MORATO",
    "47": "D VERDE CALAMBA", "48": "SM STA. ROSA", "49": "ROBINSONS DASMA",
    "50": "NAIA T3", "51": "GREENHILLS", "52": "ORTIGAS ESTANCIA",
    "54": "ALABANG TOWN CENTER", "55": "XENTROMALL MONTALBAN",
    "56": "SM SAN PABLO", "57": "3MD COMMISSARY",
}

# Roving/office files: their template employees may punch at ANY store.
# (For the extras section we therefore never flag their punchers as "not in template"
#  based on a single store; PIN-global match already covers them.)
ROVING_FILE_NUMS = {"02", "15", "22", "53"}

# Night-shift grouping: a punch before this PHT hour may belong to the
# previous day's shift if the gap is under MAX_OVERNIGHT_GAP.
EARLY_MORNING_HOUR = 6
MAX_OVERNIGHT_GAP = timedelta(hours=10)


def norm(s):
    """Lowercase, strip non-alphanumerics. Non-strings -> ''."""
    return re.sub(r"[^a-z0-9]", "", s.lower()) if isinstance(s, str) else ""


def coerce_bio(v):
    """Return an int Bio ID in 9000000..9999999 or None.

    Handles int, float, and string cells (some templates store Bio IDs as
    strings, occasionally with a stray apostrophe, e.g. "9000920'").
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        iv = int(v)
        return iv if 9000000 <= iv <= 9999999 else None
    if isinstance(v, str):
        digits = re.sub(r"\D", "", v)
        if len(digits) == 7 and digits[0] == "9":
            iv = int(digits)
            return iv if 9000000 <= iv <= 9999999 else None
    return None


def file_num(filename):
    """Leading 2-digit file-number prefix, e.g. '28_SJDM...' -> '28'."""
    m = re.match(r"\s*(\d{2})", filename)
    return m.group(1) if m else None


def load_punches(csv_path):
    """Read punch CSV -> {pin: [ (datetime_pht, store_name), ... ]} sorted by time.

    Also returns a flat list of (pin, dt_pht, store_name) for the extras section.
    """
    by_pin = defaultdict(list)
    flat = []
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pin = (row.get("pin") or "").strip()
            et = (row.get("event_time") or "").strip()
            if not pin or not et:
                continue
            dt = datetime.fromisoformat(et).astimezone(PHT)
            store = (row.get("store_name") or "").strip()
            by_pin[pin].append((dt, store))
            flat.append((pin, dt, store))
    for pin in by_pin:
        by_pin[pin].sort(key=lambda t: t[0])
    return by_pin, flat


def group_shift_days(punches):
    """Group one employee's sorted [(dt, store)] into shift-days.

    Base grouping is by PHT calendar date. The night-shift exception: a punch
    before EARLY_MORNING_HOUR PHT is reassigned to the PREVIOUS shift-day when
    that day has punches and the gap from its last punch is < MAX_OVERNIGHT_GAP
    (BEI night shifts cross midnight). A shift-day is labelled by the calendar
    date its punches end up grouped under.

    Returns list of dicts: {date(YYYY-MM-DD), punches:[(dt,store)], first, last}.
    """
    # ordered list of (label_date_str, [(dt, store), ...]); built in time order
    days = []
    for dt, store in punches:
        cal_label = dt.date().isoformat()
        attached = False
        if dt.hour < EARLY_MORNING_HOUR and days:
            prev_label, prev_punches = days[-1]
            last_dt = prev_punches[-1][0]
            # only attach to the immediately preceding shift-day, small gap
            if dt - last_dt < MAX_OVERNIGHT_GAP:
                prev_punches.append((dt, store))
                attached = True
        if not attached:
            if days and days[-1][0] == cal_label:
                days[-1][1].append((dt, store))  # same calendar date -> same day
            else:
                days.append((cal_label, [(dt, store)]))
    out = []
    for label, ps in days:
        out.append({
            "date": label,
            "punches": ps,
            "first": ps[0][0],
            "last": ps[-1][0],
        })
    return out


def in_window(dt, from_date, to_date):
    """True if dt's PHT calendar date is within [from_date, to_date] inclusive."""
    return from_date <= dt.date() <= to_date


def parse_date(s):
    """'YYYY-MM-DD' -> date."""
    return datetime.strptime(s, "%Y-%m-%d").date()

#!/usr/bin/env python3
"""Apply Google Sheets dashboard expert patch to the Delivery Sales workbook.

This script:
1) Refines KPI/selector section.
2) Fixes hidden-row conflicts that crop charts.
3) Rebuilds dashboard charts with bounded, non-overlapping source ranges.
4) Applies lightweight formatting and validations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build


SPREADSHEET_ID = "1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78"
SERVICE_ACCOUNT_FILE = "credentials/task-manager-service.json"
IMPERSONATE_USER = "sam@bebang.ph"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DASHBOARD_TAB = "DASHBOARD"


@dataclass(frozen=True)
class RGB:
    r: float
    g: float
    b: float

    def as_dict(self) -> dict[str, float]:
        return {"red": self.r, "green": self.g, "blue": self.b}


NAVY = RGB(0.04, 0.10, 0.22)
NAVY_2 = RGB(0.12, 0.19, 0.33)
SOFT_BLUE = RGB(0.90, 0.94, 0.98)
SOFT_ORANGE = RGB(0.99, 0.93, 0.86)
SOFT_GRAY = RGB(0.93, 0.95, 0.97)
SOFT_GREEN = RGB(0.88, 0.95, 0.89)
SOFT_NOTE = RGB(0.95, 0.96, 0.98)
WHITE = RGB(1.0, 1.0, 1.0)

SERIES_BLUE = RGB(0.15, 0.39, 0.92)
SERIES_ORANGE = RGB(0.92, 0.39, 0.06)
SERIES_GREEN = RGB(0.09, 0.64, 0.37)
SERIES_RED = RGB(0.86, 0.15, 0.15)


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    ).with_subject(IMPERSONATE_USER)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def find_dashboard_info(service) -> tuple[int, int, list[int]]:
    meta = (
        service.spreadsheets()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)),charts(chartId))",
        )
        .execute()
    )

    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") != DASHBOARD_TAB:
            continue
        sheet_id = props["sheetId"]
        row_count = props.get("gridProperties", {}).get("rowCount", 5000)
        chart_ids = [c.get("chartId") for c in sheet.get("charts", []) if c.get("chartId")]
        return sheet_id, row_count, chart_ids
    raise RuntimeError(f"Dashboard tab not found: {DASHBOARD_TAB}")


def get_default_window_dates(service) -> tuple[str, str]:
    values = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range="SALES_FACT_DAILY_FINAL!A2:A",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
        .get("values", [])
    )

    max_serial = None
    for row in values:
        if not row:
            continue
        val = row[0]
        if isinstance(val, (int, float)):
            if max_serial is None or float(val) > max_serial:
                max_serial = float(val)

    if max_serial is None:
        today = datetime.now(timezone.utc).date()
        start = today
        end = today
    else:
        epoch = datetime(1899, 12, 30).date()
        end = epoch.fromordinal(epoch.toordinal() + int(max_serial))
        start = end.fromordinal(end.toordinal() - 29)

    return start.isoformat(), end.isoformat()


def write_dashboard_values(service):
    start_date, end_date = get_default_window_dates(service)
    data = [
        {"range": "DASHBOARD!A1", "values": [["Delivery Sales Dashboard"]]},
        {
            "range": "DASHBOARD!A2",
            "values": [
                [
                    '=IFERROR("Last refresh: "&TEXT(DATA_QUALITY!D2,"yyyy-mm-dd hh:mm:ss"),"Last refresh: n/a")&" | Source: SALES_FACT_DAILY_FINAL | FoodPanda disputes included when status=Approved"'
                ]
            ],
        },
        {"range": "DASHBOARD!A3", "values": [["FoodPanda Daily"]]},
        {
            "range": "DASHBOARD!B3",
            "values": [
                [
                    '=IFERROR(SUM(FILTER(SALES_FACT_DAILY_FINAL!F:F,SALES_FACT_DAILY_FINAL!A:A=$D$4,SALES_FACT_DAILY_FINAL!B:B="FoodPanda",IF($F$4="All Stores",SALES_FACT_DAILY_FINAL!E:E<>"",SALES_FACT_DAILY_FINAL!E:E=$F$4))),0)'
                ]
            ],
        },
        {"range": "DASHBOARD!D3", "values": [["Website Daily"]]},
        {
            "range": "DASHBOARD!E3",
            "values": [
                [
                    '=IFERROR(SUM(FILTER(SALES_FACT_DAILY_FINAL!F:F,SALES_FACT_DAILY_FINAL!A:A=$D$4,SALES_FACT_DAILY_FINAL!B:B="Website",IF($F$4="All Stores",SALES_FACT_DAILY_FINAL!E:E<>"",SALES_FACT_DAILY_FINAL!E:E=$F$4))),0)'
                ]
            ],
        },
        {"range": "DASHBOARD!G3", "values": [["Total Daily Sales"]]},
        {"range": "DASHBOARD!H3", "values": [["=IFERROR(B3+E3,0)"]]},
        {"range": "DASHBOARD!J3", "values": [["vs Last Week"]]},
        {
            "range": "DASHBOARD!K3",
            "values": [
                [
                    '=IFERROR(H3/SUM(FILTER(SALES_FACT_DAILY_FINAL!F:F,SALES_FACT_DAILY_FINAL!A:A=$D$4-7,IF($F$4="All Stores",SALES_FACT_DAILY_FINAL!E:E<>"",SALES_FACT_DAILY_FINAL!E:E=$F$4))),"")'
                ]
            ],
        },
        {"range": "DASHBOARD!A4", "values": [["Start Date"]]},
        {"range": "DASHBOARD!B4", "values": [[start_date]]},
        {"range": "DASHBOARD!C4", "values": [["End Date"]]},
        {"range": "DASHBOARD!D4", "values": [[end_date]]},
        {"range": "DASHBOARD!E4", "values": [["Store Filter"]]},
        {"range": "DASHBOARD!F4", "values": [["All Stores"]]},
        {"range": "DASHBOARD!G4", "values": [["Top Stores"]]},
        {"range": "DASHBOARD!H4", "values": [[15]]},
        {"range": "DASHBOARD!I4", "values": [["Compare 1"]]},
        {"range": "DASHBOARD!J4", "values": [["Ayala Evo"]]},
        {"range": "DASHBOARD!K4", "values": [["Compare 2"]]},
        {"range": "DASHBOARD!L4", "values": [["SM Megamall"]]},
        {
            "range": "DASHBOARD!A5",
            "values": [['="Window: "&TEXT(B4,"yyyy-mm-dd")&" to "&TEXT(D4,"yyyy-mm-dd")']],
        },
        {
            "range": "DASHBOARD!C5",
            "values": [['=IF(D4>=TODAY()-2,"Latest 2 days may still change due to dispute lead time","Window stable")']],
        },
        {
            "range": "DASHBOARD!G5",
            "values": [['="Comparable date: "&TEXT(D4-7,"yyyy-mm-dd")&" | "&IF(D4<=TODAY()-3,"Finalized window","Includes provisional days")']],
        },
        {"range": "DASHBOARD!I5", "values": [["Compare 3"]]},
        {"range": "DASHBOARD!J5", "values": [["BF Homes"]]},
        {"range": "DASHBOARD!K5", "values": [["Compare 4"]]},
        {"range": "DASHBOARD!L5", "values": [["CTTM"]]},
        {"range": "DASHBOARD!A6", "values": [["How to use filters:"]]},
        {"range": "DASHBOARD!B6", "values": [["1) Pick date range in B4 and D4"]]},
        {"range": "DASHBOARD!F6", "values": [["2) Pick main store in F4 (or All Stores)"]]},
        {"range": "DASHBOARD!J6", "values": [["3) Optional compares: J4, L4, J5, L5"]]},
        {"range": "DASHBOARD!A7", "values": [["1) Daily Progression for Selected Store (FoodPanda vs Website)"]]},
        {"range": "DASHBOARD!A25", "values": [["2) Store Leaders by Channel (Selected Date Range)"]]},
        {"range": "DASHBOARD!A53", "values": [["3) Multi-Store Daily Comparison (Absolute Sales)"]]},
        {"range": "DASHBOARD!A71", "values": [["4) Multi-Store Indexed Trend (Cannibalization View, Day 1 = 100)"]]},
        {"range": "DASHBOARD!A27", "values": [[""]]},
        {"range": "DASHBOARD!A52", "values": [[""]]},
        {"range": "DASHBOARD!A69", "values": [[""]]},
        {
            "range": "DASHBOARD!A260",
            "values": [['=IF($F$4<>"All Stores",$F$4,IF($J$4<>"",$J$4,IFERROR($A$201,"")))']],
        },
        {
            "range": "DASHBOARD!A261",
            "values": [['=IF($F$4<>"All Stores",IF($J$4<>"",$J$4,IFERROR($A$201,"")),IF($L$4<>"",$L$4,IFERROR($A$202,"")))']],
        },
        {
            "range": "DASHBOARD!A262",
            "values": [['=IF($F$4<>"All Stores",IF($L$4<>"",$L$4,IFERROR($A$202,"")),IF($J$5<>"",$J$5,IFERROR($A$203,"")))']],
        },
        {
            "range": "DASHBOARD!A263",
            "values": [['=IF($F$4<>"All Stores",IF($J$5<>"",$J$5,IFERROR($A$203,"")),IF($L$5<>"",$L$5,IFERROR($A$204,"")))']],
        },
    ]
    (
        service.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        )
        .execute()
    )


def source(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict[str, Any]:
    return {
        "sheetId": sheet_id,
        "startRowIndex": r0,
        "endRowIndex": r1,
        "startColumnIndex": c0,
        "endColumnIndex": c1,
    }


def line_chart(
    title: str,
    domain_source: dict[str, Any],
    series_sources: list[dict[str, Any]],
    colors: list[RGB],
    y_axis_title: str = "Sales (PHP)",
) -> dict[str, Any]:
    series = []
    for rng, color in zip(series_sources, colors, strict=False):
        series.append(
            {
                "series": {"sourceRange": {"sources": [rng]}},
                "targetAxis": "LEFT_AXIS",
                "color": color.as_dict(),
            }
        )
    return {
        "title": title,
        "hiddenDimensionStrategy": "SKIP_HIDDEN_ROWS_AND_COLUMNS",
        "basicChart": {
            "chartType": "LINE",
            "legendPosition": "BOTTOM_LEGEND",
            "lineSmoothing": True,
            "headerCount": 1,
            "axis": [
                {"position": "BOTTOM_AXIS", "title": "Date"},
                {"position": "LEFT_AXIS", "title": y_axis_title},
            ],
            "domains": [{"domain": {"sourceRange": {"sources": [domain_source]}}}],
            "series": series,
        },
    }


def bar_chart(
    title: str,
    domain_source: dict[str, Any],
    series_sources: list[dict[str, Any]],
    colors: list[RGB],
) -> dict[str, Any]:
    series = []
    for rng, color in zip(series_sources, colors, strict=False):
        series.append(
            {
                "series": {"sourceRange": {"sources": [rng]}},
                "targetAxis": "BOTTOM_AXIS",
                "color": color.as_dict(),
            }
        )
    return {
        "title": title,
        "hiddenDimensionStrategy": "SKIP_HIDDEN_ROWS_AND_COLUMNS",
        "basicChart": {
            "chartType": "BAR",
            "legendPosition": "BOTTOM_LEGEND",
            "headerCount": 1,
            "axis": [
                {"position": "LEFT_AXIS", "title": "Store"},
                {"position": "BOTTOM_AXIS", "title": "Sales (PHP)"},
            ],
            "domains": [{"domain": {"sourceRange": {"sources": [domain_source]}}}],
            "series": series,
        },
    }


def build_batch_requests(sheet_id: int, row_count: int, chart_ids: list[int]) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []

    # Unhide all rows to avoid chart-series loss when using SKIP_HIDDEN_ROWS_AND_COLUMNS.
    reqs.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": row_count,
                },
                "properties": {"hiddenByUser": False},
                "fields": "hiddenByUser",
            }
        }
    )

    # Column widths A:L
    reqs.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 12,
                },
                "properties": {"pixelSize": 122},
                "fields": "pixelSize",
            }
        }
    )

    # Key row heights
    for row_idx, px in [(0, 42), (1, 24), (2, 30), (3, 30), (4, 24), (6, 22), (24, 22), (52, 22), (70, 22)]:
        reqs.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row_idx,
                        "endIndex": row_idx + 1,
                    },
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )

    # Base wipe top section formatting
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 0, 8, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": WHITE.as_dict(),
                        "textFormat": {"fontSize": 10, "foregroundColor": {"red": 0.13, "green": 0.16, "blue": 0.2}},
                        "horizontalAlignment": "LEFT",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        }
    )

    # Header rows
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 0, 1, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": NAVY.as_dict(),
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"bold": True, "fontSize": 18, "foregroundColor": WHITE.as_dict()},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
            }
        }
    )
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 1, 2, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": NAVY_2.as_dict(),
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"fontSize": 10, "foregroundColor": WHITE.as_dict()},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
            }
        }
    )

    # KPI cells styling
    for rng, bg in [
        (source(sheet_id, 2, 3, 0, 3), SOFT_BLUE),
        (source(sheet_id, 2, 3, 3, 6), SOFT_ORANGE),
        (source(sheet_id, 2, 3, 6, 9), SOFT_GRAY),
        (source(sheet_id, 2, 3, 9, 12), SOFT_GREEN),
    ]:
        reqs.append(
            {
                "repeatCell": {
                    "range": rng,
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": bg.as_dict(),
                            "horizontalAlignment": "CENTER",
                            "textFormat": {"bold": True, "fontSize": 11},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
                }
            }
        )

    # Controls/status rows
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 3, 6, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": SOFT_NOTE.as_dict(),
                        "textFormat": {"fontSize": 10, "bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        }
    )
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 5, 6, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": WHITE.as_dict(),
                        "horizontalAlignment": "LEFT",
                        "textFormat": {"fontSize": 9, "bold": False},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
            }
        }
    )
    for rng in (
        source(sheet_id, 3, 4, 1, 2),   # B4
        source(sheet_id, 3, 4, 3, 4),   # D4
        source(sheet_id, 3, 4, 5, 6),   # F4
        source(sheet_id, 3, 4, 7, 8),   # H4
        source(sheet_id, 3, 4, 9, 10),  # J4
        source(sheet_id, 3, 4, 11, 12), # L4
        source(sheet_id, 4, 5, 9, 10),  # J5
        source(sheet_id, 4, 5, 11, 12), # L5
    ):
        reqs.append(
            {
                "repeatCell": {
                    "range": rng,
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": WHITE.as_dict(),
                            "textFormat": {"bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            }
        )

    # Section headers
    reqs.append(
        {
            "repeatCell": {
                "range": source(sheet_id, 6, 7, 0, 12),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": SOFT_BLUE.as_dict(),
                        "textFormat": {"bold": True, "fontSize": 10},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }
    )
    for start in (24, 52, 70):
        reqs.append(
            {
                "repeatCell": {
                    "range": source(sheet_id, start, start + 1, 0, 12),
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": SOFT_BLUE.as_dict(),
                            "textFormat": {"bold": True, "fontSize": 10},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            }
        )

    # Number/date formats
    reqs.extend(
        [
            {
                "repeatCell": {
                    "range": source(sheet_id, 2, 3, 1, 2),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "₱#,##0.00"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 2, 3, 4, 5),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "₱#,##0.00"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 2, 3, 7, 8),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "₱#,##0.00"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 2, 3, 10, 11),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "PERCENT", "pattern": "0.0%"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 3, 4, 1, 2),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 3, 4, 3, 4),
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 3, 4, 7, 8),
                    "cell": {
                        "userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0"}}
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
            {
                "repeatCell": {
                    "range": source(sheet_id, 320, 5000, 1, 5),  # B321:E indexed helper values
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "NUMBER", "pattern": "0.0"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            },
        ]
    )

    # Validations
    store_rule = {
        "condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": "=DASHBOARD!$A$200:$A"}]},
        "strict": True,
        "showCustomUi": True,
    }
    reqs.extend(
        [
            {
                "setDataValidation": {
                    "range": source(sheet_id, 3, 4, 1, 2),  # B4
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_RANGE",
                            "values": [{"userEnteredValue": "=SALES_FACT_DAILY_FINAL!$A$2:$A"}],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {
                    "range": source(sheet_id, 3, 4, 3, 4),  # D4
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_RANGE",
                            "values": [{"userEnteredValue": "=SALES_FACT_DAILY_FINAL!$A$2:$A"}],
                        },
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            },
            {
                "setDataValidation": {"range": source(sheet_id, 3, 4, 5, 6), "rule": store_rule},  # F4
            },
            {
                "setDataValidation": {
                    "range": source(sheet_id, 3, 4, 7, 8),  # H4
                    "rule": {
                        "condition": {
                            "type": "NUMBER_BETWEEN",
                            "values": [{"userEnteredValue": "1"}, {"userEnteredValue": "50"}],
                        },
                        "strict": True,
                    },
                }
            },
            {
                "setDataValidation": {"range": source(sheet_id, 3, 4, 9, 10), "rule": store_rule},  # J4
            },
            {
                "setDataValidation": {"range": source(sheet_id, 3, 4, 11, 12), "rule": store_rule},  # L4
            },
            {
                "setDataValidation": {"range": source(sheet_id, 4, 5, 9, 10), "rule": store_rule},  # J5
            },
            {
                "setDataValidation": {"range": source(sheet_id, 4, 5, 11, 12), "rule": store_rule},  # L5
            },
            {
                "setDataValidation": {"range": source(sheet_id, 5, 6, 9, 12), "rule": None},  # J6:L6 clear stray DV
            },
        ]
    )

    # Remove prior charts.
    for cid in chart_ids:
        reqs.append({"deleteEmbeddedObject": {"objectId": cid}})

    # Rebuild charts with bounded ranges that do not overlap helper blocks.
    chart_1 = line_chart(
        title="Daily Sales Progression: FoodPanda vs Website",
        domain_source=source(sheet_id, 199, 240, 2, 3),  # C200:C240
        series_sources=[
            source(sheet_id, 199, 240, 3, 4),  # D
            source(sheet_id, 199, 240, 4, 5),  # E
        ],
        colors=[SERIES_BLUE, SERIES_ORANGE],
    )

    chart_2 = bar_chart(
        title="Store Leaders: FoodPanda vs Website (Top N)",
        domain_source=source(sheet_id, 199, 260, 6, 7),  # G200:G260
        series_sources=[
            source(sheet_id, 199, 260, 7, 8),  # H
            source(sheet_id, 199, 260, 8, 9),  # I
        ],
        colors=[SERIES_BLUE, SERIES_ORANGE],
    )

    chart_3 = line_chart(
        title="Multi-Store Daily Comparison (Absolute)",
        domain_source=source(sheet_id, 259, 320, 6, 7),  # G260:G320
        series_sources=[
            source(sheet_id, 259, 320, 7, 8),  # H
            source(sheet_id, 259, 320, 8, 9),  # I
            source(sheet_id, 259, 320, 9, 10),  # J
            source(sheet_id, 259, 320, 10, 11),  # K
        ],
        colors=[SERIES_BLUE, SERIES_GREEN, SERIES_ORANGE, SERIES_RED],
    )

    chart_4 = line_chart(
        title="Multi-Store Indexed Trend (Cannibalization View, Day 1 = 100)",
        domain_source=source(sheet_id, 319, 380, 0, 1),  # A320:A380
        series_sources=[
            source(sheet_id, 319, 380, 1, 2),  # B
            source(sheet_id, 319, 380, 2, 3),  # C
            source(sheet_id, 319, 380, 3, 4),  # D
            source(sheet_id, 319, 380, 4, 5),  # E
        ],
        colors=[SERIES_BLUE, SERIES_GREEN, SERIES_ORANGE, SERIES_RED],
        y_axis_title="Index (Day 1 = 100)",
    )

    reqs.extend(
        [
            {
                "addChart": {
                    "chart": {
                        "spec": chart_1,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": sheet_id, "rowIndex": 8, "columnIndex": 0},
                                "widthPixels": 1460,
                                "heightPixels": 305,
                            }
                        },
                    }
                }
            },
            {
                "addChart": {
                    "chart": {
                        "spec": chart_2,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": sheet_id, "rowIndex": 26, "columnIndex": 0},
                                "widthPixels": 1460,
                                "heightPixels": 620,
                            }
                        },
                    }
                }
            },
            {
                "addChart": {
                    "chart": {
                        "spec": chart_3,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": sheet_id, "rowIndex": 54, "columnIndex": 0},
                                "widthPixels": 1460,
                                "heightPixels": 305,
                            }
                        },
                    }
                }
            },
            {
                "addChart": {
                    "chart": {
                        "spec": chart_4,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": sheet_id, "rowIndex": 72, "columnIndex": 0},
                                "widthPixels": 1460,
                                "heightPixels": 305,
                            }
                        },
                    }
                }
            },
        ]
    )

    return reqs


def verify(service):
    # KPI + controls quick check
    value_check = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range="DASHBOARD!A1:L7",
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )

    # Chart summary + hidden rows around display area
    audit = (
        service.spreadsheets()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            ranges=["DASHBOARD!1:120"],
            includeGridData=True,
            fields=(
                "sheets(properties(sheetId,title),"
                "charts(chartId,position,spec),"
                "data(rowMetadata(hiddenByUser)))"
            ),
        )
        .execute()
    )

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kpi_rows": value_check.get("values", [])[:7],
        "charts": [],
        "hidden_rows_1_120": [],
    }

    sh = audit["sheets"][0]
    for idx, rm in enumerate(sh.get("data", [])[0].get("rowMetadata", []), start=1):
        if rm.get("hiddenByUser"):
            report["hidden_rows_1_120"].append(idx)

    for ch in sh.get("charts", []):
        spec = ch.get("spec", {})
        basic = spec.get("basicChart", {})
        pos = ch.get("position", {}).get("overlayPosition", {})
        anc = pos.get("anchorCell", {})
        report["charts"].append(
            {
                "chartId": ch.get("chartId"),
                "title": spec.get("title"),
                "anchorRow": (anc.get("rowIndex", 0) or 0) + 1,
                "series_count": len(basic.get("series", [])),
                "domain_count": len(basic.get("domains", [])),
                "hiddenDimensionStrategy": spec.get("hiddenDimensionStrategy"),
                "width": pos.get("widthPixels"),
                "height": pos.get("heightPixels"),
            }
        )

    return report


def main():
    service = get_service()
    sheet_id, row_count, chart_ids = find_dashboard_info(service)

    write_dashboard_values(service)
    requests = build_batch_requests(sheet_id=sheet_id, row_count=row_count, chart_ids=chart_ids)

    (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests})
        .execute()
    )

    report = verify(service)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

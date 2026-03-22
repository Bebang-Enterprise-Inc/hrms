"""
Blip Tool Definitions

Defines all tools available to the agentic Blip assistant.
These tools follow the Anthropic Tool Use API schema.
"""

from typing import List, Dict, Any

# Tool definitions following Anthropic's tool use schema
BLIP_TOOLS: List[Dict[str, Any]] = [
    # === SALES & REVENUE ===
    {
        "name": "get_sales_data",
        "description": "Get sales data for a specific store, area, or company-wide. Use this when the user asks about revenue, sales performance, gross sales, net sales, or store metrics. Can compare periods or show trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name (e.g., 'Megamall', 'Market Market', 'Trinoma'). Omit for area-wide or company-wide data."
                },
                "area": {
                    "type": "string",
                    "description": "Area name (e.g., 'BGC', 'Makati', 'Ortigas', 'North'). Omit for store-specific or company-wide data."
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "last_week", "this_month", "last_month"],
                    "description": "Time period for sales data"
                },
                "compare_to": {
                    "type": "string",
                    "enum": ["previous_period", "same_period_last_year"],
                    "description": "Optional comparison period for trend analysis"
                }
            },
            "required": ["period"]
        }
    },
    {
        "name": "get_food_cost",
        "description": "Get food cost percentage and breakdown for a store. Use when user asks about food cost, COGS, cost of goods, or margin analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name. Required for food cost analysis."
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "last_week", "this_month"],
                    "description": "Time period"
                }
            },
            "required": ["store", "period"]
        }
    },

    # === INVENTORY ===
    {
        "name": "get_inventory",
        "description": "Check inventory levels at a store. Use when user asks about stock, items, product availability, or 'do we have X'. Can check specific items or overall stock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name to check inventory for"
                },
                "item": {
                    "type": "string",
                    "description": "Specific item to check (e.g., 'Ice', 'Leche Flan', 'Cups'). Omit for full inventory."
                },
                "category": {
                    "type": "string",
                    "description": "Item category filter (e.g., 'Toppings', 'Packaging', 'Raw Materials')"
                },
                "low_stock_only": {
                    "type": "boolean",
                    "description": "If true, only return items below reorder level"
                }
            },
            "required": ["store"]
        }
    },

    # === COMMISSARY / PRODUCTION ===
    {
        "name": "get_commissary_production",
        "description": "Get commissary (Bebang Kitchen) production data. Use when user asks about leche flan production, frozen milk output, ube halaya, or any commissary product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name (e.g., 'Leche Flan', 'Frozen Milk', 'Ube Halaya')"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "this_month"],
                    "description": "Alternative to specific date"
                }
            }
        }
    },

    # === HR / LEAVE ===
    {
        "name": "get_leave_balance",
        "description": "Get an employee's remaining leave balance by type. Use when user asks about their leave credits, vacation days, sick leave remaining, or someone else's leave balance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee": {
                    "type": "string",
                    "description": "Employee name or email. Omit to check the asking user's balance."
                },
                "leave_type": {
                    "type": "string",
                    "enum": ["Vacation", "Sick", "Emergency", "All"],
                    "description": "Type of leave to check. Default is 'All'."
                }
            }
        }
    },
    {
        "name": "get_leave_applications",
        "description": "Get leave application status for an employee. Use when user asks about pending leave requests, approved leaves, or leave application history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee": {
                    "type": "string",
                    "description": "Employee name or email. Omit for asking user."
                },
                "status": {
                    "type": "string",
                    "enum": ["Pending", "Approved", "Rejected", "All"],
                    "description": "Filter by status"
                }
            }
        }
    },
    {
        "name": "get_employees_on_leave",
        "description": "Get list of employees on leave for a specific date. Use when user asks 'who is on leave', 'who's out tomorrow', or about team availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format, or relative like 'today', 'tomorrow'"
                },
                "store": {
                    "type": "string",
                    "description": "Filter by store (optional)"
                },
                "area": {
                    "type": "string",
                    "description": "Filter by area (optional)"
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "submit_leave_request",
        "description": "Submit a leave request on behalf of the user. IMPORTANT: Only use this after explicitly confirming the details with the user. Ask for confirmation before calling this tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "leave_type": {
                    "type": "string",
                    "enum": ["Vacation", "Sick", "Emergency"],
                    "description": "Type of leave"
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for leave (optional but recommended)"
                }
            },
            "required": ["leave_type", "from_date", "to_date"]
        }
    },

    # === ATTENDANCE ===
    {
        "name": "get_attendance",
        "description": "Get attendance records for an employee. Use when user asks about their check-in/out times, attendance history, or working hours.",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee": {
                    "type": "string",
                    "description": "Employee name or email. Omit for asking user."
                },
                "date": {
                    "type": "string",
                    "description": "Specific date in YYYY-MM-DD format"
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "last_week"],
                    "description": "Time period for attendance records"
                }
            }
        }
    },
    {
        "name": "get_team_attendance",
        "description": "Get attendance overview for a store or team. Use when user asks about team attendance, who's late, who's present, or store staffing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format or 'today'"
                }
            },
            "required": ["store", "date"]
        }
    },

    # === EMPLOYEE DIRECTORY ===
    {
        "name": "search_employees",
        "description": "Search for employees by name, position, or store. Use when user asks about team members, org structure, 'who works at X', or looking up colleagues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - can be name, position, or partial match"
                },
                "store": {
                    "type": "string",
                    "description": "Filter by store"
                },
                "department": {
                    "type": "string",
                    "description": "Filter by department"
                },
                "position": {
                    "type": "string",
                    "description": "Filter by position/designation"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_store_info",
        "description": "Get information about a store including address, contact, manager, and operating hours. Use when user asks about store details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name"
                }
            },
            "required": ["store"]
        }
    },

    # === WEATHER ===
    {
        "name": "get_weather_forecast",
        "description": "Get weather forecast for a location with sales impact prediction. Use when user asks about weather or planning events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location name (e.g., 'BGC', 'Makati', 'Metro Manila'). Default: Metro Manila"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of forecast days (1-7)",
                    "minimum": 1,
                    "maximum": 7
                }
            }
        }
    },

    # === MEMORY / PERSONALIZATION ===
    {
        "name": "remember_fact",
        "description": "Store a fact about the user for future reference. Use when user says 'remember that...', shares preferences, or provides important context they want you to recall later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["preference", "schedule", "team", "personal", "work", "other"],
                    "description": "Category of the fact"
                },
                "fact": {
                    "type": "string",
                    "description": "The fact to remember"
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "How important this fact is"
                }
            },
            "required": ["category", "fact"]
        }
    },
    {
        "name": "recall_facts",
        "description": "Recall stored facts about the user. Use this proactively to personalize responses when relevant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category of facts to recall. Omit to get all facts."
                }
            }
        }
    }
]


# Tool categories for documentation/UI
TOOL_CATEGORIES = {
    "sales": ["get_sales_data", "get_food_cost"],
    "inventory": ["get_inventory"],
    "commissary": ["get_commissary_production"],
    "hr": ["get_leave_balance", "get_leave_applications", "get_employees_on_leave", "submit_leave_request"],
    "attendance": ["get_attendance", "get_team_attendance"],
    "directory": ["search_employees", "get_store_info"],
    "weather": ["get_weather_forecast"],
    "memory": ["remember_fact", "recall_facts"]
}


# Tools that require explicit user confirmation before execution
CONFIRMATION_REQUIRED = [
    "submit_leave_request",
    # Add more action-based tools here as they're implemented
]


def get_tool_by_name(name: str) -> dict | None:
    """Get a tool definition by name."""
    for tool in BLIP_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tools_by_category(category: str) -> list:
    """Get all tools in a category."""
    tool_names = TOOL_CATEGORIES.get(category, [])
    return [get_tool_by_name(name) for name in tool_names if get_tool_by_name(name)]

"""
Blip Tool Executor

Executes tools called by the agentic loop and returns results.
Each tool maps to a Frappe API call or internal function.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any,
    memory_store: Any = None
) -> Dict[str, Any]:
    """
    Execute a tool and return results.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        user_context: User permissions and context
        frappe_client: Frappe API client instance
        memory_store: Optional memory storage for remember/recall tools

    Returns:
        Tool execution result as a dictionary
    """
    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

    try:
        # Resolve relative dates in input
        tool_input = _resolve_dates(tool_input)

        # Route to appropriate handler
        if tool_name == "get_sales_data":
            return await _get_sales_data(tool_input, user_context, frappe_client)

        elif tool_name == "get_food_cost":
            return await _get_food_cost(tool_input, user_context, frappe_client)

        elif tool_name == "get_inventory":
            return await _get_inventory(tool_input, user_context, frappe_client)

        elif tool_name == "get_commissary_production":
            return await _get_commissary_production(tool_input, user_context, frappe_client)

        elif tool_name == "get_leave_balance":
            return await _get_leave_balance(tool_input, user_context, frappe_client)

        elif tool_name == "get_leave_applications":
            return await _get_leave_applications(tool_input, user_context, frappe_client)

        elif tool_name == "get_employees_on_leave":
            return await _get_employees_on_leave(tool_input, user_context, frappe_client)

        elif tool_name == "submit_leave_request":
            return await _submit_leave_request(tool_input, user_context, frappe_client)

        elif tool_name == "get_attendance":
            return await _get_attendance(tool_input, user_context, frappe_client)

        elif tool_name == "get_team_attendance":
            return await _get_team_attendance(tool_input, user_context, frappe_client)

        elif tool_name == "search_employees":
            return await _search_employees(tool_input, user_context, frappe_client)

        elif tool_name == "get_store_info":
            return await _get_store_info(tool_input, user_context, frappe_client)

        elif tool_name == "get_weather_forecast":
            return await _get_weather_forecast(tool_input)

        elif tool_name == "remember_fact":
            return await _remember_fact(tool_input, user_context, memory_store)

        elif tool_name == "recall_facts":
            return await _recall_facts(tool_input, user_context, memory_store)

        else:
            logger.warning(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return {"error": str(e)}


def _resolve_dates(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve relative date references to actual dates."""
    today = datetime.now().date()

    # Handle 'date' field
    date_value = tool_input.get("date")
    if date_value:
        if date_value == "today":
            tool_input["date"] = today.isoformat()
        elif date_value == "yesterday":
            tool_input["date"] = (today - timedelta(days=1)).isoformat()
        elif date_value == "tomorrow":
            tool_input["date"] = (today + timedelta(days=1)).isoformat()

    # Handle 'period' to date range conversion
    period = tool_input.get("period")
    if period and "date" not in tool_input:
        if period == "today":
            tool_input["from_date"] = today.isoformat()
            tool_input["to_date"] = today.isoformat()
        elif period == "yesterday":
            yesterday = today - timedelta(days=1)
            tool_input["from_date"] = yesterday.isoformat()
            tool_input["to_date"] = yesterday.isoformat()
        elif period == "this_week":
            start_of_week = today - timedelta(days=today.weekday())
            tool_input["from_date"] = start_of_week.isoformat()
            tool_input["to_date"] = today.isoformat()
        elif period == "last_week":
            start_of_last_week = today - timedelta(days=today.weekday() + 7)
            end_of_last_week = start_of_last_week + timedelta(days=6)
            tool_input["from_date"] = start_of_last_week.isoformat()
            tool_input["to_date"] = end_of_last_week.isoformat()
        elif period == "this_month":
            tool_input["from_date"] = today.replace(day=1).isoformat()
            tool_input["to_date"] = today.isoformat()
        elif period == "last_month":
            first_of_this_month = today.replace(day=1)
            last_of_last_month = first_of_this_month - timedelta(days=1)
            first_of_last_month = last_of_last_month.replace(day=1)
            tool_input["from_date"] = first_of_last_month.isoformat()
            tool_input["to_date"] = last_of_last_month.isoformat()

    return tool_input


# === SALES TOOLS ===

async def _get_sales_data(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get sales data from Frappe."""
    return await frappe_client.get_sales_data(
        store=tool_input.get("store"),
        area=tool_input.get("area"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
        compare_to=tool_input.get("compare_to"),
        user_context=user_context
    )


async def _get_food_cost(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get food cost analysis from Frappe."""
    return await frappe_client.get_food_cost(
        store=tool_input.get("store"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
        user_context=user_context
    )


# === INVENTORY TOOLS ===

async def _get_inventory(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get inventory levels from Frappe."""
    return await frappe_client.get_inventory(
        store=tool_input.get("store"),
        item=tool_input.get("item"),
        category=tool_input.get("category"),
        low_stock_only=tool_input.get("low_stock_only", False),
        user_context=user_context
    )


# === COMMISSARY TOOLS ===

async def _get_commissary_production(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get commissary production data from Frappe."""
    return await frappe_client.get_commissary_production(
        product=tool_input.get("product"),
        date=tool_input.get("date"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
        user_context=user_context
    )


# === HR / LEAVE TOOLS ===

async def _get_leave_balance(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get leave balance from Frappe."""
    # Default to asking user if no employee specified
    employee = tool_input.get("employee") or user_context.get("employee")
    if not employee:
        return {"error": "Could not determine which employee to check. Please specify."}

    return await frappe_client.get_leave_balance(
        employee=employee,
        leave_type=tool_input.get("leave_type", "All"),
        user_context=user_context
    )


async def _get_leave_applications(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get leave applications from Frappe."""
    employee = tool_input.get("employee") or user_context.get("employee")
    return await frappe_client.get_leave_applications(
        employee=employee,
        status=tool_input.get("status"),
        user_context=user_context
    )


async def _get_employees_on_leave(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get employees on leave for a date."""
    return await frappe_client.get_employees_on_leave(
        date=tool_input.get("date"),
        store=tool_input.get("store"),
        area=tool_input.get("area"),
        user_context=user_context
    )


async def _submit_leave_request(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Submit a leave request to Frappe."""
    employee = user_context.get("employee")
    if not employee:
        return {"error": "Cannot submit leave request - employee not identified."}

    return await frappe_client.submit_leave_request(
        employee=employee,
        leave_type=tool_input.get("leave_type"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
        reason=tool_input.get("reason", ""),
        user_context=user_context
    )


# === ATTENDANCE TOOLS ===

async def _get_attendance(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get attendance records from Frappe."""
    employee = tool_input.get("employee") or user_context.get("employee")
    return await frappe_client.get_attendance(
        employee=employee,
        date=tool_input.get("date"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
        user_context=user_context
    )


async def _get_team_attendance(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get team attendance from Frappe."""
    return await frappe_client.get_team_attendance(
        store=tool_input.get("store"),
        date=tool_input.get("date"),
        user_context=user_context
    )


# === DIRECTORY TOOLS ===

async def _search_employees(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Search employees in Frappe."""
    return await frappe_client.search_employees(
        query=tool_input.get("query"),
        store=tool_input.get("store"),
        department=tool_input.get("department"),
        position=tool_input.get("position"),
        user_context=user_context
    )


async def _get_store_info(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    frappe_client: Any
) -> Dict[str, Any]:
    """Get store information from Frappe."""
    return await frappe_client.get_store_info(
        store=tool_input.get("store"),
        user_context=user_context
    )


# === WEATHER TOOLS ===

async def _get_weather_forecast(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Get weather forecast."""
    # Import from the data module
    from ..data.weather import get_weather_forecast as fetch_weather

    # Build entities dict expected by weather module
    entities = {
        "location": tool_input.get("location", "Metro Manila"),
        "store": tool_input.get("location"),  # Weather module uses store/area hints
    }

    return await fetch_weather(entities=entities)


# === MEMORY TOOLS ===

async def _remember_fact(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    memory_store: Any
) -> Dict[str, Any]:
    """Store a fact about the user."""
    if not memory_store:
        return {"error": "Memory system not available"}

    user_email = user_context.get("email")
    if not user_email:
        return {"error": "Cannot store memory - user not identified"}

    category = tool_input.get("category", "other")
    fact = tool_input.get("fact")
    importance = tool_input.get("importance", "medium")

    # Create a unique key for this fact
    import hashlib
    fact_hash = hashlib.md5(fact.encode()).hexdigest()[:8]
    key = f"{category}_{fact_hash}"

    await memory_store.remember(
        user_email=user_email,
        key=key,
        value={
            "category": category,
            "fact": fact,
            "importance": importance,
            "stored_at": datetime.now().isoformat()
        },
        ttl_days=90  # Remember for 90 days
    )

    return {
        "success": True,
        "message": f"I'll remember that: {fact}"
    }


async def _recall_facts(
    tool_input: Dict[str, Any],
    user_context: Dict[str, Any],
    memory_store: Any
) -> Dict[str, Any]:
    """Recall stored facts about the user."""
    if not memory_store:
        return {"facts": [], "message": "Memory system not available"}

    user_email = user_context.get("email")
    if not user_email:
        return {"facts": [], "error": "User not identified"}

    all_memories = await memory_store.get_all_memories(user_email)

    # Filter by category if specified
    category_filter = tool_input.get("category")
    if category_filter:
        facts = [
            m for m in all_memories.values()
            if isinstance(m, dict) and m.get("category") == category_filter
        ]
    else:
        facts = [m for m in all_memories.values() if isinstance(m, dict)]

    return {
        "facts": facts,
        "count": len(facts)
    }

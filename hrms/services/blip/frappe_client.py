"""
Frappe API Client

Handles all communication with the Frappe backend for data queries.
"""

import logging
from typing import Any, Optional
from datetime import datetime, date, timedelta

import httpx

from config import settings

logger = logging.getLogger(__name__)


class FrappeClient:
    """Client for Frappe API interactions."""

    def __init__(self):
        """Initialize the Frappe client."""
        self.base_url = settings.FRAPPE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"token {settings.FRAPPE_API_KEY}:{settings.FRAPPE_API_SECRET}",
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        data: dict = None
    ) -> dict:
        """Make an authenticated request to Frappe API."""
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

    async def get_user_context(self, email: str) -> dict:
        """
        Get user context from Frappe for permission checking.

        Args:
            email: User's email address

        Returns:
            User context with employee info, roles, store, area
        """
        try:
            # Call custom Blip API endpoint
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_user_context",
                params={"email": email}
            )
            return result.get("message", {})
        except Exception as e:
            logger.warning(f"Could not get user context for {email}: {e}")
            return {}

    # ==================== HR Data ====================

    async def get_leave_balance(
        self,
        employee: str = None,
        user_context: dict = None
    ) -> dict:
        """Get leave balance for an employee."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_leave_balance",
                params={
                    "employee": employee,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting leave balance: {e}")
            return {"error": str(e)}

    async def get_leave_applications(
        self,
        employee: str = None,
        status: str = None,
        user_context: dict = None
    ) -> dict:
        """Get leave applications with optional filters."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_leave_applications",
                params={
                    "employee": employee,
                    "status": status,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting leave applications: {e}")
            return {"error": str(e)}

    async def get_employees_on_leave(
        self,
        date: str = None,
        store: str = None,
        user_context: dict = None
    ) -> dict:
        """Get list of employees on leave for a date."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_employees_on_leave",
                params={
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "store": store,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting employees on leave: {e}")
            return {"error": str(e)}

    async def get_attendance(
        self,
        employee: str = None,
        date: str = None,
        user_context: dict = None
    ) -> dict:
        """Get attendance record for an employee."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_attendance",
                params={
                    "employee": employee,
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting attendance: {e}")
            return {"error": str(e)}

    async def get_team_attendance(
        self,
        date: str = None,
        store: str = None,
        user_context: dict = None
    ) -> dict:
        """Get team attendance for a store/date."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_team_attendance",
                params={
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "store": store,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting team attendance: {e}")
            return {"error": str(e)}

    # ==================== Sales Data ====================

    async def get_sales_data(
        self,
        store: str = None,
        area: str = None,
        period: str = None,
        user_context: dict = None
    ) -> dict:
        """
        Get sales data with optional filters.

        Args:
            store: Store name or ID
            area: Area name (South, North, etc.)
            period: Time period (today, yesterday, this_week, last_week, this_month)
            user_context: User permissions context
        """
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_sales_data",
                params={
                    "store": store,
                    "area": area,
                    "period": period or "today",
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting sales data: {e}")
            return {"error": str(e)}

    # ==================== Food Cost Data ====================

    async def get_food_cost(
        self,
        store: str = None,
        period: str = None,
        user_context: dict = None
    ) -> dict:
        """Get food cost analysis."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_food_cost",
                params={
                    "store": store,
                    "period": period or "this_month",
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting food cost: {e}")
            return {"error": str(e)}

    # ==================== Inventory Data ====================

    async def get_inventory(
        self,
        store: str = None,
        item: str = None,
        user_context: dict = None
    ) -> dict:
        """Get inventory levels."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_inventory",
                params={
                    "store": store,
                    "item": item,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting inventory: {e}")
            return {"error": str(e)}

    # ==================== Commissary Data ====================

    async def get_commissary_production(
        self,
        product: str = None,
        date: str = None,
        from_date: str = None,
        to_date: str = None,
        user_context: dict = None
    ) -> dict:
        """Get commissary production data."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_commissary_production",
                params={
                    "product": product,
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "from_date": from_date,
                    "to_date": to_date,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting commissary production: {e}")
            return {"error": str(e)}

    # ==================== Employee Directory ====================

    async def search_employees(
        self,
        query: str,
        store: str = None,
        department: str = None,
        position: str = None,
        user_context: dict = None
    ) -> dict:
        """Search for employees by name, position, or store."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.search_employees",
                params={
                    "query": query,
                    "store": store,
                    "department": department,
                    "position": position,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error searching employees: {e}")
            return {"error": str(e)}

    async def get_store_info(
        self,
        store: str,
        user_context: dict = None
    ) -> dict:
        """Get information about a store."""
        try:
            result = await self._request(
                "GET",
                "/api/method/hrms.api.blip.get_store_info",
                params={
                    "store": store,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error getting store info: {e}")
            return {"error": str(e)}

    # ==================== Leave Actions ====================

    async def submit_leave_request(
        self,
        employee: str,
        leave_type: str,
        from_date: str,
        to_date: str,
        reason: str = "",
        user_context: dict = None
    ) -> dict:
        """Submit a leave request for an employee."""
        try:
            result = await self._request(
                "POST",
                "/api/method/hrms.api.blip.submit_leave_request",
                data={
                    "employee": employee,
                    "leave_type": leave_type,
                    "from_date": from_date,
                    "to_date": to_date,
                    "reason": reason,
                    "email": user_context.get("email") if user_context else None
                }
            )
            return result.get("message", {})
        except Exception as e:
            logger.error(f"Error submitting leave request: {e}")
            return {"error": str(e)}

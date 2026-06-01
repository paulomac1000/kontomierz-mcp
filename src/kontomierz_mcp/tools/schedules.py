"""Schedule tools — [READ] list/get + [WRITE] create/update/mark + [DESTRUCTIVE] delete.

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool
from ..validators import (
    check_write_enabled,
    validate_currency_name,
    validate_date,
    validate_direction,
    validate_holidays,
    validate_repeat,
    validate_required,
)


def _do_list_scheduled_transactions(
    client: KontomierzClient,
    schedule_group_name: str,
    page: int = 1,
    per_page: int = 0,
    start_on: str = "",
    end_on: str = "",
    direction: str = "",
) -> dict[str, Any]:
    result = client.get_scheduled_transactions(
        schedule_group_name=schedule_group_name,
        page=page,
        per_page=per_page or None,
        start_on=start_on or None,
        end_on=end_on or None,
        direction=direction or None,
    )
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch scheduled transactions.", retryable=True)}
    transactions = result if isinstance(result, list) else []
    return {
        "success": True,
        "data": {
            "scheduled_transactions": transactions,
            "page": page,
            "limit": per_page,
            "has_more": len(transactions) == (per_page or 0) or len(transactions) > 0,
            "next_offset": page + 1 if (len(transactions) == (per_page or 0) or len(transactions) > 0) else None,
            "total": len(transactions),
        },
    }


def _do_get_schedule(client: KontomierzClient, schedule_id: int) -> dict[str, Any]:
    result = client.get_schedule(schedule_id)
    if result is None:
        return {
            "success": False,
            "error": error_dict("RESOURCE_NOT_FOUND", f"Schedule {schedule_id} not found or fetch failed.", retryable=False),
        }
    return {"success": True, "data": result}


def _do_create_schedule(
    client: KontomierzClient,
    direction: str,
    deadline_on: str,
    holidays: str,
    description: str,
    currency_amount: str,
    currency_name: str,
    repeat: str,
) -> dict[str, Any]:
    check_write_enabled()
    validate_direction(direction)
    validate_date(deadline_on, "deadline_on")
    validate_holidays(holidays)
    validate_required(description, "description")
    validate_currency_name(currency_name)
    validate_repeat(repeat)
    result = client.create_schedule(direction, deadline_on, holidays, description, currency_amount, currency_name, repeat)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to create schedule.", retryable=True)}
    return {"success": True, "data": result}


def _do_update_schedule(
    client: KontomierzClient,
    schedule_id: int,
    direction: str = "",
    deadline_on: str = "",
    holidays: str = "",
    description: str = "",
    currency_amount: str = "",
    currency_name: str = "",
    repeat: str = "",
) -> dict[str, Any]:
    check_write_enabled()
    result = client.update_schedule(
        schedule_id, direction, deadline_on, holidays, description, currency_amount, currency_name, repeat
    )
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to update schedule {schedule_id}.", retryable=True)}
    return {"success": True, "data": result}


def _do_delete_schedule(client: KontomierzClient, schedule_id: int) -> dict[str, Any]:
    check_write_enabled()
    if not client.delete_schedule(schedule_id):
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to delete schedule {schedule_id}.", retryable=False)}
    return {"success": True, "data": {"deleted": True, "schedule_id": schedule_id}}


def _do_mark_schedule_paid(client: KontomierzClient, schedule_id: int, date: str) -> dict[str, Any]:
    check_write_enabled()
    if not client.mark_schedule_paid(schedule_id, date):
        return {
            "success": False,
            "error": error_dict("API_ERROR", f"Failed to mark schedule {schedule_id} as paid on {date}.", retryable=True),
        }
    return {"success": True, "data": {"schedule_id": schedule_id, "date": date, "paid": True}}


def _do_mark_schedule_unpaid(client: KontomierzClient, schedule_id: int, date: str) -> dict[str, Any]:
    check_write_enabled()
    if not client.mark_schedule_unpaid(schedule_id, date):
        return {
            "success": False,
            "error": error_dict("API_ERROR", f"Failed to mark schedule {schedule_id} as unpaid on {date}.", retryable=True),
        }
    return {"success": True, "data": {"schedule_id": schedule_id, "date": date, "unpaid": True}}


def register_schedules_tools(mcp: Any) -> None:

    @mcp.tool()
    async def list_scheduled_transactions(
        schedule_group_name: str = "unpaid",
        page: int = 1,
        per_page: int = 0,
        start_on: str = "",
        end_on: str = "",
        direction: str = "",
    ) -> str:
        """[READ] List scheduled payments.

        Args:
            schedule_group_name: "unpaid" (planned) or "paid" (completed).
            page: Page number, starting from 1.
            per_page: Transactions per page (1-100).
            start_on: Filter from date (DD-MM-YYYY).
            end_on: Filter to date (DD-MM-YYYY).
            direction: "all", "withdrawals", or "deposits".

        Returns:
            JSON with scheduled transactions list and pagination metadata.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "list_scheduled_transactions",
            _do_list_scheduled_transactions,
            schedule_group_name,
            page,
            per_page,
            start_on,
            end_on,
            direction,
        )

    @mcp.tool()
    async def get_schedule(schedule_id: int) -> str:
        """[READ] Get details of a payment schedule.

        Args:
            schedule_id: Numeric schedule ID.

        Returns:
            JSON with schedule details (description, repeat, next-deadline-on, etc.).
        @since v1.0.0
        """
        return await invoke_tool(mcp, "get_schedule", _do_get_schedule, schedule_id)

    @mcp.tool()
    async def create_schedule(
        direction: str,
        deadline_on: str,
        holidays: str,
        description: str,
        currency_amount: str,
        currency_name: str,
        repeat: str,
    ) -> str:
        """[WRITE] Create a new payment schedule.

        Args:
            direction: "withdrawal" or "deposit".
            deadline_on: Next payment date (DD-MM-YYYY).
            holidays: 0=no shift, 1=before weekend, 2=after weekend.
            description: Payment name.
            currency_amount: Payment amount.
            currency_name: 3-letter currency code.
            repeat: 1=once, 8=weekly, 9=biweekly, 2=monthly, 7=bimonthly, 3=quarterly, 4=semiannual, 5=yearly, 6=biennial.

        Returns:
            JSON with created schedule data or error.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "create_schedule",
            _do_create_schedule,
            direction,
            deadline_on,
            holidays,
            description,
            currency_amount,
            currency_name,
            repeat,
        )

    @mcp.tool()
    async def update_schedule(
        schedule_id: int,
        direction: str = "",
        deadline_on: str = "",
        holidays: str = "",
        description: str = "",
        currency_amount: str = "",
        currency_name: str = "",
        repeat: str = "",
    ) -> str:
        """[WRITE] Update a payment schedule. Only provided fields are changed.

        Args:
            schedule_id: Numeric schedule ID to update.
            (other parameters same as create_schedule.)

        Returns:
            JSON with updated schedule data or error.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "update_schedule",
            _do_update_schedule,
            schedule_id,
            direction,
            deadline_on,
            holidays,
            description,
            currency_amount,
            currency_name,
            repeat,
        )

    @mcp.tool()
    async def delete_schedule(schedule_id: int) -> str:
        """[DESTRUCTIVE] Delete a payment schedule.

        Args:
            schedule_id: Numeric schedule ID to delete.

        Returns:
            JSON with deletion confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "delete_schedule", _do_delete_schedule, schedule_id)

    @mcp.tool()
    async def mark_schedule_paid(schedule_id: int, date: str) -> str:
        """[WRITE] Mark a scheduled payment as paid.

        Args:
            schedule_id: Numeric schedule ID.
            date: Payment date in DD-MM-YYYY format.

        Returns:
            JSON with paid confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "mark_schedule_paid", _do_mark_schedule_paid, schedule_id, date)

    @mcp.tool()
    async def mark_schedule_unpaid(schedule_id: int, date: str) -> str:
        """[WRITE] Mark a scheduled payment as unpaid.

        Args:
            schedule_id: Numeric schedule ID.
            date: Payment date in DD-MM-YYYY format.

        Returns:
            JSON with unpaid confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "mark_schedule_unpaid", _do_mark_schedule_unpaid, schedule_id, date)

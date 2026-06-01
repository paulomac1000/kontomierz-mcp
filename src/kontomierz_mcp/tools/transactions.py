"""Transaction tools — [READ] list/get + [WRITE] create/update + [DESTRUCTIVE] delete.

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool
from ..validators import check_write_enabled


def _do_list_transactions(
    client: KontomierzClient,
    page: int = 1,
    per_page: int | None = None,
    user_account_id: int | None = None,
    q: str | None = None,
    start_on: str | None = None,
    end_on: str | None = None,
    direction: str | None = None,
    tag_name: str | None = None,
    category_group_id: int | None = None,
    category_id: int | None = None,
    show_hidden_transactions: str | None = None,
) -> dict[str, Any]:
    transactions = client.get_money_transactions(
        page=page,
        per_page=per_page,
        user_account_id=user_account_id,
        q=q,
        start_on=start_on,
        end_on=end_on,
        direction=direction,
        tag_name=tag_name,
        category_group_id=category_group_id,
        category_id=category_id,
        show_hidden_transactions=show_hidden_transactions,
    )
    if transactions is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to fetch transactions.", retryable=True)}
    return {
        "success": True,
        "data": {
            "transactions": transactions,
            "page": page,
            "has_more": len(transactions) == (per_page or 0) or len(transactions) > 0,
            "total_count": len(transactions),
        },
    }


def _do_get_transaction(client: KontomierzClient, transaction_id: int) -> dict[str, Any]:
    tx = client.get_money_transaction(transaction_id)
    if tx is None:
        return {
            "success": False,
            "error": error_dict(
                "RESOURCE_NOT_FOUND", f"Transaction {transaction_id} not found or fetch failed.", retryable=False
            ),
        }
    return {"success": True, "data": tx}


def _do_create_transaction(
    client: KontomierzClient,
    client_assigned_id: str,
    user_account_id: int | None = None,
    category_id: int | None = None,
    currency_amount: str = "",
    currency_name: str = "",
    direction: str = "withdrawal",
    tag_string: str = "",
    name: str = "",
    transaction_on: str = "",
) -> dict[str, Any]:
    check_write_enabled()
    result = client.create_money_transaction(
        client_assigned_id=client_assigned_id,
        user_account_id=user_account_id,
        category_id=category_id,
        currency_amount=currency_amount,
        currency_name=currency_name,
        direction=direction,
        tag_string=tag_string,
        name=name,
        transaction_on=transaction_on,
    )
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", "Failed to create transaction.", retryable=True)}
    return {"success": True, "data": result}


def _do_update_transaction(
    client: KontomierzClient,
    transaction_id: int,
    user_account_id: int | None = None,
    category_id: int | None = None,
    currency_amount: str = "",
    currency_name: str = "",
    direction: str = "",
    tag_string: str = "",
    name: str = "",
    transaction_on: str = "",
) -> dict[str, Any]:
    check_write_enabled()
    result = client.update_money_transaction(
        transaction_id=transaction_id,
        user_account_id=user_account_id,
        category_id=category_id,
        currency_amount=currency_amount,
        currency_name=currency_name,
        direction=direction,
        tag_string=tag_string,
        name=name,
        transaction_on=transaction_on,
    )
    if result is None:
        return {
            "success": False,
            "error": error_dict("API_ERROR", f"Failed to update transaction {transaction_id}.", retryable=True),
        }
    return {"success": True, "data": result}


def _do_delete_transaction(client: KontomierzClient, transaction_id: int) -> dict[str, Any]:
    check_write_enabled()
    if not client.delete_money_transaction(transaction_id):
        return {
            "success": False,
            "error": error_dict("API_ERROR", f"Failed to delete transaction {transaction_id}.", retryable=False),
        }
    return {"success": True, "data": {"deleted": True, "transaction_id": transaction_id}}


def register_transactions_tools(mcp: Any) -> None:

    @mcp.tool()
    async def list_transactions(
        page: int = 1,
        per_page: int | None = None,
        user_account_id: int | None = None,
        q: str | None = None,
        start_on: str | None = None,
        end_on: str | None = None,
        direction: str | None = None,
        tag_name: str | None = None,
        category_group_id: int | None = None,
        category_id: int | None = None,
        show_hidden_transactions: str | None = None,
    ) -> str:
        """[READ] List money transactions with pagination and filters.

        Args:
            page: Page number, starting from 1.
            per_page: Transactions per page (1-100).
            user_account_id: Filter by account ID.
            q: Search query text.
            start_on: Filter from date (DD-MM-YYYY).
            end_on: Filter to date (DD-MM-YYYY).
            direction: "all", "withdrawals", or "deposits".
            tag_name: Filter by tag name.
            category_group_id: Filter by category group ID.
            category_id: Filter by category ID.
            show_hidden_transactions: "true" or "false".

        Returns:
            JSON with transactions data, pagination metadata, _meta envelope.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "list_transactions",
            _do_list_transactions,
            page,
            per_page,
            user_account_id,
            q,
            start_on,
            end_on,
            direction,
            tag_name,
            category_group_id,
            category_id,
            show_hidden_transactions,
        )

    @mcp.tool()
    async def get_transaction(transaction_id: int) -> str:
        """[READ] Get details of a single money transaction.

        Args:
            transaction_id: Numeric transaction ID.

        Returns:
            JSON with transaction details or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "get_transaction", _do_get_transaction, transaction_id)

    @mcp.tool()
    async def create_transaction(
        client_assigned_id: str,
        user_account_id: int | None = None,
        category_id: int | None = None,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "withdrawal",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> str:
        """[WRITE] Create a new money transaction in a wallet.

        Args:
            client_assigned_id: Unique client-side idempotency key (e.g. timestamp).
            user_account_id: Wallet ID. Default: default wallet.
            category_id: Category ID.
            currency_amount: Positive transaction amount.
            currency_name: 3-letter currency code.
            direction: "withdrawal" (expense) or "deposit" (income).
            tag_string: Comma-separated tags.
            name: Transaction description.
            transaction_on: Date in DD-MM-YYYY format. Default: today.

        Returns:
            JSON with created transaction data or error.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "create_transaction",
            _do_create_transaction,
            client_assigned_id,
            user_account_id,
            category_id,
            currency_amount,
            currency_name,
            direction,
            tag_string,
            name,
            transaction_on,
        )

    @mcp.tool()
    async def update_transaction(
        transaction_id: int,
        user_account_id: int | None = None,
        category_id: int | None = None,
        currency_amount: str = "",
        currency_name: str = "",
        direction: str = "",
        tag_string: str = "",
        name: str = "",
        transaction_on: str = "",
    ) -> str:
        """[WRITE] Update an existing money transaction.

        Args:
            transaction_id: Numeric transaction ID to update.
            (other parameters as in create_transaction, only provided fields are changed.)

        Returns:
            JSON with updated transaction data or error.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp,
            "update_transaction",
            _do_update_transaction,
            transaction_id,
            user_account_id,
            category_id,
            currency_amount,
            currency_name,
            direction,
            tag_string,
            name,
            transaction_on,
        )

    @mcp.tool()
    async def delete_transaction(transaction_id: int) -> str:
        """[DESTRUCTIVE] Delete a money transaction.

        Args:
            transaction_id: Numeric transaction ID to delete.

        Returns:
            JSON with deletion confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "delete_transaction", _do_delete_transaction, transaction_id)

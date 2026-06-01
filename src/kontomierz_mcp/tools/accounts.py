"""Accounts tools — [READ] list + [WRITE] create/update + [DESTRUCTIVE] delete.

@since v1.0.0
"""

from typing import Any

from ..client import KontomierzClient
from ..response import error_dict, invoke_tool
from ..validators import check_write_enabled, validate_currency_name, validate_required


def _do_list_accounts(client: KontomierzClient) -> dict[str, Any]:
    accounts = client.get_user_accounts()
    if accounts is None:
        return {
            "success": False,
            "error": error_dict(
                "API_ERROR",
                "Failed to fetch accounts from Kontomierz API.",
                retryable=True,
                suggestion="Verify API key and network connectivity.",
            ),
        }
    return {"success": True, "data": accounts}


def _do_create_wallet(
    client: KontomierzClient,
    currency_balance: str,
    currency_name: str,
    user_name: str = "",
    liquid: str = "1",
) -> dict[str, Any]:
    check_write_enabled()
    validate_required(currency_balance, "currency_balance")
    validate_currency_name(currency_name)
    result = client.create_wallet(currency_balance, currency_name, user_name, liquid)
    if result is None:
        return {
            "success": False,
            "error": error_dict(
                "API_ERROR", "Failed to create wallet on Kontomierz.", retryable=True, suggestion="Check parameters and retry."
            ),
        }
    return {"success": True, "data": result}


def _do_update_wallet(
    client: KontomierzClient,
    wallet_id: int,
    currency_balance: str = "",
    currency_name: str = "",
    user_name: str = "",
    liquid: str = "",
) -> dict[str, Any]:
    check_write_enabled()
    result = client.update_wallet(wallet_id, currency_balance, currency_name, user_name, liquid)
    if result is None:
        return {"success": False, "error": error_dict("API_ERROR", f"Failed to update wallet {wallet_id}.", retryable=True)}
    return {"success": True, "data": result}


def _do_destroy_wallet(client: KontomierzClient, wallet_id: int) -> dict[str, Any]:
    check_write_enabled()
    if not client.destroy_wallet(wallet_id):
        return {
            "success": False,
            "error": error_dict(
                "API_ERROR",
                f"Failed to delete wallet {wallet_id}. It may be the default wallet or have linked bank accounts.",
                retryable=False,
            ),
        }
    return {"success": True, "data": {"deleted": True, "wallet_id": wallet_id}}


def register_accounts_tools(mcp: Any) -> None:

    @mcp.tool()
    async def list_accounts() -> str:
        """[READ] List all bank accounts and wallets with their balances.

        Returns:
            JSON with success, data[accounts] array, _meta envelope.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "list_accounts", _do_list_accounts)

    @mcp.tool()
    async def create_wallet(currency_balance: str, currency_name: str, user_name: str = "", liquid: str = "1") -> str:
        """[WRITE] Create a new cash wallet.

        Args:
            currency_balance: Initial balance as a string (e.g. "100.00").
            currency_name: 3-letter currency code (e.g. "PLN").
            user_name: Display name for the wallet.
            liquid: "1" = current funds, "0" = savings. Default "1".

        Returns:
            JSON with created wallet data or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "create_wallet", _do_create_wallet, currency_balance, currency_name, user_name, liquid)

    @mcp.tool()
    async def update_wallet(
        wallet_id: int,
        currency_balance: str = "",
        currency_name: str = "",
        user_name: str = "",
        liquid: str = "",
    ) -> str:
        """[WRITE] Update a cash wallet. Only provided fields are changed.

        Args:
            wallet_id: Numeric ID of the wallet to update.
            currency_balance: New balance (string).
            currency_name: New 3-letter currency code.
            user_name: New display name.
            liquid: New liquid status ("1" or "0").

        Returns:
            JSON with updated wallet data or error.
        @since v1.0.0
        """
        return await invoke_tool(
            mcp, "update_wallet", _do_update_wallet, wallet_id, currency_balance, currency_name, user_name, liquid
        )

    @mcp.tool()
    async def destroy_wallet(wallet_id: int) -> str:
        """[DESTRUCTIVE] Delete a cash wallet. Cannot delete default wallet or wallet with bank accounts.

        Args:
            wallet_id: Numeric ID of the wallet to delete.

        Returns:
            JSON with deletion confirmation or error.
        @since v1.0.0
        """
        return await invoke_tool(mcp, "destroy_wallet", _do_destroy_wallet, wallet_id)

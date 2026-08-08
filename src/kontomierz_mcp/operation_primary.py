"""Account and transaction operation handlers."""

from __future__ import annotations

from typing import Any

from .operation_support import (
    currency,
    date_range,
    date_value,
    direction,
    fail,
    identifier,
    money,
    page,
    page_limit,
    paging,
    provided,
    resolve,
    text,
)

PRIMARY_NAMES = {
    "list_accounts",
    "create_wallet",
    "update_wallet",
    "destroy_wallet",
    "list_transactions",
    "get_transaction",
    "create_transaction",
    "update_transaction",
    "delete_transaction",
    "list_categories",
    "list_tags",
    "list_currencies",
}


async def dispatch_primary(name: str, a: dict[str, Any], client: Any) -> Any:
    if name == "list_accounts":
        return await resolve(client.get_user_accounts())
    if name == "create_wallet":
        liquid = a.get("liquid", "1")
        if liquid not in {"0", "1"}:
            fail("liquid must be 0 or 1")
        return await resolve(
            client.create_wallet(
                money(a["currency_balance"], "currency_balance", positive=False),
                currency(a["currency_name"]),
                a.get("user_name"),
                liquid,
            )
        )
    if name == "update_wallet":
        wallet_fields = provided(a, ("currency_balance", "currency_name", "user_name", "liquid"))
        if "currency_balance" in wallet_fields:
            wallet_fields["currency_balance"] = money(
                wallet_fields["currency_balance"], "currency_balance", positive=False
            )
        if "currency_name" in wallet_fields:
            wallet_fields["currency_name"] = currency(wallet_fields["currency_name"])
        if "liquid" in wallet_fields and wallet_fields["liquid"] not in {"0", "1"}:
            fail("liquid must be 0 or 1")
        return await resolve(client.update_wallet(identifier(a["wallet_id"], "wallet_id"), **wallet_fields))
    if name == "destroy_wallet":
        item_id = identifier(a["wallet_id"], "wallet_id")
        await resolve(client.destroy_wallet(item_id))
        return {"deleted": True, "wallet_id": item_id}
    if name == "list_transactions":
        number, limit = page(a.get("page", 1)), page_limit(a.get("per_page", 0))
        start, end = date_range(a.get("start_on", ""), a.get("end_on", ""))
        items = await resolve(
            client.get_money_transactions(
                page=number,
                per_page=limit,
                user_account_id=identifier(a.get("user_account_id"), "user_account_id", optional=True),
                q=str(a.get("q", "")).strip() or None,
                start_on=start,
                end_on=end,
                direction=direction(a.get("direction", "all"), allow_all=True, plural=True),
                tag_name=str(a.get("tag_name", "")).strip() or None,
                category_group_id=identifier(a.get("category_group_id"), "category_group_id", optional=True),
                category_id=identifier(a.get("category_id"), "category_id", optional=True),
                show_hidden_transactions="true" if a.get("show_hidden_transactions", False) else "false",
            )
        )
        return paging(items, number, limit)
    if name == "get_transaction":
        return await resolve(client.get_money_transaction(identifier(a["transaction_id"], "transaction_id")))
    if name == "create_transaction":
        create_fields: dict[str, Any] = {
            "client_assigned_id": text(a["client_assigned_id"], "client_assigned_id"),
            "user_account_id": identifier(a.get("user_account_id"), "user_account_id", optional=True),
            "category_id": identifier(a.get("category_id"), "category_id", optional=True),
            "direction": direction(a.get("direction", "withdrawal")),
            "tag_string": a.get("tag_string", ""),
            "name": a.get("name", ""),
        }
        if a.get("currency_amount"):
            create_fields["currency_amount"] = money(a["currency_amount"], "currency_amount", positive=True)
        if a.get("currency_name"):
            create_fields["currency_name"] = currency(a["currency_name"])
        if a.get("transaction_on"):
            create_fields["transaction_on"] = date_value(a["transaction_on"], "transaction_on")
        return await resolve(client.create_money_transaction(**create_fields))
    if name == "update_transaction":
        update_fields = provided(
            a,
            (
                "user_account_id",
                "category_id",
                "currency_amount",
                "currency_name",
                "direction",
                "tag_string",
                "name",
                "transaction_on",
            ),
        )
        if "user_account_id" in update_fields:
            update_fields["user_account_id"] = identifier(update_fields["user_account_id"], "user_account_id")
        if "category_id" in update_fields:
            update_fields["category_id"] = identifier(update_fields["category_id"], "category_id")
        if "currency_amount" in update_fields:
            update_fields["currency_amount"] = money(update_fields["currency_amount"], "currency_amount", positive=True)
        if "currency_name" in update_fields:
            update_fields["currency_name"] = currency(update_fields["currency_name"])
        if "direction" in update_fields:
            update_fields["direction"] = direction(update_fields["direction"])
        if "transaction_on" in update_fields:
            update_fields["transaction_on"] = date_value(update_fields["transaction_on"], "transaction_on")
        transaction_id = identifier(a["transaction_id"], "transaction_id")
        return await resolve(client.update_money_transaction(transaction_id, **update_fields))
    if name == "delete_transaction":
        item_id = identifier(a["transaction_id"], "transaction_id")
        await resolve(client.delete_money_transaction(item_id))
        return {"deleted": True, "transaction_id": item_id}
    if name == "list_categories":
        return await resolve(client.get_categories(direction(a.get("direction", "withdrawal"))))
    if name == "list_tags":
        return await resolve(client.get_tags())
    if name == "list_currencies":
        return await resolve(client.get_currencies())
    raise KeyError(name)

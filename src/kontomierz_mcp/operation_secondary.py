"""Budget, schedule, chart, and wealth operation handlers."""

from __future__ import annotations

from typing import Any

from .operation_support import (
    bounded,
    bounded_text,
    currency,
    date_range,
    date_value,
    direction,
    fail,
    identifier,
    money,
    month,
    page,
    page_limit,
    paging,
    provided,
    resolve,
    text,
)


async def dispatch_secondary(name: str, a: dict[str, Any], client: Any) -> Any:
    if name == "list_budgets":
        items = await resolve(client.get_budgets(month(a.get("month", "")) or None))
        return {"items": items, "items_in_page": len(items), "month": a.get("month") or None}
    if name == "create_budget":
        category = identifier(a.get("category_id"), "category_id", optional=True)
        group = identifier(a.get("category_group_id"), "category_group_id", optional=True)
        if (category is None) == (group is None):
            fail("provide exactly one of category_id or category_group_id")
        return await resolve(
            client.create_budget(
                money(a["limit"], "limit", positive=True),
                category,
                group,
                month(a.get("month", "")),
            )
        )
    if name == "update_budget":
        return await resolve(
            client.update_budget(
                identifier(a["budget_id"], "budget_id"),
                money(a["limit"], "limit", positive=True),
            )
        )
    if name == "delete_budget":
        item_id = identifier(a["budget_id"], "budget_id")
        await resolve(client.delete_budget(item_id))
        return {"deleted": True, "budget_id": item_id}
    if name == "copy_budgets_from_last_month":
        await resolve(client.copy_budgets_from_last_month())
        return {"copied": True}
    if name == "list_scheduled_transactions":
        group = bounded_text(
            a.get("schedule_group_name", "unpaid"),
            "schedule_group_name",
            max_bytes=16,
            allow_empty=False,
            strip=True,
        )
        if group not in {"paid", "unpaid"}:
            fail("schedule_group_name must be paid or unpaid")
        number, limit = page(a.get("page", 1)), page_limit(a.get("per_page", 0))
        start, end = date_range(a.get("start_on", ""), a.get("end_on", ""))
        items = await resolve(
            client.get_scheduled_transactions(
                schedule_group_name=group,
                page=number,
                per_page=limit,
                start_on=start,
                end_on=end,
                direction=direction(a.get("direction", "all"), allow_all=True, plural=True),
            )
        )
        return paging(items, number, limit)
    if name == "get_schedule":
        return await resolve(client.get_schedule(identifier(a["schedule_id"], "schedule_id")))
    if name == "create_schedule":
        return await resolve(
            client.create_schedule(
                direction=direction(a["direction"]),
                deadline_on=date_value(a["deadline_on"], "deadline_on"),
                holidays=str(bounded(a["holidays"], "holidays", {0, 1, 2})),
                description=text(a["description"], "description", max_bytes=512),
                currency_amount=money(a["currency_amount"], "currency_amount", positive=True),
                currency_name=currency(a["currency_name"]),
                repeat=str(bounded(a["repeat"], "repeat", set(range(1, 10)))),
            )
        )
    if name == "update_schedule":
        fields = provided(
            a,
            (
                "direction",
                "deadline_on",
                "holidays",
                "description",
                "currency_amount",
                "currency_name",
                "repeat",
            ),
        )
        if "direction" in fields:
            fields["direction"] = direction(fields["direction"])
        if "deadline_on" in fields:
            fields["deadline_on"] = date_value(fields["deadline_on"], "deadline_on")
        if "holidays" in fields:
            fields["holidays"] = str(bounded(fields["holidays"], "holidays", {0, 1, 2}))
        if "description" in fields:
            fields["description"] = bounded_text(fields["description"], "description", max_bytes=512)
        if "currency_amount" in fields:
            fields["currency_amount"] = money(fields["currency_amount"], "currency_amount", positive=True)
        if "currency_name" in fields:
            fields["currency_name"] = currency(fields["currency_name"])
        if "repeat" in fields:
            fields["repeat"] = str(bounded(fields["repeat"], "repeat", set(range(1, 10))))
        return await resolve(client.update_schedule(identifier(a["schedule_id"], "schedule_id"), **fields))
    if name == "delete_schedule":
        item_id = identifier(a["schedule_id"], "schedule_id")
        await resolve(client.delete_schedule(item_id))
        return {"deleted": True, "schedule_id": item_id}
    if name in {"mark_schedule_paid", "mark_schedule_unpaid"}:
        item_id = identifier(a["schedule_id"], "schedule_id")
        payment = date_value(a["payment_date"], "payment_date")
        method = client.mark_schedule_paid if name == "mark_schedule_paid" else client.mark_schedule_unpaid
        await resolve(method(item_id, payment))
        return {"schedule_id": item_id, "payment_date": a["payment_date"], "paid": name == "mark_schedule_paid"}
    if name == "get_pie_chart":
        chart_kind = bounded_text(a.get("chart_kind", "pie"), "chart_kind", max_bytes=16, strip=True)
        if chart_kind != "pie":
            fail("chart_kind must be pie")
        start, end = date_range(a.get("start_on", ""), a.get("end_on", ""))
        query = bounded_text(a.get("q", ""), "q", max_bytes=256, strip=True) or None
        tag_name = bounded_text(a.get("tag_name", ""), "tag_name", max_bytes=128, strip=True) or None
        return await resolve(
            client.get_pie_chart(
                chart_kind="pie",
                start_on=start,
                end_on=end,
                direction=direction(a.get("direction", "all"), allow_all=True, plural=True),
                category_group_id=identifier(a.get("category_group_id"), "category_group_id", optional=True),
                category_id=identifier(a.get("category_id"), "category_id", optional=True),
                user_account_id=identifier(a.get("user_account_id"), "user_account_id", optional=True),
                q=query,
                tag_name=tag_name,
            )
        )
    if name == "list_wealth_points":
        start, end = date_range(a.get("start_on", ""), a.get("end_on", ""))
        return await resolve(client.get_wealth_points(start, end))
    raise KeyError(name)

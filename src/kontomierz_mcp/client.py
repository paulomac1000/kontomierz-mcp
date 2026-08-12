"""Asynchronous Kontomierz HTTP adapter with typed, bounded failure mapping."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .errors import ErrorCode, UpstreamError

Json = dict[str, Any] | list[Any]


class KontomierzClient:
    """Dependency client that owns one cancellation-aware asynchronous session."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
        body_mode: str = "form",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._body_mode = body_mode
        self._client = client or httpx.AsyncClient(
            headers={"Accept": "application/json", "User-Agent": "kontomierz-mcp/2"},
            timeout=httpx.Timeout(timeout_seconds),
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def probe(self) -> bool:
        """Check the mandatory dependency without exposing upstream details."""
        try:
            await self.get_currencies()
        except UpstreamError:
            return False
        return True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        expect_json: bool = True,
    ) -> Json | bool | None:
        params = {"api_key": self._api_key}
        if query:
            params.update({key: value for key, value in query.items() if value is not None and value != ""})
        kwargs: dict[str, Any] = {
            "method": method,
            "url": f"{self._base_url}/{path.lstrip('/')}",
            "params": params,
            "timeout": self._timeout,
        }
        if body is not None:
            body_key = "json" if self._body_mode == "json" else "data"
            kwargs[body_key] = dict(body)
        is_write = method.upper() not in {"GET", "HEAD", "OPTIONS"}
        try:
            response = await self._client.request(**kwargs)
        except httpx.TimeoutException as exc:
            raise UpstreamError(
                ErrorCode.TIMEOUT,
                "Kontomierz request timed out",
                retryable=not is_write,
                write_outcome_ambiguous=is_write,
            ) from exc
        except httpx.TransportError as exc:
            raise UpstreamError(
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                "Kontomierz is unavailable",
                retryable=not is_write,
                write_outcome_ambiguous=is_write,
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz request failed",
                write_outcome_ambiguous=is_write,
            ) from exc

        if response.status_code in {401, 403}:
            raise UpstreamError(ErrorCode.AUTHENTICATION_FAILED, "Kontomierz rejected the API credentials")
        if response.status_code == 404:
            raise UpstreamError(ErrorCode.RESOURCE_NOT_FOUND, "Kontomierz resource was not found")
        if response.status_code in {409, 422}:
            raise UpstreamError(
                ErrorCode.CONFLICT,
                "Kontomierz rejected the requested state change",
                details={"status": response.status_code},
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            details = {"retry_after": retry_after} if retry_after else None
            raise UpstreamError(
                ErrorCode.RATE_LIMITED,
                "Kontomierz rate limit exceeded",
                retryable=not is_write,
                details=details,
            )
        if response.status_code >= 500:
            raise UpstreamError(
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                "Kontomierz service failed",
                retryable=not is_write,
                details={"status": response.status_code},
                write_outcome_ambiguous=is_write,
            )
        if response.status_code >= 400:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz rejected the request",
                details={"status": response.status_code},
            )

        if not expect_json or response.status_code == 204:
            return True
        if response.status_code in {200, 201} and not response.content.strip():
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz returned invalid JSON",
                write_outcome_ambiguous=is_write,
            ) from exc
        if not isinstance(payload, (dict, list)):
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz returned an unsupported JSON value",
                write_outcome_ambiguous=is_write,
            )
        return payload

    @staticmethod
    def _unwrap(payload: Json | bool | None, key: str) -> Any:
        if payload is True or payload is None:
            return payload
        if isinstance(payload, dict):
            return payload.get(key, payload)
        return payload

    @staticmethod
    def _created_marker() -> dict[str, bool]:
        """Represent known create success when upstream did not identify the new resource."""
        return {"created": True, "reconciliation_required": True}

    async def get_user_accounts(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "user_accounts.json")
        items = self._expect_list(payload)
        return [self._expect_dict(item.get("user_account", item)) for item in items]

    async def create_wallet(
        self,
        currency_balance: str,
        currency_name: str,
        user_name: str | None = None,
        liquid: str = "1",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "user_account[currency_balance]": currency_balance,
            "user_account[currency_name]": currency_name,
            "user_account[liquid]": liquid,
        }
        if user_name is not None:
            body["user_account[user_name]"] = user_name
        payload = await self._request("POST", "user_accounts/create_wallet.json", body=body)
        if payload is None:
            return self._created_marker()
        return self._response_object(payload, "user_account", write=True)

    async def update_wallet(self, wallet_id: int, **fields: Any) -> dict[str, Any]:
        body = {f"user_account[{key}]": value for key, value in fields.items() if value is not None}
        payload = await self._request("PUT", f"user_accounts/{wallet_id}/update_wallet.json", body=body)
        if payload is None:
            return {"updated": True, "wallet_id": wallet_id}
        return self._response_object(payload, "user_account", write=True)

    async def destroy_wallet(self, wallet_id: int) -> bool:
        return bool(await self._request("DELETE", f"user_accounts/{wallet_id}/destroy_wallet.json", expect_json=False))

    async def get_money_transactions(self, **filters: Any) -> list[dict[str, Any]]:
        return self._expect_list(
            self._unwrap(
                await self._request("GET", "money_transactions.json", query=filters),
                "money_transactions",
            )
        )

    async def get_money_transaction(self, transaction_id: int) -> dict[str, Any]:
        return self._response_object(
            await self._request("GET", f"money_transactions/{transaction_id}.json"),
            "money_transaction",
            write=False,
        )

    async def create_money_transaction(self, **fields: Any) -> dict[str, Any]:
        body = {f"money_transaction[{key}]": value for key, value in fields.items() if value is not None}
        payload = await self._request("POST", "money_transactions.json", body=body)
        if payload is None:
            return self._created_marker()
        return self._response_object(payload, "money_transaction", write=True)

    async def update_money_transaction(self, transaction_id: int, **fields: Any) -> dict[str, Any]:
        body = {f"money_transaction[{key}]": value for key, value in fields.items() if value is not None}
        payload = await self._request("PUT", f"money_transactions/{transaction_id}.json", body=body)
        if payload is None:
            return {"updated": True, "transaction_id": transaction_id}
        return self._response_object(payload, "money_transaction", write=True)

    async def delete_money_transaction(self, transaction_id: int) -> bool:
        return bool(await self._request("DELETE", f"money_transactions/{transaction_id}.json", expect_json=False))

    async def get_categories(self, direction: str) -> list[dict[str, Any]]:
        return self._expect_list(
            self._unwrap(
                await self._request("GET", "categories.json", query={"direction": direction, "in_wallet": "true"}),
                "category_groups",
            )
        )

    async def get_tags(self) -> list[dict[str, Any]]:
        return self._expect_list(self._unwrap(await self._request("GET", "tags.json"), "tags"))

    async def get_currencies(self) -> list[dict[str, Any]]:
        return self._expect_list(self._unwrap(await self._request("GET", "currencies.json"), "currencies"))

    async def get_budgets(self, month_on: str | None = None) -> list[dict[str, Any]]:
        return self._expect_list(
            self._unwrap(
                await self._request("GET", "budgets.json", query={"month_on": month_on}),
                "budgets",
            )
        )

    async def create_budget(
        self,
        limit: str,
        category_id: int | None = None,
        category_group_id: int | None = None,
        month_on: str = "",
    ) -> dict[str, Any]:
        return await self._budget_write("POST", "budgets.json", limit, category_id, category_group_id, month_on)

    async def update_budget(self, budget_id: int, limit: str) -> dict[str, Any]:
        return await self._budget_write("PUT", f"budgets/{budget_id}.json", limit, None, None, "")

    async def _budget_write(
        self,
        method: str,
        path: str,
        limit: str,
        category_id: int | None,
        category_group_id: int | None,
        month_on: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"budget[limit]": limit}
        if category_id is not None:
            body["budget[category_id]"] = category_id
        if category_group_id is not None:
            body["budget[category_group_id]"] = category_group_id
        if month_on:
            body["budget[month_on]"] = month_on
        payload = await self._request(method, path, body=body)
        if payload is None:
            return {"updated": True} if method == "PUT" else self._created_marker()
        return self._response_object(payload, "budget", write=True)

    async def delete_budget(self, budget_id: int) -> bool:
        return bool(await self._request("DELETE", f"budgets/{budget_id}.json", expect_json=False))

    async def copy_budgets_from_last_month(self) -> bool:
        return bool(await self._request("POST", "budgets/copy_from_last_to_present_month.json", expect_json=False))

    async def get_scheduled_transactions(self, **filters: Any) -> list[dict[str, Any]]:
        return self._expect_list(
            self._unwrap(
                await self._request("GET", "scheduled_transactions.json", query=filters),
                "scheduled_transactions",
            )
        )

    async def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        return self._response_object(
            await self._request("GET", f"schedules/{schedule_id}.json"),
            "schedule",
            write=False,
        )

    async def create_schedule(self, **fields: Any) -> dict[str, Any]:
        payload = await self._schedule_write("POST", "schedules.json", fields)
        return self._created_marker() if payload is None else payload

    async def update_schedule(self, schedule_id: int, **fields: Any) -> dict[str, Any]:
        payload = await self._schedule_write("PUT", f"schedules/{schedule_id}.json", fields)
        if payload is None:
            return {"updated": True, "schedule_id": schedule_id}
        return payload

    async def _schedule_write(self, method: str, path: str, fields: Mapping[str, Any]) -> dict[str, Any] | None:
        body = {f"schedule[{key}]": value for key, value in fields.items() if value is not None}
        payload = await self._request(method, path, body=body)
        if payload is None:
            return None
        return self._response_object(payload, "schedule", write=True)

    async def delete_schedule(self, schedule_id: int) -> bool:
        return bool(await self._request("DELETE", f"schedules/{schedule_id}.json", expect_json=False))

    async def mark_schedule_paid(self, schedule_id: int, date: str) -> bool:
        return bool(await self._request("PUT", f"schedules/{schedule_id}/mark_as_payed/{date}.json", expect_json=False))

    async def mark_schedule_unpaid(self, schedule_id: int, date: str) -> bool:
        return bool(
            await self._request(
                "PUT",
                f"schedules/{schedule_id}/mark_as_unpayed/{date}.json",
                expect_json=False,
            )
        )

    async def get_wealth_points(self, start_on: str | None = None, end_on: str | None = None) -> list[dict[str, Any]]:
        payload = await self._request("GET", "wealth_points.json", query={"start_on": start_on, "end_on": end_on})
        items = self._expect_list(payload)
        # The upstream wraps every wealth point in a per-item "wealth_point" object.
        return [item.get("wealth_point", item) for item in items]

    async def get_pie_chart(self, **filters: Any) -> dict[str, Any]:
        return self._expect_dict(await self._request("GET", "charts/money_transactions.json", query=filters))

    @staticmethod
    def _response_object(payload: Json | bool | None, key: str, *, write: bool) -> dict[str, Any]:
        if payload is None:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz returned an empty response",
                write_outcome_ambiguous=write,
            )
        if not isinstance(payload, dict) or key not in payload:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                f"Kontomierz response is missing the {key} object",
                write_outcome_ambiguous=write,
            )
        return KontomierzClient._expect_dict(payload[key], write=write)

    @staticmethod
    def _expect_dict(value: Any, *, write: bool = False) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Unexpected object response from Kontomierz",
                write_outcome_ambiguous=write,
            )
        return value

    @staticmethod
    def _expect_list(value: Any, *, write: bool = False) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Unexpected list response from Kontomierz",
                write_outcome_ambiguous=write,
            )
        return value

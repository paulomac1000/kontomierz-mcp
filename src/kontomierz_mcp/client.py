"""Asynchronous Kontomierz HTTP adapter with typed, bounded failure mapping."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, NoReturn

import httpx

from .errors import ApplicationError, ErrorCode, UpstreamError

Json = dict[str, Any] | list[Any]
_MAX_UPSTREAM_RESPONSE_BYTES = 4 * 1024 * 1024


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

    @staticmethod
    async def _bounded_content(response: httpx.Response, *, write: bool) -> bytes:
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                declared_bytes = int(declared)
            except ValueError:
                declared_bytes = -1
            if declared_bytes > _MAX_UPSTREAM_RESPONSE_BYTES:
                raise UpstreamError(
                    ErrorCode.UPSTREAM_FAILURE,
                    "Kontomierz response exceeded the safe size limit",
                    retryable=False,
                    details={"max_response_bytes": _MAX_UPSTREAM_RESPONSE_BYTES},
                    write_outcome_ambiguous=write,
                )

        content = bytearray()
        async for chunk in response.aiter_bytes():
            if len(content) + len(chunk) > _MAX_UPSTREAM_RESPONSE_BYTES:
                raise UpstreamError(
                    ErrorCode.UPSTREAM_FAILURE,
                    "Kontomierz response exceeded the safe size limit",
                    retryable=False,
                    details={"max_response_bytes": _MAX_UPSTREAM_RESPONSE_BYTES},
                    write_outcome_ambiguous=write,
                )
            content.extend(chunk)
        return bytes(content)

    @staticmethod
    def _raise_status(response: httpx.Response, *, write: bool) -> None:
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
                retryable=not write,
                details=details,
            )
        if 300 <= response.status_code < 400:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz returned an unexpected redirect",
                retryable=False,
                details={"status": response.status_code},
                write_outcome_ambiguous=write,
            )
        if response.status_code >= 500:
            raise UpstreamError(
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                "Kontomierz service failed",
                retryable=not write,
                details={"status": response.status_code},
                write_outcome_ambiguous=write,
            )
        if response.status_code >= 400:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz rejected the request",
                details={"status": response.status_code},
            )
        if not 200 <= response.status_code < 300:
            raise UpstreamError(
                ErrorCode.UPSTREAM_FAILURE,
                "Kontomierz returned an unexpected HTTP status",
                retryable=False,
                details={"status": response.status_code},
                write_outcome_ambiguous=write,
            )

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
            async with self._client.stream(**kwargs) as response:
                self._raise_status(response, write=is_write)
                if not expect_json or response.status_code == 204:
                    return True
                content = await self._bounded_content(response, write=is_write)
                if response.status_code in {200, 201} and not content.strip():
                    return None
        except UpstreamError:
            raise
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

        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
    def _raise_unidentified_create() -> NoReturn:
        """Fail closed when a create succeeded but no stable new-resource identity was returned."""
        raise UpstreamError(
            ErrorCode.UPSTREAM_FAILURE,
            "Kontomierz accepted the create but did not identify the new resource",
            retryable=False,
            write_outcome_ambiguous=True,
        )

    @staticmethod
    def _upstream_date(value: str | None) -> str | None:
        """Convert one canonical public date to the legacy Kontomierz wire format."""
        if not value:
            return value
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            try:
                datetime.strptime(value, "%d-%m-%Y")
            except ValueError as exc:
                raise ApplicationError(
                    ErrorCode.INTERNAL_ERROR,
                    "Kontomierz adapter received an invalid date",
                ) from exc
            return value

    @staticmethod
    def _upstream_month(value: str | None) -> str | None:
        """Convert a canonical YYYY-MM month selector to the legacy wire date."""
        if not value:
            return value
        try:
            return datetime.strptime(value, "%Y-%m").strftime("01-%m-%Y")
        except ValueError:
            try:
                datetime.strptime(value, "%d-%m-%Y")
            except ValueError as exc:
                raise ApplicationError(
                    ErrorCode.INTERNAL_ERROR,
                    "Kontomierz adapter received an invalid month selector",
                ) from exc
            return value

    @classmethod
    def _upstream_date_fields(cls, values: Mapping[str, Any], *names: str) -> dict[str, Any]:
        result = dict(values)
        for name in names:
            if name in result and result[name] is not None and result[name] != "":
                result[name] = cls._upstream_date(result[name])
        return result

    @staticmethod
    def _canonicalize_upstream_date(value: Any) -> Any:
        """Normalize a localized upstream date when it appears in a response."""
        if not isinstance(value, str):
            return value
        try:
            return datetime.strptime(value, "%d-%m-%Y").date().isoformat()
        except ValueError:
            return value

    @classmethod
    def _canonicalize_date_fields(cls, value: dict[str, Any], *names: str) -> dict[str, Any]:
        result = dict(value)
        for name in names:
            if name in result:
                result[name] = cls._canonicalize_upstream_date(result[name])
        return result

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
            self._raise_unidentified_create()
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
        query = self._upstream_date_fields(filters, "start_on", "end_on")
        items = self._expect_list(
            self._unwrap(
                await self._request("GET", "money_transactions.json", query=query),
                "money_transactions",
            )
        )
        return [self._canonicalize_date_fields(item, "transaction_on") for item in items]

    async def get_money_transaction(self, transaction_id: int) -> dict[str, Any]:
        item = self._response_object(
            await self._request("GET", f"money_transactions/{transaction_id}.json"),
            "money_transaction",
            write=False,
        )
        return self._canonicalize_date_fields(item, "transaction_on")

    async def create_money_transaction(self, **fields: Any) -> dict[str, Any]:
        wire_fields = self._upstream_date_fields(fields, "transaction_on")
        body = {f"money_transaction[{key}]": value for key, value in wire_fields.items() if value is not None}
        payload = await self._request("POST", "money_transactions.json", body=body)
        if payload is None:
            self._raise_unidentified_create()
        item = self._response_object(payload, "money_transaction", write=True)
        return self._canonicalize_date_fields(item, "transaction_on")

    async def update_money_transaction(self, transaction_id: int, **fields: Any) -> dict[str, Any]:
        wire_fields = self._upstream_date_fields(fields, "transaction_on")
        body = {f"money_transaction[{key}]": value for key, value in wire_fields.items() if value is not None}
        payload = await self._request("PUT", f"money_transactions/{transaction_id}.json", body=body)
        if payload is None:
            return {"updated": True, "transaction_id": transaction_id}
        item = self._response_object(payload, "money_transaction", write=True)
        return self._canonicalize_date_fields(item, "transaction_on")

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
        items = self._expect_list(
            self._unwrap(
                await self._request("GET", "budgets.json", query={"month_on": self._upstream_month(month_on)}),
                "budgets",
            )
        )
        return [self._canonicalize_date_fields(item, "month_on") for item in items]

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
            body["budget[month_on]"] = self._upstream_month(month_on)
        payload = await self._request(method, path, body=body)
        if payload is None:
            if method == "PUT":
                return {"updated": True}
            self._raise_unidentified_create()
        item = self._response_object(payload, "budget", write=True)
        return self._canonicalize_date_fields(item, "month_on")

    async def delete_budget(self, budget_id: int) -> bool:
        return bool(await self._request("DELETE", f"budgets/{budget_id}.json", expect_json=False))

    async def copy_budgets_from_last_month(self) -> bool:
        return bool(await self._request("POST", "budgets/copy_from_last_to_present_month.json", expect_json=False))

    async def get_scheduled_transactions(self, **filters: Any) -> list[dict[str, Any]]:
        query = self._upstream_date_fields(filters, "start_on", "end_on")
        items = self._expect_list(
            self._unwrap(
                await self._request("GET", "scheduled_transactions.json", query=query),
                "scheduled_transactions",
            )
        )
        return [self._canonicalize_date_fields(item, "transaction_on") for item in items]

    async def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        item = self._response_object(
            await self._request("GET", f"schedules/{schedule_id}.json"),
            "schedule",
            write=False,
        )
        return self._canonicalize_date_fields(item, "deadline_on", "next_deadline_on")

    async def create_schedule(self, **fields: Any) -> dict[str, Any]:
        payload = await self._schedule_write("POST", "schedules.json", fields)
        if payload is None:
            self._raise_unidentified_create()
        return payload

    async def update_schedule(self, schedule_id: int, **fields: Any) -> dict[str, Any]:
        payload = await self._schedule_write("PUT", f"schedules/{schedule_id}.json", fields)
        if payload is None:
            return {"updated": True, "schedule_id": schedule_id}
        return payload

    async def _schedule_write(self, method: str, path: str, fields: Mapping[str, Any]) -> dict[str, Any] | None:
        wire_fields = self._upstream_date_fields(fields, "deadline_on")
        body = {f"schedule[{key}]": value for key, value in wire_fields.items() if value is not None}
        payload = await self._request(method, path, body=body)
        if payload is None:
            return None
        item = self._response_object(payload, "schedule", write=True)
        return self._canonicalize_date_fields(item, "deadline_on", "next_deadline_on")

    async def delete_schedule(self, schedule_id: int) -> bool:
        return bool(await self._request("DELETE", f"schedules/{schedule_id}.json", expect_json=False))

    async def mark_schedule_paid(self, schedule_id: int, date: str) -> bool:
        wire_date = self._upstream_date(date)
        return bool(
            await self._request("PUT", f"schedules/{schedule_id}/mark_as_payed/{wire_date}.json", expect_json=False)
        )

    async def mark_schedule_unpaid(self, schedule_id: int, date: str) -> bool:
        wire_date = self._upstream_date(date)
        return bool(
            await self._request(
                "PUT",
                f"schedules/{schedule_id}/mark_as_unpayed/{wire_date}.json",
                expect_json=False,
            )
        )

    async def get_wealth_points(self, start_on: str | None = None, end_on: str | None = None) -> list[dict[str, Any]]:
        query = self._upstream_date_fields({"start_on": start_on, "end_on": end_on}, "start_on", "end_on")
        payload = await self._request("GET", "wealth_points.json", query=query)
        items = self._expect_list(payload)
        return [
            self._canonicalize_date_fields(self._expect_dict(item.get("wealth_point", item)), "date_on")
            for item in items
        ]

    async def get_pie_chart(self, **filters: Any) -> dict[str, Any]:
        query = self._upstream_date_fields(filters, "start_on", "end_on")
        return self._expect_dict(await self._request("GET", "charts/money_transactions.json", query=query))

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

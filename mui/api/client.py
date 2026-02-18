"""Async Monday.com GraphQL client."""

from __future__ import annotations

from typing import Any

import httpx

API_URL = "https://api.monday.com/v2"


class MondayClient:
    def __init__(self, api_token: str) -> None:
        self._token = api_token
        self._http = httpx.AsyncClient(
            base_url=API_URL,
            headers={
                "Authorization": api_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def execute(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._http.post("", json=payload)
        if resp.status_code == 400:
            raise MondayApiError(
                f"400 Bad Request\n"
                f"Query: {query.strip()}\n"
                f"Variables: {variables}\n"
                f"Response: {resp.text}"
            )
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            msgs = [e.get("message", str(e)) for e in body["errors"]]
            raise MondayApiError("; ".join(msgs))
        return body["data"]

    async def close(self) -> None:
        await self._http.aclose()


class MondayApiError(Exception):
    pass

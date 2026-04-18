"""Async client for the Zotero Web API v3."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import DEFAULT_LIMIT, MAX_LIMIT, USER_AGENT, ZOTERO_API_BASE


class ZoteroError(Exception):
    """Raised when the Zotero API returns an error or the network fails."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


class ZoteroClient:
    """Read-only async client for a single Zotero user or group library."""

    def __init__(
        self,
        api_key: str,
        library_id: str,
        library_type: str = "user",
        api_base: str = ZOTERO_API_BASE,
    ) -> None:
        if library_type not in ("user", "group"):
            raise ValueError(
                f"library_type must be 'user' or 'group', got {library_type!r}"
            )
        self.api_key = api_key
        self.library_id = library_id
        self.library_type = library_type
        self.api_base = api_base.rstrip("/")
        prefix = "users" if library_type == "user" else "groups"
        self._library_prefix = f"{self.api_base}/{prefix}/{library_id}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Zotero-API-Key": self.api_key,
            "Zotero-API-Version": "3",
            "User-Agent": USER_AGENT,
        }

    async def _request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        """Make an authenticated GET request with retry on rate-limit and transient errors."""
        last_error: ZoteroError | None = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as http:
                    response = await http.get(
                        url, headers=self._headers, params=params, timeout=30.0
                    )
            except httpx.RequestError as exc:
                last_error = ZoteroError(0, f"Network error: {exc}")
                if attempt < 2:
                    await asyncio.sleep(1)
                continue

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                last_error = ZoteroError(429, "Rate limit exceeded after retries.")
                await asyncio.sleep(min(retry_after, 30))
                continue

            if response.status_code == 401:
                raise ZoteroError(
                    401,
                    "Invalid or missing Zotero API key. Check the ZOTERO_API_KEY environment variable.",
                )
            if response.status_code == 403:
                raise ZoteroError(
                    403,
                    "Access denied. Ensure your API key has read access to this library.",
                )
            if response.status_code == 404:
                raise ZoteroError(404, "Resource not found.")

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ZoteroError(
                    response.status_code,
                    f"HTTP error {response.status_code}.",
                ) from exc

            return response.json(), dict(response.headers)

        raise last_error or ZoteroError(0, "Request failed after all retries.")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_collections(
        self,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a page of top-level collections and the total count."""
        url = f"{self._library_prefix}/collections"
        data, headers = await self._request(
            url, {"start": start, "limit": min(limit, MAX_LIMIT)}
        )
        total = int(headers.get("total-results", len(data)))
        return data, total

    async def get_items(
        self,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        item_type: str | None = None,
        tag: str | None = None,
        sort: str = "dateModified",
        direction: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a page of library items with optional filtering."""
        url = f"{self._library_prefix}/items"
        params: dict[str, Any] = {
            "start": start,
            "limit": min(limit, MAX_LIMIT),
            "sort": sort,
            "direction": direction,
        }
        if item_type:
            params["itemType"] = item_type
        if tag:
            params["tag"] = tag
        data, headers = await self._request(url, params)
        total = int(headers.get("total-results", len(data)))
        return data, total

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """Return full data for a single item by key."""
        url = f"{self._library_prefix}/items/{item_key}"
        data, _ = await self._request(url)
        return data

    async def search_items(
        self,
        query: str,
        qmode: str = "everything",
        tag: str | None = None,
        item_type: str | None = None,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> tuple[list[dict[str, Any]], int]:
        """Full-text search across library items."""
        url = f"{self._library_prefix}/items"
        params: dict[str, Any] = {
            "q": query,
            "qmode": qmode,
            "start": start,
            "limit": min(limit, MAX_LIMIT),
        }
        if tag:
            params["tag"] = tag
        if item_type:
            params["itemType"] = item_type
        data, headers = await self._request(url, params)
        total = int(headers.get("total-results", len(data)))
        return data, total

    async def get_tags(
        self,
        start: int = 0,
        limit: int = MAX_LIMIT,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a page of tags used in the library."""
        url = f"{self._library_prefix}/tags"
        data, headers = await self._request(
            url, {"start": start, "limit": min(limit, MAX_LIMIT)}
        )
        total = int(headers.get("total-results", len(data)))
        return data, total

    async def get_item_children(
        self,
        item_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return child items (notes, attachments) of a given item."""
        url = f"{self._library_prefix}/items/{item_key}/children"
        data, headers = await self._request(
            url, {"start": start, "limit": min(limit, MAX_LIMIT)}
        )
        total = int(headers.get("total-results", len(data)))
        return data, total

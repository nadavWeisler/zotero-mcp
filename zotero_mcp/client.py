"""Async client for the Zotero Web API v3."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import (
    DEFAULT_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_LIMIT,
    MAX_RETRIES,
    MAX_RETRY_DELAY,
    ZOTERO_API_BASE,
)

logger = logging.getLogger(__name__)


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
        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Zotero-API-Key": self.api_key,
            "Zotero-API-Version": "3",
        }

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=DEFAULT_REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying shared HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "ZoteroClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def _error_detail(self, response: httpx.Response) -> str:
        raw_detail = response.text.strip()
        if not raw_detail:
            return ""
        normalized_detail = " ".join(raw_detail.split())
        if len(normalized_detail) > 200:
            truncated_detail = normalized_detail[:200] + "…"
        else:
            truncated_detail = normalized_detail
        return f" Details: {truncated_detail}"

    @staticmethod
    def _get_retry_after(response: httpx.Response) -> int:
        raw_value = response.headers.get("Retry-After", "5")
        try:
            return max(1, min(int(raw_value), MAX_RETRY_DELAY))
        except ValueError:
            return 5

    @staticmethod
    def _is_saved_search(collection: dict[str, Any]) -> bool:
        return bool(collection.get("data", {}).get("search"))

    async def _request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        extra_headers: dict[str, str] | None = None,
        response_type: str = "json",
    ) -> tuple[Any, dict[str, str]]:
        """Make an authenticated GET request with retry on transient errors."""
        last_error: ZoteroError | None = None

        for attempt in range(MAX_RETRIES):
            try:
                http = await self._get_http_client()
                response = await http.get(url, params=params, headers=extra_headers)
            except httpx.RequestError as exc:
                message = f"Network error while requesting Zotero: {exc}"
                last_error = ZoteroError(0, message)
                logger.warning(
                    "Zotero request failed on attempt %s/%s for %s: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, MAX_RETRY_DELAY))
                    continue
                break

            status_code = response.status_code
            if status_code == 429:
                retry_after = self._get_retry_after(response)
                message = (
                    "Rate limit exceeded while requesting Zotero."
                    f" Retry after approximately {retry_after} seconds."
                )
                last_error = ZoteroError(429, message)
                logger.warning(
                    "Zotero rate limit on attempt %s/%s for %s; retrying in %ss",
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    retry_after,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(retry_after)
                    continue
                break

            if status_code == 401:
                raise ZoteroError(
                    401,
                    "Invalid or missing Zotero API key."
                    " Check the ZOTERO_API_KEY environment variable."
                    + self._error_detail(response),
                )
            if status_code == 403:
                raise ZoteroError(
                    403,
                    "Access denied."
                    " Ensure your API key has read access to this library."
                    + self._error_detail(response),
                )
            if status_code == 404:
                raise ZoteroError(
                    404,
                    "Resource not found in the configured Zotero library."
                    + self._error_detail(response),
                )
            if 500 <= status_code < 600:
                message = (
                    f"Zotero API server error {status_code} while requesting {url}."
                    + self._error_detail(response)
                )
                last_error = ZoteroError(status_code, message)
                logger.warning(
                    "Zotero server error on attempt %s/%s for %s: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    status_code,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, MAX_RETRY_DELAY))
                    continue
                break

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ZoteroError(
                    status_code,
                    f"HTTP error {status_code} while requesting {url}."
                    + self._error_detail(response),
                ) from exc

            headers = dict(response.headers)
            if response_type == "text":
                return response.text, headers
            return response.json(), headers

        raise last_error or ZoteroError(0, "Request failed after all retries.")

    @staticmethod
    def _extract_total(headers: dict[str, str], data: Any) -> int:
        fallback_total = len(data) if isinstance(data, list) else 1
        return int(headers.get("total-results", fallback_total))

    async def _get_collections_page(
        self, start: int = 0, limit: int = DEFAULT_LIMIT
    ) -> tuple[list[dict[str, Any]], int]:
        url = f"{self._library_prefix}/collections"
        data, headers = await self._request(
            url, {"start": start, "limit": min(limit, MAX_LIMIT)}
        )
        return data, self._extract_total(headers, data)

    async def _get_all_collections(self) -> list[dict[str, Any]]:
        all_collections: list[dict[str, Any]] = []
        start = 0
        total = 1
        while start < total:
            page, total = await self._get_collections_page(start=start, limit=MAX_LIMIT)
            if not page:
                break
            all_collections.extend(page)
            start += len(page)
        return all_collections

    def _slice_page(
        self, items: list[dict[str, Any]], start: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        bounded_limit = min(limit, MAX_LIMIT)
        return items[start : start + bounded_limit], len(items)

    async def get_collections(
        self,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        *,
        include_saved_searches: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a page of top-level collections and the total count."""
        if include_saved_searches:
            return await self._get_collections_page(start=start, limit=limit)

        collections = [
            collection
            for collection in await self._get_all_collections()
            if not self._is_saved_search(collection)
        ]
        return self._slice_page(collections, start, limit)

    async def get_saved_searches(
        self, start: int = 0, limit: int = DEFAULT_LIMIT
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a page of saved searches exposed as Zotero collections."""
        collections = [
            collection
            for collection in await self._get_all_collections()
            if self._is_saved_search(collection)
        ]
        return self._slice_page(collections, start, limit)

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
        return data, self._extract_total(headers, data)

    async def get_collection_items(
        self,
        collection_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        sort: str = "dateModified",
        direction: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return items belonging to a Zotero collection or saved search."""
        url = f"{self._library_prefix}/collections/{collection_key}/items"
        params = {
            "start": start,
            "limit": min(limit, MAX_LIMIT),
            "sort": sort,
            "direction": direction,
        }
        data, headers = await self._request(url, params)
        return data, self._extract_total(headers, data)

    async def get_saved_search_items(
        self,
        search_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        sort: str = "dateModified",
        direction: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Return items matching a saved search."""
        return await self.get_collection_items(
            search_key,
            start=start,
            limit=limit,
            sort=sort,
            direction=direction,
        )

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """Return full data for a single item by key."""
        url = f"{self._library_prefix}/items/{item_key}"
        data, _ = await self._request(url)
        return data

    async def get_note(self, item_key: str) -> dict[str, Any]:
        """Return a note item and validate its type."""
        item = await self.get_item(item_key)
        if item.get("data", {}).get("itemType") != "note":
            raise ZoteroError(400, f"Item {item_key!r} is not a note.")
        return item

    async def get_attachment(self, item_key: str) -> dict[str, Any]:
        """Return an attachment item and validate its type."""
        item = await self.get_item(item_key)
        if item.get("data", {}).get("itemType") != "attachment":
            raise ZoteroError(400, f"Item {item_key!r} is not an attachment.")
        return item

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
        return data, self._extract_total(headers, data)

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
        return data, self._extract_total(headers, data)

    async def get_item_children(
        self,
        item_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        item_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return child items (notes, attachments) of a given item."""
        url = f"{self._library_prefix}/items/{item_key}/children"
        params: dict[str, Any] = {"start": start, "limit": min(limit, MAX_LIMIT)}
        if item_type:
            params["itemType"] = item_type
        data, headers = await self._request(url, params)
        return data, self._extract_total(headers, data)

    async def get_item_citation(
        self,
        item_key: str,
        style: str = "apa",
        locale: str | None = None,
        linkwrap: bool = False,
    ) -> str:
        """Return a formatted citation for a single item."""
        url = f"{self._library_prefix}/items/{item_key}"
        params: dict[str, Any] = {"format": "citation", "style": style}
        if locale:
            params["locale"] = locale
        if linkwrap:
            params["linkwrap"] = 1
        data, _ = await self._request(url, params, response_type="text")
        return data.strip()

    async def export_item(
        self,
        item_key: str,
        export_format: str = "bibtex",
    ) -> str:
        """Return an item exported in a bibliographic format."""
        url = f"{self._library_prefix}/items/{item_key}"
        data, _ = await self._request(
            url,
            {"format": export_format},
            response_type="text",
        )
        return data.strip()

"""Unit tests for ZoteroClient — request building, response parsing, error handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zotero_mcp.client import ZoteroClient, ZoteroError
from zotero_mcp.config import ZOTERO_API_BASE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    data: Any,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {
        "total-results": str(len(data) if isinstance(data, list) else 1)
    }
    response.json = MagicMock(return_value=data)
    if status_code >= 400:
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        )
    else:
        response.raise_for_status = MagicMock()
    return response


def _patch_httpx(response: MagicMock):
    """Return a context manager that patches httpx.AsyncClient to return *response*."""
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=response)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_http)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    return patch("httpx.AsyncClient", return_value=mock_ctx), mock_http


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_user_library_prefix() -> None:
    client = ZoteroClient(api_key="key", library_id="123")
    assert client._library_prefix == f"{ZOTERO_API_BASE}/users/123"


def test_group_library_prefix() -> None:
    client = ZoteroClient(api_key="key", library_id="456", library_type="group")
    assert client._library_prefix == f"{ZOTERO_API_BASE}/groups/456"


def test_invalid_library_type_raises() -> None:
    with pytest.raises(ValueError, match="library_type"):
        ZoteroClient(api_key="key", library_id="1", library_type="invalid")


def test_custom_api_base_trailing_slash() -> None:
    client = ZoteroClient(
        api_key="key", library_id="1", api_base="https://example.com/"
    )
    assert client.api_base == "https://example.com"


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


def test_headers_contain_api_key() -> None:
    client = ZoteroClient(api_key="my-secret-key", library_id="1")
    assert client._headers["Zotero-API-Key"] == "my-secret-key"
    assert client._headers["Zotero-API-Version"] == "3"


# ---------------------------------------------------------------------------
# get_collections
# ---------------------------------------------------------------------------


async def test_get_collections_success() -> None:
    data = [{"key": "ABC123", "data": {"name": "My Collection"}}]
    response = _make_response(data, headers={"total-results": "5"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        cols, total = await client.get_collections()

    assert total == 5
    assert cols == data
    # Verify request URL contains "collections"
    call_url = mock_http.get.call_args[0][0]
    assert call_url.endswith("/collections")


async def test_get_collections_pagination_params() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_collections(start=50, limit=10)

    params = mock_http.get.call_args[1]["params"]
    assert params["start"] == 50
    assert params["limit"] == 10


async def test_get_collections_limit_capped_at_max() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_collections(limit=999)

    params = mock_http.get.call_args[1]["params"]
    assert params["limit"] == 100  # MAX_LIMIT


# ---------------------------------------------------------------------------
# get_items
# ---------------------------------------------------------------------------


async def test_get_items_default_sort() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_items()

    params = mock_http.get.call_args[1]["params"]
    assert params["sort"] == "dateModified"
    assert params["direction"] == "desc"


async def test_get_items_with_filters() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_items(item_type="book", tag="science")

    params = mock_http.get.call_args[1]["params"]
    assert params["itemType"] == "book"
    assert params["tag"] == "science"


async def test_get_items_none_filters_excluded() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_items(item_type=None, tag=None)

    params = mock_http.get.call_args[1]["params"]
    assert "itemType" not in params
    assert "tag" not in params


# ---------------------------------------------------------------------------
# get_item
# ---------------------------------------------------------------------------


async def test_get_item_builds_correct_url() -> None:
    item_data = {"key": "AAAA1234", "data": {"title": "Test"}}
    response = _make_response(item_data)
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        result = await client.get_item("AAAA1234")

    assert result == item_data
    call_url = mock_http.get.call_args[0][0]
    assert call_url.endswith("/items/AAAA1234")


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------


async def test_search_items_passes_query_params() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.search_items(
            query="machine learning",
            qmode="titleCreatorYear",
            tag="AI",
            item_type="journalArticle",
        )

    params = mock_http.get.call_args[1]["params"]
    assert params["q"] == "machine learning"
    assert params["qmode"] == "titleCreatorYear"
    assert params["tag"] == "AI"
    assert params["itemType"] == "journalArticle"


# ---------------------------------------------------------------------------
# get_tags
# ---------------------------------------------------------------------------


async def test_get_tags_returns_data_and_total() -> None:
    tags = [{"tag": "physics", "meta": {"numItems": 3}}]
    response = _make_response(tags, headers={"total-results": "1"})
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        result, total = await client.get_tags()

    assert result == tags
    assert total == 1


# ---------------------------------------------------------------------------
# get_item_children
# ---------------------------------------------------------------------------


async def test_get_item_children_url() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_item_children("AAAA1234")

    call_url = mock_http.get.call_args[0][0]
    assert call_url.endswith("/items/AAAA1234/children")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


async def test_401_raises_zotero_error() -> None:
    response = _make_response({}, status_code=401)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="bad-key", library_id="1")
        with pytest.raises(ZoteroError) as exc_info:
            await client.get_collections()

    assert exc_info.value.status_code == 401
    assert "ZOTERO_API_KEY" in str(exc_info.value)


async def test_403_raises_zotero_error() -> None:
    response = _make_response({}, status_code=403)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError) as exc_info:
            await client.get_items()

    assert exc_info.value.status_code == 403


async def test_404_raises_zotero_error() -> None:
    response = _make_response({}, status_code=404)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError) as exc_info:
            await client.get_item("MISSING1")

    assert exc_info.value.status_code == 404


async def test_429_retries_then_raises() -> None:
    """A persistent 429 should be retried up to 3 times then raise ZoteroError."""
    response = _make_response({}, status_code=429, headers={"Retry-After": "0"})

    call_count = 0
    mock_http = AsyncMock()

    async def counting_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return response

    mock_http.get = counting_get

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_http)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError) as exc_info:
            await client.get_collections()

    assert exc_info.value.status_code == 429
    assert call_count == 3


async def test_network_error_retries_then_raises() -> None:
    """A persistent network error should be retried and then raise ZoteroError."""
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_http)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            client = ZoteroClient(api_key="k", library_id="1")
            with pytest.raises(ZoteroError) as exc_info:
                await client.get_collections()

    assert "Network error" in str(exc_info.value)


async def test_total_results_falls_back_to_data_length() -> None:
    """If the Total-Results header is absent, fall back to len(data)."""
    data = [{"key": "A"}, {"key": "B"}]
    response = _make_response(data, headers={})  # no total-results header
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        cols, total = await client.get_collections()

    assert total == 2

"""Unit tests for ZoteroClient — request building, retries, and filtering."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zotero_mcp.client import ZoteroClient, ZoteroError
from zotero_mcp.config import ZOTERO_API_BASE


def _make_response(
    data: Any,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    text: str = "",
) -> MagicMock:
    """Build a mock httpx response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {
        "total-results": str(len(data) if isinstance(data, list) else 1)
    }
    response.json = MagicMock(return_value=data)
    response.text = text
    if status_code >= 400:
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        )
    else:
        response.raise_for_status = MagicMock()
    return response


def _patch_httpx(
    response_or_side_effect: Any,
) -> tuple[Any, AsyncMock]:
    """Patch httpx.AsyncClient with a reusable AsyncMock instance."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.aclose = AsyncMock()
    if isinstance(response_or_side_effect, list):
        mock_http.get.side_effect = response_or_side_effect
    else:
        mock_http.get.return_value = response_or_side_effect
    return patch("httpx.AsyncClient", return_value=mock_http), mock_http


def _collection(key: str, *, search: bool = False) -> dict[str, Any]:
    return {
        "data": {
            "key": key,
            "name": key,
            "search": search,
        }
    }


def _item(key: str = "ITEM0001", item_type: str = "journalArticle") -> dict[str, Any]:
    return {
        "data": {
            "key": key,
            "itemType": item_type,
            "title": "Example",
        }
    }


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


def test_headers_contain_api_key() -> None:
    client = ZoteroClient(api_key="my-secret-key", library_id="1")
    assert client._headers["Zotero-API-Key"] == "my-secret-key"
    assert client._headers["Zotero-API-Version"] == "3"


async def test_get_http_client_reused_until_closed() -> None:
    response = _make_response([])
    patcher, mock_http = _patch_httpx(response)

    with patcher as async_client_ctor:
        client = ZoteroClient(api_key="k", library_id="1")
        first = await client._get_http_client()
        second = await client._get_http_client()

    assert first is second is mock_http
    async_client_ctor.assert_called_once()


async def test_close_shared_client() -> None:
    response = _make_response([])
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client._get_http_client()
        await client.close()

    mock_http.aclose.assert_awaited_once()


async def test_get_collections_filters_out_saved_searches_by_default() -> None:
    data = [_collection("COLL0001"), _collection("SRCH0001", search=True)]
    response = _make_response(data, headers={"total-results": "2"})
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        collections, total = await client.get_collections()

    assert total == 1
    assert [collection["data"]["key"] for collection in collections] == ["COLL0001"]


async def test_get_saved_searches_filters_search_collections() -> None:
    data = [_collection("COLL0001"), _collection("SRCH0001", search=True)]
    response = _make_response(data, headers={"total-results": "2"})
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        searches, total = await client.get_saved_searches()

    assert total == 1
    assert [search["data"]["key"] for search in searches] == ["SRCH0001"]


async def test_get_collections_can_include_saved_searches() -> None:
    data = [_collection("COLL0001"), _collection("SRCH0001", search=True)]
    response = _make_response(data, headers={"total-results": "2"})
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        collections, total = await client.get_collections(include_saved_searches=True)

    assert total == 2
    assert len(collections) == 2


async def test_get_items_default_sort() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_items()

    params = mock_http.get.call_args.kwargs["params"]
    assert params["sort"] == "dateModified"
    assert params["direction"] == "desc"


async def test_get_collection_items_builds_correct_url() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_collection_items("COLL0001")

    call_url = mock_http.get.call_args.args[0]
    assert call_url.endswith("/collections/COLL0001/items")


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

    params = mock_http.get.call_args.kwargs["params"]
    assert params["q"] == "machine learning"
    assert params["qmode"] == "titleCreatorYear"
    assert params["tag"] == "AI"
    assert params["itemType"] == "journalArticle"


async def test_get_item_children_item_type_filter() -> None:
    response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        await client.get_item_children("AAAA1234", item_type="note")

    params = mock_http.get.call_args.kwargs["params"]
    assert params["itemType"] == "note"


async def test_get_note_validates_item_type() -> None:
    response = _make_response(_item(item_type="attachment"))
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="is not a note"):
            await client.get_note("ATT0001")


async def test_get_attachment_validates_item_type() -> None:
    response = _make_response(_item(item_type="note"))
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="is not an attachment"):
            await client.get_attachment("NOTE0001")


async def test_get_item_citation_uses_format_params() -> None:
    response = _make_response({}, text="Citation text")
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        citation = await client.get_item_citation(
            "ITEM0001", style="mla", locale="en-GB", linkwrap=True
        )

    assert citation == "Citation text"
    params = mock_http.get.call_args.kwargs["params"]
    assert params == {
        "format": "citation",
        "style": "mla",
        "locale": "en-GB",
        "linkwrap": 1,
    }


async def test_export_item_uses_requested_format() -> None:
    response = _make_response({}, text="@article{example}")
    patcher, mock_http = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        export_text = await client.export_item("ITEM0001", export_format="bibtex")

    assert export_text == "@article{example}"
    params = mock_http.get.call_args.kwargs["params"]
    assert params == {"format": "bibtex"}


async def test_401_raises_zotero_error() -> None:
    response = _make_response({}, status_code=401)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="bad-key", library_id="1")
        with pytest.raises(ZoteroError, match="Invalid or missing Zotero API key"):
            await client.get_items()


async def test_403_raises_zotero_error() -> None:
    response = _make_response({}, status_code=403)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="Access denied"):
            await client.get_items()


async def test_404_raises_zotero_error() -> None:
    response = _make_response({}, status_code=404)
    patcher, _ = _patch_httpx(response)

    with patcher:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="Resource not found"):
            await client.get_item("MISSING1")


async def test_429_retries_then_raises() -> None:
    response = _make_response({}, status_code=429, headers={"Retry-After": "1"})
    patcher, mock_http = _patch_httpx([response, response, response])

    with patcher, patch("zotero_mcp.client.asyncio.sleep", new=AsyncMock()) as sleep:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="Rate limit exceeded"):
            await client.get_items()

    assert mock_http.get.await_count == 3
    assert sleep.await_count == 2


async def test_server_error_retries_then_succeeds() -> None:
    retry_response = _make_response({}, status_code=500)
    success_response = _make_response([], headers={"total-results": "0"})
    patcher, mock_http = _patch_httpx([retry_response, success_response])

    with patcher, patch("zotero_mcp.client.asyncio.sleep", new=AsyncMock()) as sleep:
        client = ZoteroClient(api_key="k", library_id="1")
        items, total = await client.get_items()

    assert items == []
    assert total == 0
    assert mock_http.get.await_count == 2
    sleep.assert_awaited_once()


async def test_network_error_retries_then_raises() -> None:
    request = MagicMock(spec=httpx.Request)
    error = httpx.RequestError("boom", request=request)
    patcher, mock_http = _patch_httpx([error, error, error])

    with patcher, patch("zotero_mcp.client.asyncio.sleep", new=AsyncMock()) as sleep:
        client = ZoteroClient(api_key="k", library_id="1")
        with pytest.raises(ZoteroError, match="Network error"):
            await client.get_items()

    assert mock_http.get.await_count == 3
    assert sleep.await_count == 2

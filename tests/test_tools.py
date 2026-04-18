"""Integration-style tests for MCP tool logic.

Each tool's internal function (``_list_collections``, etc.) is called directly
with a mock ``ZoteroClient`` so we can verify end-to-end output formatting and
error handling without running FastMCP.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.client import ZoteroClient, ZoteroError
from zotero_mcp.tools import (
    _get_item,
    _get_item_children,
    _list_collections,
    _list_items,
    _list_tags,
    _search_items,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_client() -> ZoteroClient:
    """Return a real ZoteroClient that has all API methods replaced with AsyncMocks."""
    client = ZoteroClient(api_key="test-key", library_id="123456")
    client.get_collections = AsyncMock()
    client.get_items = AsyncMock()
    client.get_item = AsyncMock()
    client.search_items = AsyncMock()
    client.get_tags = AsyncMock()
    client.get_item_children = AsyncMock()
    return client


def _item(key: str = "AAAA0001", title: str = "Test Item") -> dict:
    return {
        "data": {
            "key": key,
            "itemType": "journalArticle",
            "title": title,
            "creators": [{"lastName": "Doe", "firstName": "Jane"}],
            "date": "2024-01-01",
            "tags": [{"tag": "research"}],
            "abstractNote": "",
        }
    }


def _collection(key: str = "COLL0001", name: str = "My Coll") -> dict:
    return {
        "data": {"key": key, "name": name, "parentCollection": False},
        "meta": {"numItems": 5},
    }


def _tag(name: str = "science", n: int = 3) -> dict:
    return {"tag": name, "meta": {"numItems": n}}


def _child(key: str = "CHLD0001", item_type: str = "note") -> dict:
    return {
        "data": {
            "key": key,
            "itemType": item_type,
            "note": "<p>A note.</p>" if item_type == "note" else "",
            "title": "" if item_type == "note" else "attachment.pdf",
        }
    }


# ---------------------------------------------------------------------------
# list_collections
# ---------------------------------------------------------------------------


async def test_list_collections_returns_formatted_output() -> None:
    client = _make_client()
    client.get_collections.return_value = ([_collection()], 1)

    result = await _list_collections(client)

    assert "COLL0001" in result
    assert "My Coll" in result
    assert "Showing" in result


async def test_list_collections_empty_library() -> None:
    client = _make_client()
    client.get_collections.return_value = ([], 0)

    result = await _list_collections(client)

    assert "No collections" in result


async def test_list_collections_shows_paging_hint_when_more() -> None:
    client = _make_client()
    client.get_collections.return_value = ([_collection()], 50)

    result = await _list_collections(client, start=0, limit=1)

    assert "next page" in result or "start=1" in result


async def test_list_collections_error_propagated() -> None:
    client = _make_client()
    client.get_collections.side_effect = ZoteroError(401, "Unauthorized")

    result = await _list_collections(client)

    assert "Error" in result
    assert "Unauthorized" in result


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_items_returns_items() -> None:
    client = _make_client()
    client.get_items.return_value = ([_item()], 1)

    result = await _list_items(client)

    assert "AAAA0001" in result
    assert "Test Item" in result


async def test_list_items_empty() -> None:
    client = _make_client()
    client.get_items.return_value = ([], 0)

    result = await _list_items(client)

    assert "No items" in result


async def test_list_items_passes_filters_to_client() -> None:
    client = _make_client()
    client.get_items.return_value = ([], 0)

    await _list_items(client, item_type="book", tag="ai", sort="title", direction="asc")

    client.get_items.assert_called_once_with(
        start=0,
        limit=25,
        item_type="book",
        tag="ai",
        sort="title",
        direction="asc",
    )


async def test_list_items_empty_string_filters_become_none() -> None:
    """Empty string item_type/tag should be passed to the client as None."""
    client = _make_client()
    client.get_items.return_value = ([], 0)

    await _list_items(client, item_type="", tag="")

    kwargs = client.get_items.call_args[1]
    assert kwargs["item_type"] is None
    assert kwargs["tag"] is None


async def test_list_items_error_propagated() -> None:
    client = _make_client()
    client.get_items.side_effect = ZoteroError(403, "Forbidden")

    result = await _list_items(client)

    assert "Error" in result
    assert "Forbidden" in result


# ---------------------------------------------------------------------------
# get_item
# ---------------------------------------------------------------------------


async def test_get_item_returns_formatted_item() -> None:
    client = _make_client()
    client.get_item.return_value = _item(key="AAAA1234", title="Great Book")

    result = await _get_item(client, "AAAA1234")

    assert "AAAA1234" in result
    assert "Great Book" in result


async def test_get_item_expanded_includes_abstract() -> None:
    client = _make_client()
    item = _item()
    item["data"]["abstractNote"] = "This is the abstract."
    client.get_item.return_value = item

    result = await _get_item(client, "AAAA0001", expanded=True)

    assert "Abstract" in result
    assert "This is the abstract." in result


async def test_get_item_not_found_returns_error() -> None:
    client = _make_client()
    client.get_item.side_effect = ZoteroError(404, "Resource not found.")

    result = await _get_item(client, "MISSING1")

    assert "Error" in result
    assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# search_items
# ---------------------------------------------------------------------------


async def test_search_items_returns_matching_items() -> None:
    client = _make_client()
    client.search_items.return_value = ([_item(title="AI paper")], 1)

    result = await _search_items(client, query="AI")

    assert "AI paper" in result


async def test_search_items_no_results() -> None:
    client = _make_client()
    client.search_items.return_value = ([], 0)

    result = await _search_items(client, query="xyzzy")

    assert "xyzzy" in result
    assert "No items" in result


async def test_search_items_passes_all_params() -> None:
    client = _make_client()
    client.search_items.return_value = ([], 0)

    await _search_items(
        client,
        query="neural networks",
        qmode="titleCreatorYear",
        tag="ml",
        item_type="journalArticle",
        start=10,
        limit=5,
    )

    client.search_items.assert_called_once_with(
        query="neural networks",
        qmode="titleCreatorYear",
        tag="ml",
        item_type="journalArticle",
        start=10,
        limit=5,
    )


async def test_search_items_empty_optional_strings_become_none() -> None:
    client = _make_client()
    client.search_items.return_value = ([], 0)

    await _search_items(client, query="test", tag="", item_type="")

    kwargs = client.search_items.call_args[1]
    assert kwargs["tag"] is None
    assert kwargs["item_type"] is None


async def test_search_items_paging_shows_next_hint() -> None:
    client = _make_client()
    items = [_item(key=f"KEY{i:04d}", title=f"Item {i}") for i in range(5)]
    client.search_items.return_value = (items, 100)

    result = await _search_items(client, query="topic", start=0, limit=5)

    assert "start=5" in result


# ---------------------------------------------------------------------------
# list_tags
# ---------------------------------------------------------------------------


async def test_list_tags_returns_tags() -> None:
    client = _make_client()
    client.get_tags.return_value = ([_tag("physics", 10), _tag("chemistry", 4)], 2)

    result = await _list_tags(client)

    assert "physics" in result
    assert "chemistry" in result
    assert "10" in result


async def test_list_tags_empty() -> None:
    client = _make_client()
    client.get_tags.return_value = ([], 0)

    result = await _list_tags(client)

    assert "No tags" in result


async def test_list_tags_error() -> None:
    client = _make_client()
    client.get_tags.side_effect = ZoteroError(429, "Rate limit exceeded after retries.")

    result = await _list_tags(client)

    assert "Error" in result
    assert "Rate limit" in result


# ---------------------------------------------------------------------------
# get_item_children
# ---------------------------------------------------------------------------


async def test_get_item_children_returns_children() -> None:
    client = _make_client()
    client.get_item_children.return_value = (
        [_child("NOTE0001", "note"), _child("ATT00001", "attachment")],
        2,
    )

    result = await _get_item_children(client, "PARENT01")

    assert "[note]" in result
    assert "[attachment]" in result


async def test_get_item_children_no_children() -> None:
    client = _make_client()
    client.get_item_children.return_value = ([], 0)

    result = await _get_item_children(client, "PARENT01")

    assert "no child" in result.lower()
    assert "PARENT01" in result


async def test_get_item_children_paging() -> None:
    client = _make_client()
    children = [_child(f"NOTE{i:04d}") for i in range(5)]
    client.get_item_children.return_value = (children, 20)

    result = await _get_item_children(client, "PARENT01", start=0, limit=5)

    assert "start=5" in result


async def test_get_item_children_error() -> None:
    client = _make_client()
    client.get_item_children.side_effect = ZoteroError(404, "Resource not found.")

    result = await _get_item_children(client, "MISSING1")

    assert "Error" in result
    assert "not found" in result.lower()

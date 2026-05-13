"""Integration-style tests for MCP tool logic."""

from __future__ import annotations

from unittest.mock import AsyncMock

from zotero_mcp.client import ZoteroClient, ZoteroError
from zotero_mcp.tools import (
    _export_item,
    _get_attachment,
    _get_item,
    _get_item_children,
    _get_item_citation,
    _get_note,
    _list_collection_items,
    _list_collections,
    _list_items,
    _list_saved_search_items,
    _list_saved_searches,
    _list_tags,
    _search_items,
)


def _make_client() -> ZoteroClient:
    client = ZoteroClient(api_key="test-key", library_id="123456")
    client.get_collections = AsyncMock()
    client.get_saved_searches = AsyncMock()
    client.get_items = AsyncMock()
    client.get_collection_items = AsyncMock()
    client.get_saved_search_items = AsyncMock()
    client.get_item = AsyncMock()
    client.get_note = AsyncMock()
    client.get_attachment = AsyncMock()
    client.search_items = AsyncMock()
    client.get_tags = AsyncMock()
    client.get_item_children = AsyncMock()
    client.get_item_citation = AsyncMock()
    client.export_item = AsyncMock()
    return client


def _item(key: str = "AAAA0001", title: str = "Test Item", item_type: str = "journalArticle") -> dict:
    return {
        "data": {
            "key": key,
            "itemType": item_type,
            "title": title,
            "creators": [{"lastName": "Doe", "firstName": "Jane"}],
            "date": "2024-01-01",
            "tags": [{"tag": "research"}],
            "abstractNote": "Short abstract.",
        }
    }


def _collection(key: str = "COLL0001", name: str = "My Coll", *, search: bool = False) -> dict:
    return {
        "data": {"key": key, "name": name, "parentCollection": False, "search": search},
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
            "filename": "attachment.pdf" if item_type == "attachment" else "",
            "contentType": "application/pdf" if item_type == "attachment" else "",
        }
    }


async def test_list_collections_returns_formatted_output() -> None:
    client = _make_client()
    client.get_collections.return_value = ([_collection()], 1)

    result = await _list_collections(client)

    assert "COLL0001" in result
    assert "My Coll" in result
    assert "Showing" in result


async def test_list_collections_returns_json() -> None:
    client = _make_client()
    client.get_collections.return_value = ([_collection()], 1)

    result = await _list_collections(client, output_format="json")

    assert result["collections"][0]["key"] == "COLL0001"
    assert result["paging"]["total"] == 1


async def test_list_saved_searches_returns_saved_searches() -> None:
    client = _make_client()
    client.get_saved_searches.return_value = ([_collection(search=True)], 1)

    result = await _list_saved_searches(client)

    assert "Saved search" in result


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


async def test_list_items_returns_json_with_filters() -> None:
    client = _make_client()
    client.get_items.return_value = ([_item()], 1)

    result = await _list_items(client, output_format="json")

    assert result["items"][0]["key"] == "AAAA0001"
    assert result["filters"]["sort"] == "dateModified"


async def test_list_items_invalid_sort_returns_error() -> None:
    client = _make_client()

    result = await _list_items(client, sort="bad-sort")

    assert "Error" in result
    assert "sort must be one of" in result


async def test_list_collection_items_uses_collection_client_method() -> None:
    client = _make_client()
    client.get_collection_items.return_value = ([_item()], 1)

    result = await _list_collection_items(client, "COLL0001")

    assert "Test Item" in result
    client.get_collection_items.assert_called_once()


async def test_list_saved_search_items_uses_saved_search_client_method() -> None:
    client = _make_client()
    client.get_saved_search_items.return_value = ([_item(title="Saved Search Item")], 1)

    result = await _list_saved_search_items(client, "SRCH0001")

    assert "Saved Search Item" in result


async def test_get_item_returns_json() -> None:
    client = _make_client()
    client.get_item.return_value = _item(key="AAAA1234", title="Great Book")

    result = await _get_item(client, "AAAA1234", expanded=True, output_format="json")

    assert result["item"]["key"] == "AAAA1234"
    assert result["item"]["abstract"] == "Short abstract."


async def test_get_note_returns_formatted_note() -> None:
    client = _make_client()
    client.get_note.return_value = {
        "data": {"key": "NOTE0001", "itemType": "note", "note": "<p>Important note.</p>"}
    }

    result = await _get_note(client, "NOTE0001")

    assert "Important note." in result


async def test_get_attachment_returns_json() -> None:
    client = _make_client()
    client.get_attachment.return_value = {
        "data": {
            "key": "ATT0001",
            "itemType": "attachment",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
        }
    }

    result = await _get_attachment(client, "ATT0001", output_format="json")

    assert result["attachment"]["filename"] == "paper.pdf"


async def test_search_items_paging_shows_next_hint() -> None:
    client = _make_client()
    items = [_item(key=f"KEY{i:04d}", title=f"Item {i}") for i in range(5)]
    client.search_items.return_value = (items, 100)

    result = await _search_items(client, query="topic", start=0, limit=5)

    assert "start=5" in result


async def test_list_tags_returns_json() -> None:
    client = _make_client()
    client.get_tags.return_value = ([_tag("physics", 10), _tag("chemistry", 4)], 2)

    result = await _list_tags(client, output_format="json")

    assert result["tags"][0]["name"] == "physics"
    assert result["paging"]["total"] == 2


async def test_get_item_children_supports_filter_and_json() -> None:
    client = _make_client()
    client.get_item_children.return_value = ([_child("NOTE0001", "note")], 1)

    result = await _get_item_children(
        client, "PARENT01", item_type="note", output_format="json"
    )

    assert result["children"][0]["kind"] == "note"
    assert result["filter"] == "note"


async def test_get_item_children_error() -> None:
    client = _make_client()
    client.get_item_children.side_effect = ZoteroError(404, "Resource not found.")

    result = await _get_item_children(client, "MISSING1")

    assert "Error" in result
    assert "not found" in result.lower()


async def test_get_item_citation_returns_json() -> None:
    client = _make_client()
    client.get_item_citation.return_value = "Doe, J. (2024). Test Item."

    result = await _get_item_citation(client, "AAAA0001", output_format="json")

    assert result["citation"] == "Doe, J. (2024). Test Item."
    assert result["style"] == "apa"


async def test_export_item_returns_text_preview() -> None:
    client = _make_client()
    client.export_item.return_value = "@article{test}"

    result = await _export_item(client, "AAAA0001", export_format="bibtex")

    assert "Format: bibtex" in result
    assert "@article" in result


async def test_export_item_rejects_unknown_format() -> None:
    client = _make_client()

    result = await _export_item(client, "AAAA0001", export_format="invalid")

    assert "Error" in result
    assert "export_format must be one of" in result

"""End-to-end tests for FastMCP tool registration."""

from __future__ import annotations

import json

import pytest
from mcp.server.fastmcp import FastMCP

from zotero_mcp.tools import register_tools


class StubClient:
    async def get_collections(self, **_: object):
        return ([{"data": {"key": "COLL0001", "name": "Collection"}}], 1)

    async def get_saved_searches(self, **_: object):
        return ([{"data": {"key": "SRCH0001", "name": "Recent", "search": True}}], 1)

    async def get_items(self, **_: object):
        return ([{"data": {"key": "ITEM0001", "itemType": "book", "title": "Book"}}], 1)

    async def get_collection_items(self, **_: object):
        return ([{"data": {"key": "ITEM0002", "itemType": "book", "title": "In Collection"}}], 1)

    async def get_saved_search_items(self, **_: object):
        return ([{"data": {"key": "ITEM0003", "itemType": "book", "title": "In Search"}}], 1)

    async def get_item(self, _: str):
        return {"data": {"key": "ITEM0001", "itemType": "book", "title": "Book"}}

    async def get_note(self, _: str):
        return {"data": {"key": "NOTE0001", "itemType": "note", "note": "<p>Note</p>"}}

    async def get_attachment(self, _: str):
        return {
            "data": {
                "key": "ATT0001",
                "itemType": "attachment",
                "filename": "paper.pdf",
            }
        }

    async def search_items(self, **_: object):
        return ([{"data": {"key": "ITEM0004", "itemType": "book", "title": "Found"}}], 1)

    async def get_tags(self, **_: object):
        return ([{"tag": "ai", "meta": {"numItems": 1}}], 1)

    async def get_item_children(self, *_: object, **__: object):
        return ([{"data": {"key": "NOTE0002", "itemType": "note", "note": "<p>Child</p>"}}], 1)

    async def get_item_citation(self, **_: object):
        return "Doe. Book."

    async def export_item(self, **_: object):
        return "@book{demo}"


@pytest.mark.asyncio
async def test_register_tools_exposes_new_tool_set() -> None:
    mcp = FastMCP("zotero")
    client = StubClient()
    register_tools(mcp, client)

    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)

    assert names == [
        "export_item",
        "get_attachment",
        "get_item",
        "get_item_children",
        "get_item_citation",
        "get_note",
        "list_collection_items",
        "list_collections",
        "list_items",
        "list_saved_search_items",
        "list_saved_searches",
        "list_tags",
        "search_items",
    ]


@pytest.mark.asyncio
async def test_registered_tool_returns_structured_json_text_block() -> None:
    mcp = FastMCP("zotero")
    client = StubClient()
    register_tools(mcp, client)

    content, _ = await mcp.call_tool("list_saved_searches", {"output_format": "json"})

    payload = json.loads(content[0].text)
    assert payload["saved_searches"][0]["key"] == "SRCH0001"
    assert payload["paging"]["total"] == 1


@pytest.mark.asyncio
async def test_registered_tool_returns_text_output() -> None:
    mcp = FastMCP("zotero")
    client = StubClient()
    register_tools(mcp, client)

    content, _ = await mcp.call_tool("export_item", {"item_key": "ITEM0001"})

    assert "Format: bibtex" in content[0].text
    assert "@book{demo}" in content[0].text

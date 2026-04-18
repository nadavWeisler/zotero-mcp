"""MCP tool implementations for the Zotero library.

Each tool is implemented as a module-level async function (prefixed with ``_``)
so it can be called directly in tests.  ``register_tools`` wraps each one in a
FastMCP ``@mcp.tool()`` decorator and binds it to a specific ``ZoteroClient``
instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .client import ZoteroClient, ZoteroError
from .formatters import (
    format_child,
    format_collection,
    format_item,
    format_tag,
    paging_hint,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Internal implementations (testable without FastMCP)
# ---------------------------------------------------------------------------


async def _list_collections(
    client: ZoteroClient,
    start: int = 0,
    limit: int = 25,
) -> str:
    try:
        collections, total = await client.get_collections(start=start, limit=limit)
    except ZoteroError as exc:
        return f"Error: {exc}"

    if not collections:
        return "No collections found."

    hint = paging_hint(start, len(collections), total, "collections")
    blocks = [format_collection(col) for col in collections]
    return hint + "\n\n" + "\n---\n".join(blocks)


async def _list_items(
    client: ZoteroClient,
    start: int = 0,
    limit: int = 25,
    item_type: str = "",
    tag: str = "",
    sort: str = "dateModified",
    direction: str = "desc",
) -> str:
    try:
        items, total = await client.get_items(
            start=start,
            limit=limit,
            item_type=item_type or None,
            tag=tag or None,
            sort=sort,
            direction=direction,
        )
    except ZoteroError as exc:
        return f"Error: {exc}"

    if not items:
        return "No items found."

    hint = paging_hint(start, len(items), total, "items")
    blocks = [format_item(item) for item in items]
    return hint + "\n\n" + "\n---\n".join(blocks)


async def _get_item(
    client: ZoteroClient,
    item_key: str,
    expanded: bool = False,
) -> str:
    try:
        item = await client.get_item(item_key)
    except ZoteroError as exc:
        return f"Error: {exc}"

    return format_item(item, expanded=expanded)


async def _search_items(
    client: ZoteroClient,
    query: str,
    qmode: str = "everything",
    tag: str = "",
    item_type: str = "",
    start: int = 0,
    limit: int = 25,
) -> str:
    try:
        items, total = await client.search_items(
            query=query,
            qmode=qmode,
            tag=tag or None,
            item_type=item_type or None,
            start=start,
            limit=limit,
        )
    except ZoteroError as exc:
        return f"Error: {exc}"

    if not items:
        return f"No items found matching {query!r}."

    hint = paging_hint(start, len(items), total, "results")
    blocks = [format_item(item) for item in items]
    return hint + "\n\n" + "\n---\n".join(blocks)


async def _list_tags(
    client: ZoteroClient,
    start: int = 0,
    limit: int = 100,
) -> str:
    try:
        tags, total = await client.get_tags(start=start, limit=limit)
    except ZoteroError as exc:
        return f"Error: {exc}"

    if not tags:
        return "No tags found."

    hint = paging_hint(start, len(tags), total, "tags")
    tag_lines = [format_tag(t) for t in tags]
    return hint + "\n" + "\n".join(tag_lines)


async def _get_item_children(
    client: ZoteroClient,
    item_key: str,
    start: int = 0,
    limit: int = 25,
) -> str:
    try:
        children, total = await client.get_item_children(
            item_key, start=start, limit=limit
        )
    except ZoteroError as exc:
        return f"Error: {exc}"

    if not children:
        return f"Item {item_key!r} has no child items."

    hint = paging_hint(start, len(children), total, "children")
    child_lines = [format_child(c) for c in children]
    return hint + "\n" + "\n".join(child_lines)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_tools(mcp: "FastMCP", client: ZoteroClient) -> None:
    """Register all Zotero tools on *mcp*, bound to *client*."""

    @mcp.tool()
    async def list_collections(start: int = 0, limit: int = 25) -> str:
        """List collections in the Zotero library.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of collections to return, max 100 (default: 25).
        """
        return await _list_collections(client, start=start, limit=limit)

    @mcp.tool()
    async def list_items(
        start: int = 0,
        limit: int = 25,
        item_type: str = "",
        tag: str = "",
        sort: str = "dateModified",
        direction: str = "desc",
    ) -> str:
        """List items in the Zotero library with optional filtering.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of items to return, max 100 (default: 25).
            item_type: Filter by Zotero item type (e.g. "journalArticle", "book").
            tag: Filter by tag name.
            sort: Sort field — dateModified, title, creator, or date (default: dateModified).
            direction: Sort direction — "asc" or "desc" (default: desc).
        """
        return await _list_items(
            client,
            start=start,
            limit=limit,
            item_type=item_type,
            tag=tag,
            sort=sort,
            direction=direction,
        )

    @mcp.tool()
    async def get_item(item_key: str, expanded: bool = False) -> str:
        """Get details of a specific Zotero item by its key.

        Args:
            item_key: The Zotero item key (e.g. "ABCD1234").
            expanded: When true, include the abstract in the output (default: false).
        """
        return await _get_item(client, item_key=item_key, expanded=expanded)

    @mcp.tool()
    async def search_items(
        query: str,
        qmode: str = "everything",
        tag: str = "",
        item_type: str = "",
        start: int = 0,
        limit: int = 25,
    ) -> str:
        """Search items in the Zotero library by keyword.

        Args:
            query: Search query string.
            qmode: Search mode — "everything" (full text) or "titleCreatorYear" (default: everything).
            tag: Optionally filter results by tag name.
            item_type: Optionally filter results by item type (e.g. "book").
            start: Pagination offset (default: 0).
            limit: Number of results to return, max 100 (default: 25).
        """
        return await _search_items(
            client,
            query=query,
            qmode=qmode,
            tag=tag,
            item_type=item_type,
            start=start,
            limit=limit,
        )

    @mcp.tool()
    async def list_tags(start: int = 0, limit: int = 100) -> str:
        """List tags used in the Zotero library.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of tags to return, max 100 (default: 100).
        """
        return await _list_tags(client, start=start, limit=limit)

    @mcp.tool()
    async def get_item_children(
        item_key: str, start: int = 0, limit: int = 25
    ) -> str:
        """Get child items (notes and attachments) of a Zotero item.

        Args:
            item_key: The Zotero item key of the parent item.
            start: Pagination offset (default: 0).
            limit: Number of children to return, max 100 (default: 25).
        """
        return await _get_item_children(
            client, item_key=item_key, start=start, limit=limit
        )

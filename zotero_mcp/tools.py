"""MCP tool implementations for the Zotero library.

Each tool is implemented as a module-level async function (prefixed with ``_``)
so it can be called directly in tests. ``register_tools`` wraps each one in a
FastMCP ``@mcp.tool()`` decorator and binds it to a specific ``ZoteroClient``
instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client import ZoteroClient, ZoteroError
from .config import DEFAULT_LIMIT, DEFAULT_TAG_LIMIT, MAX_LIMIT
from .formatters import (
    child_to_record,
    collection_to_record,
    format_attachment,
    format_child,
    format_collection,
    format_export,
    format_item,
    format_note,
    format_saved_search,
    format_tag,
    item_to_record,
    paging_hint,
    paging_record,
    tag_to_record,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

ToolResult = str | dict[str, Any]
OUTPUT_FORMATS = {"text", "json"}
SORT_FIELDS = {"dateModified", "title", "creator", "date"}
DIRECTIONS = {"asc", "desc"}
QMODES = {"everything", "titleCreatorYear"}
CHILD_ITEM_TYPES = {"attachment", "note"}
EXPORT_FORMATS = {"bibtex", "biblatex", "ris", "mods", "refer", "csljson"}


def _error_result(exc: ZoteroError | ValueError, output_format: str) -> ToolResult:
    if output_format == "json":
        status_code = exc.status_code if isinstance(exc, ZoteroError) else 400
        return {"error": str(exc), "status_code": status_code}
    return f"Error: {exc}"


def _validate_output_format(output_format: str) -> None:
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(
            f"output_format must be one of {sorted(OUTPUT_FORMATS)}, got {output_format!r}"
        )


def _validate_start_limit(start: int, limit: int) -> None:
    if start < 0:
        raise ValueError("start must be greater than or equal to 0.")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}.")


def _validate_key(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def _validate_choice(name: str, value: str, choices: set[str]) -> None:
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {value!r}.")


def _list_result(
    *,
    noun: str,
    start: int,
    total: int,
    items: list[dict[str, Any]],
    empty_message: str,
    text_formatter,
    json_formatter,
    output_format: str,
    extra: dict[str, Any] | None = None,
) -> ToolResult:
    if not items:
        if output_format == "json":
            payload = {
                noun: [],
                "paging": paging_record(start, 0, total, noun),
                "message": empty_message,
            }
            if extra:
                payload.update(extra)
            return payload
        return empty_message

    if output_format == "json":
        payload = {
            noun: [json_formatter(item) for item in items],
            "paging": paging_record(start, len(items), total, noun),
        }
        if extra:
            payload.update(extra)
        return payload

    hint = paging_hint(start, len(items), total, noun)
    blocks = [text_formatter(item) for item in items]
    return hint + "\n\n" + "\n---\n".join(blocks)


async def _list_collections(
    client: ZoteroClient,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_start_limit(start, limit)
        collections, total = await client.get_collections(start=start, limit=limit)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="collections",
        start=start,
        total=total,
        items=collections,
        empty_message="No collections found.",
        text_formatter=format_collection,
        json_formatter=collection_to_record,
        output_format=output_format,
    )


async def _list_saved_searches(
    client: ZoteroClient,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_start_limit(start, limit)
        searches, total = await client.get_saved_searches(start=start, limit=limit)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="saved_searches",
        start=start,
        total=total,
        items=searches,
        empty_message="No saved searches found.",
        text_formatter=format_saved_search,
        json_formatter=collection_to_record,
        output_format=output_format,
    )


async def _list_items(
    client: ZoteroClient,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    item_type: str = "",
    tag: str = "",
    sort: str = "dateModified",
    direction: str = "desc",
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_start_limit(start, limit)
        _validate_choice("sort", sort, SORT_FIELDS)
        _validate_choice("direction", direction, DIRECTIONS)
        items, total = await client.get_items(
            start=start,
            limit=limit,
            item_type=item_type or None,
            tag=tag or None,
            sort=sort,
            direction=direction,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="items",
        start=start,
        total=total,
        items=items,
        empty_message="No items found.",
        text_formatter=format_item,
        json_formatter=item_to_record,
        output_format=output_format,
        extra={
            "filters": {
                "item_type": item_type or None,
                "tag": tag or None,
                "sort": sort,
                "direction": direction,
            }
        },
    )


async def _list_collection_items(
    client: ZoteroClient,
    collection_key: str,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    sort: str = "dateModified",
    direction: str = "desc",
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("collection_key", collection_key)
        _validate_start_limit(start, limit)
        _validate_choice("sort", sort, SORT_FIELDS)
        _validate_choice("direction", direction, DIRECTIONS)
        items, total = await client.get_collection_items(
            collection_key=collection_key,
            start=start,
            limit=limit,
            sort=sort,
            direction=direction,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="items",
        start=start,
        total=total,
        items=items,
        empty_message=f"No items found in collection {collection_key!r}.",
        text_formatter=format_item,
        json_formatter=item_to_record,
        output_format=output_format,
        extra={
            "collection_key": collection_key,
            "filters": {"sort": sort, "direction": direction},
        },
    )


async def _list_saved_search_items(
    client: ZoteroClient,
    search_key: str,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    sort: str = "dateModified",
    direction: str = "desc",
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("search_key", search_key)
        _validate_start_limit(start, limit)
        _validate_choice("sort", sort, SORT_FIELDS)
        _validate_choice("direction", direction, DIRECTIONS)
        items, total = await client.get_saved_search_items(
            search_key=search_key,
            start=start,
            limit=limit,
            sort=sort,
            direction=direction,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="items",
        start=start,
        total=total,
        items=items,
        empty_message=f"No items found in saved search {search_key!r}.",
        text_formatter=format_item,
        json_formatter=item_to_record,
        output_format=output_format,
        extra={
            "search_key": search_key,
            "filters": {"sort": sort, "direction": direction},
        },
    )


async def _get_item(
    client: ZoteroClient,
    item_key: str,
    expanded: bool = False,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        item = await client.get_item(item_key)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if output_format == "json":
        return {"item": item_to_record(item, expanded=expanded), "expanded": expanded}
    return format_item(item, expanded=expanded)


async def _get_note(
    client: ZoteroClient,
    item_key: str,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        item = await client.get_note(item_key)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if output_format == "json":
        return {"note": item_to_record(item, expanded=True)}
    return format_note(item)


async def _get_attachment(
    client: ZoteroClient,
    item_key: str,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        item = await client.get_attachment(item_key)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if output_format == "json":
        return {"attachment": item_to_record(item)}
    return format_attachment(item)


async def _search_items(
    client: ZoteroClient,
    query: str,
    qmode: str = "everything",
    tag: str = "",
    item_type: str = "",
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("query", query)
        _validate_start_limit(start, limit)
        _validate_choice("qmode", qmode, QMODES)
        items, total = await client.search_items(
            query=query,
            qmode=qmode,
            tag=tag or None,
            item_type=item_type or None,
            start=start,
            limit=limit,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    return _list_result(
        noun="results",
        start=start,
        total=total,
        items=items,
        empty_message=f"No items found matching {query!r}.",
        text_formatter=format_item,
        json_formatter=item_to_record,
        output_format=output_format,
        extra={
            "query": query,
            "filters": {
                "qmode": qmode,
                "tag": tag or None,
                "item_type": item_type or None,
            },
        },
    )


async def _list_tags(
    client: ZoteroClient,
    start: int = 0,
    limit: int = DEFAULT_TAG_LIMIT,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_start_limit(start, limit)
        tags, total = await client.get_tags(start=start, limit=limit)
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if not tags:
        if output_format == "json":
            return {
                "tags": [],
                "paging": paging_record(start, 0, total, "tags"),
                "message": "No tags found.",
            }
        return "No tags found."

    if output_format == "json":
        return {
            "tags": [tag_to_record(tag) for tag in tags],
            "paging": paging_record(start, len(tags), total, "tags"),
        }

    hint = paging_hint(start, len(tags), total, "tags")
    tag_lines = [format_tag(tag) for tag in tags]
    return hint + "\n" + "\n".join(tag_lines)


async def _get_item_children(
    client: ZoteroClient,
    item_key: str,
    start: int = 0,
    limit: int = DEFAULT_LIMIT,
    item_type: str = "",
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        _validate_start_limit(start, limit)
        if item_type:
            _validate_choice("item_type", item_type, CHILD_ITEM_TYPES)
        children, total = await client.get_item_children(
            item_key,
            start=start,
            limit=limit,
            item_type=item_type or None,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    empty_message = (
        f"Item {item_key!r} has no {item_type} child items."
        if item_type
        else f"Item {item_key!r} has no child items."
    )
    if not children:
        if output_format == "json":
            return {
                "children": [],
                "item_key": item_key,
                "paging": paging_record(start, 0, total, "children"),
                "filter": item_type or None,
                "message": empty_message,
            }
        return empty_message

    if output_format == "json":
        return {
            "children": [child_to_record(child) for child in children],
            "item_key": item_key,
            "filter": item_type or None,
            "paging": paging_record(start, len(children), total, "children"),
        }

    hint = paging_hint(start, len(children), total, "children")
    child_lines = [format_child(child) for child in children]
    return hint + "\n" + "\n".join(child_lines)


async def _get_item_citation(
    client: ZoteroClient,
    item_key: str,
    style: str = "apa",
    locale: str = "",
    linkwrap: bool = False,
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        _validate_key("style", style)
        citation = await client.get_item_citation(
            item_key=item_key,
            style=style,
            locale=locale or None,
            linkwrap=linkwrap,
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if output_format == "json":
        return {
            "item_key": item_key,
            "style": style,
            "locale": locale or None,
            "linkwrap": linkwrap,
            "citation": citation,
        }
    return citation


async def _export_item(
    client: ZoteroClient,
    item_key: str,
    export_format: str = "bibtex",
    output_format: str = "text",
) -> ToolResult:
    try:
        _validate_output_format(output_format)
        _validate_key("item_key", item_key)
        _validate_choice("export_format", export_format, EXPORT_FORMATS)
        export_text = await client.export_item(
            item_key=item_key, export_format=export_format
        )
    except (ZoteroError, ValueError) as exc:
        return _error_result(exc, output_format)

    if output_format == "json":
        return {
            "item_key": item_key,
            "format": export_format,
            "content": export_text,
        }
    return format_export(export_text, export_format)


def register_tools(mcp: "FastMCP", client: ZoteroClient) -> None:
    """Register all Zotero tools on *mcp*, bound to *client*."""

    @mcp.tool()
    async def list_collections(
        start: int = 0, limit: int = DEFAULT_LIMIT, output_format: str = "text"
    ) -> ToolResult:
        """List collections in the Zotero library.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of collections to return, max 100 (default: 25).
            output_format: Return "text" or structured "json" output.
        """

        return await _list_collections(
            client, start=start, limit=limit, output_format=output_format
        )

    @mcp.tool()
    async def list_saved_searches(
        start: int = 0, limit: int = DEFAULT_LIMIT, output_format: str = "text"
    ) -> ToolResult:
        """List saved searches in the Zotero library.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of saved searches to return, max 100 (default: 25).
            output_format: Return "text" or structured "json" output.
        """

        return await _list_saved_searches(
            client, start=start, limit=limit, output_format=output_format
        )

    @mcp.tool()
    async def list_items(
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        item_type: str = "",
        tag: str = "",
        sort: str = "dateModified",
        direction: str = "desc",
        output_format: str = "text",
    ) -> ToolResult:
        """List items in the Zotero library with optional filtering.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of items to return, max 100 (default: 25).
            item_type: Filter by Zotero item type (e.g. "journalArticle", "book").
            tag: Filter by tag name.
            sort: Sort field — dateModified, title, creator, or date.
            direction: Sort direction — "asc" or "desc".
            output_format: Return "text" or structured "json" output.
        """

        return await _list_items(
            client,
            start=start,
            limit=limit,
            item_type=item_type,
            tag=tag,
            sort=sort,
            direction=direction,
            output_format=output_format,
        )

    @mcp.tool()
    async def list_collection_items(
        collection_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        sort: str = "dateModified",
        direction: str = "desc",
        output_format: str = "text",
    ) -> ToolResult:
        """List items belonging to a collection.

        Args:
            collection_key: Zotero collection key.
            start: Pagination offset (default: 0).
            limit: Number of items to return, max 100 (default: 25).
            sort: Sort field — dateModified, title, creator, or date.
            direction: Sort direction — "asc" or "desc".
            output_format: Return "text" or structured "json" output.
        """

        return await _list_collection_items(
            client,
            collection_key=collection_key,
            start=start,
            limit=limit,
            sort=sort,
            direction=direction,
            output_format=output_format,
        )

    @mcp.tool()
    async def list_saved_search_items(
        search_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        sort: str = "dateModified",
        direction: str = "desc",
        output_format: str = "text",
    ) -> ToolResult:
        """List items returned by a saved search.

        Args:
            search_key: Zotero saved search key.
            start: Pagination offset (default: 0).
            limit: Number of items to return, max 100 (default: 25).
            sort: Sort field — dateModified, title, creator, or date.
            direction: Sort direction — "asc" or "desc".
            output_format: Return "text" or structured "json" output.
        """

        return await _list_saved_search_items(
            client,
            search_key=search_key,
            start=start,
            limit=limit,
            sort=sort,
            direction=direction,
            output_format=output_format,
        )

    @mcp.tool()
    async def get_item(
        item_key: str, expanded: bool = False, output_format: str = "text"
    ) -> ToolResult:
        """Get details of a specific Zotero item by its key.

        Args:
            item_key: The Zotero item key (e.g. "ABCD1234").
            expanded: When true, include the abstract in the output.
            output_format: Return "text" or structured "json" output.
        """

        return await _get_item(
            client, item_key=item_key, expanded=expanded, output_format=output_format
        )

    @mcp.tool()
    async def get_note(item_key: str, output_format: str = "text") -> ToolResult:
        """Get note content for a Zotero note item."""
        return await _get_note(client, item_key=item_key, output_format=output_format)

    @mcp.tool()
    async def get_attachment(item_key: str, output_format: str = "text") -> ToolResult:
        """Get metadata for a Zotero attachment item."""
        return await _get_attachment(
            client, item_key=item_key, output_format=output_format
        )

    @mcp.tool()
    async def search_items(
        query: str,
        qmode: str = "everything",
        tag: str = "",
        item_type: str = "",
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        output_format: str = "text",
    ) -> ToolResult:
        """Search items in the Zotero library by keyword.

        Args:
            query: Search query string.
            qmode: Search mode — "everything" or "titleCreatorYear".
            tag: Optionally filter results by tag name.
            item_type: Optionally filter results by item type.
            start: Pagination offset (default: 0).
            limit: Number of results to return, max 100 (default: 25).
            output_format: Return "text" or structured "json" output.
        """

        return await _search_items(
            client,
            query=query,
            qmode=qmode,
            tag=tag,
            item_type=item_type,
            start=start,
            limit=limit,
            output_format=output_format,
        )

    @mcp.tool()
    async def list_tags(
        start: int = 0, limit: int = DEFAULT_TAG_LIMIT, output_format: str = "text"
    ) -> ToolResult:
        """List tags used in the Zotero library.

        Args:
            start: Pagination offset (default: 0).
            limit: Number of tags to return, max 100 (default: 100).
            output_format: Return "text" or structured "json" output.
        """

        return await _list_tags(
            client, start=start, limit=limit, output_format=output_format
        )

    @mcp.tool()
    async def get_item_children(
        item_key: str,
        start: int = 0,
        limit: int = DEFAULT_LIMIT,
        item_type: str = "",
        output_format: str = "text",
    ) -> ToolResult:
        """Get child items (notes and attachments) of a Zotero item.

        Args:
            item_key: Parent Zotero item key.
            start: Pagination offset (default: 0).
            limit: Number of children to return, max 100 (default: 25).
            item_type: Optional filter — "attachment" or "note".
            output_format: Return "text" or structured "json" output.
        """

        return await _get_item_children(
            client,
            item_key=item_key,
            start=start,
            limit=limit,
            item_type=item_type,
            output_format=output_format,
        )

    @mcp.tool()
    async def get_item_citation(
        item_key: str,
        style: str = "apa",
        locale: str = "",
        linkwrap: bool = False,
        output_format: str = "text",
    ) -> ToolResult:
        """Get a formatted citation for a Zotero item."""
        return await _get_item_citation(
            client,
            item_key=item_key,
            style=style,
            locale=locale,
            linkwrap=linkwrap,
            output_format=output_format,
        )

    @mcp.tool()
    async def export_item(
        item_key: str,
        export_format: str = "bibtex",
        output_format: str = "text",
    ) -> ToolResult:
        """Export a Zotero item in a bibliographic format."""
        return await _export_item(
            client,
            item_key=item_key,
            export_format=export_format,
            output_format=output_format,
        )

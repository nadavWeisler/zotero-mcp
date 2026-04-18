"""Output formatters: convert raw Zotero API responses into readable text."""

from __future__ import annotations

import re
from typing import Any

from .config import ABSTRACT_MAX_LEN, NOTE_SNIPPET_MAX_LEN


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int) -> str:
    """Truncate *text* to *max_len* characters, appending an ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "… [truncated]"


def _format_creators(creators: list[dict[str, Any]]) -> str:
    """Render a list of Zotero creator objects as a semicolon-separated string."""
    parts: list[str] = []
    for creator in creators:
        if creator.get("name"):
            parts.append(creator["name"])
        else:
            last = creator.get("lastName", "")
            first = creator.get("firstName", "")
            name = f"{last}, {first}".strip(", ")
            if name:
                parts.append(name)
    return "; ".join(parts) if parts else "Unknown"


def _strip_html(text: str) -> str:
    """Remove HTML tags from *text* (used for note snippets)."""
    return re.sub(r"<[^>]+>", " ", text).strip()


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_item(item: dict[str, Any], expanded: bool = False) -> str:
    """Format a Zotero item as a compact, human-readable block.

    Args:
        item: Raw item object from the Zotero API.
        expanded: When True, include the abstract.
    """
    data = item.get("data", {})
    key = data.get("key") or item.get("key", "?")
    title = data.get("title") or "Untitled"
    item_type = data.get("itemType", "unknown")
    creators = _format_creators(data.get("creators", []))
    date = data.get("date", "")
    tags = ", ".join(t.get("tag", "") for t in data.get("tags", []))
    abstract = data.get("abstractNote", "")

    lines = [
        f"Key:    {key}",
        f"Type:   {item_type}",
        f"Title:  {title}",
        f"Author: {creators}",
    ]
    if date:
        lines.append(f"Date:   {date}")
    if tags:
        lines.append(f"Tags:   {tags}")
    if expanded and abstract:
        lines.append(f"Abstract: {_truncate(abstract, ABSTRACT_MAX_LEN)}")
    return "\n".join(lines)


def format_collection(col: dict[str, Any]) -> str:
    """Format a Zotero collection as a compact, human-readable block."""
    data = col.get("data", {})
    key = data.get("key") or col.get("key", "?")
    name = data.get("name", "Unnamed")
    parent = data.get("parentCollection")
    n_items = col.get("meta", {}).get("numItems", "?")

    lines = [
        f"Key:   {key}",
        f"Name:  {name}",
        f"Items: {n_items}",
    ]
    if parent:
        lines.append(f"Parent: {parent}")
    return "\n".join(lines)


def format_tag(tag: dict[str, Any]) -> str:
    """Format a single Zotero tag with its item count."""
    tag_name = tag.get("tag", "?")
    n_items = tag.get("meta", {}).get("numItems", "?")
    return f"{tag_name} ({n_items} items)"


def format_child(child: dict[str, Any]) -> str:
    """Format a child item (note or attachment) as a single line with optional snippet."""
    data = child.get("data", {})
    key = data.get("key") or child.get("key", "?")
    item_type = data.get("itemType", "unknown")
    title = data.get("title") or data.get("filename") or "(no title)"

    note_snippet = ""
    if item_type == "note":
        raw = _strip_html(data.get("note", ""))
        if raw:
            note_snippet = f"\n  Note: {_truncate(raw, NOTE_SNIPPET_MAX_LEN)}"

    return f"[{item_type}] {key}: {title}{note_snippet}"


def paging_hint(start: int, count: int, total: int, noun: str = "results") -> str:
    """Return a one-line summary of the current page with a next-page hint."""
    end = start + count
    if total <= end:
        return f"Showing {noun} {start + 1}–{min(end, total)} of {total}."
    return (
        f"Showing {noun} {start + 1}–{min(end, total)} of {total}. "
        f"Use start={end} to fetch the next page."
    )

"""Output formatters: convert raw Zotero API responses into readable text."""

from __future__ import annotations

import html
import re
from typing import Any

from .config import (
    ABSTRACT_MAX_LEN,
    EXPORT_PREVIEW_MAX_LEN,
    NOTE_MAX_LEN,
    NOTE_SNIPPET_MAX_LEN,
)


def _truncate(text: str, max_len: int) -> str:
    """Truncate *text* to *max_len* characters, appending an ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "… [truncated]"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _extract_year(date_value: str | None) -> str | None:
    if not date_value:
        return None
    match = re.search(r"\b(\d{4})\b", date_value)
    return match.group(1) if match else None


def _format_creators(creators: list[dict[str, Any]]) -> str:
    """Render a list of Zotero creator objects as a semicolon-separated string."""
    parts: list[str] = []
    for creator in creators:
        if creator.get("name"):
            parts.append(_clean_text(creator["name"]))
        else:
            last = _clean_text(creator.get("lastName", ""))
            first = _clean_text(creator.get("firstName", ""))
            name = f"{last}, {first}".strip(", ")
            if name:
                parts.append(name)
    return "; ".join(parts) if parts else "Unknown"


def _creator_records(creators: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    for creator in creators:
        name = _clean_text(creator.get("name"))
        if not name:
            last = _clean_text(creator.get("lastName", ""))
            first = _clean_text(creator.get("firstName", ""))
            name = f"{last}, {first}".strip(", ")
        if not name:
            continue
        records.append(
            {
                "name": name,
                "creator_type": _optional_text(creator.get("creatorType")),
            }
        )
    return records


def _strip_html(text: str) -> str:
    """Remove HTML tags from *text* (used for note snippets)."""
    if not text:
        return ""
    unescaped = html.unescape(text)
    no_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return _clean_text(no_tags)


def item_to_record(item: dict[str, Any], expanded: bool = False) -> dict[str, Any]:
    """Normalize a Zotero item into a structured record."""
    data = item.get("data", {})
    date = _optional_text(data.get("date"))
    raw_note = data.get("note", "")
    note_text = _optional_text(_strip_html(raw_note))
    abstract = _optional_text(data.get("abstractNote"))
    tags = [
        tag_name
        for tag_name in (
            _optional_text(tag.get("tag")) for tag in data.get("tags", [])
        )
        if tag_name
    ]

    return {
        "key": _optional_text(data.get("key")) or _optional_text(item.get("key")) or "?",
        "item_type": _optional_text(data.get("itemType")) or "unknown",
        "title": _optional_text(data.get("title"))
        or _optional_text(data.get("filename"))
        or "Untitled",
        "creators": _creator_records(data.get("creators", [])),
        "creator_summary": _format_creators(data.get("creators", [])),
        "date": date,
        "year": _extract_year(date),
        "tags": tags,
        "publication_title": _optional_text(data.get("publicationTitle")),
        "publisher": _optional_text(data.get("publisher")),
        "doi": _optional_text(data.get("DOI")),
        "url": _optional_text(data.get("url")),
        "parent_item": _optional_text(data.get("parentItem")),
        "filename": _optional_text(data.get("filename")),
        "content_type": _optional_text(data.get("contentType")),
        "link_mode": _optional_text(data.get("linkMode")),
        "note": _truncate(note_text, NOTE_MAX_LEN) if expanded and note_text else None,
        "note_preview": _truncate(note_text, NOTE_SNIPPET_MAX_LEN) if note_text else None,
        "abstract": _truncate(abstract, ABSTRACT_MAX_LEN)
        if expanded and abstract
        else None,
    }


def collection_to_record(collection: dict[str, Any]) -> dict[str, Any]:
    data = collection.get("data", {})
    return {
        "key": _optional_text(data.get("key"))
        or _optional_text(collection.get("key"))
        or "?",
        "name": _optional_text(data.get("name")) or "Unnamed",
        "parent_collection": _optional_text(data.get("parentCollection")),
        "num_items": collection.get("meta", {}).get("numItems"),
        "is_saved_search": bool(data.get("search")),
    }


def tag_to_record(tag: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _optional_text(tag.get("tag")) or "?",
        "num_items": tag.get("meta", {}).get("numItems"),
    }


def child_to_record(child: dict[str, Any]) -> dict[str, Any]:
    record = item_to_record(child, expanded=False)
    record["kind"] = record["item_type"]
    return record


def paging_record(start: int, count: int, total: int, noun: str = "results") -> dict[str, Any]:
    end = start + count
    has_more = total > end
    return {
        "noun": noun,
        "start": start,
        "limit": count,
        "returned": count,
        "total": total,
        "next_start": end if has_more else None,
        "has_more": has_more,
    }


def format_item(item: dict[str, Any], expanded: bool = False) -> str:
    """Format a Zotero item as a compact, human-readable block."""
    record = item_to_record(item, expanded=expanded)
    lines = [
        f"Key:    {record['key']}",
        f"Type:   {record['item_type']}",
        f"Title:  {record['title']}",
        f"Author: {record['creator_summary']}",
    ]
    if record["year"]:
        lines.append(f"Year:   {record['year']}")
    if record["date"]:
        lines.append(f"Date:   {record['date']}")
    if record["publication_title"]:
        lines.append(f"In:     {record['publication_title']}")
    if record["publisher"]:
        lines.append(f"Press:  {record['publisher']}")
    if record["doi"]:
        lines.append(f"DOI:    {record['doi']}")
    if record["url"]:
        lines.append(f"URL:    {record['url']}")
    if record["tags"]:
        lines.append(f"Tags:   {', '.join(record['tags'])}")
    if record["parent_item"]:
        lines.append(f"Parent: {record['parent_item']}")
    if expanded and record["abstract"]:
        lines.append(f"Abstract: {record['abstract']}")
    return "\n".join(lines)


def format_collection(col: dict[str, Any]) -> str:
    """Format a Zotero collection as a compact, human-readable block."""
    record = collection_to_record(col)
    lines = [
        f"Key:   {record['key']}",
        f"Name:  {record['name']}",
        f"Items: {record['num_items'] if record['num_items'] is not None else '?'}",
    ]
    if record["is_saved_search"]:
        lines.append("Type:  Saved search")
    if record["parent_collection"]:
        lines.append(f"Parent: {record['parent_collection']}")
    return "\n".join(lines)


def format_saved_search(col: dict[str, Any]) -> str:
    record = collection_to_record(col)
    lines = [
        f"Key:   {record['key']}",
        f"Name:  {record['name']}",
        "Type:  Saved search",
    ]
    if record["num_items"] is not None:
        lines.append(f"Items: {record['num_items']}")
    if record["parent_collection"]:
        lines.append(f"Parent: {record['parent_collection']}")
    return "\n".join(lines)


def format_tag(tag: dict[str, Any]) -> str:
    """Format a single Zotero tag with its item count."""
    record = tag_to_record(tag)
    count = record["num_items"] if record["num_items"] is not None else "?"
    return f"{record['name']} ({count} items)"


def format_child(child: dict[str, Any]) -> str:
    """Format a child item (note or attachment) as a single line with optional snippet."""
    record = child_to_record(child)
    suffix_parts: list[str] = []
    if record["content_type"]:
        suffix_parts.append(record["content_type"])
    if record["note_preview"]:
        suffix_parts.append(f"Note: {record['note_preview']}")
    suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
    return f"[{record['kind']}] {record['key']}: {record['title']}{suffix}"


def format_note(item: dict[str, Any]) -> str:
    record = item_to_record(item, expanded=True)
    lines = [
        f"Key:    {record['key']}",
        "Type:   note",
        f"Title:  {record['title']}",
    ]
    if record["parent_item"]:
        lines.append(f"Parent: {record['parent_item']}")
    lines.append(f"Content: {record['note'] or '(empty note)'}")
    return "\n".join(lines)


def format_attachment(item: dict[str, Any]) -> str:
    record = item_to_record(item, expanded=False)
    lines = [
        f"Key:      {record['key']}",
        "Type:     attachment",
        f"Title:    {record['title']}",
    ]
    if record["filename"]:
        lines.append(f"Filename: {record['filename']}")
    if record["content_type"]:
        lines.append(f"MIME:     {record['content_type']}")
    if record["link_mode"]:
        lines.append(f"LinkMode: {record['link_mode']}")
    if record["parent_item"]:
        lines.append(f"Parent:   {record['parent_item']}")
    if record["url"]:
        lines.append(f"URL:      {record['url']}")
    return "\n".join(lines)


def format_export(export_text: str, export_format: str) -> str:
    preview = _truncate(export_text, EXPORT_PREVIEW_MAX_LEN)
    return f"Format: {export_format}\n\n{preview}"


def paging_hint(start: int, count: int, total: int, noun: str = "results") -> str:
    """Return a one-line summary of the current page with a next-page hint."""
    end = start + count
    if total <= end:
        return f"Showing {noun} {start + 1}–{min(end, total)} of {total}."
    return (
        f"Showing {noun} {start + 1}–{min(end, total)} of {total}. "
        f"Use start={end} to fetch the next page."
    )

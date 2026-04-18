"""Unit tests for output formatters."""

from __future__ import annotations

from zotero_mcp.formatters import (
    _format_creators,
    _strip_html,
    _truncate,
    format_child,
    format_collection,
    format_item,
    format_tag,
    paging_hint,
)


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


def test_truncate_short_string_unchanged() -> None:
    assert _truncate("hello", 10) == "hello"


def test_truncate_exact_length_unchanged() -> None:
    assert _truncate("hello", 5) == "hello"


def test_truncate_long_string() -> None:
    result = _truncate("abcdefghij", 5)
    assert result.startswith("abcde")
    assert "truncated" in result


# ---------------------------------------------------------------------------
# _format_creators
# ---------------------------------------------------------------------------


def test_format_creators_empty() -> None:
    assert _format_creators([]) == "Unknown"


def test_format_creators_last_first() -> None:
    creators = [{"lastName": "Smith", "firstName": "John"}]
    assert _format_creators(creators) == "Smith, John"


def test_format_creators_name_only() -> None:
    creators = [{"name": "NASA"}]
    assert _format_creators(creators) == "NASA"


def test_format_creators_multiple() -> None:
    creators = [
        {"lastName": "Smith", "firstName": "John"},
        {"lastName": "Doe", "firstName": "Jane"},
    ]
    result = _format_creators(creators)
    assert "Smith, John" in result
    assert "Doe, Jane" in result
    assert ";" in result


def test_format_creators_skips_empty() -> None:
    creators = [{"lastName": "", "firstName": ""}]
    assert _format_creators(creators) == "Unknown"


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------


def test_strip_html_removes_tags() -> None:
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello  world"


def test_strip_html_plain_text_unchanged() -> None:
    assert _strip_html("plain text") == "plain text"


def test_strip_html_empty() -> None:
    assert _strip_html("") == ""


# ---------------------------------------------------------------------------
# format_item
# ---------------------------------------------------------------------------


def _make_item(**overrides) -> dict:
    data = {
        "key": "ABCD1234",
        "itemType": "journalArticle",
        "title": "A Great Paper",
        "creators": [{"lastName": "Smith", "firstName": "Alice"}],
        "date": "2023-05-01",
        "tags": [{"tag": "science"}, {"tag": "ai"}],
        "abstractNote": "This paper discusses AI.",
    }
    data.update(overrides)
    return {"data": data}


def test_format_item_contains_key_fields() -> None:
    item = _make_item()
    result = format_item(item)
    assert "ABCD1234" in result
    assert "journalArticle" in result
    assert "A Great Paper" in result
    assert "Smith, Alice" in result
    assert "2023-05-01" in result
    assert "science" in result
    assert "ai" in result


def test_format_item_no_abstract_by_default() -> None:
    item = _make_item()
    result = format_item(item)
    assert "Abstract" not in result


def test_format_item_expanded_includes_abstract() -> None:
    item = _make_item()
    result = format_item(item, expanded=True)
    assert "Abstract" in result
    assert "This paper discusses AI." in result


def test_format_item_abstract_truncated_when_long() -> None:
    long_abstract = "x" * 600
    item = _make_item(abstractNote=long_abstract)
    result = format_item(item, expanded=True)
    assert "truncated" in result


def test_format_item_missing_date_omitted() -> None:
    item = _make_item(date="")
    result = format_item(item)
    assert "Date:" not in result


def test_format_item_missing_tags_omitted() -> None:
    item = _make_item(tags=[])
    result = format_item(item)
    assert "Tags:" not in result


def test_format_item_untitled_fallback() -> None:
    item = _make_item(title="")
    result = format_item(item)
    assert "Untitled" in result


def test_format_item_key_from_top_level_fallback() -> None:
    """If 'data' has no key, fall back to top-level 'key'."""
    item = {"key": "TOP0001", "data": {"itemType": "book"}}
    result = format_item(item)
    assert "TOP0001" in result


# ---------------------------------------------------------------------------
# format_collection
# ---------------------------------------------------------------------------


def test_format_collection_basic() -> None:
    col = {
        "data": {"key": "COLL1234", "name": "My Collection", "parentCollection": False},
        "meta": {"numItems": 10},
    }
    result = format_collection(col)
    assert "COLL1234" in result
    assert "My Collection" in result
    assert "10" in result
    assert "Parent" not in result


def test_format_collection_with_parent() -> None:
    col = {
        "data": {
            "key": "COLL5678",
            "name": "Sub",
            "parentCollection": "PARENT01",
        },
        "meta": {"numItems": 2},
    }
    result = format_collection(col)
    assert "PARENT01" in result


# ---------------------------------------------------------------------------
# format_tag
# ---------------------------------------------------------------------------


def test_format_tag() -> None:
    tag = {"tag": "physics", "meta": {"numItems": 7}}
    result = format_tag(tag)
    assert "physics" in result
    assert "7" in result


def test_format_tag_missing_meta() -> None:
    tag = {"tag": "orphan"}
    result = format_tag(tag)
    assert "orphan" in result
    assert "?" in result


# ---------------------------------------------------------------------------
# format_child
# ---------------------------------------------------------------------------


def test_format_child_attachment() -> None:
    child = {
        "data": {
            "key": "ATT12345",
            "itemType": "attachment",
            "title": "paper.pdf",
        }
    }
    result = format_child(child)
    assert "[attachment]" in result
    assert "paper.pdf" in result


def test_format_child_note_with_html() -> None:
    child = {
        "data": {
            "key": "NOTE1234",
            "itemType": "note",
            "note": "<p>Important <b>note</b> content.</p>",
        }
    }
    result = format_child(child)
    assert "[note]" in result
    assert "Important" in result
    assert "<p>" not in result


def test_format_child_note_snippet_truncated() -> None:
    long_note = "word " * 100
    child = {
        "data": {
            "key": "NOTE9999",
            "itemType": "note",
            "note": f"<p>{long_note}</p>",
        }
    }
    result = format_child(child)
    assert "truncated" in result


def test_format_child_uses_filename_when_no_title() -> None:
    child = {
        "data": {
            "key": "ATT00001",
            "itemType": "attachment",
            "filename": "article.pdf",
        }
    }
    result = format_child(child)
    assert "article.pdf" in result


# ---------------------------------------------------------------------------
# paging_hint
# ---------------------------------------------------------------------------


def test_paging_hint_last_page() -> None:
    result = paging_hint(start=75, count=25, total=100)
    assert "100" in result
    assert "next page" not in result


def test_paging_hint_mid_page() -> None:
    result = paging_hint(start=0, count=25, total=100)
    assert "next page" in result or "start=25" in result


def test_paging_hint_custom_noun() -> None:
    result = paging_hint(start=0, count=10, total=50, noun="collections")
    assert "collections" in result


def test_paging_hint_single_page() -> None:
    result = paging_hint(start=0, count=5, total=5)
    assert "next page" not in result

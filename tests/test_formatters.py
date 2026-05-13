"""Unit tests for output formatters."""

from __future__ import annotations

from zotero_mcp.formatters import (
    _format_creators,
    _strip_html,
    _truncate,
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


def _make_item(**overrides) -> dict:
    data = {
        "key": "ABCD1234",
        "itemType": "journalArticle",
        "title": "A Great Paper",
        "creators": [{"lastName": "Smith", "firstName": "Alice"}],
        "date": "2023-05-01",
        "tags": [{"tag": "science"}, {"tag": "ai"}],
        "abstractNote": "This paper discusses AI.",
        "publicationTitle": "Journal of Tests",
        "DOI": "10.1000/example",
        "url": "https://example.test/paper",
    }
    data.update(overrides)
    return {"data": data}


def test_truncate_short_string_unchanged() -> None:
    assert _truncate("hello", 10) == "hello"


def test_truncate_exact_length_unchanged() -> None:
    assert _truncate("hello", 5) == "hello"


def test_truncate_long_string() -> None:
    result = _truncate("abcdefghij", 5)
    assert result.startswith("abcde")
    assert "truncated" in result


def test_format_creators_empty() -> None:
    assert _format_creators([]) == "Unknown"


def test_format_creators_last_first() -> None:
    creators = [{"lastName": "Smith", "firstName": "John"}]
    assert _format_creators(creators) == "Smith, John"


def test_format_creators_name_only() -> None:
    creators = [{"name": "NASA"}]
    assert _format_creators(creators) == "NASA"


def test_strip_html_removes_tags_and_unescapes() -> None:
    assert _strip_html("<p>Hello &amp; <b>world</b></p>") == "Hello & world"


def test_item_to_record_normalizes_common_fields() -> None:
    record = item_to_record(_make_item(), expanded=True)
    assert record["key"] == "ABCD1234"
    assert record["creator_summary"] == "Smith, Alice"
    assert record["year"] == "2023"
    assert record["publication_title"] == "Journal of Tests"
    assert record["doi"] == "10.1000/example"
    assert record["abstract"] == "This paper discusses AI."


def test_item_to_record_note_extracts_plain_text() -> None:
    note = _make_item(itemType="note", title="", note="<p>Important <b>note</b></p>")
    record = item_to_record(note, expanded=True)
    assert record["title"] == "Untitled"
    assert record["note"] == "Important note"
    assert record["note_preview"] == "Important note"


def test_collection_to_record_marks_saved_search() -> None:
    record = collection_to_record(
        {"data": {"key": "SRCH0001", "name": "Recent", "search": True}}
    )
    assert record["is_saved_search"] is True


def test_tag_to_record_handles_missing_meta() -> None:
    assert tag_to_record({"tag": "orphan"}) == {"name": "orphan", "num_items": None}


def test_child_to_record_reuses_item_structure() -> None:
    record = child_to_record(
        {"data": {"key": "ATT12345", "itemType": "attachment", "filename": "paper.pdf"}}
    )
    assert record["kind"] == "attachment"
    assert record["title"] == "paper.pdf"


def test_format_item_contains_key_fields() -> None:
    result = format_item(_make_item(), expanded=True)
    assert "ABCD1234" in result
    assert "journalArticle" in result
    assert "A Great Paper" in result
    assert "Smith, Alice" in result
    assert "2023" in result
    assert "Journal of Tests" in result
    assert "10.1000/example" in result
    assert "Abstract" in result


def test_format_item_untitled_fallback() -> None:
    result = format_item(_make_item(title=""))
    assert "Untitled" in result


def test_format_collection_basic() -> None:
    col = {
        "data": {"key": "COLL1234", "name": "My Collection", "parentCollection": False},
        "meta": {"numItems": 10},
    }
    result = format_collection(col)
    assert "COLL1234" in result
    assert "My Collection" in result
    assert "10" in result
    assert "Saved search" not in result


def test_format_saved_search() -> None:
    result = format_saved_search(
        {"data": {"key": "SRCH5678", "name": "Recent", "search": True}}
    )
    assert "Saved search" in result
    assert "SRCH5678" in result


def test_format_tag() -> None:
    result = format_tag({"tag": "physics", "meta": {"numItems": 7}})
    assert "physics" in result
    assert "7" in result


def test_format_child_attachment() -> None:
    child = {
        "data": {
            "key": "ATT12345",
            "itemType": "attachment",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
        }
    }
    result = format_child(child)
    assert "[attachment]" in result
    assert "paper.pdf" in result
    assert "application/pdf" in result


def test_format_note_includes_plain_text_content() -> None:
    note = {
        "data": {
            "key": "NOTE1234",
            "itemType": "note",
            "title": "",
            "note": "<p>Important <b>note</b> content.</p>",
        }
    }
    result = format_note(note)
    assert "Content:" in result
    assert "Important note content." in result


def test_format_attachment_uses_filename_and_metadata() -> None:
    attachment = {
        "data": {
            "key": "ATT00001",
            "itemType": "attachment",
            "filename": "article.pdf",
            "contentType": "application/pdf",
            "linkMode": "imported_file",
        }
    }
    result = format_attachment(attachment)
    assert "article.pdf" in result
    assert "application/pdf" in result
    assert "imported_file" in result


def test_format_export_includes_format_label() -> None:
    result = format_export("@article{example}", "bibtex")
    assert "Format: bibtex" in result
    assert "@article" in result


def test_paging_hint_last_page() -> None:
    result = paging_hint(start=75, count=25, total=100)
    assert "100" in result
    assert "next page" not in result


def test_paging_hint_mid_page() -> None:
    result = paging_hint(start=0, count=25, total=100)
    assert "start=25" in result


def test_paging_record_has_next_start() -> None:
    record = paging_record(start=0, count=10, total=25, noun="items")
    assert record["next_start"] == 10
    assert record["has_more"] is True

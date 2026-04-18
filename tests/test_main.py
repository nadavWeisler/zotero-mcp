"""Unit tests for server entrypoint configuration logic."""

from __future__ import annotations

import pytest

import main


def test_create_client_with_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZOTERO_API_KEY", "key-123")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "456")
    monkeypatch.delenv("ZOTERO_LIBRARY_TYPE", raising=False)
    monkeypatch.delenv("ZOTERO_API_BASE", raising=False)

    client = main._create_client()

    assert client.api_key == "key-123"
    assert client.library_id == "456"
    assert client.library_type == "user"


def test_create_client_with_group_library_and_custom_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZOTERO_API_KEY", "key-123")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "456")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "group")
    monkeypatch.setenv("ZOTERO_API_BASE", "https://example.test/")

    client = main._create_client()

    assert client.library_type == "group"
    assert client.api_base == "https://example.test"


def test_create_client_missing_required_env_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main._create_client()

    message = str(exc_info.value)
    assert "Missing required environment variables" in message
    assert "ZOTERO_API_KEY" in message
    assert "ZOTERO_LIBRARY_ID" in message


def test_create_client_invalid_library_type_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZOTERO_API_KEY", "key-123")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "456")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "invalid")

    with pytest.raises(SystemExit) as exc_info:
        main._create_client()

    assert "must be 'user' or 'group'" in str(exc_info.value)

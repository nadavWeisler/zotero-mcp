"""Unit tests for server entrypoint configuration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import main
from zotero_mcp import __main__ as package_main


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


def test_main_registers_tools_runs_server_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_called = False
    original_asyncio_run = package_main.asyncio.run

    class FakeClient:
        async def close(self) -> None:
            nonlocal close_called
            close_called = True

    fake_client = FakeClient()
    fake_mcp = MagicMock()

    monkeypatch.setenv("ZOTERO_API_KEY", "key-123")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "456")

    with (
        patch.object(package_main, "FastMCP", return_value=fake_mcp),
        patch.object(package_main, "_create_client", return_value=fake_client),
        patch.object(package_main, "register_tools") as register_tools,
        patch.object(package_main.asyncio, "run", side_effect=original_asyncio_run) as asyncio_run,
    ):
        package_main.main()

    register_tools.assert_called_once_with(fake_mcp, fake_client)
    fake_mcp.run.assert_called_once_with(transport="stdio")
    asyncio_run.assert_called_once()
    assert close_called is True

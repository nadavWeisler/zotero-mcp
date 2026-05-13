"""Compatibility entry point for running the Zotero MCP server."""

from zotero_mcp.__main__ import _create_client, main

__all__ = ["_create_client", "main"]


if __name__ == "__main__":
    main()

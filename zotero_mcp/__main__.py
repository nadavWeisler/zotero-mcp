"""Console entry point for the Zotero MCP server package."""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

from zotero_mcp import config as zconfig
from zotero_mcp.client import ZoteroClient
from zotero_mcp.tools import register_tools


def _create_client() -> ZoteroClient:
    """Build a ZoteroClient from environment variables, exiting on missing config."""
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID", "")
    library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    api_base = os.environ.get("ZOTERO_API_BASE", zconfig.ZOTERO_API_BASE)

    missing = [
        name
        for name, val in [
            ("ZOTERO_API_KEY", api_key),
            ("ZOTERO_LIBRARY_ID", library_id),
        ]
        if not val
    ]
    if missing:
        sys.exit(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
            "Set them before starting the server."
        )

    if library_type not in ("user", "group"):
        sys.exit(
            f"ERROR: ZOTERO_LIBRARY_TYPE must be 'user' or 'group', got {library_type!r}."
        )

    return ZoteroClient(
        api_key=api_key,
        library_id=library_id,
        library_type=library_type,
        api_base=api_base,
    )


def main() -> None:
    """Run the MCP server over stdio."""
    mcp = FastMCP("zotero")
    client = _create_client()
    register_tools(mcp, client)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

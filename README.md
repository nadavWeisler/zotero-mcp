# zotero-mcp

An [MCP](https://modelcontextprotocol.io/) server that exposes your [Zotero](https://www.zotero.org/) library to AI assistants such as Claude.
<!-- mcp-name: io.github.nadavWeisler/zotero-mcp -->

## Features

Six read-only tools give an AI complete access to your Zotero reference library:

| Tool | Description |
|---|---|
| `list_collections` | List collections in the library (paginated) |
| `list_items` | List items with optional type/tag filtering (paginated) |
| `get_item` | Fetch full metadata for a single item by key |
| `search_items` | Full-text or title/creator/year keyword search (paginated) |
| `list_tags` | List all tags with item counts (paginated) |
| `get_item_children` | List notes and attachments belonging to an item |

## Requirements

- Python 3.13+
- A [Zotero Web API key](https://www.zotero.org/settings/keys)
- Your numeric Zotero user or group library ID

## Setup

### 1 — Get your API credentials

1. Sign in at [zotero.org](https://www.zotero.org/) and go to **Settings → Feeds/API**.
2. Click **Create new private key** and grant it **read-only** access to your library.
3. Note the generated key and your **User ID** (shown on the same page).

### 2 — Set environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ZOTERO_API_KEY` | ✅ | — | Your Zotero API key |
| `ZOTERO_LIBRARY_ID` | ✅ | — | Numeric user or group library ID |
| `ZOTERO_LIBRARY_TYPE` | | `user` | `user` or `group` |
| `ZOTERO_API_BASE` | | `https://api.zotero.org` | Override for self-hosted instances |

```bash
export ZOTERO_API_KEY="your_api_key_here"
export ZOTERO_LIBRARY_ID="123456"
export ZOTERO_LIBRARY_TYPE="user"   # or "group"
```

### 3 — Install dependencies

```bash
uv sync
```

### 4 — Run the server

```bash
uv run python main.py
```

Or run the installed package entrypoint:

```bash
python -m zotero_mcp
```

## Connecting to Claude Desktop

Add the following to your `claude_desktop_config.json`
(usually at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "uv",
      "args": ["run", "python", "/absolute/path/to/zotero-mcp/main.py"],
      "env": {
        "ZOTERO_API_KEY": "your_api_key_here",
        "ZOTERO_LIBRARY_ID": "123456",
        "ZOTERO_LIBRARY_TYPE": "user"
      }
    }
  }
}
```

Restart Claude Desktop after saving the file.

## Tool reference

### `list_collections`

List top-level collections in the library.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | int | 0 | Pagination offset |
| `limit` | int | 25 | Items per page (max 100) |

### `list_items`

List library items with optional filtering.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | int | 0 | Pagination offset |
| `limit` | int | 25 | Items per page (max 100) |
| `item_type` | str | | Filter by type, e.g. `"journalArticle"`, `"book"` |
| `tag` | str | | Filter by tag name |
| `sort` | str | `dateModified` | Sort field: `dateModified`, `title`, `creator`, `date` |
| `direction` | str | `desc` | Sort direction: `asc` or `desc` |

### `get_item`

Retrieve full metadata for one item.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | | Zotero item key (e.g. `"ABCD1234"`) |
| `expanded` | bool | false | Include the abstract in the output |

### `search_items`

Search the library by keyword.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | str | | Search terms |
| `qmode` | str | `everything` | `"everything"` (full-text) or `"titleCreatorYear"` |
| `tag` | str | | Narrow results to a specific tag |
| `item_type` | str | | Narrow results to a specific item type |
| `start` | int | 0 | Pagination offset |
| `limit` | int | 25 | Items per page (max 100) |

### `list_tags`

List all tags in the library.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | int | 0 | Pagination offset |
| `limit` | int | 100 | Tags per page (max 100) |

### `get_item_children`

List notes and attachments attached to an item.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | | Parent item key |
| `start` | int | 0 | Pagination offset |
| `limit` | int | 25 | Items per page (max 100) |

## Pagination

All list tools return a paging summary line at the top, for example:

```
Showing items 1–25 of 143. Use start=25 to fetch the next page.
```

Pass `start=<next offset>` and the same `limit` to retrieve subsequent pages.

## Known limitations

- **Read-only**: creating, editing, or deleting items is not supported in v1.
- **Attachment content**: binary file content is not downloaded. Only metadata
  (filename, MIME type) and note text are returned.
- **Group libraries**: set `ZOTERO_LIBRARY_TYPE=group` and provide the group's
  numeric ID via `ZOTERO_LIBRARY_ID`. Only one library per server instance is
  supported at a time.

## Development

### Run tests

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

If you installed with `pip`:

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Project layout

```
zotero-mcp/
├── main.py               # Server entry point
├── zotero_mcp/
│   ├── config.py         # Constants
│   ├── client.py         # Zotero Web API v3 client
│   ├── formatters.py     # Text output formatters
│   └── tools.py          # MCP tool implementations
└── tests/
    ├── test_main.py
    ├── test_client.py
    ├── test_formatters.py
    └── test_tools.py
```

## Changelog

### 0.1.0

- Initial Zotero MCP server implementation
- Six read-only tools: `list_collections`, `list_items`, `get_item`,
  `search_items`, `list_tags`, `get_item_children`
- Automatic retry on rate-limit (HTTP 429) and transient network errors
- Pagination support with next-page hints in every list response

## MCP Registry publishing

This repository includes a `server.json` file for MCP Registry publication under:

- `name`: `io.github.nadavWeisler/zotero-mcp`
- `registryType`: `pypi`
- `identifier`: `nadavweisler-zotero-mcp`

To complete publication:

1. Publish version `0.1.0` (or newer) of `nadavweisler-zotero-mcp` to PyPI.
2. Install `mcp-publisher`.
3. Run:
   - `mcp-publisher login github`
   - `mcp-publisher publish`

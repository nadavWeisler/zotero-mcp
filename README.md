# zotero-mcp

Read-only [MCP](https://modelcontextprotocol.io/) server for browsing, searching, and exporting a [Zotero](https://www.zotero.org/) library from AI assistants such as Claude.
<!-- mcp-name: io.github.nadavWeisler/zotero-mcp -->

## Features

- Read-only access to collections, saved searches, items, notes, attachments, tags, and citations
- Structured JSON responses (`output_format="json"`) for AI clients that prefer machine-readable output
- Text responses by default for chat-oriented clients
- Pagination hints, filter validation, and normalized metadata fields
- Shared HTTP client with retry/backoff and clearer upstream error handling

## Available tools

| Tool | Description |
|---|---|
| `list_collections` | List non-search collections |
| `list_saved_searches` | List saved searches |
| `list_items` | List items with optional type/tag filters |
| `list_collection_items` | List items from a specific collection |
| `list_saved_search_items` | List items returned by a saved search |
| `get_item` | Fetch normalized metadata for a single item |
| `get_note` | Fetch note content for a note item |
| `get_attachment` | Fetch attachment metadata |
| `search_items` | Full-text or title/creator/year search |
| `list_tags` | List tags with item counts |
| `get_item_children` | List note/attachment children for an item |
| `get_item_citation` | Render a citation in a Zotero style such as APA or MLA |
| `export_item` | Export an item as BibTeX, BibLaTeX, RIS, MODS, Refer, or CSL JSON |

## Requirements

- Python 3.12+
- A [Zotero Web API key](https://www.zotero.org/settings/keys)
- Your numeric Zotero user or group library ID

## Setup

### 1 — Get your API credentials

1. Sign in at [zotero.org](https://www.zotero.org/) and open **Settings → Feeds/API**.
2. Create a new private key with **read-only** access to your library.
3. Note the generated key and your numeric **User ID** or **Group ID**.

### 2 — Set environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ZOTERO_API_KEY` | ✅ | — | Zotero API key |
| `ZOTERO_LIBRARY_ID` | ✅ | — | Numeric user or group library ID |
| `ZOTERO_LIBRARY_TYPE` |  | `user` | `user` or `group` |
| `ZOTERO_API_BASE` |  | `https://api.zotero.org` | Override for alternate Zotero API bases |
| `ZOTERO_MCP_LOG_LEVEL` |  | `WARNING` | Python logging level for request/retry observability |

```bash
export ZOTERO_API_KEY="your_api_key_here"
export ZOTERO_LIBRARY_ID="123456"
export ZOTERO_LIBRARY_TYPE="user"   # or "group"
```

### 3 — Install dependencies

With `uv`:

```bash
uv sync
```

With `pip`:

```bash
python -m pip install -e .
```

### 4 — Run the server

```bash
python main.py
```

Or via the installed package entrypoint:

```bash
python -m zotero_mcp
```

## Client configuration

### Claude Desktop

Add the following to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "python",
      "args": ["/absolute/path/to/zotero-mcp/main.py"],
      "env": {
        "ZOTERO_API_KEY": "your_api_key_here",
        "ZOTERO_LIBRARY_ID": "123456",
        "ZOTERO_LIBRARY_TYPE": "user"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

### Generic stdio MCP clients

Any stdio-based MCP client can launch the server with:

```json
{
  "command": "python",
  "args": ["/absolute/path/to/zotero-mcp/main.py"],
  "env": {
    "ZOTERO_API_KEY": "your_api_key_here",
    "ZOTERO_LIBRARY_ID": "123456",
    "ZOTERO_LIBRARY_TYPE": "user"
  }
}
```

## Structured output

Every tool supports:

- `output_format="text"` (default)
- `output_format="json"`

JSON mode is useful when an MCP client or agent wants explicit paging and normalized metadata:

```json
{
  "paging": {
    "start": 0,
    "returned": 25,
    "total": 143,
    "next_start": 25,
    "has_more": true
  }
}
```

## Common workflows

- Browse a collection: `list_collection_items(collection_key="ABCD1234")`
- Explore saved searches: `list_saved_searches(output_format="json")`
- Fetch richer child data: `get_item_children(item_key="ABCD1234", item_type="note")`
- Export a reference: `export_item(item_key="ABCD1234", export_format="bibtex")`
- Render a formatted citation: `get_item_citation(item_key="ABCD1234", style="mla")`

### Example prompts for AI clients

- “List my saved searches as JSON.”
- “Show the latest 10 journal articles tagged `ai`.”
- “Export item `ABCD1234` as BibTeX.”
- “Get the note content for Zotero item `NOTE1234`.”
- “List attachments for item `ABCD1234`.”

## Tool reference

### Common pagination and output parameters

Most list tools support:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | int | `0` | Pagination offset |
| `limit` | int | `25` or `100` | Items per page (max `100`) |
| `output_format` | str | `text` | `text` or `json` |

### `list_items`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_type` | str | — | Filter by Zotero item type |
| `tag` | str | — | Filter by tag name |
| `sort` | str | `dateModified` | `dateModified`, `title`, `creator`, `date` |
| `direction` | str | `desc` | `asc` or `desc` |

### `list_collection_items` / `list_saved_search_items`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `collection_key` / `search_key` | str | — | Target Zotero key |
| `sort` | str | `dateModified` | `dateModified`, `title`, `creator`, `date` |
| `direction` | str | `desc` | `asc` or `desc` |

### `get_item`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | — | Zotero item key |
| `expanded` | bool | `false` | Include abstract text |

### `get_item_children`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | — | Parent Zotero item key |
| `item_type` | str | — | Optional `attachment` or `note` filter |

### `search_items`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | str | — | Search terms |
| `qmode` | str | `everything` | `everything` or `titleCreatorYear` |
| `tag` | str | — | Optional tag filter |
| `item_type` | str | — | Optional item type filter |

### `get_item_citation`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | — | Zotero item key |
| `style` | str | `apa` | Citation style |
| `locale` | str | — | Optional locale such as `en-US` |
| `linkwrap` | bool | `false` | Request wrapped links when supported |

### `export_item`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `item_key` | str | — | Zotero item key |
| `export_format` | str | `bibtex` | `bibtex`, `biblatex`, `ris`, `mods`, `refer`, `csljson` |

## Known limitations

- **Read-only**: creating, editing, or deleting items is not supported.
- **Attachment binaries**: attachment file content is not downloaded.
- **Saved searches**: the server exposes saved searches as special collections and uses their keys for item listing.
- **Single library scope**: one configured user or group library per server process.

## Development

### Install dev dependencies

With `uv`:

```bash
uv sync --extra dev
```

With `pip`:

```bash
python -m pip install -e ".[dev]"
```

### Run tests

```bash
python -m pytest tests/ -v
```

### Build the package

```bash
python -m build
```

### Project layout

```text
zotero-mcp/
├── main.py               # Compatibility entry point
├── server.json           # MCP Registry metadata
├── zotero_mcp/
│   ├── __main__.py       # Packaged entry point
│   ├── client.py         # Zotero Web API v3 client
│   ├── config.py         # Constants and version metadata
│   ├── formatters.py     # Text + structured output normalization
│   └── tools.py          # MCP tool implementations
└── tests/
    ├── test_client.py
    ├── test_formatters.py
    ├── test_main.py
    ├── test_server.py
    └── test_tools.py
```

## Changelog

### 0.2.0

- Added collection-scoped listing and saved-search discovery tools
- Added dedicated note, attachment, citation, and export tools
- Added structured JSON output across the tool surface
- Added stricter validation, shared HTTP client reuse, and retry/backoff logging
- Expanded automated coverage and CI expectations

### 0.1.0

- Initial Zotero MCP server implementation
- Six read-only tools for browsing items, collections, tags, and children
- Automatic retry on rate-limit (HTTP 429) and transient network errors

## MCP Registry publishing

This repository includes a `server.json` file for MCP Registry publication under:

- `name`: `io.github.nadavWeisler/zotero-mcp`
- `registryType`: `pypi`
- `identifier`: `nadavweisler-zotero-mcp`

To publish a new release:

1. Publish version `0.2.0` (or newer) of `nadavweisler-zotero-mcp` to PyPI.
2. Install `mcp-publisher`.
3. Run:
   - `mcp-publisher login github`
   - `mcp-publisher publish`

## v2 roadmap ideas

- Optional write operations behind explicit opt-in safeguards
- Multi-library support
- More advanced search composition for large libraries
- Client-selectable output modes tuned for specific MCP consumers

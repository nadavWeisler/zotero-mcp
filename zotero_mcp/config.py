"""Configuration constants for the Zotero MCP server."""

# Zotero Web API v3 base URL (override via ZOTERO_API_BASE env var)
ZOTERO_API_BASE = "https://api.zotero.org"

# Identifies this client to the Zotero API
USER_AGENT = "zotero-mcp/0.1.0"

# Pagination defaults / maximums
DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# Output shaping
ABSTRACT_MAX_LEN = 500
NOTE_SNIPPET_MAX_LEN = 200

"""Configuration constants for the Zotero MCP server."""

PACKAGE_VERSION = "0.2.0"

# Zotero Web API v3 base URL (override via ZOTERO_API_BASE env var)
ZOTERO_API_BASE = "https://api.zotero.org"

# Identifies this client to the Zotero API
USER_AGENT = f"zotero-mcp/{PACKAGE_VERSION}"

# Transport settings
DEFAULT_REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
MAX_RETRY_DELAY = 30

# Pagination defaults / maximums
DEFAULT_LIMIT = 25
DEFAULT_TAG_LIMIT = 100
MAX_LIMIT = 100

# Output shaping
ABSTRACT_MAX_LEN = 500
NOTE_SNIPPET_MAX_LEN = 200
NOTE_MAX_LEN = 4000
EXPORT_PREVIEW_MAX_LEN = 4000

"""Simple Bearer-token auth for the Logix MCP server."""

import os
from typing import Any

from fastmcp import Context


def validate_token(ctx: Context[Any, Any] | None = None) -> None:
    """Validate the Bearer token against LOGIX_MCP_TOKEN env var.

    If the env var is not set, auth is disabled (development mode).
    Raises PermissionError on invalid or missing token when enabled.
    """
    expected = os.environ.get("LOGIX_MCP_TOKEN")
    if not expected:
        return  # auth disabled

    token: str | None = None
    if ctx is not None:
        # FastMCP 2.x: headers live on the request context
        headers = getattr(ctx, "headers", {}) or {}
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if token != expected:
        raise PermissionError("Invalid or missing Bearer token")

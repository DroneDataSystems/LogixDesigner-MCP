# Logix MCP Server

MCP server that exposes the Studio 5000 Logix Designer SDK as typed MCP tools,
bridged to Linux via Cloudflare Tunnel.

## Development (Linux, mock SDK)

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest tests/ -v
```

## Windows deployment

See `deploy/` (Phase 3).

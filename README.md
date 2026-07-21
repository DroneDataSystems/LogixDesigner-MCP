# LogixDesigner-MCP

MCP server wrapping the Rockwell Automation Logix Designer SDK (Studio 5000) as typed MCP tools, bridged from Windows to Linux via Cloudflare Tunnel.

A Hermes Agent can open ACD files, export to L5K/L5X, read rung logic, enumerate tags and program structure, run verification — all over a typed MCP interface — without ever touching Studio 5000's GUI.

## Architecture

```
Linux (Hermes) ── SSE/HTTPS ──→ Cloudflare Tunnel ──→ Windows
                                                          │
                                              FastMCP ── pythonnet ── Logix Designer SDK
                                              localhost:8765
```

The Linux side runs mock-based tests; all COM-dependent logic lives on the Windows deployment.

## Tools

| Tool | Description |
|------|-------------|
| `get_sdk_info` | SDK version, license status, availability |
| `open_project(path)` | Open an ACD — returns controller name/type/revision |
| `close_project` | Close the current project |
| `project_status` | Is a project open? Which one? |
| `save_acd(path)` | Save the open project as ACD |
| `export_l5k(path)` | Export to L5K text format |
| `export_l5x(path)` | Export to L5X XML format |
| `import_l5k(path)` | Import an L5K (create ACD from text) |
| `get_controller_tags(scope?)` | List controller/program-scope tags |
| `get_program_structure` | Programs → routines → rung counts |
| `get_rung_logic(program, routine)` | Rung-by-rung ladder text |
| `get_task_structure` | Controller task configuration |
| `verify` | Run controller verification |
| `restart_host` | Restart the SDK COM host |

All tools that can fail return structured `SdkError` — no raw tracebacks.

## Development (Linux)

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -v
```

## Deployment (Windows)

See [`deploy/README.md`](deploy/README.md). Requires:

- Windows Server with Studio 5000 v33+
- Logix Designer SDK installed
- Python 3.11+
- Cloudflare Tunnel (cloudflared)

```
deploy/install.bat        # Create venv, discover SDK, verify
deploy/cloudflared-config.yml   # Tunnel setup guide
deploy/hermes-config.yaml       # Hermes MCP client config
```

## Project status

- [x] Phase 0: Project skeleton
- [x] Phase 1: Pydantic models, abstract SDK interface, mock implementation (Linux tested)
- [x] Phase 2: FastMCP server with 14 tools, error contract, async wrappers
- [x] Phase 3: Windows deployment artifacts
- [ ] Phase 4: Real COM interop (`RealSdkInterop`) — requires Windows

# Logix MCP Server — Windows Deployment Guide

This document walks through deploying the Logix MCP Server on a Windows machine
with Studio 5000 installed, and connecting it to the Linux Hermes agent via
Cloudflare Tunnel.

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| OS | Windows Server 2022 or Windows 10/11 |
| Studio 5000 | v33+ installed and licensed |
| Python | 3.11+ (64-bit) with "Add to PATH" enabled |
| Git | For cloning the repository |
| Cloudflare | Account with a domain (for tunnel) |
| Network | Outbound HTTPS/7844 to Cloudflare edge |

## Architecture Overview

```
Linux Hermes Agent
      |
      | MCP/SSE over HTTPS
      v
Cloudflare Tunnel (cloudflared on Windows)
      |
      | localhost:8765
      v
FastMCP Server (Python) --> pythonnet --> Studio 5000 SDK
```

## Step 1: Clone the Repository

On the Windows machine, clone the project repository:

```powershell
git clone <repository-url> C:\projects\logix-mcp
cd C:\projects\logix-mcp
```

## Step 2: Run the Installation Script

```powershell
deploy\install.bat
```

The script will:
- Verify Python 3.11+ is available
- Create a virtual environment in `.venv\`
- Install the package and dependencies
- Attempt to discover the Logix Designer SDK assembly
- Print next steps

**Note the SDK path** if auto-discovery succeeds. If not, you'll need to
manually locate the SDK DLL under `C:\Program Files (x86)\Rockwell Software\Studio 5000\`.

## Step 3: Configure Environment Variables

Set the shared authentication token (required for remote access):

```powershell
setx LOGIX_MCP_TOKEN "your-secret-token-here"
```

Generate a strong token:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

If the SDK assembly was not auto-discovered, set it manually:

```powershell
setx LOGIX_SDK_ASSEMBLY "C:\Program Files (x86)\Rockwell Software\Studio 5000\LogixDesigner.SDK.dll"
```

**Important:** Open a new command prompt after `setx` for the variables to take effect.

## Step 4: Start the MCP Server

From the repository root:

```powershell
.venv\Scripts\activate
fastmcp run src\logix_mcp\server.py:create_app --transport sse --host 127.0.0.1 --port 8765
```

Or without activating:

```powershell
.venv\Scripts\python -m fastmcp run src\logix_mcp\server.py:create_app --transport sse --host 127.0.0.1 --port 8765
```

Verify the server is running:

```powershell
curl http://localhost:8765/sse
# Should return an SSE stream or 401 Unauthorized (if token is set)
```

## Step 5: Set Up Cloudflare Tunnel

See `deploy\cloudflared-config.yml` for detailed instructions.

Quick summary:

```powershell
# 1. Install cloudflared
winget install --id Cloudflare.cloudflared

# 2. Authenticate
cloudflared tunnel login

# 3. Create tunnel
cloudflared tunnel create logix-mcp

# 4. Create DNS record
cloudflared tunnel route dns logix-mcp logix-mcp.your-domain.com

# 5. Copy config to systemprofile and install service
copy %USERPROFILE%\.cloudflared\config.yml C:\Windows\System32\config\systemprofile\.cloudflared\
copy %USERPROFILE%\.cloudflared\<tunnel-id>.json C:\Windows\System32\config\systemprofile\.cloudflared\
cloudflared service install
net start cloudflared
```

## Step 6: Configure Hermes (Linux Side)

Merge `deploy\hermes-config.yaml` into your Linux `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  logix-sdk:
    transport: sse
    url: https://logix-mcp.your-domain.com/sse
    headers:
      Authorization: "Bearer ${LOGIX_MCP_TOKEN}"
    connect_timeout: 30
```

Export the token on Linux:

```bash
export LOGIX_MCP_TOKEN="your-secret-token-here"
```

Restart Hermes, then verify:

```bash
/mcp list
/mcp call logix-sdk sdk_get_info
```

## Step 7: Run as Windows Services (Production)

For persistent operation, run both the MCP server and cloudflared as services.

### MCP Server via NSSM

```powershell
# Download NSSM from https://nssm.cc/download

nssm install LogixMCPServer "C:\projects\logix-mcp\.venv\Scripts\python.exe" "-m fastmcp run src\logix_mcp\server.py:create_app --transport sse --host 127.0.0.1 --port 8765"
nssm set LogixMCPServer AppDirectory "C:\projects\logix-mcp"
nssm set LogixMCPServer AppEnvironmentExtra LOGIX_MCP_TOKEN=your-secret-token-here
nssm start LogixMCPServer
```

### Cloudflared Service

Already covered in Step 5. The service auto-starts on boot.

## Verification Checklist

- [ ] `install.bat` completes without errors
- [ ] `sdk_get_info` returns version and license status
- [ ] Cloudflare Tunnel shows "Active" in Zero Trust dashboard
- [ ] Hermes `/mcp list` shows `logix-sdk` as connected
- [ ] Can open an ACD file: `/mcp call logix-sdk sdk_open_acd --path "C:\Projects\Test.ACD"`
- [ ] Can export L5K: `/mcp call logix-sdk sdk_export_l5k --output_path "C:\Projects\Test.L5K"`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Python not found | Install Python 3.11+ and check "Add to PATH" |
| SDK not found | Set `LOGIX_SDK_ASSEMBLY` env var manually |
| pythonnet fails | Install .NET Framework 4.8 + VC++ 2015-2022 Redist x64 |
| 401 from Hermes | Token mismatch; verify `LOGIX_MCP_TOKEN` on both sides |
| 502 Bad Gateway | MCP server not running; check `curl localhost:8765/sse` |
| Tunnel down | Check cloudflared service; verify config.yml and credentials |
| COM threading errors | May need STA thread; check server logs |

## Security Notes

- Never expose the MCP server directly to the network (always bind to `127.0.0.1`)
- Use a strong, randomly generated `LOGIX_MCP_TOKEN`
- Rotate the token periodically
- The Cloudflare Tunnel provides TLS termination; no need for local certificates
- Studio 5000 licenses are checked out per COM session — close projects when done

## File Reference

| File | Purpose |
|------|---------|
| `deploy\install.bat` | Windows installation script |
| `deploy\cloudflared-config.yml` | Cloudflare Tunnel setup guide + example config |
| `deploy\hermes-config.yaml` | Hermes MCP client config snippet |
| `deploy\README.md` | This file |
